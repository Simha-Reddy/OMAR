from __future__ import annotations

from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional


def _fileman_to_iso(value: Any) -> Optional[str]:
    try:
        text = str(value or "").strip()
        if not text:
            return None
        if "." in text:
            date_part, time_part = text.split(".", 1)
        else:
            date_part, time_part = text, ""
        if len(date_part) != 7 or not date_part.isdigit():
            return None
        year = 1700 + int(date_part[:3])
        month = int(date_part[3:5])
        day = int(date_part[5:7])
        digits = "".join(ch for ch in time_part if ch.isdigit())
        hour = int(digits[0:2]) if len(digits) >= 2 else 0
        minute = int(digits[2:4]) if len(digits) >= 4 else 0
        second = int(digits[4:6]) if len(digits) >= 6 else 0
        stamp = datetime(year, month, day, hour, minute, second, tzinfo=timezone.utc)
        return stamp.isoformat().replace("+00:00", "Z")
    except Exception:
        return None


_VISTA_DT_FORMATS = (
    "%b %d, %Y@%H:%M:%S",
    "%b %d, %Y@%H:%M",
    "%b %d %Y@%H:%M:%S",
    "%b %d %Y@%H:%M",
    "%b %d %Y %H:%M:%S",
    "%b %d %Y %H:%M",
)


def _vista_datetime_to_iso(value: str | None) -> Optional[str]:
    if not value:
        return None
    cleaned = value.strip()
    if not cleaned:
        return None
    cleaned = cleaned.replace("  ", " ")
    cleaned = cleaned.replace("@ ", "@")
    cleaned = cleaned.replace(" @", "@")
    for fmt in _VISTA_DT_FORMATS:
        try:
            stamp = datetime.strptime(cleaned, fmt)
            if stamp.tzinfo is None:
                stamp = stamp.replace(tzinfo=timezone.utc)
            else:
                stamp = stamp.astimezone(timezone.utc)
            return stamp.isoformat().replace("+00:00", "Z")
        except Exception:
            continue
    # Last resort: attempt to parse when value ends with timezone abbreviation we do not support
    try:
        without_suffix = cleaned.split(" ")[:-1]
        if without_suffix:
            guess = " ".join(without_suffix)
            for fmt in _VISTA_DT_FORMATS:
                try:
                    stamp = datetime.strptime(guess, fmt)
                    stamp = stamp.replace(tzinfo=timezone.utc)
                    return stamp.isoformat().replace("+00:00", "Z")
                except Exception:
                    continue
    except Exception:
        pass
    return None


def parse_orwcv_lab(raw: str) -> List[Dict[str, Any]]:
    """Parse ORWCV LAB response into structured panel summaries."""
    items: List[Dict[str, Any]] = []
    for line in str(raw or "").splitlines():
        parts = [segment.strip() for segment in line.split("^")]
        if len(parts) < 4 or not parts[0]:
            continue
        lab_id = parts[0]
        name = parts[1]
        fm_ts = parts[2]
        status = parts[3]
        iso = _fileman_to_iso(fm_ts)
        item: Dict[str, Any] = {
            "id": lab_id,
            "labId": lab_id,
            "displayName": name,
            "name": name,
            "status": status,
            "statusName": status.title() if status else "",
            "result": status or fm_ts,
            "resulted": iso,
            "observed": iso,
            "filemanTimestamp": fm_ts,
        }
        items.append(item)
    # Sort descending by resulted when present
    items.sort(key=lambda it: it.get("resulted") or "", reverse=True)
    return items


def parse_orwor_result(raw: str) -> Dict[str, Any]:
    """Parse ORWOR RESULT response for a single panel."""
    out: Dict[str, Any] = {"panel": "", "tests": []}
    if not raw:
        return out
    lines = [ln.rstrip() for ln in str(raw).splitlines() if ln and ln.strip()]

    import re

    for ln in lines[:15]:
        low = ln.lower()
        if "panel:" in low:
            out["panel"] = ln.split(":", 1)[1].strip()
        elif re.search(r"collect(ed|ion)", low) and ":" in ln:
            value = ln.split(":", 1)[1].strip()
            out["collected"] = value
            out["collectedIso"] = _vista_datetime_to_iso(value)
        elif ("result" in low or "reported" in low) and ":" in ln:
            value = ln.split(":", 1)[1].strip()
            out["resulted"] = value
            out["resultedIso"] = _vista_datetime_to_iso(value)
        elif "specimen" in low and ":" in ln:
            out["specimen"] = ln.split(":", 1)[1].strip()

    def _strip_range(seg: str) -> str:
        return re.sub(r"\([^)]*\)\s*$", "", seg or "").strip()

    def _extract_range(seg: str) -> Optional[str]:
        m = re.search(r"\(([^(]*)\)\s*$", seg or "")
        if m:
            return m.group(1).strip()
        return None

    def _normalize_flag(value: Optional[str]) -> Optional[str]:
        if not value:
            return None
        flag = value.strip().upper()
        if flag in {">", ">>"}:
            return "H"
        if flag in {"<", "<<"}:
            return "L"
        if "CRIT" in flag:
            return "CRIT"
        if flag in {"H", "HH", "HIGH"}:
            return "H"
        if flag in {"L", "LL", "LOW"}:
            return "L"
        return flag or None

    last_rec: Optional[Dict[str, Any]] = None

    def _ensure_iso(record: Dict[str, Any]) -> None:
        if "resultedIso" not in out:
            out["resultedIso"] = record.get("resulted")

    for ln in lines:
        low = ln.lower()
        if low.startswith("comment") or low.startswith("provider"):
            break
        if not ln.strip() or re.fullmatch(r"[-=]{3,}", ln.strip()):
            continue
        # Pattern: NAME: RESULT UNIT (RANGE) FLAG
        m = re.match(r"^([^:]{2,}?):\s*(\S+)\s*([^()\s]+)?\s*(\([^)]*\))?\s*([A-Z*<>]{0,4})\s*$", ln)
        if m:
            name = m.group(1).strip()
            result = m.group(2).strip()
            unit = (m.group(3) or "").strip() or None
            ref = _extract_range(m.group(4) or "")
            flag = _normalize_flag(m.group(5))
            rec = {
                "test": name,
                "result": result,
                "unit": unit,
                "referenceRange": ref,
                "flag": flag,
            }
            rec["abnormal"] = bool(flag in {"H", "L", "CRIT"})
            out["tests"].append(rec)
            last_rec = rec
            _ensure_iso(rec)
            continue
        # Pattern with columns separated by two spaces
        parts = re.split(r"\s{2,}", ln.strip())
        if len(parts) >= 2:
            name = parts[0].strip(": ")
            rest = parts[1:]
            joined = "  ".join(rest)
            ref = _extract_range(joined)
            clean = _strip_range(joined)
            tokens = clean.split()
            if not tokens:
                continue
            result = tokens[0]
            unit = None
            flag = None
            for tok in tokens[1:]:
                up = tok.upper()
                if up in {"H", "HH", "L", "LL", "CRIT", ">", "<", ">>", "<<"}:
                    flag = _normalize_flag(up)
                    continue
                if not unit:
                    unit = tok
                else:
                    unit = f"{unit} {tok}"
            rec = {
                "test": name,
                "result": result,
                "unit": unit,
                "referenceRange": ref,
                "flag": flag,
            }
            rec["abnormal"] = bool(flag in {"H", "L", "CRIT"})
            out["tests"].append(rec)
            last_rec = rec
            _ensure_iso(rec)
            continue
        # Standalone range line following previous record
        if last_rec and not ln.startswith(" "):
            standalone = _extract_range(ln)
            if standalone and not last_rec.get("referenceRange"):
                last_rec["referenceRange"] = standalone
    return out


def rpc_panel_to_quick_tests(panel_summary: Dict[str, Any], panel_detail: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Convert ORWOR RESULT detail into quick lab rows."""
    tests: List[Dict[str, Any]] = []
    observed_iso = panel_detail.get("collectedIso") or panel_summary.get("resulted")
    resulted_iso = panel_detail.get("resultedIso") or panel_summary.get("resulted")
    specimen = panel_detail.get("specimen") or panel_summary.get("specimen")
    panel_name = panel_detail.get("panel") or panel_summary.get("displayName") or panel_summary.get("name")
    for test in panel_detail.get("tests", []):
        name = test.get("test") or panel_name or ""
        unit = test.get("unit") or None
        quick = {
            "source": "rpc",
            "panel": panel_name,
            "name": name,
            "test": name,
            "result": test.get("result"),
            "units": unit,
            "unit": unit,
            "referenceRange": test.get("referenceRange"),
            "refRange": test.get("referenceRange"),
            "flag": test.get("flag"),
            "abnormal": test.get("abnormal"),
            "specimen": specimen,
            "observed": panel_summary.get("filemanTimestamp"),
            "observedDate": observed_iso,
            "resulted": resulted_iso,
        }
        tests.append(quick)
    return tests


def filter_panels(panels: List[Dict[str, Any]], *, start: Optional[str], end: Optional[str], max_panels: Optional[int]) -> List[Dict[str, Any]]:
    """Filter and limit panel summaries."""
    def _within(item: Dict[str, Any]) -> bool:
        stamp = item.get("resulted") or item.get("observed")
        if not stamp:
            return True
        if start and stamp < start:
            return False
        if end and stamp > end:
            return False
        return True

    filtered = [item for item in panels if _within(item)]
    if max_panels is not None and max_panels >= 0:
        return filtered[:max_panels]
    return filtered


__all__ = [
    "parse_orwcv_lab",
    "parse_orwor_result",
    "rpc_panel_to_quick_tests",
    "filter_panels",
]
