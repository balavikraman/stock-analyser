from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from ..config import get_settings
from ..evidence import EvidenceRecord, actionable_gate, summarize_evidence, utc_now_iso
from ..providers.demo import DemoProvider
from ..scoring import combine_scores, fundamental_score, governance_score, valuation_score
from ..schemas import AnalysisReport, ScoreComponent
from ..technical import analyze_technicals
from ..valuation import build_entry_plan, build_scenarios
from .financials import enrich_quarterlies, forensic_checks
from .news import classify_news, research_score
from .official_evidence import fetch_official_evidence
from .official_validation import assess_official_bundle, official_action_blocks


class StockAnalyzer:
    def __init__(self) -> None:
        self.settings = get_settings()

    def _provider(self):
        if self.settings.data_provider.lower() == "demo":
            return DemoProvider()
        from ..providers.yfinance_provider import YFinanceProvider
        return YFinanceProvider()

    def analyze(self, symbol: str) -> AnalysisReport:
        symbol = symbol.strip().upper()
        if not symbol:
            raise ValueError("symbol required")
        source_errors: list[str] = []
        try:
            provider = self._provider()
            metrics = provider.company_snapshot(symbol)
            history = provider.price_history(symbol)
            annuals = provider.annual_financials(symbol)
            quarterlies = enrich_quarterlies(provider.quarterly_financials(symbol))
            news = provider.news(symbol, metrics.get("company_name") or symbol)
        except Exception as exc:
            if self.settings.data_provider.lower() == "auto" and not self.settings.production_like:
                provider = DemoProvider()
                source_errors.append(f"Live provider failed: {type(exc).__name__}. Demo fallback used for testing only.")
                metrics = provider.company_snapshot(symbol)
                history = provider.price_history(symbol)
                annuals = provider.annual_financials(symbol)
                quarterlies = enrich_quarterlies(provider.quarterly_financials(symbol))
                news = provider.news(symbol, metrics.get("company_name") or symbol)
            else:
                raise

        if history and not metrics.get("price"):
            metrics["price"] = history[-1].get("close")
        if metrics.get("market_cap") and metrics.get("fcf"):
            metrics["fcf_yield"] = round(float(metrics["fcf"]) / float(metrics["market_cap"]) * 100, 2)

        official_bundle: dict[str, Any] | None = None
        official_assessment: dict[str, Any] = {
            "summary": {"available": False, "errors": []},
            "facts": {},
            "mismatches": [],
            "high_mismatch_count": 0,
            "medium_mismatch_count": 0,
            "verified": False,
        }
        if provider.name != "demo" and self.settings.official_evidence_enabled:
            official_bundle = fetch_official_evidence(symbol)
            official_assessment = assess_official_bundle(official_bundle, metrics)
            source_errors.extend([f"Official evidence: {error}" for error in official_bundle.get("errors", [])])

        forensic = forensic_checks(annuals, metrics)
        technical = analyze_technicals(history)
        fundamental = fundamental_score(metrics, annuals, metrics.get("sector"))
        metrics.update(fundamental.get("growth", {}))
        valuation = valuation_score(metrics, metrics.get("sector"))
        governance = governance_score(metrics)
        classified_news = classify_news(news)
        research = research_score(classified_news)
        combined = combine_scores({"fundamental": fundamental, "valuation": valuation, "technical": technical, "governance": governance, "research": research})
        scenarios = build_scenarios(metrics, fundamental.get("growth", {}))
        entry = build_entry_plan(metrics.get("price"), technical, scenarios, combined["confidence"])

        evidence = self._build_evidence(provider.name, metrics, history, annuals, quarterlies, classified_news)
        if official_bundle:
            evidence.update(official_bundle.get("evidence") or {})
        evidence_summary = summarize_evidence(evidence)
        gate = actionable_gate(
            live_data=provider.name != "demo",
            overall_confidence=combined["confidence"],
            evidence_summary=evidence_summary,
            strict_mode=self.settings.production_like,
            min_confidence=self.settings.min_actionable_confidence,
        )
        official_blocks = official_action_blocks(official_assessment, required=self.settings.require_official_evidence and provider.name != "demo")
        if official_blocks:
            gate = {"actionable": False, "reasons": list(dict.fromkeys(list(gate["reasons"]) + official_blocks))}

        verdict, summary = self._verdict(combined["score"], combined["confidence"], valuation.get("score"), technical.get("score"))
        if not gate["actionable"]:
            verdict = "RESEARCH ONLY / NOT ACTIONABLE"
            summary = "Do not commit capital from this report yet. " + "; ".join(gate["reasons"])
            entry = dict(entry)
            entry["status"] = "BLOCKED — EVIDENCE REVIEW REQUIRED"
            entry["actionable"] = False
            entry["block_reasons"] = gate["reasons"]
        else:
            entry = dict(entry)
            entry["actionable"] = True

        score_models = {
            "fundamental": ScoreComponent(score=fundamental.get("score"), confidence=fundamental.get("confidence", 0), label="Business & financial strength", explanation="Profitability, growth, leverage and cash conversion."),
            "valuation": ScoreComponent(score=valuation.get("score"), confidence=valuation.get("confidence", 0), label="Valuation", explanation="How much you pay for earnings/assets/cash flow, adjusted by sector."),
            "technical": ScoreComponent(score=technical.get("score"), confidence=technical.get("confidence", 0), label="Entry timing", explanation="Trend, moving averages, RSI, momentum, drawdown and support context."),
            "governance": ScoreComponent(score=governance.get("score"), confidence=governance.get("confidence", 0), label="Governance", explanation="Missing governance evidence lowers confidence instead of being guessed."),
            "research": ScoreComponent(score=research.get("score"), confidence=research.get("confidence", 0), label="Current news & external context", explanation=research.get("explanation", "")),
        }
        mismatch_risks = [item.get("message") for item in official_assessment.get("mismatches", []) if item.get("message")]
        risks = self._risks(metrics, technical, classified_news, source_errors) + mismatch_risks + [f["message"] for f in forensic["flags"] if f["severity"] in ("high", "medium")]
        risks = list(dict.fromkeys(risks))[:10]

        return AnalysisReport(
            symbol=symbol,
            company_name=metrics.get("company_name") or symbol,
            sector=metrics.get("sector"),
            industry=metrics.get("industry"),
            as_of=datetime.now(timezone.utc),
            price=metrics.get("price"),
            currency=metrics.get("currency") or "INR",
            scores=score_models,
            overall_score=combined["score"],
            overall_confidence=combined["confidence"],
            verdict=verdict,
            action_summary=summary,
            metrics=metrics,
            annuals=annuals,
            quarterlies=quarterlies,
            technicals=technical,
            price_history=history[-500:],
            entry_plan=entry,
            scenarios=scenarios,
            news=classified_news,
            risks=risks,
            catalysts=self._catalysts(metrics, fundamental, classified_news),
            data_quality={
                "provider": provider.name,
                "live_data": provider.name != "demo",
                "fundamental_confidence": fundamental.get("confidence"),
                "valuation_confidence": valuation.get("confidence"),
                "technical_confidence": technical.get("confidence"),
                "research_confidence": research.get("confidence"),
                "source_warnings": source_errors,
                "forensic_score": forensic["score"],
                "forensic_flags": forensic["flags"],
                "evidence": evidence,
                "evidence_summary": evidence_summary,
                "official_validation": official_assessment,
                "official_evidence_required": self.settings.require_official_evidence,
                "actionable": gate["actionable"],
                "action_block_reasons": gate["reasons"],
                "strict_mode": self.settings.production_like,
            },
            disclaimers=[
                "Decision-support tool, not a profit guarantee or personalized regulated investment advice.",
                "Low-confidence, stale, demo, missing or materially conflicting official evidence blocks an actionable verdict.",
                "Entry zones are risk-management ranges, not predictions of exact bottoms or tops.",
            ],
        )

    @staticmethod
    def _build_evidence(provider_name: str, metrics: dict[str, Any], history: list[dict[str, Any]], annuals: list[dict[str, Any]], quarterlies: list[dict[str, Any]], news: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
        is_demo = provider_name == "demo"
        source_type = "demo" if is_demo else "aggregator"
        base_conf = 0.0 if is_demo else 0.60
        fetched = utc_now_iso()
        latest_price_date = history[-1].get("date") if history else None
        latest_news_date = next((n.get("published") for n in news if n.get("published")), None)
        latest_annual = annuals[-1].get("period") if annuals else None
        latest_quarter = quarterlies[-1].get("period") if quarterlies else None
        return {
            "price": EvidenceRecord(metrics.get("price"), provider_name, source_type, observed_at=latest_price_date, fetched_at=fetched, confidence=base_conf + (0.20 if not is_demo else 0), stale_after_days=7).to_dict(),
            "company_snapshot": EvidenceRecord({k: metrics.get(k) for k in ("pe", "pb", "roe", "debt_to_equity", "operating_margin", "net_margin")}, provider_name, source_type, fetched_at=fetched, confidence=base_conf).to_dict(),
            "annual_financials": EvidenceRecord(len(annuals), provider_name, source_type, period=latest_annual, fetched_at=fetched, confidence=base_conf).to_dict(),
            "quarterly_financials": EvidenceRecord(len(quarterlies), provider_name, source_type, period=latest_quarter, fetched_at=fetched, confidence=base_conf).to_dict(),
            "news": EvidenceRecord(len(news), provider_name, source_type, observed_at=latest_news_date, fetched_at=fetched, confidence=0.0 if is_demo else 0.45, stale_after_days=14).to_dict(),
        }

    @staticmethod
    def _verdict(score: float | None, conf: float, valuation: float | None, technical: float | None) -> tuple[str, str]:
        if score is None or conf < 0.45:
            return "INSUFFICIENT DATA", "Do not act yet; collect higher-quality data first."
        if score >= 82 and (valuation or 0) >= 65:
            return "ACCUMULATE", "Strong overall setup; build the position in stages rather than all at once."
        if score >= 72:
            return "WATCH / SELECTIVE ENTRY", "Good business setup, but wait for valuation or timing to improve before aggressive buying."
        if score >= 60:
            return "HOLD / RESEARCH", "Mixed setup. Existing holders should review thesis; new capital needs a clearer edge."
        return "AVOID / REASSESS", "Risk, valuation or business quality is not strong enough for a new long-term position."

    @staticmethod
    def _risks(metrics: dict[str, Any], technical: dict[str, Any], news: list[dict[str, Any]], errors: list[str]) -> list[str]:
        out = list(errors)
        if isinstance(metrics.get("debt_to_equity"), (int, float)) and metrics["debt_to_equity"] > 1:
            out.append("Leverage is elevated relative to equity.")
        if isinstance(technical.get("rsi14"), (int, float)) and technical["rsi14"] > 72:
            out.append("Price momentum is overextended; chasing increases entry risk.")
        if any(n.get("classification") == "structural_negative" for n in news):
            out.append("Current news contains a potentially structural negative that needs manual verification.")
        if not out:
            out.append("No major automated red flag detected, but governance and industry-specific risks still require review.")
        return out[:8]

    @staticmethod
    def _catalysts(metrics: dict[str, Any], fundamental: dict[str, Any], news: list[dict[str, Any]]) -> list[str]:
        out = []
        growth = fundamental.get("growth", {})
        if isinstance(growth.get("profit_cagr"), (int, float)) and growth["profit_cagr"] > 10:
            out.append("Multi-year profit growth remains supportive if it persists.")
        if any(n.get("classification") == "structural_positive" for n in news):
            out.append("Current news contains a potentially structural positive catalyst.")
        if isinstance(metrics.get("dividend_yield"), (int, float)) and metrics["dividend_yield"] >= 3:
            out.append("Dividend yield provides some return while waiting for rerating.")
        return out or ["No high-confidence catalyst identified automatically; deeper company/industry research required."]
