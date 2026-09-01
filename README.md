# Stock Analyzer — local-first investment intelligence

A beginner-friendly but auditable stock-analysis application for long-term compounding plus a smaller tactical/swing workflow. It is designed to answer four questions:

1. **Should I own this business?**
2. **Is the current valuation sensible?**
3. **Is this a reasonable entry/accumulation point?**
4. **What would make me reduce or exit?**

> The system is decision support, not a profit guarantee. Missing evidence lowers confidence instead of being silently guessed.

## Implemented in V0.3

- Polished local dashboard and deep stock report
- Annual and quarterly financial tables
- Fundamental quality scoring with confidence weighting
- Valuation scoring with sector-aware handling
- Technical engine: 20/50/100/200-day averages, RSI, MACD, ATR, support/resistance, 52-week drawdown
- Staged entry / accumulation / do-not-chase / partial-profit review ranges
- Transparent bear/base/bull EPS-multiple scenario model
- Current-provider news ingestion + conservative triage
- Risk/catalyst and value-trap oriented reporting
- Data-quality/confidence layer
- PostgreSQL support with SQLite first-run fallback
- Local investment journal and analysis snapshots
- Opportunity scanner for a configurable watchlist
- Zerodha **read-only** login/holdings integration; no order methods are implemented
- Demo mode for validation when external data is unavailable
- Automated tests for scoring, confidence and technical calculations

## Windows quick start

1. Install **Python 3.12+**.
2. Open the `stock-analyzer` folder.
3. Double-click `setup.cmd` once.
4. Double-click `start.cmd` whenever you want to use the analyzer.
5. Browser opens at `http://127.0.0.1:8765`.

The first run can use SQLite automatically. PostgreSQL is recommended for the permanent portfolio database.

## Data modes

`DATA_PROVIDER=auto` tries the external provider first and falls back to clearly labelled demo data if unavailable. `DATA_PROVIDER=yfinance` fails loudly instead of falling back. `DATA_PROVIDER=demo` is for UI/testing only.

NSE symbols generally use `.NS`, e.g. `INFY.NS`, `TCS.NS`, `HDFCBANK.NS`.

## Zerodha read-only integration

Set your API key and secret only in the local `.env`. Tokens are stored under `.runtime/`, which is gitignored. The code intentionally exposes holdings/positions/margins only; it contains no order-placement methods.

## Score design

Default overall weighting:

- Fundamentals: 34%
- Valuation: 22%
- Technical/entry timing: 16%
- Governance: 10%
- Current research/news: 18%

Each component is multiplied by its evidence confidence. Missing data reduces influence instead of creating false precision.

## Validation rule

A valid historical fundamental backtest needs **point-in-time financial data** to avoid look-ahead bias. This project will not claim a valid backtest using today's revised fundamentals. It stores every analysis snapshot and investment thesis so future 1/3/6/12-month outcomes can be measured honestly.

## API

- `GET /api/health`
- `GET /api/analyze/{symbol}`
- `GET /api/scan`
- `GET/POST /api/journal`
- `GET /api/portfolio`
- `GET /api/zerodha/login`
- `GET /api/zerodha/callback`
- Interactive docs: `/api/docs`

## Research limitation

Deep current-affairs/global-news reasoning needs high-quality research sources. Automated news triage is intentionally low-confidence until official filing/news research adapters and the ChatGPT app/plugin layer are connected.
