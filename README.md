# FinPilot: Sprint 2 (AI report + API)

Educational use only. Not financial advice.

## Setup (Python 3.12)

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env
```

## Run

```bash
python -m finpilot.cli MSFT      # prints profile, metrics, scores and score explanation
```

## Run the API

```bash
# Set FINPILOT_OPENAI_API_KEY in .env (without it, responses are degraded: metrics + scores only)
uvicorn finpilot.main:create_app --factory --reload
# Interactive docs: http://127.0.0.1:8000/docs
curl -X POST localhost:8000/v1/research -H 'content-type: application/json' -d '{"ticker":"MSFT"}'
```

| Method | Path | Purpose |
|---|---|---|
| GET | `/health` | Liveness, database and OpenAI configuration status |
| GET | `/v1/companies/{ticker}` | Profile and fundamentals (no LLM) |
| GET | `/v1/companies/{ticker}/scores` | Scores with per-metric explanations (no LLM) |
| POST | `/v1/research` | Full pipeline. Body: `{"ticker": "MSFT", "refresh": false}` |
| GET | `/v1/research/{report_id}` | Stored report |
| GET | `/v1/research?ticker=&limit=` | Report history (summaries) |

Errors use `{"error": {"code", "message", "request_id"}}`. Codes: `INVALID_TICKER` (400),
`TICKER_NOT_FOUND` / `REPORT_NOT_FOUND` (404), `INSUFFICIENT_DATA` / `VALIDATION_ERROR` (422),
`DATA_PROVIDER_ERROR` / `LLM_ERROR` (502), `INTERNAL_ERROR` (500). Every response carries `X-Request-ID`.
If report generation fails, `/v1/research` still returns 200 with `degraded: true` and `report: null`.

## Quality gates

```bash
pytest --cov=finpilot            # 81 tests
ruff check src tests
mypy src tests                   # strict
```

## Layout

| Path | Purpose |
|---|---|
| `config/scoring.yaml` | Score curves and weights. Tune here, no code changes. |
| `src/finpilot/domain` | Pydantic models, ticker validation |
| `src/finpilot/market_data` | `MarketDataProvider` protocol, yfinance adapter, normalizer |
| `src/finpilot/analytics` | Pure derived-metric functions |
| `src/finpilot/scoring` | Config schema, curves, deterministic engine |
| `src/finpilot/reporting` | Prompt builder, OpenAI generator (JSON mode + validation + retry), advisory-language guardrails |
| `src/finpilot/persistence` | SQLAlchemy models, repositories (report history, company data cache) |
| `src/finpilot/research` | `ResearchService` orchestrating data, scores, report, cache, degradation |
| `src/finpilot/api` | FastAPI routes, schemas, error envelope; app factory in `main.py` |
| `src/finpilot/core` | Settings, JSON logging, errors, DI container |
| `src/finpilot/cli.py` | Sprint 1 exit-criterion CLI |

## Notes

- yfinance reports debt/equity as a percentage (150 = 1.5x). The normalizer converts it to a ratio.
- Scores are not rounded in the engine. Round only for display.
- Thresholds are absolute, not sector-relative (Phase 2).
- yfinance is unofficial and may break or be rate-limited. Swap providers via `MarketDataProvider`.
- Two cache layers: company data (24h, `ticker_cache` table) and reports (24h, `research_reports`). Degraded reports are never served from cache.
- Reports are stored as one JSON column for now; normalize when query needs appear. Tables are created with `create_all`; move to Alembic once the schema changes.
- The OpenAI reply is requested in JSON mode and validated with Pydantic plus a banned-phrase check, retried once. The generator is verified only against a fake client here, so try it with a real key.
- Pandas/NumPy are not needed yet and are intentionally not dependencies until analytics grows.
