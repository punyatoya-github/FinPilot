# FinPilot

AI investment research co-pilot. Enter a ticker, get fundamentals, deterministic health scores
and an AI-written educational report. **Educational use only. Not financial advice.**

## Quick start

```bash
python -m venv .venv && source .venv/bin/activate    # Python 3.12   # For Windows -  .venv/Scripts/activate
pip install -e ".[dev]"
cp .env.example .env                                  # add FINPILOT_OPENAI_API_KEY
uvicorn finpilot.main:create_app --factory --reload
```

- Dashboard: http://127.0.0.1:8000/ui (the root URL redirects there)
- API docs: http://127.0.0.1:8000/docs
- CLI: `python -m finpilot.cli MSFT`

Without an OpenAI key everything still works except the narrative: `/v1/research` returns
metrics and scores with `degraded: true`, and the dashboard says the report is unavailable.

### Running without containers

**Local or a single server (recommended):** use a virtualenv from a repository checkout.

```bash
pip install -e .                  # editable install keeps config/scoring.yaml discoverable
uvicorn finpilot.main:create_app --factory --host 127.0.0.1 --port 8000
```

Drop `--reload` outside development and keep a single worker: the rate limiter is in memory and
SQLite allows one writer at a time. If you install non-editable (`pip install .`), set
`FINPILOT_SCORING_CONFIG_PATH` to the absolute path of `config/scoring.yaml`.

**Linux server with systemd:** see `deploy/finpilot.service` (restarts on failure, loads `.env`,
logs to `journalctl -u finpilot`). Put nginx or Caddy in front for HTTPS and set
`FINPILOT_RATE_LIMIT_TRUST_PROXY=true` only when such a proxy sets `X-Forwarded-For`.

**Platforms that run Python directly (Railway, Heroku and similar):** the `Procfile` has the start
command. Platforms without Procfile support (for example Render) take the same command as their
start command. Set the environment variables from `.env.example` in the platform's dashboard.
Their filesystems are usually ephemeral, so the SQLite database and caches reset on each deploy;
attach a persistent disk and point `FINPILOT_DATABASE_URL` at it, or switch to PostgreSQL (add a
driver such as `psycopg` to your dependencies).

### Dashboard modes

- **Mounted (default):** the dashboard runs inside the API process and calls the service directly.
- **Standalone:** `finpilot-ui --api-url http://host:8000` talks to a remote API over HTTP. The API
  then sees all users as one client IP (the UI server), so per-IP limits apply to them jointly.
  Set `FINPILOT_ENABLE_UI=false` on the API if you only want the API.

## API

| Method | Path | Purpose |
|---|---|---|
| GET | `/health` | Liveness, database and OpenAI configuration (not rate limited) |
| GET | `/v1/companies/{ticker}` | Profile and fundamentals (no LLM) |
| GET | `/v1/companies/{ticker}/scores` | Scores with per-metric explanations (no LLM) |
| POST | `/v1/research` | Full pipeline. Body: `{"ticker": "MSFT", "refresh": false}` |
| GET | `/v1/research/{report_id}` | Stored report |
| GET | `/v1/research?ticker=&limit=` | Report history (summaries) |

Errors use `{"error": {"code", "message", "request_id"}}`: `INVALID_TICKER` 400,
`TICKER_NOT_FOUND` / `REPORT_NOT_FOUND` 404, `INSUFFICIENT_DATA` / `VALIDATION_ERROR` 422,
`RATE_LIMITED` 429 (with `Retry-After`), `DATA_PROVIDER_ERROR` / `LLM_ERROR` 502,
`INTERNAL_ERROR` 500. Every response carries `X-Request-ID`.

## Rate limiting

In-memory sliding window per client IP, single process only (use Redis if you run several
instances). Defaults: 10 research requests/min and 60 other `/v1` requests/min. The dashboard
shares the research limit. Set a limit to `0` to disable. `FINPILOT_RATE_LIMIT_TRUST_PROXY=true`
makes the limiter use `X-Forwarded-For`; enable it only behind a reverse proxy you control, because
clients can spoof that header otherwise.

## Quality gates

```bash
pytest --cov=finpilot      # 121 tests
ruff check src tests scripts
mypy src tests             # strict
```

### Evaluating report quality (needs network + OpenAI key)

```bash
python scripts/evaluate_reports.py            # AAPL MSFT GOOGL AMZN NVDA META JPM KO XOM TSLA
python scripts/evaluate_reports.py KO JPM --out docs/evaluation_report.md
```

Generates fresh reports and checks: all nine sections present, advisory language (buy/sell,
price targets), disclaimer intact, percentages in the text that don't match provided metrics
(possible invented figures), low-confidence scores and sector caveats (banks, REITs, utilities).
It writes a markdown file for human review and exits non-zero on error-level findings. The automated
checks catch rule violations; they do not replace reading the reports.

## Layout

| Path | Purpose |
|---|---|
| `config/scoring.yaml` | Score curves and weights. Tune here, no code changes. |
| `src/finpilot/domain` | Pydantic models, ticker validation, display formatting |
| `src/finpilot/market_data` | Provider protocol, yfinance adapter, normalizer, TTL cache decorator |
| `src/finpilot/analytics`, `scoring` | Pure derived metrics and the deterministic scoring engine |
| `src/finpilot/reporting` | Prompt builder, OpenAI generator (JSON mode, validation, retry), guardrails |
| `src/finpilot/persistence` | SQLAlchemy models and repositories (report history, data cache) |
| `src/finpilot/research` | `ResearchService`: data, scores, report, cache, degradation |
| `src/finpilot/api` | FastAPI routes, schemas, error envelope; app factory in `main.py` |
| `src/finpilot/ui` | Gradio dashboard, backends (in-process / HTTP), pure rendering |
| `src/finpilot/evaluation` | Report quality checks and the multi-ticker runner |
| `src/finpilot/core` | Settings, JSON logging, errors, rate limiter, DI container |

## Known limitations

- yfinance is unofficial and may break, be rate-limited, or restrict commercial use. Move to a
  licensed provider (FMP, Polygon) before a public launch by implementing `MarketDataProvider`.
- Scores use absolute thresholds, not sector-relative ones. Financials, REITs and
  utilities can be misjudged, and the dashboard says so.
- Qualitative sections (business model, competitive position) come from the model's general
  knowledge and can be stale. The prompt asks readers to verify against filings.
- Reports are stored as one JSON column; tables are created with `create_all`. Add Alembic
  migrations when the schema starts changing.
- The OpenAI path has only been tested against a fake client.
