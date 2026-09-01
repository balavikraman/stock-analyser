from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from ..config import get_settings
from ..providers.demo import DemoProvider
from ..scoring import combine_scores, fundamental_score, governance_score, valuation_score
from ..schemas import AnalysisReport, ScoreComponent
from ..technical import analyze_technicals
from ..valuation import build_entry_plan, build_scenarios
from .financials import enrich_quarterlies, forensic_checks
from .news import classify_news, research_score


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
            if self.settings.data_provider.lower() == "auto":
                provider = DemoProvider()
                source_errors.append(f"Live provider failed: {type(exc).__name__}. Demo fallback used.")
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
        verdict, summary = self._verdict(combined["score"], combined["confidence"], valuation.get("score"), technical.get("score"))
        score_models = {
            "fundamental": ScoreComponent(score=fundamental.get("score"), confidence=fundamental.get("confidence", 0), label="Business & financial strength", explanation="Profitability, growth, leverage and cash conversion."),
            "valuation": ScoreComponent(score=valuation.get("score"), confidence=valuation.get("confidence", 0), label="Valuation", explanation="How much you pay for earnings/assets/cash flow, adjusted by sector."),
            "technical": ScoreComponent(score=technical.get("score"), confidence=technical.get("confidence", 0), label="Entry timing", explanation="Trend, moving averages, RSI, momentum, drawdown and support context."),
            "governance": ScoreComponent(score=governance.get("score"), confidence=governance.get("confidence", 0), label="Governance", explanation="Missing governance evidence lowers confidence instead of being guessed."),
            "research": ScoreComponent(score=research.get("score"), confidence=research.get("confidence", 0), label="Current news & external context", explanation=research.get("explanation", "")),
        }
        risks = self._risks(metrics, technical, classified_news, source_errors) + [f["message"] for f in forensic["flags"] if f["severity"] in ("high", "medium")]
        return AnalysisReport(symbol=symbol, company_name=metrics.get("company_name") or symbol, sector=metrics.get("sector"), industry=metrics.get("industry"), as_of=datetime.now(timezone.utc), price=metrics.get("price"), currency=metrics.get("currency") or "INR", scores=score_models, overall_score=combined["score"], overall_confidence=combined["confidence"], verdict=verdict, action_summary=summary, metrics=metrics, annuals=annuals, quarterlies=quarterlies, technicals=technical, price_history=history[-500:], entry_plan=entry, scenarios=scenarios, news=classified_news, risks=risks, catalysts=self._catalysts(metrics, fundamental, classified_news), data_quality={"provider": provider.name, "live_data": provider.name != "demo", "fundamental_confidence": fundamental.get("confidence"), "valuation_confidence": valuation.get("confidence"), "technical_confidence": technical.get("confidence"), "research_confidence": research.get("confidence"), "source_warnings": source_errors, "forensic_score": forensic["score"], "forensic_flags": forensic["flags"]}, disclaimers=["Decision-support tool, not a profit guarantee or personalized regulated investment advice.", "Low-confidence or missing data must be reviewed before capital is committed.", "Entry zones are risk-management ranges, not predictions of exact bottoms or tops."])

    @staticmethod
    def _verdict(score: float | None, conf: float, valuation: float | None, technical: float | None) -> tuple[str, str]:
        if score is None or conf < 0.45: return "INSUFFICIENT DATA", "Do not act yet; collect higher-quality data first."
        if score >= 82 and (valuation or 0) >= 65: return "ACCUMULATE", "Strong overall setup; build the position in stages rather than all at once."
        if score >= 72: return "WATCH / SELECTIVE ENTRY", "Good business setup, but wait for valuation or timing to improve before aggressive buying."
        if score >= 60: return "HOLD / RESEARCH", "Mixed setup. Existing holders should review thesis; new capital needs a clearer edge."
        return "AVOID / REASSESS", "Risk, valuation or business quality is not strong enough for a new long-term position."

    @staticmethod
    def _risks(metrics: dict[str, Any], technical: dict[str, Any], news: list[dict[str, Any]], errors: list[str]) -> list[str]:
        out = list(errors)
        if isinstance(metrics.get("debt_to_equity"), (int, float)) and metrics["debt_to_equity"] > 1: out.append("Leverage is elevated relative to equity.")
        if isinstance(technical.get("rsi14"), (int, float)) and technical["rsi14"] > 72: out.append("Price momentum is overextended; chasing increases entry risk.")
        if any(n.get("classification") == "structural_negative" for n in news): out.append("Current news contains a potentially structural negative that needs manual verification.")
        if not out: out.append("No major automated red flag detected, but governance and industry-specific risks still require review.")
        return out[:8]

    @staticmethod
    def _catalysts(metrics: dict[str, Any], fundamental: dict[str, Any], news: list[dict[str, Any]]) -> list[str]:
        out = []
        growth = fundamental.get("growth", {})
        if isinstance(growth.get("profit_cagr"), (int, float)) and growth["profit_cagr"] > 10: out.append("Multi-year profit growth remains supportive if it persists.")
        if any(n.get("classification") == "structural_positive" for n in news): out.append("Current news contains a potentially structural positive catalyst.")
        if isinstance(metrics.get("dividend_yield"), (int, float)) and metrics["dividend_yield"] >= 3: out.append("Dividend yield provides some return while waiting for rerating.")
        return out or ["No high-confidence catalyst identified automatically; deeper company/industry research required."]
