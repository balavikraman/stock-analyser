from __future__ import annotations

import io
import re
import zipfile
from dataclasses import dataclass
from datetime import date, datetime
from typing import Any
from xml.etree import ElementTree as ET


# Conservative tag aliases. We match normalized XBRL element local names, not free text.
# Unsupported concepts remain unavailable until explicitly mapped and tested.
CONCEPT_ALIASES: dict[str, tuple[str, ...]] = {
    "revenue": (
        "revenuefromoperations",
        "incomefromoperations",
        "revenuefromsaleofproductsandrenderingofservices",
    ),
    "total_income": ("totalincome",),
    "net_profit": (
        "profitlossforperiod",
        "profitaftertax",
        "netprofitlossforperiod",
        "profitlossfortheperiod",
    ),
    "eps": (
        "basicearningslosspershare",
        "basicearningspershare",
        "earningspersharebasic",
    ),
    "diluted_eps": (
        "dilutedearningslosspershare",
        "dilutedearningspershare",
        "earningspersharediluted",
    ),
    "finance_cost": ("financecost", "financecosts"),
    "tax_expense": ("taxexpense", "taxexpenses"),
    "promoter_holding": (
        "shareholdingasapercentageoftotalnumberofsharespromoterandpromotergroup",
        "promoterandpromotergroupshareholdingpercentage",
        "percentageofsharesheldbypromoterandpromotergroup",
    ),
    "public_holding": (
        "shareholdingasapercentageoftotalnumberofsharespublic",
        "publicshareholdingpercentage",
        "percentageofsharesheldbypublic",
    ),
    "promoter_pledge": (
        "percentageofsharespledgedorotherwiseencumberedbypromoterandpromotergroup",
        "promoterpledgepercentage",
        "promotersharespledgedpercentage",
    ),
}


def _local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1].split(":")[-1]


def _norm(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", value.lower())


def _number(text: str | None, scale: str | None = None, sign: str | None = None) -> float | None:
    if text is None:
        return None
    raw = text.strip().replace(",", "")
    if not raw or raw.lower() in {"nil", "nan", "na", "n/a", "-", "--"}:
        return None
    if raw.startswith("(") and raw.endswith(")"):
        raw = "-" + raw[1:-1]
    try:
        value = float(raw)
    except ValueError:
        return None
    if sign == "-":
        value = -abs(value)
    if scale:
        try:
            value *= 10 ** int(scale)
        except (TypeError, ValueError, OverflowError):
            return None
    return value


def _parse_date(value: str | None) -> date | None:
    if not value:
        return None
    text = value.strip()[:10]
    try:
        return datetime.strptime(text, "%Y-%m-%d").date()
    except ValueError:
        return None


@dataclass(frozen=True)
class ContextInfo:
    context_id: str
    start: date | None = None
    end: date | None = None
    instant: date | None = None
    dimensions: tuple[str, ...] = ()

    @property
    def period_end(self) -> date | None:
        return self.instant or self.end

    @property
    def is_dimension_free(self) -> bool:
        return not self.dimensions


def _extract_xml_bytes(payload: bytes, max_uncompressed_bytes: int = 20_000_000) -> bytes:
    if payload.startswith(b"PK"):
        with zipfile.ZipFile(io.BytesIO(payload)) as archive:
            candidates = [i for i in archive.infolist() if not i.is_dir() and i.filename.lower().endswith((".xml", ".xbrl", ".html", ".xhtml"))]
            if not candidates:
                raise ValueError("ZIP contains no XML/XBRL document")
            candidates.sort(key=lambda i: (0 if i.filename.lower().endswith((".xml", ".xbrl")) else 1, i.file_size))
            item = candidates[0]
            if item.file_size > max_uncompressed_bytes:
                raise ValueError("XBRL document exceeds safe uncompressed size")
            return archive.read(item)
    if len(payload) > max_uncompressed_bytes:
        raise ValueError("XBRL document exceeds safe size")
    return payload


def _contexts(root: ET.Element) -> dict[str, ContextInfo]:
    out: dict[str, ContextInfo] = {}
    for node in root.iter():
        if _local(node.tag).lower() != "context":
            continue
        context_id = node.attrib.get("id")
        if not context_id:
            continue
        start = end = instant = None
        dimensions: list[str] = []
        for child in node.iter():
            name = _local(child.tag).lower()
            if name == "startdate":
                start = _parse_date(child.text)
            elif name == "enddate":
                end = _parse_date(child.text)
            elif name == "instant":
                instant = _parse_date(child.text)
            elif name in {"explicitmember", "typedmember"}:
                dim = child.attrib.get("dimension") or "dimension"
                member = (child.text or "").strip()
                dimensions.append(f"{dim}={member}" if member else dim)
        out[context_id] = ContextInfo(context_id, start, end, instant, tuple(sorted(dimensions)))
    return out


def _units(root: ET.Element) -> dict[str, str]:
    out: dict[str, str] = {}
    for node in root.iter():
        if _local(node.tag).lower() != "unit":
            continue
        unit_id = node.attrib.get("id")
        if not unit_id:
            continue
        measures = [(child.text or "").strip() for child in node.iter() if _local(child.tag).lower() == "measure" and (child.text or "").strip()]
        if measures:
            out[unit_id] = " * ".join(measures)
    return out


def _canonical_for(local_name: str) -> str | None:
    normalized = _norm(local_name)
    for canonical, aliases in CONCEPT_ALIASES.items():
        if normalized in aliases:
            return canonical
    return None


def parse_xbrl_bytes(payload: bytes) -> dict[str, Any]:
    """Parse explicit numeric XBRL concepts and select only unambiguous latest facts.

    The function does not infer column order, units, standalone/consolidated status, or
    convert currencies. All candidates retain their source concept/context for audit.
    """
    xml_bytes = _extract_xml_bytes(payload)
    try:
        root = ET.fromstring(xml_bytes)
    except ET.ParseError as exc:
        raise ValueError("Invalid XML/XBRL document") from exc

    contexts = _contexts(root)
    units = _units(root)
    candidates: dict[str, list[dict[str, Any]]] = {}

    for node in root.iter():
        context_ref = node.attrib.get("contextRef") or node.attrib.get("contextref")
        if not context_ref:
            continue
        canonical = _canonical_for(_local(node.tag))
        if not canonical:
            continue
        value = _number(node.text, node.attrib.get("scale"), node.attrib.get("sign"))
        if value is None:
            continue
        context = contexts.get(context_ref, ContextInfo(context_ref))
        unit_ref = node.attrib.get("unitRef") or node.attrib.get("unitref")
        candidates.setdefault(canonical, []).append({
            "value": value,
            "concept": _local(node.tag),
            "context_id": context_ref,
            "period_start": context.start.isoformat() if context.start else None,
            "period_end": context.period_end.isoformat() if context.period_end else None,
            "dimensions": list(context.dimensions),
            "dimension_free": context.is_dimension_free,
            "unit": units.get(unit_ref, unit_ref),
            "decimals": node.attrib.get("decimals"),
        })

    selected: dict[str, dict[str, Any]] = {}
    ambiguities: list[dict[str, Any]] = []

    for canonical, rows in candidates.items():
        dated = [r for r in rows if r.get("period_end")]
        latest_period = max((r["period_end"] for r in dated), default=None)
        pool = [r for r in rows if r.get("period_end") == latest_period] if latest_period else list(rows)
        dimension_free = [r for r in pool if r.get("dimension_free")]
        if dimension_free:
            pool = dimension_free

        # Collapse exact duplicates, but never silently choose conflicting values/units.
        unique: dict[tuple[Any, Any], dict[str, Any]] = {}
        for row in pool:
            unique[(round(float(row["value"]), 10), row.get("unit"))] = row
        if len(unique) == 1:
            selected[canonical] = next(iter(unique.values()))
        elif len(unique) > 1:
            ambiguities.append({
                "metric": canonical,
                "period_end": latest_period,
                "reason": "conflicting XBRL facts for latest comparable context",
                "candidates": list(unique.values()),
            })

    return {
        "facts": selected,
        "ambiguities": ambiguities,
        "candidate_counts": {key: len(value) for key, value in candidates.items()},
        "context_count": len(contexts),
        "unit_count": len(units),
    }
