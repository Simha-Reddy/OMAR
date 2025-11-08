from __future__ import annotations
import os
import json
from dataclasses import dataclass
from typing import Any, Dict, List, Tuple, Optional, Set
from pathlib import Path
from datetime import datetime, timezone

# Ensure project root is importable
import sys
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv
load_dotenv()

# ---------------------------------------------------------------------------
# Embedded vista-api-x configuration fallback (self-contained parity script)
# If the environment already defines these, those values win. Otherwise the
# embedded constants are applied (mirrors logic in fetch_vpr_xml.py).
# NOTE: User explicitly approved embedding this key for this diagnostic tool.
# ---------------------------------------------------------------------------
EMBED_VISTA_API_BASE_URL = 'https://vista-api-x.vetext.app/api'
EMBED_VISTA_API_KEY = 'THRcjCj3WuSZoMW1.fAAD6srSpwcvwIH'
EMBED_VISTA_API_VERIFY_SSL = False  # disable verification for dev parity runs

import os as _os
_os.environ.setdefault('VISTA_API_BASE_URL', EMBED_VISTA_API_BASE_URL)
if EMBED_VISTA_API_KEY and not _os.environ.get('VISTA_API_KEY'):
    _os.environ['VISTA_API_KEY'] = EMBED_VISTA_API_KEY
_os.environ.setdefault('VISTA_API_VERIFY_SSL', 'true' if EMBED_VISTA_API_VERIFY_SSL else 'false')

# Reuse existing gateway and helpers (import AFTER env defaults)
from app.gateways.vista_api_x_gateway import VistaApiXGateway, VPR_RPC_CONTEXT
from app.gateways.vpr_xml_parser import parse_vpr_results_xml, DOMAIN_TAGS
from app.services.transforms import _get_nested_items  # type: ignore

# Reuse XML normalizer from socket gateway to avoid duplication
try:
    from app.gateways.vista_socket_gateway import _normalize_vpr_xml_to_items  # type: ignore
except Exception:
    # Fallback: minimal inline normalizer using xmltodict
    def _normalize_vpr_xml_to_items(xml_text: str) -> Dict[str, Any]:
        try:
            import xmltodict  # type: ignore
        except Exception as e:
            raise RuntimeError("xmltodict not available and app.gateways.vista_socket_gateway not importable")
        obj = xmltodict.parse(xml_text)
        d = obj
        for k in ("data","Data"):
            if isinstance(d, dict) and k in d:
                d = d[k]
                break
        items = None
        if isinstance(d, dict):
            itwrap = d.get('items') or d.get('Items')
            if isinstance(itwrap, dict):
                items = itwrap.get('item') or itwrap.get('Item')
            elif isinstance(itwrap, list):
                items = itwrap
        if items is None:
            items = []
        if isinstance(items, dict):
            items = [items]
        def _to_plain(x):
            if isinstance(x, dict):
                return {k: _to_plain(v) for k, v in x.items()}
            if isinstance(x, list):
                return [ _to_plain(v) for v in x ]
            return x
        def _flatten_special(dct: Any) -> Any:
            if not isinstance(dct, dict):
                return dct
            out = {}
            for k, v in dct.items():
                if isinstance(v, dict) and '#text' in v and len(v) <= 2:
                    out[k] = v['#text']
                else:
                    out[k] = _flatten_special(v)
            return out
        plain_items = _to_plain(items)
        plain_items = [ _flatten_special(it) for it in plain_items ]
        return { 'items': plain_items }

# Parser for <results> ... domain sections XML (full XML shape)
def _normalize_results_xml_to_domain_items(xml_text: str, domain: str) -> List[Dict[str, Any]]:
    try:
        import xmltodict  # type: ignore
    except Exception as e:
        raise RuntimeError("xmltodict is required to parse <results> XML")
    obj = xmltodict.parse(xml_text)
    # Expect root 'results'
    root = obj.get('results') if isinstance(obj, dict) else None
    if not isinstance(root, dict):
        # sometimes payload is already just one domain
        # return best-effort coercion
        if isinstance(obj, dict):
            return [obj]
        return []
    # map domain -> path under results
    path_map = {
        'patient': ('demographics', 'patient'),
        'med': ('medications', 'medication'),
        'lab': ('labs', 'lab'),
        'vital': ('vitals', 'vital'),
        'document': ('documents', 'document'),
        'image': ('images', 'image'),
        'procedure': ('procedures', 'procedure'),
        'visit': ('visits', 'visit'),
        'problem': ('problems', 'problem'),
        'allergy': ('allergies', 'allergy'),
    }
    sec = path_map.get(domain)
    if not sec:
        return []
    outer = root.get(sec[0]) if isinstance(root, dict) else None
    if not isinstance(outer, dict):
        return []
    items = outer.get(sec[1])
    if items is None:
        # patient demographics is a single object
        if domain == 'patient' and 'patient' in outer:
            items = outer.get('patient')
        else:
            items = []
    # Coerce list
    if isinstance(items, dict):
        items = [items]
    if not isinstance(items, list):
        return []
    # Convert ordered dicts into plain dicts
    def _to_plain(x):
        if isinstance(x, dict):
            return {k: _to_plain(v) for k, v in x.items()}
        if isinstance(x, list):
            return [ _to_plain(v) for v in x ]
        return x
    plain_list = [_to_plain(it) for it in items]
    # Ensure each entry is a dict
    out: List[Dict[str, Any]] = []
    for it in plain_list:
        if isinstance(it, dict):
            out.append(it)
        else:
            out.append({'value': it})
    return out

@dataclass
class DomainResult:
    domain: str
    json_items: List[Dict[str, Any]]
    xml_items: List[Dict[str, Any]]

@dataclass
class DomainDiff:
    domain: str
    count_json: int
    count_xml: int
    missing_in_xml: int
    missing_in_json: int
    json_only_fields: List[str]
    xml_only_fields: List[str]
    common_field_mismatch_samples: List[Dict[str, Any]]


def fetch_json_and_xml(gw: VistaApiXGateway, dfn: str, domain: str, params: Optional[Dict[str, Any]] = None) -> DomainResult:
    # JSON
    vpr_json = gw.get_vpr_domain(dfn, domain=domain, params=params)
    json_items = _get_nested_items(vpr_json)  # type: ignore
    # XML domain-limited attempt using positional parameter order (DFN, TYPE, START, STOP, MAX, ITEM)
    type_map = {
        'patient': 'demographics',
        'med': 'meds',
        'lab': 'labs',
        'vital': 'vitals',
        'document': 'documents',
        'image': 'images',
        'procedure': 'procedures',
        'visit': 'visits',
        'problem': 'problems',
        'allergy': 'reactions',
    }
    type_val = type_map.get(domain)
    positional: List[Dict[str, Any]] = []
    # vista-api-x positional literal params: provide each as {'string': value}
    positional.append({'string': str(dfn)})
    if type_val:
        positional.append({'string': type_val})
    if params and isinstance(params, dict):
        start = params.get('start') or params.get('START')
        stop = params.get('stop') or params.get('STOP')
        max_items = params.get('max') or params.get('MAX')
        item_id = params.get('item') or params.get('ITEM')
        if any(v is not None for v in (start, stop, max_items, item_id)):
            positional.append({'string': str(start) if start else ''})
            positional.append({'string': str(stop) if stop else ''})
            positional.append({'string': str(max_items) if max_items else ''})
            positional.append({'string': str(item_id) if item_id else ''})
    xml_raw = gw.call_rpc(context=VPR_RPC_CONTEXT, rpc='VPR GET PATIENT DATA', parameters=positional, json_result=False, timeout=90)
    # Some deployments wrap raw results in a JSON object under 'payload' or 'data'. Unwrap if needed.
    try:
        if isinstance(xml_raw, (bytes, bytearray)):
            xml_raw = xml_raw.decode('utf-8', errors='ignore')
        if isinstance(xml_raw, str) and xml_raw.strip().startswith('{'):
            obj = json.loads(xml_raw)
            pl = obj.get('payload')
            if pl is None:
                pl = obj.get('data')
            if isinstance(pl, list):
                xml_raw = "\n".join(str(x) for x in pl)
            elif isinstance(pl, (str, bytes, bytearray)):
                xml_raw = pl.decode('utf-8', errors='ignore') if isinstance(pl, (bytes, bytearray)) else str(pl)
            else:
                # fallback: keep original
                xml_raw = xml_raw
    except Exception:
        # if unwrap fails, keep original
        pass
    # Ensure xml_raw is a string for the normalizer
    if isinstance(xml_raw, (bytes, bytearray)):
        xml_raw = xml_raw.decode('utf-8', errors='ignore')
    xml_raw_str = str(xml_raw)
    # First attempt: parse <results> domain section
    parsed_dom = parse_vpr_results_xml(xml_raw_str, domain=domain)
    xml_items = parsed_dom.get('items', []) if isinstance(parsed_dom, dict) else []
    if not xml_items:
        # Fallback namedArray approach then attempt results parsing again, else use legacy normalizer
        named: Dict[str, Any] = { 'patientId': str(dfn) }
        if domain:
            named['domain'] = domain
        if params:
            for k, v in params.items():
                if v is not None:
                    named[str(k)] = v
        xml_raw_named = gw.call_rpc(context=VPR_RPC_CONTEXT, rpc='VPR GET PATIENT DATA', parameters=[ { 'namedArray': named } ], json_result=False, timeout=90)
        if isinstance(xml_raw_named, (bytes, bytearray)):
            xml_raw_named = xml_raw_named.decode('utf-8', errors='ignore')
        xml_raw_named_str = str(xml_raw_named)
        parsed_dom2 = parse_vpr_results_xml(xml_raw_named_str, domain=domain)
        xml_items = parsed_dom2.get('items', []) if isinstance(parsed_dom2, dict) else []
        if not xml_items:
            try:
                xml_norm = _normalize_vpr_xml_to_items(xml_raw_named_str)
                maybe_items = xml_norm.get('items') if isinstance(xml_norm, dict) else []
                if isinstance(maybe_items, list):
                    xml_items = [it for it in maybe_items if isinstance(it, dict)]
            except Exception:
                # Last resort: full chart literal DFN fetch and slice
                xml_raw_full = gw.call_rpc(context=VPR_RPC_CONTEXT, rpc='VPR GET PATIENT DATA', parameters=[ { 'string': str(dfn) } ], json_result=False, timeout=90)
                if isinstance(xml_raw_full, (bytes, bytearray)):
                    xml_raw_full = xml_raw_full.decode('utf-8', errors='ignore')
                xml_items = _normalize_results_xml_to_domain_items(str(xml_raw_full), domain)
                return DomainResult(domain=domain, json_items=json_items, xml_items=xml_items)
    # Coerce dicts
    xml_items = [it for it in xml_items if isinstance(it, dict)]
    json_items = [it for it in json_items if isinstance(it, dict)]
    return DomainResult(domain=domain, json_items=json_items, xml_items=xml_items)


def _key_for_item(it: Dict[str, Any]) -> Optional[str]:
    # Prefer uid, else id/localId; stringify
    for k in ('uid','id','localId'):
        v = it.get(k)
        if v is not None:
            s = str(v).strip()
            if s:
                return s
    return None


def compare_domain(dr: DomainResult, sample_limit: int = 5) -> DomainDiff:
    json_by = {}
    xml_by = {}
    for it in dr.json_items:
        k = _key_for_item(it)
        if k:
            json_by[k] = it
    for it in dr.xml_items:
        k = _key_for_item(it)
        if k:
            xml_by[k] = it
    json_keys = set(json_by.keys())
    xml_keys = set(xml_by.keys())
    missing_in_xml = len(json_keys - xml_keys)
    missing_in_json = len(xml_keys - json_keys)

    # Field presence sets
    def field_union(items: List[Dict[str, Any]]) -> Set[str]:
        s: Set[str] = set()
        for it in items:
            for k in it.keys():
                s.add(str(k))
        return s
    json_fields = field_union(dr.json_items)
    xml_fields = field_union(dr.xml_items)
    json_only = sorted(list(json_fields - xml_fields))
    xml_only = sorted(list(xml_fields - json_fields))

    # Sample mismatches: for shared keys, compare overlapping fields and find differing simple values
    samples: List[Dict[str, Any]] = []
    shared_keys = list(json_keys & xml_keys)[: sample_limit * 2]
    for k in shared_keys:
        j = json_by[k]
        x = xml_by[k]
        diffs: Dict[str, Tuple[Any, Any]] = {}
        # Only compare leaf simple fields
        fields = set(j.keys()) | set(x.keys())
        for f in fields:
            vj = j.get(f)
            vx = x.get(f)
            # Compare simple scalars only; skip dict/list
            if isinstance(vj, (dict, list)) or isinstance(vx, (dict, list)):
                continue
            if vj != vx:
                diffs[f] = (vj, vx)
        if diffs:
            samples.append({'key': k, 'diffs': diffs})
        if len(samples) >= sample_limit:
            break

    return DomainDiff(
        domain=dr.domain,
        count_json=len(dr.json_items),
        count_xml=len(dr.xml_items),
        missing_in_xml=missing_in_xml,
        missing_in_json=missing_in_json,
        json_only_fields=json_only,
        xml_only_fields=xml_only,
        common_field_mismatch_samples=samples,
    )


def run_parity(dfn: str = '237', station: str = '500', duz: str = '983', domains: Optional[List[str]] = None, outdir: str = 'examples', prefix: str = 'vpr_parity') -> Path:
    gw = VistaApiXGateway(station=station, duz=duz)
    if not domains:
        domains = ['patient','med','lab','vital','document','image','procedure','visit','problem','allergy']
    results: List[DomainDiff] = []
    for dom in domains:
        try:
            dr = fetch_json_and_xml(gw, dfn=dfn, domain=dom)
            diff = compare_domain(dr)
            results.append(diff)
        except Exception as e:
            results.append(DomainDiff(
                domain=dom,
                count_json=0,
                count_xml=0,
                missing_in_xml=0,
                missing_in_json=0,
                json_only_fields=[f"ERROR: {e}"],
                xml_only_fields=[],
                common_field_mismatch_samples=[],
            ))
    # Write report
    ts = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    out_path = Path(outdir)
    out_path.mkdir(parents=True, exist_ok=True)
    json_path = out_path / f"{prefix}_{dfn}_{ts}.json"
    md_path = out_path / f"{prefix}_{dfn}_{ts}.md"

    data = [
        {
            'domain': d.domain,
            'count_json': d.count_json,
            'count_xml': d.count_xml,
            'missing_in_xml': d.missing_in_xml,
            'missing_in_json': d.missing_in_json,
            'json_only_fields': d.json_only_fields,
            'xml_only_fields': d.xml_only_fields,
            'common_field_mismatch_samples': d.common_field_mismatch_samples,
        }
        for d in results
    ]
    with json_path.open('w', encoding='utf-8') as f:
        json.dump({
            'dfn': dfn,
            'station': station,
            'duz': duz,
            'generatedAt': datetime.now(timezone.utc).isoformat().replace('+00:00','Z'),
            'domains': data,
        }, f, indent=2)

    # Markdown summary table
    def row(d: DomainDiff) -> str:
        return f"| {d.domain} | {d.count_json} | {d.count_xml} | {d.missing_in_xml} | {d.missing_in_json} | {len(d.json_only_fields)} | {len(d.xml_only_fields)} | {len(d.common_field_mismatch_samples)} |"

    lines = []
    lines.append(f"# VPR Parity Report for DFN {dfn} (station {station}, duz {duz})")
    lines.append("")
    lines.append("| Domain | JSON items | XML items | Missing in XML | Missing in JSON | JSON-only fields | XML-only fields | Sample diffs |")
    lines.append("|---|---:|---:|---:|---:|---:|---:|---:|")
    for d in results:
        lines.append(row(d))
    lines.append("")
    lines.append("## Notes")
    lines.append("- Counts compare items extracted via VPR GET PATIENT DATA JSON vs normalized XML from VPR GET PATIENT DATA.")
    lines.append("- Field counts show union-of-fields present in one vs the other across items.")
    lines.append("- Sample diffs show a few mismatched simple fields for overlapping items (by uid/id).")

    with md_path.open('w', encoding='utf-8') as f:
        f.write("\n".join(lines))

    return md_path


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description='Compare VPR JSON vs XML via vista-api-x for parity')
    parser.add_argument('--dfn', default=os.getenv('TEST_DFN','237'))
    parser.add_argument('--station', default=os.getenv('TEST_STATION','500'))
    parser.add_argument('--duz', default=os.getenv('TEST_DUZ','983'))
    parser.add_argument('--domains', default=None, help='Comma list of domains (default: patient,med,lab,vital,document,image,procedure,visit,problem,allergy)')
    parser.add_argument('--out', default=os.getenv('SNAPSHOT_OUTDIR','examples'))
    parser.add_argument('--full', action='store_true', help='Fetch full payloads without domain filtering and dump raw JSON/XML files')
    args = parser.parse_args()
    # When --full is set, dump raw JSON fullchart and raw XML (literal DFN param) to files, then exit
    if args.full:
        out_dir = Path(args.out)
        out_dir.mkdir(parents=True, exist_ok=True)
        ts = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
        gw = VistaApiXGateway(station=str(args.station), duz=str(args.duz))
        # JSON fullchart
        full_json = gw.get_vpr_fullchart(str(args.dfn))
        json_path = out_dir / f"vpr_full_json_{args.dfn}_{ts}.json"
        with json_path.open('w', encoding='utf-8') as f:
            json.dump(full_json, f, indent=2)
        # XML raw (literal DFN param), write both raw and unwrapped-xml variants
        raw_xml_resp = gw.call_rpc(context=VPR_RPC_CONTEXT, rpc='VPR GET PATIENT DATA', parameters=[ { 'string': str(args.dfn) } ], json_result=False, timeout=120)
        # Keep original raw exactly as returned
        raw_path = out_dir / f"vpr_full_xml_raw_{args.dfn}_{ts}.txt"
        try:
            raw_text = raw_xml_resp.decode('utf-8', errors='ignore') if isinstance(raw_xml_resp, (bytes, bytearray)) else str(raw_xml_resp)
        except Exception:
            raw_text = str(raw_xml_resp)
        with raw_path.open('w', encoding='utf-8') as f:
            f.write(raw_text)
        # Unwrap if JSON wrapper
        unwrapped = raw_text
        try:
            s = raw_text.strip()
            if s.startswith('{'):
                obj = json.loads(s)
                pl = obj.get('payload') or obj.get('data')
                if isinstance(pl, list):
                    unwrapped = "\n".join(str(x) for x in pl)
                elif isinstance(pl, (str, bytes, bytearray)):
                    unwrapped = pl.decode('utf-8', errors='ignore') if isinstance(pl, (bytes, bytearray)) else str(pl)
        except Exception:
            pass
        unwrapped_path = out_dir / f"vpr_full_xml_{args.dfn}_{ts}.xml"
        with unwrapped_path.open('w', encoding='utf-8') as f:
            f.write(unwrapped)
        print(f"Wrote full JSON: {json_path}")
        print(f"Wrote full XML (raw): {raw_path}")
        print(f"Wrote full XML (unwrapped): {unwrapped_path}")
    else:
        domains = [s.strip() for s in args.domains.split(',')] if args.domains else None
        p = run_parity(dfn=str(args.dfn), station=str(args.station), duz=str(args.duz), domains=domains, outdir=args.out)
        print(f"Wrote parity report: {p}")
