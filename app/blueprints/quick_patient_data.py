"""
Helper module for OMAR quick patient data lookups.
Provides convenience functions for common CPRS/VistA RPCs to quickly
populate patient header and summary sections when opening a chart.
"""
import datetime as dt
from typing import List, Dict, Tuple, Any, Optional

from vista_api import VistaRPCClient

DEFAULT_CONTEXTS = ['OR CPRS GUI CHART']


# --- Time helpers ---

def now_utc() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc)


def to_fileman(dt_obj: dt.datetime) -> str:
    """Convert a datetime to FileMan YYYMMDD(.HHMMSS). UTC."""
    z = dt_obj.astimezone(dt.timezone.utc)
    y = z.year - 1700
    return f"{y:03d}{z.month:02d}{z.day:02d}.{z.hour:02d}{z.minute:02d}{z.second:02d}"


def to_fileman_minute(dt_obj: dt.datetime) -> str:
    """Convert a datetime to FileMan YYYMMDD(.HHMM). UTC."""
    z = dt_obj.astimezone(dt.timezone.utc)
    y = z.year - 1700
    return f"{y:03d}{z.month:02d}{z.day:02d}.{z.hour:02d}{z.minute:02d}"


# --- Core caller ---

def call_rpc(client: VistaRPCClient, rpc_name: str, params: List[Any], contexts: Optional[List[str]] = None) -> Tuple[str, str]:
    """Call an RPC under the first context that succeeds. Returns (raw, used_context).
    Expects client to be connected; will attempt to setContext if needed.
    """
    contexts = contexts or DEFAULT_CONTEXTS
    last_err: Optional[Exception] = None
    for ctx in contexts:
        try:
            if getattr(client, 'context', None) != ctx:
                client.setContext(ctx)
            raw = client.invokeRPC(rpc_name, params)
            return raw, ctx
        except Exception as e:
            last_err = e
            continue
    raise RuntimeError(f"All contexts failed for {rpc_name} | contexts={contexts} | last={last_err}")


# --- Parsing helpers ---

def parse_orwcv_lab(raw: str) -> List[Dict[str, str]]:
    """Parse ORWCV LAB lines: <ID>^<Name>^<FileMan date>^<Status>"""
    items: List[Dict[str, str]] = []
    if not raw:
        return items
    for line in raw.splitlines():
        line = line.strip()
        if not line or '^' not in line:
            continue
        p = line.split('^')
        ident = p[0].strip() if len(p) > 0 else ''
        name = p[1].strip() if len(p) > 1 else ''
        fm_date = p[2].strip() if len(p) > 2 else ''
        status = p[3].strip() if len(p) > 3 else ''
        if ident:
            items.append({'id': ident, 'name': name, 'fmDate': fm_date, 'status': status})
    return items


def parse_orwpt_ptinq(raw: str) -> Dict[str, Any]:
    """Parse ORWPT PTINQ demographics response into a dict when possible.
    Falls back to {'raw': raw} if format is unexpected.
    Expected typical lines like: FIELD^VALUE or FIELD^VALUE1^VALUE2
    """
    result: Dict[str, Any] = {}
    if not raw:
        return result
    try:
        lines = [ln.strip() for ln in raw.splitlines() if ln.strip()]
        for ln in lines:
            if '^' not in ln:
                # try key: value pattern
                if ':' in ln:
                    k, v = ln.split(':', 1)
                    result[k.strip()] = v.strip()
                continue
            parts = ln.split('^')
            key = parts[0].strip()
            vals = [p.strip() for p in parts[1:] if p is not None]
            if not key:
                continue
            if len(vals) == 0:
                result[key] = ''
            elif len(vals) == 1:
                result[key] = vals[0]
            else:
                result[key] = vals
        if result:
            return result
    except Exception:
        pass
    return {'raw': raw}


# --- Quick patient data functions ---

def get_recent_labs(client: VistaRPCClient, dfn: str, context: str = 'OR CPRS GUI CHART') -> Tuple[List[Dict[str, str]], str, str]:
    """ORWCV LAB -> recent lab accessions/panels. Returns (parsed, raw, used_context)."""
    raw, used = call_rpc(client, 'ORWCV LAB', [dfn], [context] + [c for c in DEFAULT_CONTEXTS if c != context])
    return parse_orwcv_lab(raw), raw, used


def get_lab_result(client: VistaRPCClient, dfn: str, lab_id: str, context: str = 'OR CPRS GUI CHART') -> Tuple[str, str]:
    """ORWOR RESULT -> single lab result detail. Returns (raw, used_context)."""
    return call_rpc(client, 'ORWOR RESULT', [dfn, '0', lab_id], [context] + [c for c in DEFAULT_CONTEXTS if c != context])


def get_recent_notes(client: VistaRPCClient, dfn: str, limit: int = 300, context: str = 'OR CPRS GUI CHART') -> Tuple[str, str]:
    """TIU DOCUMENTS BY CONTEXT -> list of most recent TIU notes (raw). Returns (raw, used_context).
    Param pattern mirrors working example.
    """
    params_last_300 = ['3', '1', dfn, '-1', '-1', '0', str(limit), 'D', '1', '0', '1', '']
    return call_rpc(client, 'TIU DOCUMENTS BY CONTEXT', params_last_300, [context] + [c for c in DEFAULT_CONTEXTS if c != context])


def get_active_medications(client: VistaRPCClient, dfn: str, context: str = 'OR CPRS GUI CHART') -> Tuple[str, str]:
    """ORWPS ACTIVE -> active medications (raw). Returns (raw, used_context)."""
    return call_rpc(client, 'ORWPS ACTIVE', [dfn], [context] + [c for c in DEFAULT_CONTEXTS if c != context])


def get_problem_list(client: VistaRPCClient, dfn: str, context: str = 'OR CPRS GUI CHART') -> Tuple[str, str]:
    """ORQQPL PROBLEM LIST -> problems (raw). Returns (raw, used_context)."""
    return call_rpc(client, 'ORQQPL PROBLEM LIST', [dfn], [context] + [c for c in DEFAULT_CONTEXTS if c != context])


def get_problem_detail(client: VistaRPCClient, dfn: str, problem_id: str, context: str = 'OR CPRS GUI CHART') -> Tuple[str, str]:
    """ORQQPL DETAIL -> detailed info for a problem. Returns (raw, used_context)."""
    return call_rpc(client, 'ORQQPL DETAIL', [dfn, problem_id], [context] + [c for c in DEFAULT_CONTEXTS if c != context])


def get_allergies(client: VistaRPCClient, dfn: str, context: str = 'OR CPRS GUI CHART') -> Tuple[str, str]:
    """ORQQAL LIST -> allergies (raw). Returns (raw, used_context)."""
    return call_rpc(client, 'ORQQAL LIST', [dfn], [context] + [c for c in DEFAULT_CONTEXTS if c != context])


def get_vitals_for_date_range(client: VistaRPCClient, dfn: str, fm_start: str, fm_end: str, context: str = 'OR CPRS GUI CHART') -> Tuple[str, str]:
    """ORQQVI VITALS FOR DATE RANGE -> vitals (raw). Returns (raw, used_context)."""
    return call_rpc(client, 'ORQQVI VITALS FOR DATE RANGE', [dfn, fm_start, fm_end], [context] + [c for c in DEFAULT_CONTEXTS if c != context])


def get_patient_demographics(client: VistaRPCClient, dfn: str, context: str = 'OR CPRS GUI CHART') -> Tuple[Dict[str, Any], str, str]:
    """ORWPT PTINQ -> patient demographics. Returns (parsed_dict, raw, used_context)."""
    raw, used = call_rpc(client, 'ORWPT PTINQ', [dfn], [context] + [c for c in DEFAULT_CONTEXTS if c != context])
    return parse_orwpt_ptinq(raw), raw, used


__all__ = [
    'now_utc', 'to_fileman', 'to_fileman_minute',
    'call_rpc',
    'get_recent_labs', 'get_lab_result', 'get_recent_notes',
    'get_active_medications', 'get_problem_list', 'get_problem_detail',
    'get_allergies', 'get_vitals_for_date_range', 'get_patient_demographics',
]
