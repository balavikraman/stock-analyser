from __future__ import annotations

from typing import Any


def alert_status(settings: Any) -> dict[str, Any]:
    configured = bool(settings.telegram_bot_token and settings.telegram_chat_id)
    return {
        "provider": "telegram",
        "configured": configured,
        "enabled": bool(configured and settings.telegram_alerts_enabled),
        "delivery": "research-only",
        "min_actionable_confidence": settings.telegram_min_actionable_confidence,
        "reason": None if configured else "Set TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID in your local .env to enable optional research alerts.",
    }


def build_research_alert(report: dict[str, Any], min_confidence: float) -> dict[str, Any]:
    """Build, but never send, a conservative alert candidate from an analysis."""
    quality = report.get("data_quality") or {}
    actionable = bool(quality.get("actionable"))
    confidence = float(report.get("overall_confidence") or 0)
    if not actionable:
        return {"eligible": False, "reason": "Report is not actionable; research alert suppressed."}
    if confidence < min_confidence:
        return {"eligible": False, "reason": f"Evidence confidence is below the {min_confidence:.0%} alert threshold."}
    text = "\n".join([
        "Stock Analyzer — research alert only",
        f"{report.get('symbol')} · {report.get('verdict')}",
        f"Evidence confidence: {confidence:.0%}",
        f"Market regime: {(quality.get('market_regime') or {}).get('regime', 'UNKNOWN')}",
        "Review the full report before making any decision. No order is placed by this app.",
    ])
    return {"eligible": True, "text": text}
