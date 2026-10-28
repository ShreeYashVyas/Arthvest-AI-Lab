# Arthvest — Macro Intelligence

Arthvest is a research-first macroeconomic intelligence dashboard. It presents source-attributed observations, data-quality status, historical trends and a transparent **provisional U.S. macro conditions subscore**.

> The current score is experimental, not backtested, and is not the full global/India macro regime model or a market-return forecast.

## Current Phase 1 capabilities

- Next.js dashboard with API connection state, indicator cards, historical sparklines, normalized cross-indicator comparisons, archive health, upstream revision audit and a per-indicator source-quality matrix.
- FastAPI endpoints for health, a macro-indicator catalog, a best-effort overview, history, data quality, and a provisional U.S. score.
- U.S. indicators: Federal Funds Effective Rate, CPI inflation (calculated year over year), and unemployment rate.
- India-related indicators: quarterly real GDP growth, annual consumer-price inflation, Economic Policy Uncertainty Index, INR per USD exchange rate, and real effective exchange rate.
- Source observation dates, retrieval timestamps, native units, frequency-aware freshness and period-labelled historical trends.
- In-process 15-minute source-series cache; optional SQLAlchemy persistence for source observations, upstream revisions, and fetch successes/failures; descriptive analytics, relative comparison and scheduled archive ingestion.
- GitHub Actions workflow for backend tests and frontend production build.
- Optional Upstox-powered India Market Pulse page for read-only NIFTY 50, NIFTY BANK and India VIX quote snapshots; the token stays in the backend environment.
- Nine-role evidence-grounded AI research council using local Ollama by default: seven specialists, a Risk & Evidence Auditor, and a Lead Research Analyst.

## Technology

- **Frontend:** Next.js, React, TypeScript, Tailwind CSS, Lucide
- **Backend:** Python, FastAPI, Pydantic
- **Source data:** published FRED series with source-attribution links; optional Upstox Market Quote API for Indian indices
- **AI research:** OpenAI Agents SDK over local Ollama by default; hosted OpenAI inference is opt-in
- **Persistence:** optional SQLAlchemy archive for observations, revisions, and source checks
- **Database:** PostgreSQL through `DATABASE_URL` when configured; live source feeds still run without persistence

## Project structure

```text
Arthvest/
├── .github/workflows/ci.yml
├── backend/
│   ├── app/
│   │   ├── api/routes/  # macro.py, market.py, health.py
│   │   ├── schemas/
│   │   ├── services/    # macro, archive, analytics, Upstox
│   │   └── main.py
│   ├── tests/
│   └── requirements.txt
├── docs/MACRO_DATA.md
└── frontend/
    └── src/app/
```

## Run locally (Windows PowerShell)

Use two VS Code terminals.

### 1. Backend

Requires Python 3.11 or newer.

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
if (-not (Test-Path .env)) { Copy-Item .env.example .env }
# Edit .env privately if enabling PostgreSQL or Upstox; never commit it.
uvicorn app.main:app --reload --env-file .env
```

- Health: http://127.0.0.1:8000/health
- API docs: http://127.0.0.1:8000/docs

### 2. Frontend

Requires a current Node.js LTS release.

```powershell
cd frontend
npm install
Copy-Item .env.example .env.local
npm run dev
```

Open http://localhost:3000. The frontend expects the API at `http://127.0.0.1:8000` by default.

### 3. Backend tests

```powershell
cd backend
.\.venv\Scripts\Activate.ps1
python -m pytest -q
```

## Live source sanity check

For a deliberate, networked check of the configured FRED feeds, run the diagnostic from the backend directory:

```powershell
cd backend
python -m scripts.check_data_sources
```

The diagnostic fetches the eight configured series, displays each latest validated observation and freshness state, and exits non-zero if a source cannot be fetched or validated. A `stale` or `in-progress` observation is reported separately from a connection failure. It needs internet access and is not part of normal CI.

You can also trigger **Live Macro Source Check** from the repository's **Actions** tab using **Run workflow**. This workflow is manual by design, so routine pull requests and pushes remain independent of upstream release timing.

## Optional persistent archive

Live fetching works without a database. To retain source observations, detect upstream revisions, and record fetch failures across restarts, configure `DATABASE_URL` for PostgreSQL using a URL such as `postgresql+psycopg://USER:PASSWORD@HOST:5432/arthvest`. Provider URLs using `postgres://` or `postgresql://` are normalized automatically. Keep credentials in deployment secrets or an untracked `.env`; never commit real credentials. On the first storage operation, Arthvest creates its initial SQLAlchemy tables. Without `DATABASE_URL`, the `/api/macro/storage` endpoint reports persistence as disabled and archive endpoints return HTTP 503 while live macro endpoints continue.

## Optional Upstox market data

Generate an Analytics Token in the [Upstox Developer Apps portal](https://account.upstox.com/developer/apps) and place it in `backend/.env` as `UPSTOX_ANALYTICS_TOKEN`. This is a read-only integration for market-data GET APIs; the token is never returned by Arthvest endpoints or shipped to the browser. The `/markets` page shows NIFTY 50, NIFTY BANK, and India VIX quotes from Upstox. An absent token is reported explicitly, and absent quotes are never replaced with sample values. See [Upstox Analytics Token documentation](https://upstox.com/developer/api-documentation/analytics-token/) and the [Full Market Quotes API](https://upstox.com/developer/api-documentation/get-full-market-quote/).

## Optional AI research agents

The nine-role AI Research Council defaults to **local Ollama inference** for development, so it does not need an OpenAI API key or incur per-request OpenAI API charges. Seven specialists cover macro, India markets, geopolitical risk, cross-asset context, conditional scenarios, Indian sector transmission channels, and contrarian interpretations. A Risk & Evidence Auditor critiques all seven reports before the Lead Research Analyst synthesizes the final brief. Evidence is collected server-side from configured FRED-backed indicators and, when available, the read-only Upstox quote endpoint.

### Run the free local model

1. Install [Ollama for Windows](https://ollama.com/download/windows) and start it.
2. In PowerShell, run `ollama pull qwen3:4b` (about 2.5 GB for the default quantized model) and confirm it appears in `ollama list`.
3. Set these values in the untracked `backend/.env` file, then restart FastAPI:

   ```dotenv
   ARTHVEST_LLM_PROVIDER=ollama
   OLLAMA_BASE_URL=http://127.0.0.1:11434
   ARTHVEST_AGENT_MODEL=qwen3:4b
   ARTHVEST_AGENT_MAX_CONCURRENCY=3
   ```

4. Visit `GET /api/agents/status` or the Agents page. The status endpoint checks that Ollama is reachable and the selected model is installed.

Local inference uses the machine RAM/GPU and power. The AI calls stay local, but collecting macro and Upstox market data can still use the internet. The geopolitical role has no dedicated live-news source, and the cross-asset role cannot infer correlations from single snapshots.

### Optional cloud provider

To switch deliberately to cloud inference, set `ARTHVEST_LLM_PROVIDER=openai`, configure `OPENAI_API_KEY` privately, and set `ARTHVEST_AGENT_MODEL=gpt-4.1-mini`. This mode may incur API charges. Never put the key in the frontend environment or source control. Local mode disables remote OpenAI tracing and does not use an OpenAI key.

- Agent status: `GET /api/agents/status`
- Generate a research brief: `POST /api/agents/research` with JSON body `{"question":"Summarize current macro risks for India" }`

This is descriptive decision support, not a calibrated forecast or personalized financial advice. Agents must not invent unavailable readings, stale observations remain marked, market quote gaps are disclosed, and no agent can place or modify trades. Each research run makes nine model calls (seven specialists, one evidence audit, and one lead synthesis). Local inference runs at most three specialists simultaneously by default to reduce pressure on developer RAM/VRAM; override `ARTHVEST_AGENT_MAX_CONCURRENCY` when appropriate.

## Archived historical analytics

The optional archive can power a descriptive analytics endpoint such as `/api/macro/analytics/fed-funds?limit=12`. It reports the oldest/latest values in the returned window, absolute and relative change, direction, mean, min/max, and population standard deviation. The endpoint requires a reachable configured database and at least two archived display observations. For U.S. CPI inflation it derives year-over-year inflation from archived CPI index levels, matching the dashboard's units. These are descriptive statistics only—not a calibrated regime score or forecast. `limit` is between 2 and 60.

## API endpoints

| Endpoint | Purpose |
|---|---|
| `GET /health` | Backend health |
| `GET /api/macro/catalog` | Indicator definitions and metadata |
| `GET /api/macro/overview` | Latest available snapshot for configured indicators |
| `GET /api/macro/quality` | Coverage, staleness and availability summary |
| `GET /api/macro/history/{indicator_key}?limit=12` | Historical observations; limit from 1 to 60 |
| `GET /api/macro/fed-funds` | Federal Funds Rate endpoint |
| `GET /api/macro/score/us-conditions` | Provisional U.S.-only macro conditions subscore |
| `GET /api/macro/storage` | Database readiness and archive counts |
| `GET /api/market/upstox/status` | Upstox token readiness without exposing credentials |
| `GET /api/market/upstox/quotes` | Read-only NIFTY 50, NIFTY BANK and India VIX snapshot (requires `UPSTOX_ANALYTICS_TOKEN`) |
| `GET /api/agents/status` | AI research-agent readiness without exposing credentials |
| `POST /api/agents/research` | Run the nine-call, nine-role evidence-grounded research workflow (local Ollama by default) |
| `GET /api/macro/archive/{indicator_key}?limit=12` | Stored source-native observations (requires `DATABASE_URL`) |
| `GET /api/macro/revisions/{indicator_key}?limit=20` | Detected upstream value revisions (requires `DATABASE_URL`) |
| `GET /api/macro/source-checks?limit=24` | Recent persisted source fetch outcomes (requires `DATABASE_URL`)
| `GET /api/macro/analytics/{indicator_key}?limit=12` | Descriptive analytics over archived observations (requires `DATABASE_URL`)
| `GET /api/macro/compare?indicators=fed-funds,us-inflation,us-unemployment&years=5` | Rebased relative trends for 2–5 archived indicators (requires `DATABASE_URL`)

Indicator keys, formulas, sources and freshness thresholds are documented in [docs/MACRO_DATA.md](docs/MACRO_DATA.md).

## Data integrity principles

- Never fabricate current readings or replace missing data with zero.
- Distinguish source observation date from retrieval timestamp.
- Show stale data explicitly; freshness thresholds are provisional operational checks.
- Treat initial scoring weights and thresholds as illustrative until empirically reviewed and backtested.
- FRED data may be revised; consult the original source links for details.
- Arthvest is research and decision support, not personalized financial advice.

## Current limitations

Persistence is optional rather than automatic: archive, archived analytics, and comparisons require a reachable `DATABASE_URL`. The Upstox Market Pulse is optional and requires `UPSTOX_ANALYTICS_TOKEN`; it currently provides quote snapshots, not continuous WebSocket streaming or archived market candles. The AI Research Council defaults to local Ollama inference and does not require an OpenAI API key. It runs seven specialists plus an evidence audit and lead synthesis. Set `ARTHVEST_LLM_PROVIDER=openai` to opt into cloud inference, which may incur API charges; each brief uses nine model runs (seven specialists, one audit, one synthesis). A geopolitical event model and a calibrated full composite score are not implemented yet. Live indicators and upstream historical sparklines continue to work without the archive.


## Cross-indicator historical comparison

The optional archive also powers `GET /api/macro/compare?indicators=fed-funds,us-inflation,us-unemployment&years=5`. Select 2–5 supported keys and a 1, 3, 5, or 10 year calendar window. Each indicator is rebased independently to 100 at its first archived display observation inside the window, allowing relative value movements to be seen together despite different native units. The output preserves each series' actual observation dates and source link; it does not interpolate dates or interpret an increase as positive or negative for the economy. Series with insufficient observations or a non-positive starting value are explicitly marked rather than misleadingly normalized.


## Archive health monitor

The dashboard's Archive Health panel reads `GET /api/macro/storage` and, when persistence is reachable, `GET /api/macro/source-checks?limit=12`. It shows whether persistence is disabled, reachable, or configured but unreachable, along with retained observation/revision/source-check counts and recent fetch outcomes. The configured database URL and credentials are never displayed by this endpoint.


## Scheduled archive ingestion

The **Archive Macro Observations** GitHub Actions workflow can be run manually or on its daily schedule (02:00 UTC / 07:30 IST). It fetches all eight configured macro indicators and verifies that the database source-check count increased, so a fetch-only run is not reported as a successful archive write. Configure a repository Actions secret named `DATABASE_URL` before enabling it. This must be set separately from any deployment environment secret; keep the connection string private. The workflow fails clearly when the secret is missing, the database is unreachable, or expected write records are not confirmed.


## Source revision audit

The dashboard's Source Revision Audit panel reads `GET /api/macro/revisions/{indicator_key}?limit=20`. It shows the observation date whose stored value changed, the previous and revised source-native values, their difference, and when Arthvest detected the change. A first-time archive import is not recorded as a revision; the same observation date must be fetched again with a changed upstream value.


The Source Coverage & Freshness section also includes a per-indicator quality matrix that joins each latest reading and observation age to the live data-quality endpoint and, when the database is configured and reachable, the most recent recorded archive fetch status.
