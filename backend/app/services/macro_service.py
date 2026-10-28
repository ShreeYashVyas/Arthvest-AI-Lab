"""Fetch and validate macroeconomic observations from FRED.

The service is deliberately source-first: indicator readings retain their source
observation date and the time this process last retrieved the upstream data.
"""

import calendar
import logging
import csv
import math
import time
from datetime import date, datetime, timezone
from io import StringIO
from threading import Lock
from urllib.error import URLError
from urllib.request import Request, urlopen

from app.services import observation_store

logger = logging.getLogger(__name__)

FRED_GRAPH_URL = "https://fred.stlouisfed.org/graph/fredgraph.csv?id={series_id}"
REQUEST_TIMEOUT_SECONDS = 15
CACHE_TTL_SECONDS = 15 * 60

INDICATORS: dict[str, dict[str, str]] = {
    "fed-funds": {
        "indicator": "Federal Funds Effective Rate",
        "description": "Monthly average effective interest rate on overnight reserve-balance lending between depository institutions.",
        "frequency": "Monthly",
        "series_id": "FEDFUNDS",
        "unit": "percent",
        "source": "Board of Governors of the Federal Reserve System via FRED",
        "calculation": "Latest available FEDFUNDS observation.",
        "max_age_days": "120",
    },
    "us-inflation": {
        "indicator": "U.S. CPI Inflation (year over year)",
        "description": "Twelve-month percentage change in the Consumer Price Index for All Urban Consumers.",
        "frequency": "Monthly",
        "series_id": "CPIAUCSL",
        "unit": "percent year over year",
        "source": "U.S. Bureau of Labor Statistics via FRED",
        "calculation": "Calculated as the 12-month percentage change in CPIAUCSL.",
        "max_age_days": "100",
    },
    "us-unemployment": {
        "indicator": "U.S. Unemployment Rate",
        "description": "Civilian unemployment rate, seasonally adjusted.",
        "frequency": "Monthly",
        "series_id": "UNRATE",
        "unit": "percent, seasonally adjusted",
        "source": "U.S. Bureau of Labor Statistics via FRED",
        "calculation": "Latest available UNRATE observation.",
        "max_age_days": "100",
    },
    "india-gdp-growth": {
        "indicator": "India Real GDP Growth (year over year)",
        "description": "Quarterly year-over-year growth rate for India's real gross domestic product.",
        "frequency": "Quarterly",
        "series_id": "INDGDPRQPSMEI",
        "unit": "percent year over year",
        "source": "Organisation for Economic Co-operation and Development (OECD) via FRED",
        "calculation": "Latest available quarterly year-over-year growth observation, shown as published.",
        "max_age_days": "240",
    },
    "india-cpi-inflation-annual": {
        "indicator": "India Consumer Price Inflation (annual)",
        "description": "Annual percentage change in consumer prices in India, based on the consumer price index.",
        "frequency": "Annual",
        "series_id": "FPCPITOTLZGIND",
        "unit": "percent (annual)",
        "source": "World Bank via FRED",
        "calculation": "Latest published annual percentage change in consumer prices; this is annual data, not a monthly inflation reading.",
        "max_age_days": "550",
    },
    "india-policy-uncertainty": {
        "indicator": "India Economic Policy Uncertainty Index",
        "description": "Monthly index tracking economic policy uncertainty in India.",
        "frequency": "Monthly",
        "series_id": "INDEPUINDXM",
        "unit": "index",
        "source": "Baker, Bloom and Davis via FRED",
        "calculation": "Latest published index observation; interpret relative to its own history, not as a percentage.",
        "max_age_days": "120",
    },
    "usd-inr": {
        "indicator": "Indian Rupees per U.S. Dollar",
        "description": "Daily noon buying rate for Indian rupees to one U.S. dollar.",
        "frequency": "Daily, except non-publishing days",
        "series_id": "DEXINUS",
        "unit": "INR per USD",
        "source": "Board of Governors of the Federal Reserve System via FRED",
        "calculation": "Latest available spot exchange-rate observation. A higher value means more rupees per U.S. dollar.",
        "max_age_days": "7",
    },
    "india-reer": {
        "indicator": "India Real Effective Exchange Rate",
        "description": "CPI-based real effective exchange-rate index for India.",
        "frequency": "Monthly",
        "series_id": "CCRETT01INM661N",
        "unit": "index (2015=100)",
        "source": "Organisation for Economic Co-operation and Development (OECD) via FRED",
        "calculation": "Latest published index observation; interpret relative to its base and history.",
        "max_age_days": "100",
    },
}

def _indicator_key_for_series(series_id: str) -> str | None:
    return next((key for key, config in INDICATORS.items() if config["series_id"] == series_id), None)


def _record_failed_source_check(series_id: str, error_code: str, elapsed_ms: int) -> None:
    try:
        observation_store.record_source_failure(
            _indicator_key_for_series(series_id), series_id, error_code, elapsed_ms
        )
    except Exception:
        logger.warning("Could not persist failed source check for %s", series_id, exc_info=True)


def _record_successful_source_check(
    series_id: str, observations: list[tuple[str, float]], retrieved_at: str, elapsed_ms: int
) -> None:
    try:
        observation_store.record_source_success(
            _indicator_key_for_series(series_id), series_id, observations, retrieved_at, elapsed_ms
        )
    except Exception:
        logger.warning("Could not persist source observations for %s", series_id, exc_info=True)



class MacroDataError(RuntimeError):
    """Raised when upstream macro data is unavailable or invalid."""


_cache_lock = Lock()
_series_cache: dict[str, tuple[float, list[tuple[str, float]], str]] = {}
_series_locks: dict[str, Lock] = {}


def _parse_fred_csv(csv_text: str, series_id: str) -> list[tuple[str, float]]:
    """Parse and sort valid date/value observations from a FRED CSV response."""
    reader = csv.DictReader(StringIO(csv_text.lstrip("\ufeff")))
    if not reader.fieldnames or not {"observation_date", series_id}.issubset(
        set(reader.fieldnames)
    ):
        raise MacroDataError("FRED response did not contain expected columns")

    valid_rows: list[tuple[datetime, str, float]] = []
    for row in reader:
        raw_date = (row.get("observation_date") or "").strip()
        raw_value = (row.get(series_id) or "").strip()
        if not raw_date or raw_value in {"", "."}:
            continue

        try:
            observation_date = datetime.strptime(raw_date, "%Y-%m-%d")
            value = float(raw_value)
        except (ValueError, TypeError):
            continue

        if not math.isfinite(value):
            continue
        valid_rows.append((observation_date, raw_date, value))

    if not valid_rows:
        raise MacroDataError(f"FRED returned no valid observations for {series_id}")

    valid_rows.sort(key=lambda item: item[0])
    return [(date_string, value) for _, date_string, value in valid_rows]


def _parse_fed_funds_csv(csv_text: str) -> dict[str, str | float]:
    """Backward-compatible helper retained for the Federal Funds Rate tests."""
    date_string, value = _parse_fred_csv(csv_text, "FEDFUNDS")[-1]
    return {"observation_date": date_string, "value_percent": value}


def _fetch_fred_series(series_id: str) -> tuple[list[tuple[str, float]], str]:
    """Fetch a series with TTL caching and single-flight requests per series."""
    now = time.monotonic()
    with _cache_lock:
        cached = _series_cache.get(series_id)
        if cached and now - cached[0] < CACHE_TTL_SECONDS:
            return list(cached[1]), cached[2]
        series_lock = _series_locks.setdefault(series_id, Lock())

    # Different series can load in parallel; callers for the same series share
    # one upstream request instead of racing to fetch duplicate CSV payloads.
    with series_lock:
        now = time.monotonic()
        with _cache_lock:
            cached = _series_cache.get(series_id)
            if cached and now - cached[0] < CACHE_TTL_SECONDS:
                return list(cached[1]), cached[2]

        fetch_started = time.monotonic()
        request = Request(
            FRED_GRAPH_URL.format(series_id=series_id),
            headers={"User-Agent": "Arthvest/0.1 (macro research dashboard)"},
        )
        try:
            with urlopen(request, timeout=REQUEST_TIMEOUT_SECONDS) as response:
                status = getattr(response, "status", 200)
                if status != 200:
                    _record_failed_source_check(
                        series_id, "http-status", int((time.monotonic() - fetch_started) * 1000)
                    )
                    raise MacroDataError(f"FRED returned HTTP status {status}")
                csv_text = response.read().decode("utf-8-sig")
        except (URLError, TimeoutError, OSError, UnicodeDecodeError) as exc:
            _record_failed_source_check(
                series_id, "request-failed", int((time.monotonic() - fetch_started) * 1000)
            )
            raise MacroDataError(
                f"Unable to retrieve {series_id} data from FRED"
            ) from exc

        try:
            observations = _parse_fred_csv(csv_text, series_id)
        except MacroDataError:
            _record_failed_source_check(
                series_id, "invalid-response", int((time.monotonic() - fetch_started) * 1000)
            )
            raise

        retrieved_at = datetime.now(timezone.utc).isoformat()
        _record_successful_source_check(
            series_id, observations, retrieved_at,
            int((time.monotonic() - fetch_started) * 1000),
        )
        with _cache_lock:
            _series_cache[series_id] = (
                time.monotonic(),
                observations,
                retrieved_at,
            )
        return list(observations), retrieved_at


def _observation_period_end(
    observation_date: str,
    frequency: str,
) -> date:
    """Interpret period-start timestamps as the end of their represented period."""
    parsed = datetime.strptime(observation_date, "%Y-%m-%d").date()
    if frequency == "Annual":
        return date(parsed.year, 12, 31)
    if frequency == "Quarterly":
        quarter_end_month = ((parsed.month - 1) // 3 + 1) * 3
        return date(
            parsed.year,
            quarter_end_month,
            calendar.monthrange(parsed.year, quarter_end_month)[1],
        )
    if frequency == "Monthly":
        return date(
            parsed.year,
            parsed.month,
            calendar.monthrange(parsed.year, parsed.month)[1],
        )
    return parsed


def fetch_macro_indicator(indicator_key: str) -> dict[str, str | float]:
    """Fetch and normalize one supported indicator into a provenance-rich payload."""
    config = INDICATORS.get(indicator_key)
    if config is None:
        raise MacroDataError(f"Unsupported macro indicator: {indicator_key}")

    series_id = config["series_id"]
    observations, retrieved_at = _fetch_fred_series(series_id)
    observation_date, latest_value = observations[-1]
    value = latest_value

    if indicator_key == "us-inflation":
        target_date = datetime.strptime(observation_date, "%Y-%m-%d")
        prior_year_date = target_date.replace(year=target_date.year - 1).strftime("%Y-%m-%d")
        historical_values = {date_string: item for date_string, item in observations}
        prior_year_value = historical_values.get(prior_year_date)
        if prior_year_value is None or prior_year_value == 0:
            raise MacroDataError(
                "Not enough historical CPI data to calculate year-over-year inflation"
            )
        value = round((latest_value / prior_year_value - 1) * 100, 2)

    today = datetime.now(timezone.utc).date()
    source_date = datetime.strptime(observation_date, "%Y-%m-%d").date()
    if source_date > today:
        raise MacroDataError(f"FRED returned a future observation date for {series_id}")

    # Some monthly and quarterly series timestamp a whole period using its
    # first day. If the current period is not over yet, its period-end age is
    # zero; it should not be rejected merely because that period end is future.
    observation_period_end = _observation_period_end(
        observation_date,
        config["frequency"],
    )
    period_in_progress = observation_period_end > today
    age_days = max((today - observation_period_end).days, 0)

    if period_in_progress:
        freshness_status = "in-progress"
    else:
        freshness_status = (
            "fresh" if age_days <= int(config["max_age_days"]) else "stale"
        )

    return {
        "indicator": config["indicator"],
        "series_id": series_id,
        "value": value,
        "observation_date": observation_date,
        "frequency": config["frequency"],
        "unit": config["unit"],
        "source": config["source"],
        "source_url": f"https://fred.stlouisfed.org/series/{series_id}",
        "retrieved_at": retrieved_at,
        "calculation": config["calculation"],
        "observation_age_days": age_days,
        "freshness_status": freshness_status,
    }


def fetch_fed_funds_rate() -> dict[str, str | float]:
    """Compatibility wrapper for the original FEDFUNDS endpoint."""
    return fetch_macro_indicator("fed-funds")



def fetch_macro_history(indicator_key: str, limit: int = 12) -> dict[str, object]:
    """Return the latest historical points for an indicator.

    The CPI index is converted into year-over-year inflation for each month with
    a matching observation from 12 months earlier. Other indicators expose the
    source series directly.
    """
    if not 1 <= limit <= 60:
        raise MacroDataError("History limit must be between 1 and 60")

    config = INDICATORS.get(indicator_key)
    if config is None:
        raise MacroDataError(f"Unsupported macro indicator: {indicator_key}")

    series_id = config["series_id"]
    observations, retrieved_at = _fetch_fred_series(series_id)
    if indicator_key == "us-inflation":
        value_by_date = {date_string: value for date_string, value in observations}
        derived_points: list[dict[str, str | float]] = []
        for date_string, current_value in observations:
            current_date = datetime.strptime(date_string, "%Y-%m-%d")
            try:
                prior_date_string = current_date.replace(
                    year=current_date.year - 1
                ).strftime("%Y-%m-%d")
            except ValueError:
                continue
            prior_value = value_by_date.get(prior_date_string)
            if prior_value is None or prior_value == 0:
                continue
            derived_points.append(
                {
                    "observation_date": date_string,
                    "value": round((current_value / prior_value - 1) * 100, 2),
                }
            )
        points = derived_points[-limit:]
        unit = config["unit"]
    else:
        points = [
            {"observation_date": date_string, "value": value}
            for date_string, value in observations[-limit:]
        ]
        unit = config["unit"]

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "key": indicator_key,
        "indicator": config["indicator"],
        "series_id": series_id,
        "unit": unit,
        "frequency": config["frequency"],
        "source": config["source"],
        "source_url": f"https://fred.stlouisfed.org/series/{series_id}",
        "calculation": config["calculation"],
        "requested_limit": limit,
        "returned_count": len(points),
        "points": points,
        "retrieved_at": retrieved_at,
    }
