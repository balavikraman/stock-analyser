from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=ROOT / ".env", env_file_encoding="utf-8", extra="ignore")

    app_host: str = "127.0.0.1"
    app_port: int = 8765
    app_env: str = "development"
    database_url: str = ""
    data_provider: str = "auto"
    allow_demo_fallback_for_real_symbols: bool = False
    strict_analysis_mode: bool = False
    min_actionable_confidence: float = 0.60

    # V0.5 official evidence layer. This enriches the normalized market-data
    # provider with exchange/company filings; it does not silently invent data.
    official_evidence_enabled: bool = True
    require_official_evidence: bool = False
    official_evidence_cache_minutes: int = 20

    # Prospective validation. Costs are configurable because Indian brokerage,
    # taxes and slippage vary by product, broker and trade direction.
    validation_benchmark_symbol: str = "^NSEI"
    validation_round_trip_cost_pct: float = 0.25
    validation_update_limit: int = 100
    validation_timezone: str = "Asia/Kolkata"
    validation_run_timeout_minutes: int = 120
    validation_minimum_rule_sample: int = 30

    # Free, broad-market reference used only as a decision guardrail. It is
    # deliberately separate from the outcome-validation benchmark setting.
    market_regime_benchmark_symbol: str = "^NSEI"
    market_breadth_minimum_symbols: int = 3

    # Read-only portfolio guardrails. These report concentration risk and never
    # submit or modify a broker order.
    portfolio_max_position_pct: float = 15.0
    portfolio_max_concentration_index: float = 25.0

    # Optional local-only research alerts. Empty values keep alerts disabled.
    telegram_bot_token: str = ""
    telegram_chat_id: str = ""
    telegram_alerts_enabled: bool = False
    telegram_min_actionable_confidence: float = 0.70
    official_event_review_days: int = 7

    default_symbol: str = "INFY.NS"
    watchlist: str = "INFY.NS,TCS.NS,HCLTECH.NS,POWERGRID.NS,NTPC.NS,ITC.NS"

    zerodha_api_key: str = ""
    zerodha_api_secret: str = ""
    zerodha_redirect_url: str = "http://127.0.0.1:8765/api/zerodha/callback"

    @property
    def watchlist_symbols(self) -> list[str]:
        return [s.strip().upper() for s in self.watchlist.split(",") if s.strip()]

    @property
    def effective_database_url(self) -> str:
        if self.database_url.strip():
            return self.database_url.strip()
        runtime = ROOT / ".runtime"
        runtime.mkdir(exist_ok=True)
        return f"sqlite:///{runtime / 'stock_analyzer.db'}"

    @property
    def production_like(self) -> bool:
        return self.app_env.lower() in {"production", "prod"} or self.strict_analysis_mode


@lru_cache
def get_settings() -> Settings:
    return Settings()
