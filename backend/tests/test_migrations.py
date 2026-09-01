from __future__ import annotations

from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect, text

ROOT = Path(__file__).resolve().parents[2]


def _config(db_url: str) -> Config:
    cfg = Config(str(ROOT / "alembic.ini"))
    cfg.set_main_option("script_location", str(ROOT / "migrations"))
    cfg.set_main_option("sqlalchemy.url", db_url)
    return cfg


def test_fresh_database_migrates_to_head(tmp_path):
    db_path = tmp_path / "fresh.db"
    url = f"sqlite:///{db_path}"
    command.upgrade(_config(url), "head")

    engine = create_engine(url)
    tables = set(inspect(engine).get_table_names())
    assert {"analysis_snapshots", "journal_entries", "watchlist_items", "filing_snapshots", "prediction_records", "prediction_outcomes", "validation_runs", "alembic_version"}.issubset(tables)


def test_existing_pre_v05_database_keeps_data_and_adds_filings(tmp_path):
    db_path = tmp_path / "existing.db"
    url = f"sqlite:///{db_path}"
    engine = create_engine(url)

    with engine.begin() as conn:
        conn.execute(text("CREATE TABLE analysis_snapshots (id INTEGER PRIMARY KEY, symbol VARCHAR(32) NOT NULL, created_at DATETIME NOT NULL, overall_score FLOAT, confidence FLOAT NOT NULL, verdict VARCHAR(64) NOT NULL, payload JSON NOT NULL)"))
        conn.execute(text("CREATE TABLE journal_entries (id INTEGER PRIMARY KEY, created_at DATETIME NOT NULL, symbol VARCHAR(32) NOT NULL, action VARCHAR(32) NOT NULL, price FLOAT, quantity FLOAT, thesis TEXT NOT NULL, thesis_breaker TEXT NOT NULL, snapshot_id INTEGER)"))
        conn.execute(text("CREATE TABLE watchlist_items (id INTEGER PRIMARY KEY, symbol VARCHAR(32) NOT NULL UNIQUE, note TEXT NOT NULL, target_entry FLOAT, created_at DATETIME NOT NULL)"))
        conn.execute(text("INSERT INTO watchlist_items (id, symbol, note, target_entry, created_at) VALUES (1, 'INFY.NS', 'keep me', NULL, CURRENT_TIMESTAMP)"))

    command.upgrade(_config(url), "head")

    tables = set(inspect(engine).get_table_names())
    assert "filing_snapshots" in tables
    with engine.connect() as conn:
        assert conn.execute(text("SELECT note FROM watchlist_items WHERE id = 1")).scalar_one() == "keep me"
        assert conn.execute(text("SELECT version_num FROM alembic_version")).scalar_one() == "20260901_0003"
