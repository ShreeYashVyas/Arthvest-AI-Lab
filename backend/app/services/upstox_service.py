"""Read-only market quote integration using the Upstox Analytics Token."""

from __future__ import annotations

import json
import logging
import math
import os
from datetime import datetime, timezone
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

logger = logging.getLogger(__name__)

UPSTOX_QUOTES_URL = "https://api.upstox.com/v2/market-quote/quotes"
REQUEST_TIMEOUT_SECONDS = 10
SOURCE_URL = "https://upstox.com/developer/api-documentation/get-full-market-quote/"

INSTRUMENTS: tuple[dict[str, str], ...] = (
    {
        "key": "nifty-50",
        "name": "NIFTY 50",
        "instrument_key": "NSE_INDEX|Nifty 50",
    },
    {
        "key": "nifty-bank",
        "name": "NIFTY BANK",
        "instrument_key": "NSE_INDEX|Nifty Bank",
    },
    {
        "key": "india-vix",
        "name": "INDIA VIX",
        "instrument_key": "NSE_INDEX|India VIX",
    },
)


class UpstoxServiceError(RuntimeError):
    """A safe-to-display provider error with an HTTP status for the API layer."""

    def __init__(self, message: str, status_code: int = 502) -> None:
        super().__init__(message)
        self.status_code = status_code


def _analytics_token() -> str:
    """Read the server-side token; never return it in API payloads or logs."""
    return os.getenv("UPSTOX_ANALYTICS_TOKEN", "").strip()


def get_upstox_status() -> dict[str, object]:
    """Report configuration readiness without disclosing any credential."""
    configured = bool(_analytics_token())
    return {
        "provider": "Upstox",
        "configured": configured,
        "auth_mode": "Analytics Token (read-only)" if configured else None,
        "note": (
            "An Analytics Token is configured. Market quotes are fetched from Upstox on request."
            if configured
            else (
                "Set UPSTOX_ANALYTICS_TOKEN in backend/.env and start the backend with "
                "--env-file .env to enable market quotes."
            )
        ),
    }


def _request_quotes_payload(token: str) -> dict[str, object]:
    """Request the configured index snapshot from Upstox with a bounded timeout."""
    query = urlencode({"instrument_key": ",".join(item["instrument_key"] for item in INSTRUMENTS)})
    request = Request(
        UPSTOX_QUOTES_URL + "?" + query,
        headers={
            "Accept": "application/json",
            "Content-Type": "application/json",
            "Authorization": "Bearer " + token,
            "User-Agent": "Arthvest/0.2 (read-only market intelligence)",
        },
        method="GET",
    )

    try:
        with urlopen(request, timeout=REQUEST_TIMEOUT_SECONDS) as response:
            raw_body = response.read().decode("utf-8")
    except HTTPError as exc:
        if exc.code in (401, 403):
            raise UpstoxServiceError(
                "Upstox rejected the configured token. Confirm the Analytics Token is active and copied in full.",
                502,
            ) from exc
        if exc.code == 429:
            raise UpstoxServiceError(
                "Upstox rate limit reached. Wait briefly before refreshing market data.",
                503,
            ) from exc
        if exc.code >= 500:
            raise UpstoxServiceError(
                "Upstox market-data service is temporarily unavailable.",
                503,
            ) from exc
        raise UpstoxServiceError(
            "Upstox rejected the market-data request. Check the token and API configuration.",
            502,
        ) from exc
    except (URLError, TimeoutError, OSError) as exc:
        logger.warning("Upstox quote request failed: %s", type(exc).__name__)
        raise UpstoxServiceError(
            "Could not reach Upstox. Check your internet connection and try again.",
            503,
        ) from exc
    except UnicodeDecodeError as exc:
        raise UpstoxServiceError("Upstox returned an unreadable market-data response.", 502) from exc

    try:
        payload = json.loads(raw_body)
    except json.JSONDecodeError as exc:
        raise UpstoxServiceError("Upstox returned invalid JSON for market quotes.", 502) from exc

    if (
        not isinstance(payload, dict)
        or payload.get("status") != "success"
        or not isinstance(payload.get("data"), dict)
    ):
        raise UpstoxServiceError("Upstox returned an unexpected market-quote response.", 502)
    return payload


def _normalise_instrument_key(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    return value.strip().replace(":", "|").casefold()


def _finite_number(value: object) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    numeric = float(value)
    return numeric if math.isfinite(numeric) else None


def _quote_timestamp(quote: dict[str, object]) -> str | None:
    """Normalize the quote timestamp where the provider supplies one."""
    value = quote.get("timestamp")
    if isinstance(value, str) and value.strip():
        return value
    trade_time = quote.get("last_trade_time")
    if isinstance(trade_time, (str, int, float)) and not isinstance(trade_time, bool):
        try:
            milliseconds = int(trade_time)
            return datetime.fromtimestamp(milliseconds / 1000, timezone.utc).isoformat()
        except (ValueError, TypeError, OverflowError, OSError):
            return None
    return None


def _normalise_quote(
    instrument: dict[str, str],
    quote: dict[str, object] | None,
) -> dict[str, object]:
    if quote is None:
        return {
            **instrument,
            "status": "unavailable",
            "last_price": None,
            "previous_close": None,
            "change": None,
            "change_percent": None,
            "open": None,
            "high": None,
            "low": None,
            "volume": None,
            "timestamp": None,
        }

    ohlc = quote.get("ohlc")
    ohlc_data = ohlc if isinstance(ohlc, dict) else {}
    last_price = _finite_number(quote.get("last_price"))
    previous_close = _finite_number(ohlc_data.get("close"))
    change = _finite_number(quote.get("net_change"))
    if change is None and last_price is not None and previous_close is not None:
        change = last_price - previous_close
    change_percent = (
        round((change / previous_close) * 100, 4)
        if change is not None and previous_close is not None and previous_close > 0
        else None
    )

    return {
        **instrument,
        "status": "available" if last_price is not None else "unavailable",
        "last_price": last_price,
        "previous_close": previous_close,
        "change": change,
        "change_percent": change_percent,
        "open": _finite_number(ohlc_data.get("open")),
        "high": _finite_number(ohlc_data.get("high")),
        "low": _finite_number(ohlc_data.get("low")),
        "volume": _finite_number(quote.get("volume")),
        "timestamp": _quote_timestamp(quote),
    }


def get_market_quotes() -> dict[str, object]:
    """Return normalized, source-attributed index quotes or a clear service error."""
    token = _analytics_token()
    if not token:
        raise UpstoxServiceError(
            "Upstox is not configured. Add UPSTOX_ANALYTICS_TOKEN to backend/.env and restart the backend with --env-file .env.",
            503,
        )

    payload = _request_quotes_payload(token)
    raw_data = payload["data"]
    assert isinstance(raw_data, dict)

    indexed_data: dict[str, dict[str, object]] = {}
    for response_key, raw_quote in raw_data.items():
        if not isinstance(raw_quote, dict):
            continue
        instrument_token = raw_quote.get("instrument_token")
        normalised_key = _normalise_instrument_key(instrument_token)
        if normalised_key is None:
            normalised_key = _normalise_instrument_key(response_key)
        if normalised_key is not None:
            indexed_data[normalised_key] = raw_quote

    quotes: list[dict[str, object]] = []
    for instrument in INSTRUMENTS:
        key = _normalise_instrument_key(instrument["instrument_key"])
        quotes.append(_normalise_quote(instrument, indexed_data.get(key or "")))

    available_count = sum(item["status"] == "available" for item in quotes)
    if not indexed_data:
        raise UpstoxServiceError("Upstox returned no market quotes for the requested indices.", 502)

    timestamps = [
        item["timestamp"]
        for item in quotes
        if isinstance(item.get("timestamp"), str)
    ]
    return {
        "provider": "Upstox",
        "source_url": SOURCE_URL,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "data_as_of": max(timestamps) if timestamps else None,
        "available_count": available_count,
        "total_count": len(quotes),
        "quotes": quotes,
        "read_only": True,
        "limitations": [
            "Quotes are a snapshot returned by Upstox at request time; they are not a continuous WebSocket feed.",
            "An unavailable or closed-market quote is shown as unavailable rather than filled with fabricated data.",
            "This endpoint does not place orders or read account holdings.",
        ],
    }
