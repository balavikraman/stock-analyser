from __future__ import annotations

from datetime import date, datetime, timedelta

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from backend.app.db import Base
from backend.app.models import AnalysisSnapshot, PredictionOutcome, PredictionRecord
from backend.app.services.validation import (
    MODEL_VERSIONS,
    build_walk_forward_splits,
    calculate_forward_outcome,
    record_analysis_predictions,
    update_prediction_outcomes,
    validation_metrics,
    walk_forward_plan,
)


def _session() -> Session:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return Session(engine)


def _history(start: date, prices: list[float]) -> list[dict]:
    return [{"date": (start + timedelta(days=index)).isoformat(), "close": price} for index, price in enumerate(prices)]


def _report() -> dict:
    return {
        "symbol": "INFY.NS",
        "as_of": "2026-01-01T10:00:00+00:00",
        "price": 100.0,
        "verdict": "ACCUMULATE",
        "overall_confidence": 0.70,
        "scores": {"technical": {"score": 72, "confidence": 0.65}},
        "metrics": {"roe": 25.0},
        "technicals": {"score": 72.0, "confidence": 0.65},
        "entry_plan": {"status": "staged"},
        "scenarios": {},
        "data_quality": {
            "live_data": True,
            "actionable": True,
            "evidence": {"price": {"source": "test"}},
            "evidence_summary": {"evidence_confidence": 0.80},
            "official_validation": {"verified": True},
            "action_block_reasons": [],
        },
    }


def test_recording_freezes_separate_strategy_baselines_without_fake_probability():
    db = _session()
    snapshot = AnalysisSnapshot(symbol="INFY.NS", overall_score=80, confidence=0.7, verdict="ACCUMULATE", payload=_report())
    db.add(snapshot); db.commit(); db.refresh(snapshot)

    rows = record_analysis_predictions(db, snapshot.id, _report())

    assert {row.strategy for row in rows} == {"long_term", "swing"}
    assert all(row.model_frozen for row in rows)
    assert all(row.model_probability is None for row in rows)
    assert all(row.validation_eligible for row in rows)
    assert {row.model_version for row in rows} == set(MODEL_VERSIONS.values())
    long_term = next(row for row in rows if row.strategy == "long_term")
    swing = next(row for row in rows if row.strategy == "swing")
    assert long_term.signal == "ACCUMULATE"
    assert long_term.decision_confidence == 0.7
    assert swing.signal == "BULLISH_SETUP"
    assert swing.decision_confidence == 0.65
    assert swing.input_snapshot["analysis_snapshot_id"] == snapshot.id


def test_forward_outcome_uses_trading_sessions_costs_benchmark_and_excursions():
    prediction = PredictionRecord(
        id=1,
        created_at=datetime(2026, 1, 1),
        symbol="INFY.NS",
        strategy="swing",
        model_version="test",
        signal="BULLISH_SETUP",
        entry_price=100,
        benchmark_symbol="^NSEI",
        horizon_spec={"5d": 5},
        input_snapshot={},
    )
    stock = _history(date(2026, 1, 1), [100, 98, 103, 102, 105, 106])
    benchmark = _history(date(2026, 1, 1), [200, 201, 202, 203, 204, 205])

    result = calculate_forward_outcome(prediction, "5d", 5, stock, benchmark, estimated_cost_pct=0.25)

    assert result["status"] == "complete"
    assert result["gross_return_pct"] == 6.0
    assert result["net_return_pct"] == 5.75
    assert result["benchmark_return_pct"] == 2.5
    assert result["excess_return_pct"] == 3.25
    assert result["max_favorable_excursion_pct"] == 6.0
    assert result["max_adverse_excursion_pct"] == -2.0


def test_forward_outcome_stays_pending_until_full_horizon_exists():
    prediction = PredictionRecord(created_at=datetime(2026, 1, 1), entry_price=100)
    result = calculate_forward_outcome(prediction, "5d", 5, _history(date(2026, 1, 1), [100, 101, 102]), [])
    assert result["status"] == "pending"
    assert result.get("end_date") is None


def test_swing_target_stop_measurement_uses_daily_bars_and_marks_same_day_order_ambiguous():
    prediction = PredictionRecord(
        created_at=datetime(2026, 1, 1), symbol="INFY.NS", strategy="swing", signal="BULLISH_SETUP",
        entry_price=100, horizon_spec={"5d": 5},
        input_snapshot={"swing_evaluation": {"available": True, "long_target_price": 110, "long_stop_price": 95}},
    )
    stock = [
        {"date": "2026-01-01", "close": 100, "high": 102, "low": 99},
        {"date": "2026-01-02", "close": 98, "high": 100, "low": 94},
        {"date": "2026-01-03", "close": 111, "high": 112, "low": 108},
        {"date": "2026-01-04", "close": 105, "high": 111, "low": 94},
        {"date": "2026-01-05", "close": 106, "high": 107, "low": 103},
        {"date": "2026-01-06", "close": 107, "high": 108, "low": 105},
    ]
    result = calculate_forward_outcome(prediction, "5d", 5, stock, [])

    assert result["target_price"] == 110
    assert result["stop_price"] == 95
    assert result["target_stop_status"] == "stop_hit_first"

    prediction.input_snapshot["swing_evaluation"] = {"available": True, "long_target_price": 110, "long_stop_price": 95}
    stock[1] = {"date": "2026-01-02", "close": 100, "high": 111, "low": 94}
    result = calculate_forward_outcome(prediction, "5d", 5, stock, [])
    assert result["target_stop_status"] == "ambiguous_same_session"


def test_prediction_snapshot_marks_historical_reconstruction_as_unsupported():
    db = _session()
    snapshot = AnalysisSnapshot(symbol="INFY.NS", overall_score=80, confidence=0.7, verdict="ACCUMULATE", payload=_report())
    db.add(snapshot); db.commit(); db.refresh(snapshot)
    swing = next(row for row in record_analysis_predictions(db, snapshot.id, _report()) if row.strategy == "swing")

    assert swing.input_snapshot["point_in_time"]["status"] == "frozen_at_signal_time"
    assert swing.input_snapshot["point_in_time"]["historical_reconstruction_supported"] is False
    assert swing.input_snapshot["swing_evaluation"]["available"] is False


class FakeProvider:
    name = "fake_point_in_time"

    def __init__(self, histories: dict[str, list[dict]]):
        self.histories = histories

    def price_history(self, symbol: str, period: str = "5y") -> list[dict]:
        return self.histories[symbol]


def test_outcome_updater_persists_mature_and_pending_horizons():
    db = _session()
    row = PredictionRecord(
        created_at=datetime(2026, 1, 1), symbol="INFY.NS", strategy="swing", model_version="test-v1",
        model_frozen=True, signal="BULLISH_SETUP", actionable=True, validation_eligible=True,
        entry_price=100, benchmark_symbol="^NSEI", data_quality_confidence=0.8,
        decision_confidence=0.7, horizon_spec={"5d": 5, "20d": 20}, input_snapshot={},
    )
    db.add(row); db.commit()
    provider = FakeProvider({
        "INFY.NS": _history(date(2026, 1, 1), [100 + index for index in range(11)]),
        "^NSEI": _history(date(2026, 1, 1), [200 + index for index in range(11)]),
    })

    summary = update_prediction_outcomes(db, provider=provider, as_of=date(2026, 1, 11))

    assert summary["outcomes_created"] == 2
    assert summary["complete"] == 1
    assert summary["pending"] == 1
    outcomes = db.query(PredictionOutcome).order_by(PredictionOutcome.horizon_days).all()
    assert [outcome.status for outcome in outcomes] == ["complete", "pending"]
    assert summary["random_split_used"] is False


def test_validation_metrics_report_precision_coverage_and_uncalibrated_probability():
    db = _session()
    prediction = PredictionRecord(
        created_at=datetime(2026, 1, 1), symbol="INFY.NS", strategy="swing", model_version="test-v1",
        model_frozen=True, signal="BULLISH_SETUP", actionable=True, validation_eligible=True,
        entry_price=100, benchmark_symbol="^NSEI", data_quality_confidence=0.8,
        model_probability=None, decision_confidence=0.7, horizon_spec={"5d": 5}, input_snapshot={},
    )
    db.add(prediction); db.commit(); db.refresh(prediction)
    db.add(PredictionOutcome(
        prediction_id=prediction.id, horizon_label="5d", horizon_days=5, status="complete",
        evaluated_at=datetime(2026, 1, 6), net_return_pct=4.0, excess_return_pct=2.0,
        max_adverse_excursion_pct=-1.5,
    ))
    db.commit()

    metrics = validation_metrics(db, strategy="swing")

    assert metrics["prediction_count"] == 1
    assert metrics["coverage"] == 1.0
    assert metrics["overall"]["precision"] == 1.0
    assert metrics["overall"]["win_rate"] == 1.0
    assert metrics["overall"]["brier_score"] is None
    assert metrics["overall"]["calibrated_probabilities"] == 0


def test_walk_forward_splits_are_chronological_with_a_purged_gap():
    items = [{"id": index, "created_at": f"2026-01-{index:02d}"} for index in range(1, 10)]
    splits = build_walk_forward_splits(items, min_train_size=3, test_size=2, gap_size=1)

    assert splits
    first = splits[0]
    assert first["train_ids"] == [1, 2, 3]
    assert first["gap_ids"] == [4]
    assert first["test_ids"] == [5, 6]
    for split in splits:
        assert not set(split["train_ids"]).intersection(split["test_ids"])
        assert not set(split["gap_ids"]).intersection(split["test_ids"])


def test_walk_forward_plan_uses_only_completed_records_for_one_horizon():
    db = _session()
    predictions = []
    for index in range(4):
        prediction = PredictionRecord(
            created_at=datetime(2026, 1, index + 1), symbol="INFY.NS", strategy="swing",
            model_version="test-v1", model_frozen=True, signal="BULLISH_SETUP",
            actionable=True, validation_eligible=True, entry_price=100,
            benchmark_symbol="^NSEI", data_quality_confidence=0.8,
            decision_confidence=0.7, horizon_spec={"5d": 5, "10d": 10}, input_snapshot={},
        )
        db.add(prediction)
        db.flush()
        predictions.append(prediction)
    db.add_all([
        PredictionOutcome(prediction_id=predictions[0].id, horizon_label="5d", horizon_days=5, status="complete"),
        PredictionOutcome(prediction_id=predictions[1].id, horizon_label="5d", horizon_days=5, status="pending"),
        PredictionOutcome(prediction_id=predictions[2].id, horizon_label="10d", horizon_days=10, status="complete"),
        PredictionOutcome(prediction_id=predictions[3].id, horizon_label="5d", horizon_days=5, status="complete"),
    ])
    db.commit()

    plan = walk_forward_plan(db, strategy="swing", horizon_days=5, min_train_size=1, test_size=1, gap_size=0)

    assert plan["completed_records"] == 2
    assert plan["random_split_used"] is False
    assert plan["splits"][0]["train_ids"] == [predictions[0].id]
    assert plan["splits"][0]["test_ids"] == [predictions[3].id]
