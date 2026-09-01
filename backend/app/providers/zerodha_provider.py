from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from ..config import ROOT, get_settings

TOKEN_FILE = ROOT / ".runtime" / "zerodha_token.json"


class ZerodhaReadOnly:
    """Read-only adapter by design: no order placement methods are exposed."""

    def __init__(self) -> None:
        self.settings = get_settings()
        self.kite = None
        if self.settings.zerodha_api_key:
            try:
                from kiteconnect import KiteConnect
                self.kite = KiteConnect(api_key=self.settings.zerodha_api_key)
            except ImportError:
                self.kite = None
        self._load_token()

    def _load_token(self) -> None:
        if not self.kite or not TOKEN_FILE.exists():
            return
        try:
            token = json.loads(TOKEN_FILE.read_text(encoding="utf-8")).get("access_token")
            if token:
                self.kite.set_access_token(token)
        except Exception:
            pass

    def configured(self) -> bool:
        return bool(self.settings.zerodha_api_key and self.settings.zerodha_api_secret and self.kite is not None)

    def login_url(self) -> str | None:
        return self.kite.login_url() if self.configured() and self.kite else None

    def exchange_request_token(self, request_token: str) -> dict[str, Any]:
        if not self.kite or not self.configured():
            raise RuntimeError("Zerodha API key/secret not configured")
        data = self.kite.generate_session(request_token, api_secret=self.settings.zerodha_api_secret)
        TOKEN_FILE.parent.mkdir(exist_ok=True)
        TOKEN_FILE.write_text(json.dumps({"access_token": data["access_token"]}), encoding="utf-8")
        self.kite.set_access_token(data["access_token"])
        return {"user_name": data.get("user_name"), "user_id": data.get("user_id")}

    def holdings(self) -> list[dict[str, Any]]:
        return self.kite.holdings() if self.kite else []

    def positions(self) -> dict[str, Any]:
        return self.kite.positions() if self.kite else {"net": [], "day": []}

    def margins(self) -> dict[str, Any]:
        return self.kite.margins() if self.kite else {}
