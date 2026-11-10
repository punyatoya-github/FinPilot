# FinPilot: Sprint 1 (data + scoring core)

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

## Quality gates

```bash
pytest --cov=finpilot            # 35 tests
ruff check src tests
mypy src                         # strict
```

## Layout

| Path | Purpose |
|---|---|
| `config/scoring.yaml` | Score curves and weights. Tune here, no code changes. |
| `src/finpilot/domain` | Pydantic models, ticker validation |
| `src/finpilot/market_data` | `MarketDataProvider` protocol, yfinance adapter, normalizer |
| `src/finpilot/analytics` | Pure derived-metric functions |
| `src/finpilot/scoring` | Config schema, curves, deterministic engine |
| `src/finpilot/core` | Settings, JSON logging, errors, DI container |
| `src/finpilot/cli.py` | Sprint 1 exit-criterion CLI |

## Notes

- yfinance reports debt/equity as a percentage (150 = 1.5x). The normalizer converts it to a ratio.
- Scores are not rounded in the engine. Round only for display.
- Thresholds are absolute, not sector-relative (Phase 2).
- yfinance is unofficial and may break or be rate-limited. Swap providers via `MarketDataProvider`.
- Pandas/NumPy are not needed yet and are intentionally not dependencies until analytics grows.
