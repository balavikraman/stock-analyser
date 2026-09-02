from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime, timezone
from math import isfinite
from typing import Any, Iterable

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import get_settings
from ..models import PredictionOutcome, PredictionRecord


HORIZONS: dict[str, dict[str, int]] = {
    "swing": {"5d": 5, "10d": 10, "20d": 20},
    "long_term": {"3m": 63, "6m": 126, "12m": 252},
}
MODEL_VERSIONS = {
    "swing": "swing-technical-baseline-v1",
    "long_term": "long-term-rules-baseline-v1",
}
POSITIVE_SIGNALS = {
    "swing": {"BULLISH_SETUP"},
    "long_term": {"ACCUMULATE"},
}
NEGATIVE_SIGNALS = {
    "swing": {"BEARISH_SETUP"},
    "long_term": {"AVOID / REASSESS"},
}


def _clamp_probability(value: Any) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return 0.0
    if not isfinite(number):
        return 0.0
    return round(max(0.0, min(1.0, number)), 4)


def _number(value: Any) -> float | None:
    if isinstance(value, (int, float)) and isfinite(float(value)):
        return float(value)
    return None


def _naive_utc(value: Any) -> datetime:
    if isinstance(value, datetime):
        parsed = value
    else:
        try:
            parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        except (TypeError, ValueError):
            return datetime.now(timezone.utc).replace(tzinfo=None)
    if parsed.tzinfo:
        parsed = parsed.astimezone(timezone.utc).replace(tzinfo=None)
    return parsed


def _swing_signal(report: dict[str, Any]) -> str:
    technical = report.get("technicals") or {}
    score = _number(technical.get("score"))
    if score is None:
        return "INSUFFICIENT_DATA"
    if score >= 65:
        return "BULLISH_SETUP"
    if score >= 45:
        return "NEUTRAL"
    return "BEARISH_SETUP"


def _input_snapshot(report: dict[str, Any], snapshot_id: int) -> dict[str, Any]:
    quality = report.get("data_quality") or {}
    technicals = report.get("technicals") or {}
    price = _number(report.get("price"))
    atr = _number(technicals.get("atr14"))
    swing_evaluation: dict[str, Any] = {
        "available": False,
        "purpose": "prospective baseline outcome measurement, not a trade instruction",
    }
    if price and price > 0 and atr and atr > 0:
        swing_evaluation = {
            "available": True,
            "entry_price": round(price, 6),
            "long_stop_price": round(max(0.01, price - atr), 6),
            "long_target_price": round(price + 2 * atr, 6),
            "short_stop_price": round(price + atr, 6),
            "short_target_price": round(max(0.01, price - 2 * atr), 6),
            "reward_risk_ratio": 2.0,
            "rule": "one ATR stop and two ATR target frozen at signal time",
            "purpose": "prospective baseline outcome measurement, not a trade instruction",
        }
    return {
        "analysis_snapshot_id": snapshot_id,
        "as_of": report.get("as_of"),
        "scores": report.get("scores") or {},
        "metrics": report.get("metrics") or {},
        "sector": report.get("sector") or "UNKNOWN",
        "technicals": technicals,
        "entry_plan": report.get("entry_plan") or {},
        "scenarios": report.get("scenarios") or {},
        "evidence": quality.get("evidence") or {},
        "evidence_summary": quality.get("evidence_summary") or {},
        "official_validation": quality.get("official_validation") or {},
        # Point-in-time context: later validation must not substitute today's
        # regime or relative strength for what was known at signal creation.
        "market_regime": quality.get("market_regime") or {},
        "market_breadth": quality.get("market_breadth") or {},
        "relative_strength": quality.get("relative_strength") or {},
        "official_events": quality.get("official_events") or {},
        "forensic_score": quality.get("forensic_score"),
        "forensic_flags": quality.get("forensic_flags") or [],
        "sector_risk": quality.get("sector_risk") or {},
        "action_block_reasons": quality.get("action_block_reasons") or [],
        "swing_evaluation": swing_evaluation,
        "point_in_time": {
            "status": "frozen_at_signal_time",
            "analysis_as_of": report.get("as_of"),
            "official_evidence": quality.get("evidence") or {},
            "historical_reconstruction_supported": False,
            "historical_reconstruction_note": "Historical simulations require archived source publication dates; this record is valid for prospective validation only.",
        },
    }


def record_analysis_predictions(db: Session, snapshot_id: int, report: dict[str, Any]) -> list[PredictionRecord]:
    """Freeze both strategy baselines for prospective validation.

    `model_probability` intentionally stays null: current confidence values measure
    evidence availability, not an empirically calibrated probability of success.
    """
    settings = get_settings()
    quality = report.get("data_quality") or {}
    evidence_summary = quality.get("evidence_summary") or {}
    data_quality_confidence = _clamp_probability(evidence_summary.get("evidence_confidence"))
    overall_confidence = _clamp_probability(report.get("overall_confidence"))
    technical_confidence = _clamp_probability((report.get("technicals") or {}).get("confidence"))
    live_data = bool(quality.get("live_data"))
    gate_actionable = bool(quality.get("actionable"))
    price = _number(report.get("price"))
    eligible = live_data and price is not None and price > 0
    frozen_input = _input_snapshot(report, snapshot_id)
    created_at = _naive_utc(report.get("as_of"))

    definitions = (
        (
            "long_term",
            str(report.get("verdict") or "INSUFFICIENT DATA"),
            gate_actionable,
            min(overall_confidence, data_quality_confidence),
        ),
        (
            "swing",
            _swing_signal(report),
            gate_actionable and technical_confidence >= 0.60,
            min(technical_confidence, data_quality_confidence),
        ),
    )
    records: list[PredictionRecord] = []
    for strategy, signal, actionable, decision_confidence in definitions:
        row = PredictionRecord(
            created_at=created_at,
            symbol=str(report.get("symbol") or "").upper(),
            strategy=strategy,
            model_version=MODEL_VERSIONS[strategy],
            model_frozen=True,
            signal=signal,
            actionable=bool(actionable),
            validation_eligible=eligible,
            entry_price=price,
            benchmark_symbol=settings.validation_benchmark_symbol,
            data_quality_confidence=data_quality_confidence,
            model_probability=None,
            decision_confidence=_clamp_probability(decision_confidence),
            horizon_spec=HORIZONS[strategy],
            snapshot_id=snapshot_id,
            input_snapshot=frozen_input,
        )
        db.add(row)
        records.append(row)
    db.commit()
    for row in records:
        db.refresh(row)
    return records


def _price_series(rows: Iterable[dict[str, Any]], as_of: date | None = None) -> list[tuple[date, float]]:
    series: dict[date, float] = {}
    for row in rows:
        close = _number(row.get("close"))
        try:
            observed = date.fromisoformat(str(row.get("date"))[:10])
        except (TypeError, ValueError):
            continue
        if close is None or close <= 0 or (as_of and observed > as_of):
            continue
        series[observed] = close
    return sorted(series.items())


def _ohlc_series(rows: Iterable[dict[str, Any]], as_of: date | None = None) -> list[tuple[date, float, float]]:
    """Return usable daily high/low bars, never filling absent highs/lows from close."""
    series: dict[date, tuple[float, float]] = {}
    for row in rows:
        high, low = _number(row.get("high")), _number(row.get("low"))
        try:
            observed = date.fromisoformat(str(row.get("date"))[:10])
        except (TypeError, ValueError):
            continue
        if high is None or low is None or low <= 0 or high < low or (as_of and observed > as_of):
            continue
        series[observed] = (high, low)
    return [(observed, high, low) for observed, (high, low) in sorted(series.items())]


def _target_stop_measurement(prediction: PredictionRecord, stock_history: list[dict[str, Any]], start_date: date, end_date: date) -> dict[str, Any]:
    if prediction.strategy != "swing":
        return {}
    spec = (prediction.input_snapshot or {}).get("swing_evaluation") or {}
    signal = prediction.signal
    if not spec.get("available") or signal not in {"BULLISH_SETUP", "BEARISH_SETUP"}:
        return {"target_stop_status": "not_applicable"}
    direction = "long" if signal == "BULLISH_SETUP" else "short"
    target = _number(spec.get(f"{direction}_target_price"))
    stop = _number(spec.get(f"{direction}_stop_price"))
    if target is None or stop is None:
        return {"target_stop_status": "not_available"}
    for observed, high, low in _ohlc_series(stock_history):
        if observed < start_date or observed > end_date:
            continue
        target_hit = high >= target if direction == "long" else low <= target
        stop_hit = low <= stop if direction == "long" else high >= stop
        if target_hit and stop_hit:
            return {"target_price": target, "stop_price": stop, "target_stop_status": "ambiguous_same_session"}
        if target_hit:
            return {"target_price": target, "stop_price": stop, "target_stop_status": "target_hit_first"}
        if stop_hit:
            return {"target_price": target, "stop_price": stop, "target_stop_status": "stop_hit_first"}
    return {"target_price": target, "stop_price": stop, "target_stop_status": "neither_hit"}


def _on_or_after(series: list[tuple[date, float]], target: date) -> int | None:
    return next((index for index, (observed, _) in enumerate(series) if observed >= target), None)


def _value_on_or_before(series: list[tuple[date, float]], target: date) -> float | None:
    candidates = [value for observed, value in series if observed <= target]
    return candidates[-1] if candidates else None


def calculate_forward_outcome(
    prediction: PredictionRecord,
    horizon_label: str,
    horizon_days: int,
    stock_history: list[dict[str, Any]],
    benchmark_history: list[dict[str, Any]],
    *,
    as_of: date | None = None,
    estimated_cost_pct: float = 0.25,
    price_source: str = "provider",
) -> dict[str, Any]:
    stock = _price_series(stock_history, as_of)
    benchmark = _price_series(benchmark_history, as_of)
    start_index = _on_or_after(stock, prediction.created_at.date())
    entry_price = _number(prediction.entry_price)
    base = {
        "horizon_label": horizon_label,
        "horizon_days": horizon_days,
        "status": "pending",
        "evaluated_at": datetime.now(timezone.utc).replace(tzinfo=None),
        "estimated_cost_pct": max(0.0, float(estimated_cost_pct)),
        "price_source": price_source,
        "error": None,
    }
    if start_index is None or entry_price is None or entry_price <= 0:
        return {**base, "error": "entry price or first post-prediction market session is unavailable"}
    target_index = start_index + int(horizon_days)
    if target_index >= len(stock):
        return {**base, "start_date": datetime.combine(stock[start_index][0], datetime.min.time()), "start_price": entry_price}

    start_date, _ = stock[start_index]
    end_date, end_price = stock[target_index]
    window = [value for _, value in stock[start_index:target_index + 1]]
    gross = (end_price / entry_price - 1) * 100
    net = gross - base["estimated_cost_pct"]

    benchmark_start_index = _on_or_after(benchmark, start_date)
    benchmark_start = benchmark[benchmark_start_index][1] if benchmark_start_index is not None else None
    benchmark_end = _value_on_or_before(benchmark, end_date)
    benchmark_return = None
    if benchmark_start and benchmark_end:
        benchmark_return = (benchmark_end / benchmark_start - 1) * 100

    return {
        **base,
        "status": "complete",
        "start_date": datetime.combine(start_date, datetime.min.time()),
        "end_date": datetime.combine(end_date, datetime.min.time()),
        "start_price": round(entry_price, 6),
        "end_price": round(end_price, 6),
        "gross_return_pct": round(gross, 4),
        "net_return_pct": round(net, 4),
        "benchmark_return_pct": round(benchmark_return, 4) if benchmark_return is not None else None,
        "excess_return_pct": round(net - benchmark_return, 4) if benchmark_return is not None else None,
        "max_favorable_excursion_pct": round((max(window) / entry_price - 1) * 100, 4),
        "max_adverse_excursion_pct": round((min(window) / entry_price - 1) * 100, 4),
        **_target_stop_measurement(prediction, stock_history, start_date, end_date),
    }


def update_prediction_outcomes(
    db: Session,
    *,
    provider: Any | None = None,
    as_of: date | None = None,
    limit: int | None = None,
) -> dict[str, Any]:
    settings = get_settings()
    bounded_limit = max(1, min(int(limit or settings.validation_update_limit), 1000))
    all_predictions = list(db.scalars(
        select(PredictionRecord)
        .where(PredictionRecord.validation_eligible.is_(True))
        .order_by(PredictionRecord.created_at.asc(), PredictionRecord.id.asc())
    ).all())
    all_ids = [row.id for row in all_predictions]
    all_outcomes = list(db.scalars(
        select(PredictionOutcome).where(PredictionOutcome.prediction_id.in_(all_ids))
    ).all()) if all_ids else []
    outcomes_by_prediction: dict[int, dict[int, PredictionOutcome]] = defaultdict(dict)
    for outcome in all_outcomes:
        outcomes_by_prediction[outcome.prediction_id][outcome.horizon_days] = outcome
    predictions = []
    for prediction in all_predictions:
        expected_days = {int(days) for days in (prediction.horizon_spec or HORIZONS.get(prediction.strategy, {})).values()}
        existing_rows = outcomes_by_prediction.get(prediction.id, {})
        if any(days not in existing_rows or existing_rows[days].status != "complete" for days in expected_days):
            predictions.append(prediction)
        if len(predictions) >= bounded_limit:
            break
    if provider is None:
        from ..providers.yfinance_provider import YFinanceProvider
        provider = YFinanceProvider()

    histories: dict[str, list[dict[str, Any]]] = {}
    errors: list[str] = []
    completed = pending = created = updated = 0

    def history(symbol: str) -> list[dict[str, Any]]:
        if symbol not in histories:
            try:
                histories[symbol] = provider.price_history(symbol, period="5y")
            except Exception as exc:
                histories[symbol] = []
                errors.append(f"{symbol} price history unavailable: {type(exc).__name__}")
        return histories[symbol]

    for prediction in predictions:
        existing = outcomes_by_prediction.get(prediction.id, {})
        for label, days in (prediction.horizon_spec or HORIZONS.get(prediction.strategy, {})).items():
            row = existing.get(int(days))
            if row and row.status == "complete":
                completed += 1
                continue
            result = calculate_forward_outcome(
                prediction,
                str(label),
                int(days),
                history(prediction.symbol),
                history(prediction.benchmark_symbol),
                as_of=as_of,
                estimated_cost_pct=settings.validation_round_trip_cost_pct,
                price_source=getattr(provider, "name", type(provider).__name__),
            )
            if row is None:
                row = PredictionOutcome(prediction_id=prediction.id, horizon_label=str(label), horizon_days=int(days))
                db.add(row)
                created += 1
            else:
                updated += 1
            for key, value in result.items():
                setattr(row, key, value)
            if row.status == "complete":
                completed += 1
            else:
                pending += 1
    db.commit()
    return {
        "predictions_checked": len(predictions),
        "outcomes_created": created,
        "outcomes_updated": updated,
        "complete": completed,
        "pending": pending,
        "errors": list(dict.fromkeys(errors)),
        "as_of": as_of.isoformat() if as_of else None,
        "random_split_used": False,
    }


def _success(prediction: PredictionRecord, outcome: PredictionOutcome) -> bool | None:
    value = outcome.excess_return_pct if prediction.strategy == "long_term" else outcome.net_return_pct
    if value is None:
        return None
    if prediction.signal in POSITIVE_SIGNALS.get(prediction.strategy, set()):
        return value > 0
    if prediction.signal in NEGATIVE_SIGNALS.get(prediction.strategy, set()):
        return value < 0
    return None


def _aggregate(rows: list[tuple[PredictionRecord, PredictionOutcome]]) -> dict[str, Any]:
    evaluable: list[tuple[PredictionRecord, PredictionOutcome, bool]] = []
    for prediction, outcome in rows:
        success = _success(prediction, outcome)
        if outcome.status == "complete" and success is not None:
            evaluable.append((prediction, outcome, success))
    positive = [item for item in evaluable if item[0].actionable and item[0].signal in POSITIVE_SIGNALS.get(item[0].strategy, set())]
    calibrated = [item for item in evaluable if item[0].model_probability is not None]
    returns = [item[1].net_return_pct for item in evaluable if item[1].net_return_pct is not None]
    gains = sum(value for value in returns if value > 0)
    losses = abs(sum(value for value in returns if value < 0))
    brier = None
    if calibrated:
        brier = sum((float(p.model_probability) - (1.0 if success else 0.0)) ** 2 for p, _, success in calibrated) / len(calibrated)
    return {
        "completed": len(rows),
        "evaluable": len(evaluable),
        "positive_signals": len(positive),
        "precision": round(sum(1 for _, _, success in positive if success) / len(positive), 4) if positive else None,
        "win_rate": round(sum(1 for _, _, success in evaluable if success) / len(evaluable), 4) if evaluable else None,
        "average_net_return_pct": round(sum(returns) / len(returns), 4) if returns else None,
        "average_excess_return_pct": round(sum(o.excess_return_pct for _, o, _ in evaluable if o.excess_return_pct is not None) / len([1 for _, o, _ in evaluable if o.excess_return_pct is not None]), 4) if any(o.excess_return_pct is not None for _, o, _ in evaluable) else None,
        "profit_factor": round(gains / losses, 4) if losses else (None if not gains else "infinite"),
        "worst_adverse_excursion_pct": min((o.max_adverse_excursion_pct for _, o, _ in evaluable if o.max_adverse_excursion_pct is not None), default=None),
        "brier_score": round(brier, 4) if brier is not None else None,
        "calibrated_probabilities": len(calibrated),
    }


def _context_bucket(prediction: PredictionRecord, key: str, fallback: str = "UNKNOWN") -> str:
    snapshot = prediction.input_snapshot or {}
    context = snapshot.get(key) or {}
    value = context.get("regime") if key == "market_regime" else context.get("label")
    return str(value or fallback)


def _forensic_bucket(prediction: PredictionRecord) -> str:
    flags = (prediction.input_snapshot or {}).get("forensic_flags") or []
    if any(flag.get("severity") == "high" for flag in flags if isinstance(flag, dict)):
        return "HIGH_RISK"
    if any(flag.get("severity") == "medium" for flag in flags if isinstance(flag, dict)):
        return "MEDIUM_RISK"
    return "NO_HIGH_MEDIUM_FLAG"


def _sector_bucket(prediction: PredictionRecord) -> str:
    return str((prediction.input_snapshot or {}).get("sector") or "UNKNOWN")


def _breadth_bucket(prediction: PredictionRecord) -> str:
    return str(((prediction.input_snapshot or {}).get("market_breadth") or {}).get("state") or "UNKNOWN")


def validation_metrics(
    db: Session,
    *,
    strategy: str | None = None,
    model_version: str | None = None,
    symbol: str | None = None,
    eligible_only: bool = True,
) -> dict[str, Any]:
    prediction_query = select(PredictionRecord)
    if strategy:
        prediction_query = prediction_query.where(PredictionRecord.strategy == strategy)
    if model_version:
        prediction_query = prediction_query.where(PredictionRecord.model_version == model_version)
    if symbol:
        prediction_query = prediction_query.where(PredictionRecord.symbol == symbol.upper())
    if eligible_only:
        prediction_query = prediction_query.where(PredictionRecord.validation_eligible.is_(True))
    predictions = list(db.scalars(prediction_query).all())
    ids = [row.id for row in predictions]
    outcomes: list[PredictionOutcome] = []
    if ids:
        outcomes = list(db.scalars(select(PredictionOutcome).where(PredictionOutcome.prediction_id.in_(ids))).all())
    prediction_by_id = {row.id: row for row in predictions}
    complete_rows = [(prediction_by_id[row.prediction_id], row) for row in outcomes if row.status == "complete"]
    grouped: dict[int, list[tuple[PredictionRecord, PredictionOutcome]]] = defaultdict(list)
    regimes: dict[str, list[tuple[PredictionRecord, PredictionOutcome]]] = defaultdict(list)
    strengths: dict[str, list[tuple[PredictionRecord, PredictionOutcome]]] = defaultdict(list)
    forensic: dict[str, list[tuple[PredictionRecord, PredictionOutcome]]] = defaultdict(list)
    sectors: dict[str, list[tuple[PredictionRecord, PredictionOutcome]]] = defaultdict(list)
    breadth: dict[str, list[tuple[PredictionRecord, PredictionOutcome]]] = defaultdict(list)
    for pair in complete_rows:
        grouped[pair[1].horizon_days].append(pair)
        regimes[_context_bucket(pair[0], "market_regime")].append(pair)
        strengths[_context_bucket(pair[0], "relative_strength")].append(pair)
        forensic[_forensic_bucket(pair[0])].append(pair)
        sectors[_sector_bucket(pair[0])].append(pair)
        breadth[_breadth_bucket(pair[0])].append(pair)
    return {
        "filters": {"strategy": strategy, "model_version": model_version, "symbol": symbol.upper() if symbol else None, "eligible_only": eligible_only},
        "prediction_count": len(predictions),
        "actionable_count": sum(1 for row in predictions if row.actionable),
        "coverage": round(sum(1 for row in predictions if row.actionable) / len(predictions), 4) if predictions else None,
        "pending_outcomes": sum(1 for row in outcomes if row.status != "complete"),
        "overall": _aggregate(complete_rows),
        "by_horizon": {str(days): _aggregate(rows) for days, rows in sorted(grouped.items())},
        "by_market_regime": {key: _aggregate(rows) for key, rows in sorted(regimes.items())},
        "by_relative_strength": {key: _aggregate(rows) for key, rows in sorted(strengths.items())},
        "by_forensic_risk": {key: _aggregate(rows) for key, rows in sorted(forensic.items())},
        "by_sector": {key: _aggregate(rows) for key, rows in sorted(sectors.items())},
        "by_market_breadth": {key: _aggregate(rows) for key, rows in sorted(breadth.items())},
        "probability_note": "model_probability remains null until prospective outcomes support calibration",
        "success_definition": {"swing": "net return after estimated costs is positive", "long_term": "net return exceeds the configured benchmark"},
    }


def build_walk_forward_splits(
    items: list[dict[str, Any]],
    *,
    min_train_size: int = 30,
    test_size: int = 10,
    gap_size: int = 5,
) -> list[dict[str, Any]]:
    ordered = sorted(items, key=lambda item: (str(item.get("created_at") or ""), int(item.get("id") or 0)))
    min_train = max(1, int(min_train_size))
    test = max(1, int(test_size))
    gap = max(0, int(gap_size))
    splits: list[dict[str, Any]] = []
    train_end = min_train
    while train_end + gap < len(ordered):
        test_start = train_end + gap
        test_end = min(test_start + test, len(ordered))
        training = ordered[:train_end]
        testing = ordered[test_start:test_end]
        if not testing:
            break
        splits.append({
            "fold": len(splits) + 1,
            "train_ids": [item.get("id") for item in training],
            "gap_ids": [item.get("id") for item in ordered[train_end:test_start]],
            "test_ids": [item.get("id") for item in testing],
            "train_end": training[-1].get("created_at"),
            "test_start": testing[0].get("created_at"),
            "test_end": testing[-1].get("created_at"),
        })
        train_end += test
    return splits


def walk_forward_plan(
    db: Session,
    *,
    strategy: str,
    horizon_days: int,
    model_version: str | None = None,
    min_train_size: int = 30,
    test_size: int = 10,
    gap_size: int = 5,
) -> dict[str, Any]:
    query = select(PredictionRecord).join(PredictionOutcome).where(
        PredictionRecord.strategy == strategy,
        PredictionRecord.validation_eligible.is_(True),
        PredictionOutcome.horizon_days == int(horizon_days),
        PredictionOutcome.status == "complete",
    )
    if model_version:
        query = query.where(PredictionRecord.model_version == model_version)
    rows = list(db.scalars(query.order_by(PredictionRecord.created_at.asc(), PredictionRecord.id.asc())).all())
    items = [{"id": row.id, "created_at": row.created_at.isoformat()} for row in rows]
    return {
        "strategy": strategy,
        "horizon_days": int(horizon_days),
        "model_version": model_version,
        "completed_records": len(items),
        "method": "expanding-window walk-forward with a purged time gap",
        "random_split_used": False,
        "splits": build_walk_forward_splits(items, min_train_size=min_train_size, test_size=test_size, gap_size=gap_size),
    }


def prediction_payload(row: PredictionRecord) -> dict[str, Any]:
    return {
        "id": row.id,
        "created_at": row.created_at.isoformat(),
        "symbol": row.symbol,
        "strategy": row.strategy,
        "model_version": row.model_version,
        "model_frozen": row.model_frozen,
        "signal": row.signal,
        "actionable": row.actionable,
        "validation_eligible": row.validation_eligible,
        "entry_price": row.entry_price,
        "benchmark_symbol": row.benchmark_symbol,
        "confidence": {
            "data_quality": row.data_quality_confidence,
            "model_probability": row.model_probability,
            "decision": row.decision_confidence,
        },
        "horizons": row.horizon_spec,
        "snapshot_id": row.snapshot_id,
    }


def outcome_payload(row: PredictionOutcome) -> dict[str, Any]:
    return {
        "id": row.id,
        "prediction_id": row.prediction_id,
        "horizon": {"label": row.horizon_label, "trading_days": row.horizon_days},
        "status": row.status,
        "evaluated_at": row.evaluated_at.isoformat() if row.evaluated_at else None,
        "start_date": row.start_date.isoformat() if row.start_date else None,
        "end_date": row.end_date.isoformat() if row.end_date else None,
        "start_price": row.start_price,
        "end_price": row.end_price,
        "gross_return_pct": row.gross_return_pct,
        "estimated_cost_pct": row.estimated_cost_pct,
        "net_return_pct": row.net_return_pct,
        "benchmark_return_pct": row.benchmark_return_pct,
        "excess_return_pct": row.excess_return_pct,
        "max_favorable_excursion_pct": row.max_favorable_excursion_pct,
        "max_adverse_excursion_pct": row.max_adverse_excursion_pct,
        "swing_target_stop": {
            "target_price": row.target_price,
            "stop_price": row.stop_price,
            "status": row.target_stop_status,
            "note": "Daily bars cannot establish the order when target and stop were both touched in one session.",
        },
        "price_source": row.price_source,
        "error": row.error,
    }
