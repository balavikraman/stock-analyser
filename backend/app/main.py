from __future__ import annotations

from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import select
from sqlalchemy.orm import Session

from .config import get_settings
from .db import SessionLocal, init_db
from .models import AnalysisSnapshot, JournalEntry
from .portfolio import summarize_holdings
from .providers.zerodha_provider import ZerodhaReadOnly
from .schemas import JournalCreate
from .services.analyzer import StockAnalyzer
from .services.bse_public import discover_bse_filings
from .services.company_ir import discover_ir_documents
from .services.filing_documents import parse_latest_official_documents
from .services.filing_store import persist_filing_bundle, recent_filings
from .services.official_evidence import fetch_official_evidence, official_evidence_summary
from .services.official_facts import extract_structured_facts
from .services.official_validation import assess_official_bundle
from .services.source_registry import registry_payload

settings = get_settings()
app = FastAPI(title="Stock Analyzer", version="0.5.3", docs_url="/api/docs")
STATIC = Path(__file__).resolve().parent / "static"
app.mount("/static", StaticFiles(directory=STATIC), name="static")


def db_session():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@app.on_event("startup")
def startup() -> None:
    init_db()


@app.get("/", response_class=HTMLResponse)
def home() -> str:
    return (STATIC / "index.html").read_text(encoding="utf-8")


@app.get("/api/health")
def health() -> dict:
    return {"status": "ok", "version": "0.5.3", "provider": settings.data_provider, "official_evidence_enabled": settings.official_evidence_enabled, "require_official_evidence": settings.require_official_evidence, "database": "postgresql" if settings.effective_database_url.startswith("postgres") else "sqlite-fallback", "zerodha_configured": ZerodhaReadOnly().configured()}


@app.get("/api/analyze/{symbol}")
def analyze(symbol: str, db: Session = Depends(db_session)):
    try:
        report = StockAnalyzer().analyze(symbol)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Analysis failed: {type(exc).__name__}: {exc}") from exc
    snap = AnalysisSnapshot(symbol=report.symbol, overall_score=report.overall_score, confidence=report.overall_confidence, verdict=report.verdict, payload=report.model_dump(mode="json"))
    db.add(snap); db.commit(); db.refresh(snap)
    payload = report.model_dump(mode="json"); payload["snapshot_id"] = snap.id
    return payload


@app.get("/api/sources")
def sources(sector: str | None = None, include_planned: bool = True):
    return registry_payload(sector, include_planned=include_planned)


@app.get("/api/company-ir/{symbol}")
def company_ir(symbol: str):
    """Discover issuer-hosted public investor-relations documents for one company."""
    try:
        metrics = StockAnalyzer()._provider().company_snapshot(symbol.strip().upper())
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Company metadata provider failed: {type(exc).__name__}: {exc}") from exc
    website = metrics.get("website")
    if not website:
        return {"ok": False, "symbol": symbol.strip().upper(), "company_name": metrics.get("company_name"), "website": None, "documents": [], "pages_scanned": [], "errors": ["issuer website unavailable from normalized provider"]}
    result = discover_ir_documents(str(website))
    result["symbol"] = symbol.strip().upper()
    result["company_name"] = metrics.get("company_name")
    return result


@app.get("/api/bse-filings/{scrip_code}")
def bse_filings(scrip_code: str):
    """Discover public BSE filing links for one six-digit BSE scrip code."""
    return discover_bse_filings(scrip_code)


@app.get("/api/official-filings/{symbol}")
def official_filings(symbol: str, force: bool = False, persist: bool = True, db: Session = Depends(db_session)):
    bundle = fetch_official_evidence(symbol, force=force)
    stored = persist_filing_bundle(db, bundle) if persist else {"created": 0, "existing": 0}
    facts = extract_structured_facts((bundle.get("financial_results") or []) + (bundle.get("shareholding") or []))
    return {"summary": official_evidence_summary(bundle), "facts": facts, "evidence": bundle.get("evidence", {}), "errors": bundle.get("errors", []), "storage": stored}


@app.get("/api/official-xbrl/{symbol}")
def official_xbrl(symbol: str, force: bool = False, db: Session = Depends(db_session)):
    bundle = fetch_official_evidence(symbol, force=force)
    persist_filing_bundle(db, bundle)
    parsed = parse_latest_official_documents(bundle)
    return {"summary": official_evidence_summary(bundle), "parsed": parsed, "errors": bundle.get("errors", [])}


@app.get("/api/official-verify/{symbol}")
def official_verify(symbol: str, force: bool = False):
    try:
        metrics = StockAnalyzer()._provider().company_snapshot(symbol.strip().upper())
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Normalized provider failed: {type(exc).__name__}: {exc}") from exc
    bundle = fetch_official_evidence(symbol, force=force)
    return assess_official_bundle(bundle, metrics)


@app.get("/api/filing-history/{symbol}")
def filing_history(symbol: str, limit: int = 100, db: Session = Depends(db_session)):
    rows = recent_filings(db, symbol, limit)
    return [{"id": r.id, "symbol": r.symbol, "source": r.source, "filing_type": r.filing_type, "source_key": r.source_key, "observed_at": r.observed_at.isoformat() if r.observed_at else None, "fetched_at": r.fetched_at.isoformat(), "period": r.period, "document_url": r.document_url} for r in rows]


@app.get("/api/scan")
def scan(limit: int = 12):
    analyzer = StockAnalyzer(); results = []
    for symbol in settings.watchlist_symbols[: max(1, min(limit, 30))]:
        try:
            r = analyzer.analyze(symbol)
            results.append({"symbol": symbol, "company_name": r.company_name, "score": r.overall_score, "confidence": r.overall_confidence, "verdict": r.verdict, "price": r.price})
        except Exception as exc:
            results.append({"symbol": symbol, "error": type(exc).__name__})
    return sorted(results, key=lambda x: (x.get("score") is not None, x.get("score") or -1), reverse=True)


@app.get("/api/journal")
def journal(db: Session = Depends(db_session)):
    rows = db.scalars(select(JournalEntry).order_by(JournalEntry.created_at.desc()).limit(200)).all()
    return [{"id": r.id, "created_at": r.created_at.isoformat(), "symbol": r.symbol, "action": r.action, "price": r.price, "quantity": r.quantity, "thesis": r.thesis, "thesis_breaker": r.thesis_breaker, "snapshot_id": r.snapshot_id} for r in rows]


@app.post("/api/journal")
def add_journal(entry: JournalCreate, db: Session = Depends(db_session)):
    row = JournalEntry(**entry.model_dump(), symbol=entry.symbol.upper())
    db.add(row); db.commit(); db.refresh(row)
    return {"id": row.id, "created_at": row.created_at.isoformat()}


@app.get("/api/zerodha/status")
def zerodha_status():
    z = ZerodhaReadOnly()
    return {"configured": z.configured(), "login_url_available": bool(z.login_url()) if z.configured() else False}


@app.get("/api/zerodha/login")
def zerodha_login():
    z = ZerodhaReadOnly(); url = z.login_url()
    if not url:
        raise HTTPException(400, "Configure ZERODHA_API_KEY and ZERODHA_API_SECRET in local .env first")
    return RedirectResponse(url)


@app.get("/api/zerodha/callback")
def zerodha_callback(request_token: str):
    try:
        ZerodhaReadOnly().exchange_request_token(request_token)
    except Exception as exc:
        raise HTTPException(400, f"Zerodha login failed: {exc}") from exc
    return RedirectResponse(url="/?zerodha=connected")


@app.get("/api/portfolio")
def portfolio():
    z = ZerodhaReadOnly()
    if not z.configured():
        return {"connected": False, "reason": "Zerodha is not configured", "summary": summarize_holdings([])}
    try:
        holdings = z.holdings(); return {"connected": True, "summary": summarize_holdings(holdings)}
    except Exception as exc:
        return {"connected": False, "reason": f"Login required or token expired: {type(exc).__name__}", "summary": summarize_holdings([])}
