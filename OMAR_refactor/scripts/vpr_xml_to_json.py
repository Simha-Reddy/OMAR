#!/usr/bin/env python3
"""
Convert VPR GET PATIENT DATA (XML) into domain-by-domain JSON.

- Input: XML produced by the `fetch_vpr_xml.py` script (VPR GET PATIENT DATA).
- Output: Combined JSON file and optional per-domain JSON files with item arrays.

Design goals:
- No extra dependencies (use xml.etree.ElementTree)
- Preserve most attributes from XML elements into dicts
- Group items under familiar domain keys: demographics, allergies, problems, meds, labs, vitals, visits, notes, immunizations, radiology
- Be resilient to unexpected tags (fallback collector)

Usage examples:
  python scripts/vpr_xml_to_json.py \
    --input OMAR_refactor/examples/237_VPR_GET_PATIENT_DATA_XML_example.xml \
    --output OMAR_refactor/examples/237_VPR_from_XML.json \
    --per-domain-dir OMAR_refactor/examples/domains

Notes:
- This converter produces a practical JSON shape for downstream use and comparison
  with `237_VPR_GET_PATIENT_DATA_JSON_example.json`. It will not perfectly mirror
  the web API's JSON, but provides a consistent per-domain structure derived from the XML.
"""
from __future__ import annotations

import argparse
import json
import os
import re
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple
import xml.etree.ElementTree as ET
import string


# Map XML element tag names to destination domain keys
TAG_TO_DOMAIN = {
    # core
    "patient": "demographics",
    # common clinical domains
    "allergy": "allergies",
    "problem": "problems",
    "med": "meds",
    "lab": "labs",
    "vital": "vitals",
    "visit": "visits",
    "encounter": "visits",
    "document": "notes",
    "tiu": "notes",
    "immunization": "immunizations",
    "rad": "radiology",
}


def _elem_to_obj(elem: ET.Element) -> Dict[str, Any]:
    """Convert an XML element into a JSON-serializable dict.

    Rules:
    - Attributes become top-level keys
    - Text content under key "text" if non-empty after stripping
    - Child elements are grouped by tag;
      - if only one child of a tag -> embed as dict
      - if multiple -> embed as list of dicts
    - Tag name stored under "_tag" for debugging/context
    """
    obj: Dict[str, Any] = {}
    # attributes
    for k, v in elem.attrib.items():
        obj[k] = v
    # text
    txt = (elem.text or "").strip()
    if txt:
        obj.setdefault("text", txt)
    # children
    children_by_tag: Dict[str, List[ET.Element]] = {}
    for child in list(elem):
        children_by_tag.setdefault(child.tag, []).append(child)
    for tag, group in children_by_tag.items():
        if len(group) == 1:
            obj[tag] = _elem_to_obj(group[0])
        else:
            obj[tag] = [_elem_to_obj(c) for c in group]
    # include original tag name for reference
    obj.setdefault("_tag", elem.tag)
    return obj


def _extract_dfn_from_xml_root(root: ET.Element) -> Optional[str]:
    # Common places to find DFN: attribute on root or patient element attributes
    for key in ("dfn", "localId", "id"):
        val = root.attrib.get(key)
        if val:
            return str(val)
    # try patient element
    patient = root.find("patient")
    if patient is not None:
        for key in ("dfn", "localId", "id"):
            val = patient.attrib.get(key)
            if val:
                return str(val)
    return None


def _extract_domain_items(root: ET.Element) -> Dict[str, List[Dict[str, Any]]]:
    """Walk the tree and collect domain items by known tag mapping.
    Unknown tags are ignored at top-level, but nested items under known domains are preserved by _elem_to_obj.
    """
    domains: Dict[str, List[Dict[str, Any]]] = {}

    # Traverse all descendants and collect items whose tag maps to a domain
    for elem in root.iter():
        dom = TAG_TO_DOMAIN.get(elem.tag)
        if not dom:
            continue
        domains.setdefault(dom, []).append(_elem_to_obj(elem))

    return domains


def build_output_structure(*, dfn: Optional[str], station: Optional[str] = None, duz: Optional[str] = None, domains: Dict[str, List[Dict[str, Any]]]) -> Dict[str, Any]:
    return {
        "dfn": str(dfn) if dfn is not None else None,
        "station": str(station) if station is not None else None,
        "duz": str(duz) if duz is not None else None,
        "domains": domains,
    }


def _infer_ids_from_filename(p: Path) -> Tuple[Optional[str], Optional[str], Optional[str]]:
    """Try to infer DFN/station/duz from filename conventions like '237_VPR_...xml'.
    Very best-effort and safe to return Nones.
    """
    name = p.name
    m = re.match(r"^(\d+)_", name)
    dfn = m.group(1) if m else None
    return dfn, None, None


def convert_xml_to_json(
    *,
    input_xml: Path,
    explicit_dfn: Optional[str] = None,
    station: Optional[str] = None,
    duz: Optional[str] = None,
) -> Dict[str, Any]:
    # Read text and tolerate preambles before the first '<'
    raw = input_xml.read_text(encoding="utf-8", errors="ignore")
    s = raw.lstrip("\ufeff\n\r\t ")
    if not s:
        raise ValueError("Input XML file is empty")
    idx = s.find('<')
    if idx > 0:
        s = s[idx:]
    def _sanitize_xml(txt: str) -> str:
        # Replace stray ampersands that are not entities
        txt = re.sub(r"&(?!#\d+;|#x[0-9A-Fa-f]+;|[A-Za-z][A-Za-z0-9]+;)", "&amp;", txt)
        # Drop non-printable control chars except tab/newline/carriage return
        allowed = set("\t\n\r")
        return ''.join(ch if (ch in allowed or (32 <= ord(ch) <= 0x10FFFF)) else ' ' for ch in txt)

    def _escape_text_regions(txt: str) -> str:
        """Heuristically escape '<', '>' and stray '&' in text regions (outside of tags).
        This is a best-effort repair for VPR payloads that include unescaped symbols in note text.
        """
        out: List[str] = []
        in_tag = False
        i = 0
        while i < len(txt):
            ch = txt[i]
            if ch == '<':
                # assume tag start
                in_tag = True
                out.append(ch)
                i += 1
                continue
            if ch == '>':
                in_tag = False
                out.append(ch)
                i += 1
                continue
            if not in_tag:
                if ch == '<':
                    out.append('&lt;')
                elif ch == '>':
                    out.append('&gt;')
                elif ch == '&':
                    # keep entities, else escape
                    m = re.match(r"&(#[0-9]+;|#x[0-9A-Fa-f]+;|[A-Za-z][A-Za-z0-9]+;)", txt[i:])
                    if m:
                        out.append(m.group(0))
                        i += len(m.group(0))
                        continue
                    else:
                        out.append('&amp;')
                else:
                    out.append(ch)
            else:
                out.append(ch)
            i += 1
        return ''.join(out)

    def _wrap_content_cdata(txt: str) -> str:
        """Wrap inner text of <content>...</content> elements in CDATA to protect raw note text.
        Ensures any occurrence of ']]>' inside is split across multiple CDATA sections.
        """
        def repl(m: re.Match[str]) -> str:
            start, inner, end = m.group(1), m.group(2), m.group(3)
            # sanitize control chars first
            inner_s = _sanitize_xml(inner)
            # split ]]>
            inner_s = inner_s.replace("]]>", "]]>]]<![CDATA[>")
            return f"{start}<![CDATA[{inner_s}]]>{end}"
        # Match <content ...> ... </content> lazily with DOTALL
        return re.sub(r"(<content\b[^>]*>)(.*?)(</content>)", repl, txt, flags=re.DOTALL|re.IGNORECASE)

    try:
        root = ET.fromstring(s)
    except ET.ParseError:
        # Try with sanitization and from first '<' in raw
        first_lt = raw.find('<')
        candidate = raw[first_lt:] if first_lt >= 0 else s
        # Wrap <content> bodies in CDATA, then escape problematic text regions
        candidate = _wrap_content_cdata(candidate)
        candidate = _escape_text_regions(_sanitize_xml(candidate))
        root = ET.fromstring(candidate)
    dfn = explicit_dfn or _extract_dfn_from_xml_root(root) or _infer_ids_from_filename(input_xml)[0]
    domain_items = _extract_domain_items(root)
    return build_output_structure(dfn=dfn, station=station, duz=duz, domains=domain_items)


def write_outputs(
    data: Dict[str, Any],
    *,
    output_path: Optional[Path] = None,
    per_domain_dir: Optional[Path] = None,
) -> None:
    # Combined output
    if output_path:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(data, indent=2), encoding="utf-8")
    # Per-domain outputs
    if per_domain_dir:
        per_domain_dir.mkdir(parents=True, exist_ok=True)
        dfn = data.get("dfn") or "unknown"
        domains: Dict[str, Any] = data.get("domains") or {}
        for dom, items in domains.items():
            out = {
                "dfn": dfn,
                "domain": dom,
                "count": len(items) if isinstance(items, list) else 0,
                "items": items,
            }
            (per_domain_dir / f"{dfn}_{dom}.json").write_text(json.dumps(out, indent=2), encoding="utf-8")


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description="Convert VPR XML to domain-by-domain JSON")
    default_xml = Path(__file__).resolve().parents[1] / "examples" / "237_VPR_GET_PATIENT_DATA_XML_example.xml"
    ap.add_argument("--input", default=str(default_xml), help="Path to VPR XML input file")
    ap.add_argument("--dfn", default=None, help="Optional DFN override")
    ap.add_argument("--station", default=None, help="Optional station/site number for metadata only")
    ap.add_argument("--duz", default=None, help="Optional DUZ for metadata only")
    ap.add_argument("--output", default=None, help="Path to write combined JSON output (optional)")
    ap.add_argument("--per-domain-dir", default=None, help="Directory to write per-domain JSON files (optional)")
    args = ap.parse_args(argv)

    input_xml = Path(args.input)
    if not input_xml.exists():
        print(f"[ERROR] Input XML not found: {input_xml}")
        return 2

    try:
        data = convert_xml_to_json(
            input_xml=input_xml,
            explicit_dfn=args.dfn,
            station=args.station,
            duz=args.duz,
        )
    except Exception as e:
        print(f"[ERROR] Failed to convert XML: {e}")
        return 3

    out_path = Path(args.output) if args.output else None
    per_dir = Path(args.per_domain_dir) if args.per_domain_dir else None
    try:
        write_outputs(data, output_path=out_path, per_domain_dir=per_dir)
    except Exception as e:
        print(f"[ERROR] Failed to write outputs: {e}")
        return 4

    total = sum(len(v) for v in (data.get("domains") or {}).values())
    print(f"[OK] Converted XML to JSON. Domains: {list((data.get('domains') or {}).keys())} | Total items: {total}")
    if out_path:
        print(f"Combined output: {out_path}")
    if per_dir:
        print(f"Per-domain directory: {per_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
