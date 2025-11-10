"""VPR XML parsing utilities.

Supports parsing the <results> ... domainSection ... </results> shape returned by
the XML RPC `VPR GET PATIENT DATA` when a domain (TYPE) filter is supplied, as
well as (optionally) aggregating all domains when a full multi-domain payload
is returned.

Returned structure (domain-limited usage):
    {
        'items': [ { ...domain item... }, ... ],
        'meta': {
            'domain': 'vital',
            'total': 42,              # integer when available
            'rawTotalAttr': '42',      # original attribute string (debug)
            'version': '1.02',         # results/@version if present
            'timeZone': '-0700'        # results/@timeZone if present
        }
    }

If domain is not specified, parse_vpr_results_xml will return a mapping of all
recognized domains to their item lists under 'domains' and a combined
concatenated 'items' list (useful for rough full-chart operations):
    {
        'items': [... all items across domains ...],
        'domains': { 'vital': [...], 'lab': [...], ... },
        'meta': { 'version': '1.02', 'timeZone': '-0700' }
    }

This module purposefully does NOT attempt to normalize field names beyond the
basic xmltodict conversion; downstream transform layers handle any field
harmonization needed to reach quick/full endpoint schema parity.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

try:
    import xmltodict  # type: ignore
except Exception:  # pragma: no cover - import error surfaced at call time
    xmltodict = None  # type: ignore

DOMAIN_TAGS: Dict[str, Tuple[str, str]] = {
    # domain -> (section tag, item tag)
    'patient': ('demographics', 'patient'),
    'vital': ('vitals', 'vital'),
    'lab': ('labs', 'lab'),
    'med': ('meds', 'med'),
    'document': ('documents', 'document'),
    'image': ('images', 'image'),
    'procedure': ('procedures', 'procedure'),
    'visit': ('visits', 'visit'),
    'problem': ('problems', 'problem'),
    'allergy': ('reactions', 'allergy'),
}


class VPRXMLParseError(RuntimeError):
    """Raised when VPR XML cannot be parsed into the expected shape."""


def _ensure_lib():  # pragma: no cover - trivial
    if xmltodict is None:
        raise VPRXMLParseError("xmltodict is required for VPR XML parsing. Ensure 'xmltodict' is in requirements.")


def _coerce_list(obj: Any) -> List[Any]:
    if obj is None:
        return []
    if isinstance(obj, list):
        return obj
    return [obj]


def _to_plain(x: Any):
    if isinstance(x, dict):
        return {k: _to_plain(v) for k, v in x.items()}
    if isinstance(x, list):
        return [_to_plain(v) for v in x]
    return x


def parse_vpr_results_xml(xml_text: str, domain: Optional[str] = None) -> Dict[str, Any]:
    """Parse <results> VPR XML.

    Parameters:
        xml_text: raw XML string (already unwrapped if came in JSON wrapper)
        domain: optional domain filter. When supplied we only return that domain's items.

    Returns: dict as described in module docstring. If the shape does not match
    <results> root, an empty items list is returned (allowing caller fallbacks).
    """
    _ensure_lib()
    text = (xml_text or '').strip()
    if not text:
        return {'items': [], 'meta': {}}
    # Fast path: look for '<results' to avoid unnecessary parser cost when not applicable
    if '<results' not in text.lower():  # basic heuristic
        return {'items': [], 'meta': {}}
    try:
        parsed = xmltodict.parse(text)  # type: ignore[attr-defined]
    except Exception as e:  # pragma: no cover - xmltodict internal details
        raise VPRXMLParseError(f"Failed to parse VPR <results> XML: {e}")
    if not isinstance(parsed, dict) or 'results' not in parsed:
        return {'items': [], 'meta': {}}
    results = parsed['results']
    if not isinstance(results, dict):
        return {'items': [], 'meta': {}}

    version = results.get('@version') or results.get('version')
    timezone = results.get('@timeZone') or results.get('timeZone')

    def extract(sec_tag: str, item_tag: str) -> List[Dict[str, Any]]:
        sec = results.get(sec_tag)
        if not isinstance(sec, dict):
            return []
        items = sec.get(item_tag)
        lst = _coerce_list(items)
        plain = [_to_plain(it) for it in lst if isinstance(it, (dict, list))]
        # Ensure every element is a dict
        out: List[Dict[str, Any]] = []
        for it in plain:
            if isinstance(it, dict):
                out.append(it)
            else:  # list or scalar fallback
                out.append({'value': it})
        return out

    meta_base: Dict[str, Any] = {k: v for k, v in (('version', version), ('timeZone', timezone)) if v}

    if domain:
        mapping = DOMAIN_TAGS.get(domain)
        if not mapping:
            return {'items': [], 'meta': meta_base}
        sec_tag, item_tag = mapping
        items = extract(sec_tag, item_tag)
        sec = results.get(sec_tag)
        total_attr = None
        if isinstance(sec, dict):
            total_attr = sec.get('@total') or sec.get('total')
        meta = dict(meta_base)
        meta.update({'domain': domain})
        if total_attr is not None:
            meta['rawTotalAttr'] = total_attr
            try:  # best effort int conversion
                meta['total'] = int(str(total_attr))
            except Exception:
                pass
        return {'items': items, 'meta': meta}

    # No domain filter: collect all recognized
    domain_items: Dict[str, List[Dict[str, Any]]] = {}
    concat: List[Dict[str, Any]] = []
    for d, (sec_tag, item_tag) in DOMAIN_TAGS.items():
        items = extract(sec_tag, item_tag)
        if items:
            domain_items[d] = items
            concat.extend(items)
    return {'items': concat, 'domains': domain_items, 'meta': meta_base}


__all__ = [
    'parse_vpr_results_xml',
    'VPRXMLParseError',
    'DOMAIN_TAGS',
]
