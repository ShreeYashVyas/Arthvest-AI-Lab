"""On-demand smoke test for the real nine-agent local Ollama workflow.

Uses synthetic fixture evidence and makes real model calls. It does not query
FRED or Upstox, and it never prints API credentials or raw model output.
Run from backend/: python -m scripts.smoke_test_research_agents
"""

import asyncio
import os
import sys
from datetime import datetime, timezone
from unittest.mock import patch

from app.services import research_agents

EXPECTED_ROLES = [
    "Macro Analyst",
    "India Market Analyst",
    "Geopolitical Risk Analyst",
    "Cross-Asset Analyst",
    "Scenario Analyst",
    "India Sector Transmission Analyst",
    "Contrarian Analyst",
    "Risk & Evidence Auditor",
    "Lead Research Analyst",
]

NOW = datetime.now(timezone.utc).isoformat()
SYNTHETIC_EVIDENCE = {
    "generated_at": NOW,
    "macro_observations": [
        {
            "key": "smoke-policy-rate",
            "status": "available",
            "indicator": "Synthetic smoke-test policy-rate fixture",
            "series_id": "SYNTHETIC-SMOKE",
            "value": 3.5,
            "unit": "percent",
            "observation_date": "2026-10-01",
            "retrieved_at": NOW,
            "freshness_status": "fresh",
            "source": "Arthvest synthetic smoke-test fixture",
            "source_url": "https://example.invalid/arthvest-smoke-test",
            "calculation": "Fixed synthetic value; not a real economic observation.",
        }
    ],
    "market_snapshot": {
        "status": "available",
        "provider": "Synthetic smoke-test fixture",
        "source_url": "https://example.invalid/arthvest-smoke-test",
        "generated_at": NOW,
        "data_as_of": NOW,
        "available_count": 1,
        "total_count": 1,
        "quotes": [
            {
                "key": "nifty-50",
                "name": "Synthetic NIFTY 50 fixture (not live data)",
                "instrument_key": "SYNTHETIC|NIFTY50",
                "status": "available",
                "last_price": 25000.0,
                "previous_close": 24900.0,
                "change": 100.0,
                "change_percent": 0.4016,
                "open": 24950.0,
                "high": 25100.0,
                "low": 24800.0,
                "volume": None,
                "timestamp": NOW,
            }
        ],
        "limitations": [
            "Synthetic fixture only; no live market provider was queried.",
        ],
    },
    "data_quality_notes": [
        "All values in this smoke test are synthetic fixtures, not live market conditions.",
        "Do not infer real-world economic or market conditions from these values.",
        "No dedicated geopolitical news feed is connected.",
        "Only one synthetic observation is provided; aligned historical series are absent.",
    ],
}


def fail(message: str) -> None:
    print(f"FAIL: {message}", file=sys.stderr)
    raise SystemExit(1)


def main() -> None:
    if os.getenv("ARTHVEST_LLM_PROVIDER", "ollama").strip().lower() != "ollama":
        fail("This smoke test is intended for local Ollama mode. Set ARTHVEST_LLM_PROVIDER=ollama.")
    status = research_agents.get_agent_status()
    if not status.get("configured"):
        fail(str(status.get("note", "The selected local model is not ready.")))

    question = (
        "Smoke-test the nine-agent research workflow using only the supplied "
        "synthetic fixtures. Explicitly identify these as synthetic test values, "
        "do not describe them as live market conditions, and list relevant data gaps."
    )

    # Patch only evidence collection: all nine Agent/Runner model calls are real.
    with patch.object(
        research_agents, "_load_evidence_context", return_value=SYNTHETIC_EVIDENCE
    ):
        result = asyncio.run(research_agents.run_research(question))

    if result.get("status") != "ready":
        fail("The workflow did not return ready status.")

    agent_rows = result.get("agents")
    if not isinstance(agent_rows, list):
        fail("The response did not include per-agent statuses.")

    observed_roles = [row.get("name") for row in agent_rows if isinstance(row, dict)]
    if observed_roles != EXPECTED_ROLES:
        fail(f"Unexpected agent roster/order: {observed_roles!r}")

    statuses = {
        row["name"]: row.get("status")
        for row in agent_rows
        if isinstance(row, dict) and isinstance(row.get("name"), str)
    }
    if statuses.get("India Market Analyst") != "completed":
        fail("Market analyst did not complete despite the supplied synthetic quote.")
    if statuses.get("Risk & Evidence Auditor") != "completed":
        fail("Evidence auditor did not complete.")
    if statuses.get("Lead Research Analyst") != "completed":
        fail("Lead analyst did not complete.")

    reports = result.get("specialist_reports")
    required_reports = {
        "macro",
        "market",
        "geopolitical_risk",
        "cross_asset",
        "scenario",
        "sector_transmission",
        "contrarian",
        "risk_evidence_audit",
    }
    if not isinstance(reports, dict) or set(reports) != required_reports:
        fail("One or more specialist/audit reports are missing.")

    for name, report in reports.items():
        if not isinstance(report, dict):
            fail(f"{name} report is not a JSON object.")
        if not isinstance(report.get("summary"), str) or not report["summary"].strip():
            fail(f"{name} report has no summary.")
        if report.get("confidence") not in {"low", "moderate", "high"}:
            fail(f"{name} report has invalid confidence metadata.")

    brief = result.get("brief")
    if not isinstance(brief, dict) or not isinstance(brief.get("headline"), str):
        fail("Lead analyst brief is missing or invalid.")
    if not isinstance(brief.get("executive_summary"), str) or not brief["executive_summary"].strip():
        fail("Lead analyst brief has no executive summary.")

    validation = result.get("evidence_validation")
    if not isinstance(validation, dict):
        fail("Evidence validation metadata is missing.")
    allowed = set(validation.get("allowed_keys", []))
    if allowed != {"smoke-policy-rate", "nifty-50"}:
        fail(f"Evidence allowlist was not restricted to the synthetic fixture: {sorted(allowed)!r}")

    all_findings = list(brief.get("key_findings", []))
    for report in reports.values():
        all_findings.extend(report.get("findings", []))
    for finding in all_findings:
        if not isinstance(finding, dict):
            fail("A finding is not a JSON object.")
        keys = finding.get("evidence_keys", [])
        if not isinstance(keys, list) or not set(keys).issubset(allowed):
            fail("An output finding contains evidence keys outside the allowlist.")

    # Do not print the brief or raw model output. Local mode has no cloud key.
    model_name = status["model"]
    invalid_refs = validation.get("invalid_reference_count", 0)
    print(f"PASS: all nine real local model stages completed using {model_name}.")
    print("PASS: seven specialist reports, audit report, and lead brief are present.")
    print("PASS: output evidence keys are restricted to the synthetic fixtures.")
    print(f"INFO: unsupported evidence references removed by validation: {invalid_refs}")
    print("INFO: this run used synthetic evidence only; it did not test live FRED/Upstox connectivity.")
    print("INFO: inference used the local Ollama endpoint; no OpenAI API key was required.")
    print("Agent statuses:")
    for row in agent_rows:
        print(f"  - {row['name']}: {row['status']}")


if __name__ == "__main__":
    main()
