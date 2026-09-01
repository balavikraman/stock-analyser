# Stock Analyzer — local-first investment intelligence

A beginner-friendly but auditable stock-analysis application for long-term compounding plus a smaller tactical/swing workflow. It is designed to answer four questions:

1. **Should I own this business?**
2. **Is the current valuation sensible?**
3. **Is this a reasonable entry/accumulation point?**
4. **What would make me reduce or exit?**

> The system is decision support, not a profit guarantee. Missing evidence lowers confidence instead of being silently guessed.

## What is implemented

- Polished local dashboard and deep stock report
- 5-year/available annual financial table and recent quarterly table
- Fundamental quality scoring with confidence weighting
- Valuation scoring with sector-aware handling for financial businesses
- Technical engine: 20/50/100/200-day averages, RSI, MACD, ATR, support/resistance, 52-week drawdown
- Staged entry / accumulation / do-not-chase / partial-profit review ranges
- Transparent bear/base/bull EPS-multiple scenario model
- Current-provider news ingestion + conservative keyword triage
- Risk/catalyst and value-trap oriented reporting
- Data-quality/confidence layer
- PostgreSQL support with SQLite first-run fallback
- Local investment journal and analysis snapshots
- Opportunity scanner for a configurable watchlist
- Zerodha **read-only** login/holdings integration; no order methods are implemented
- Demo mode for UI and scoring validation when external data is unavailable
- Automated tests for scoring, confidence and technical calculations

## Important research limitation

The app can fetch external price/fundamental/news data through provider adapters, but **deep current-affairs/global-news reasoning needs a high-quality research source**. The current automated keyword triage is intentionally capped at low confidence. Later, the ChatGPT app/plugin layer can provide deeper web research without weakening the local calculations.

## Quick start on Windows

1. Install **Python 3.12+**.
2. Extract/clone this folder.
3. Double-click `setup.cmd` once.
4. Double-click `start.cmd` whenever you want to use the analyzer.
5. Browser opens automatically at `http://127.0.0.1:8765`.

The first run can use SQLite automatically. PostgreSQL is recommended for the permanent portfolio database.

## PostgreSQL

Create a database/user locally and set this in `.env`:

```env
DATABASE_URL=postgresql+psycopg://stock_analyzer:YOUR_PASSWORD@127.0.0.1:5432/stock_analyzer
```

Tables are created automatically on startup for V0.x.

## Live vs demo data

```env
DATA_PROVIDER=auto
```

- `auto`: try yfinance; fall back to clearly labelled demo data if the provider fails.
- `yfinance`: fail loudly if external data is unavailable.
- `demo`: use deterministic sample data for UI/testing only.

NSE symbols generally use the `.NS` suffix, e.g. `INFY.NS`, `TCS.NS`, `HDFCBANK.NS`.

## Zerodha read-only integration

Set only on your local PC:

```env
ZERODHA_API_KEY=...
ZERODHA_API_SECRET=...
ZERODHA_REDIRECT_URL=http://127.0.0.1:8765/api/zerodha/callback
```

Then click **Connect Zerodha**. Access tokens are stored under `.runtime/`, which is gitignored. The app exposes holdings, positions and margins only. It intentionally has **no buy/sell/order endpoints**.

## Score design

The overall score is confidence-weighted. Current default weighting:

- Fundamentals: 34%
- Valuation: 22%
- Technical/entry timing: 16%
- Governance: 10%
- Current research/news: 18%

A component with missing data contributes less to both the score and confidence. This prevents a handful of known metrics from creating false precision.

### Why governance/news can show lower confidence

Public automated data often lacks reliable promoter pledge, auditor quality, related-party, legal and point-in-time governance context. The analyzer **does not infer these facts**. Deep research and official filings will be added as separate evidence providers.

## Entry and exit philosophy

- Never average down only because price fell.
- Add only when the original business thesis remains intact.
- Long-term exits are primarily **thesis stops** and valuation reviews, not arbitrary price stop-losses.
- Tactical/swing positions should use separate rules and smaller capital allocation.
- Do not chase an excellent business at an irrational price.

## Validation philosophy

A proper fundamental backtest requires **point-in-time financial data** to avoid look-ahead bias. The project will not claim a valid historical backtest using today's revised financial database. Instead:

1. store every future analysis snapshot,
2. record the thesis and decision,
3. measure subsequent 1/3/6/12-month outcomes,
4. calibrate scores by sector and market regime,
5. add point-in-time datasets only when a reliable source is available.

## API

- `GET /api/health`
- `GET /api/analyze/{symbol}`
- `GET /api/scan`
- `GET/POST /api/journal`
- `GET /api/portfolio`
- `GET /api/zerodha/login`
- `GET /api/zerodha/callback`
- Interactive docs: `/api/docs`

## Next integrations

- Official exchange/company filing evidence provider
- Structured promoter/shareholding/governance history
- Peer and historical valuation distributions
- Sector-specific models (banks, NBFC, insurance, pharma, EV, capital goods)
- Portfolio-level sector correlation and target allocation
- ChatGPT app/plugin interface for deep live global research
- Point-in-time outcome calibration dashboard
