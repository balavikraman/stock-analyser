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


@lru_cache
def get_settings() -> Settings:
    return Settings()
