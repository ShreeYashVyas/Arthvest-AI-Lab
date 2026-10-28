# Arthvest AI Lab

An experimental home for the Arthvest multi-agent financial research council.

## Purpose

This repository separates the multi-agent research implementation from
Arthvest Core, which is intended to use a single local Ollama analyst.

## Components

- Nine-role research council and orchestration
- Macro-economic evidence collection
- Optional read-only Upstox market data
- Risk and evidence auditing
- FastAPI research endpoints
- Research API tests and smoke-test script

## Requirements

- Python
- A reachable Ollama-compatible model endpoint with a supported model
- Any environment variables required by the research service and data sources

Install the backend dependencies from this directory:

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

Configure the model and data-source settings expected by
`app/services/research_agents.py`. Never commit credentials or `.env` files.

## Run the API

From the `backend` directory:

```powershell
$env:PYTHONPATH = (Get-Location).Path
python -m uvicorn app.main:app --reload
```

Health endpoint: `http://127.0.0.1:8000/health`

Agent status: `http://127.0.0.1:8000/api/agents/status`

Research endpoint: `POST http://127.0.0.1:8000/api/agents/research`

Example request body:

```json
{"question": "Summarize current macro risks for India"}
```

## Tests

Run the API tests from `backend`:

```powershell
$env:PYTHONPATH = (Get-Location).Path
python -m pytest tests/test_research_agents_api.py -q
```

The smoke test invokes the live model workflow, so it requires a working
model endpoint and may take considerably longer than the API unit tests.

## Project status

The multi-agent source has been copied out of Arthvest Core. The standalone
project still requires independent integration verification before release.
