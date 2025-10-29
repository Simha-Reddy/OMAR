from __future__ import annotations
from flask import Blueprint, jsonify, current_app, request
from ..services.patient_service import PatientService
from ..gateways.vista_api_x_gateway import VistaApiXGateway
from ..services import transforms as T

bp = Blueprint('patient_api', __name__)

# Very small composition for now; later use DI container

def _get_patient_service() -> PatientService:
    # Station/DUZ will come from session/SSO later; use defaults for scaffold
    gw = VistaApiXGateway(station=request.args.get('station','500'), duz=request.args.get('duz','983'))
    return PatientService(gateway=gw)


# ----------------- Helpers to enrich quick results from raw -----------------

def _extract_full_text(raw_item: dict) -> str | None:
    try:
        # Common patterns across documents/radiology/procedures
        # 1) text: [ { content: "..." }, ... ]
        txt = raw_item.get('text')
        if isinstance(txt, list) and txt:
            pieces = []
            for block in txt:
                if isinstance(block, dict):
                    c = block.get('content') or block.get('text') or block.get('summary')
                    if isinstance(c, str) and c.strip():
                        pieces.append(c)
                elif isinstance(block, str) and block.strip():
                    pieces.append(block)
            if pieces:
                return "\n".join(pieces)
        # 2) report/impression (radiology)
        rpt = raw_item.get('report') or raw_item.get('impression')
        if isinstance(rpt, str) and rpt.strip():
            return rpt
        # 3) body/content/documentText
        for k in ('body','content','documentText','noteText','clinicalText','details'):
            v = raw_item.get(k)
            if isinstance(v, str) and v.strip():
                return v
        # 4) nested content
        doc = raw_item.get('document')
        if isinstance(doc, dict):
            for k in ('content','text','body'):
                v = doc.get(k)
                if isinstance(v, str) and v.strip():
                    return v
    except Exception:
        pass
    return None


def _extract_encounter_info(raw_item: dict) -> dict | None:
    try:
        enc = None
        # VPR shapes: 'visit' or 'encounter' or 'appointment'
        if isinstance(raw_item.get('visit'), dict):
            enc = raw_item.get('visit')
        elif isinstance(raw_item.get('encounter'), dict):
            enc = raw_item.get('encounter')
        elif isinstance(raw_item.get('appointment'), dict):
            enc = raw_item.get('appointment')
        out = {}
        # visit/encounter identifiers
        uid = None
        if isinstance(enc, dict):
            uid = enc.get('uid') or enc.get('visitUid')
        if not uid:
            uid = raw_item.get('encounterUid') or raw_item.get('visitUid') or raw_item.get('uid')
        if uid:
            out['visitUid'] = uid
        # date/time
        date_val = None
        for k in ('dateTime','referenceDateTime','start','time'):
            if isinstance(enc, dict) and enc.get(k):
                date_val = enc.get(k)
                break
        if not date_val:
            date_val = raw_item.get('dateTime') or raw_item.get('referenceDateTime') or raw_item.get('observed')
        dt_iso = T._parse_any_datetime_to_iso(date_val)  # type: ignore
        if dt_iso:
            out['date'] = dt_iso
        # location
        loc_name = None
        try:
            if isinstance(raw_item.get('location'), dict):
                loc_name = raw_item['location'].get('name') or raw_item['location'].get('displayName')
        except Exception:
            pass
        if not loc_name:
            for k in ('locationName','clinicName','clinic','wardName'):
                v = raw_item.get(k)
                if isinstance(v, str) and v.strip():
                    loc_name = v
                    break
        if loc_name:
            out['location'] = loc_name
        # human-readable encounter name when present
        ename = raw_item.get('encounterName')
        if isinstance(ename, str) and ename.strip():
            out['encounterName'] = ename
        return out or None
    except Exception:
        return None


def _is_problem_active(status_val: str | None) -> bool | None:
    if not status_val:
        return None
    s = status_val.strip().lower()
    # Treat resolved/inactive/historical as inactive
    if 'inactive' in s or 'resolved' in s or 'historical' in s or 'entered in error' in s:
        return False
    if 'active' in s and 'inactive' not in s:
        return True
    return None


def _extract_problem_comments(raw_item: dict) -> list[dict] | None:
    try:
        comments = raw_item.get('comments')
        out = []
        if isinstance(comments, list):
            for c in comments:
                if not isinstance(c, dict):
                    continue
                txt = c.get('comment') or c.get('text')
                when = c.get('entered') or c.get('date') or c.get('enteredDateTime')
                who = c.get('enteredBy') or c.get('author') or c.get('authorDisplayName')
                if txt:
                    out.append({
                        'text': txt,
                        'date': T._parse_any_datetime_to_iso(when),  # type: ignore
                        'author': who
                    })
        return out or None
    except Exception:
        return None

@bp.get('/<dfn>/demographics')
def demographics(dfn: str):
    svc = _get_patient_service()
    try:
        result = svc.get_demographics(dfn)
        return jsonify(result)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@bp.get('/<dfn>/quick/demographics')
def demographics_quick(dfn: str):
    svc = _get_patient_service()
    try:
        vpr = svc.get_vpr_raw(dfn, 'patient')
        quick = svc.get_demographics_quick(dfn)
        if (request.args.get('includeRaw','0').lower() in ('1','true','yes','on')):
            # Attach first raw item for traceability
            item = None
            try:
                arr = T._get_nested_items(vpr)  # type: ignore
                item = arr[0] if arr else None
            except Exception:
                item = None
            if isinstance(quick, dict):
                quick = dict(quick)
                quick['_raw'] = item
        return jsonify(quick)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@bp.get('/<dfn>/quick/meds')
def medications_quick(dfn: str):
    svc = _get_patient_service()
    try:
        vpr = svc.get_vpr_raw(dfn, 'meds')
        quick = svc.get_medications_quick(dfn)
        if (request.args.get('includeRaw','0').lower() in ('1','true','yes','on')) and isinstance(quick, list):
            # Attach raw for each item when possible (1:1 best-effort by index)
            raw_items = []
            try:
                raw_items = T._get_nested_items(vpr)  # type: ignore
            except Exception:
                raw_items = []
            out = []
            for idx, q in enumerate(quick):
                obj = dict(q)
                if idx < len(raw_items):
                    obj['_raw'] = raw_items[idx]
                out.append(obj)
            quick = out
        return jsonify(quick)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# Quick routes for other domains
@bp.get('/<dfn>/quick/labs')
def labs_quick(dfn: str):
    svc = _get_patient_service()
    try:
        vpr = svc.get_vpr_raw(dfn, 'labs')
        quick = svc.get_labs_quick(dfn)
        if (request.args.get('includeRaw','0').lower() in ('1','true','yes','on')) and isinstance(quick, list):
            raw_items = []
            try:
                raw_items = T._get_nested_items(vpr)  # type: ignore
            except Exception:
                raw_items = []
            out = []
            for idx, q in enumerate(quick):
                obj = dict(q)
                if idx < len(raw_items):
                    obj['_raw'] = raw_items[idx]
                out.append(obj)
            quick = out
        return jsonify(quick)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@bp.get('/<dfn>/quick/vitals')
def vitals_quick(dfn: str):
    svc = _get_patient_service()
    try:
        vpr = svc.get_vpr_raw(dfn, 'vitals')
        quick = svc.get_vitals_quick(dfn)
        if (request.args.get('includeRaw','0').lower() in ('1','true','yes','on')) and isinstance(quick, list):
            raw_items = []
            try:
                raw_items = T._get_nested_items(vpr)  # type: ignore
            except Exception:
                raw_items = []
            out = []
            for idx, q in enumerate(quick):
                obj = dict(q)
                if idx < len(raw_items):
                    obj['_raw'] = raw_items[idx]
                out.append(obj)
            quick = out
        return jsonify(quick)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@bp.get('/<dfn>/quick/notes')
def notes_quick(dfn: str):
    svc = _get_patient_service()
    try:
        vpr = svc.get_vpr_raw(dfn, 'notes')
        quick = svc.get_notes_quick(dfn)
        include_raw = request.args.get('includeRaw','0').lower() in ('1','true','yes','on')
        include_text = request.args.get('includeText','0').lower() in ('1','true','yes','on')
        include_enc = request.args.get('includeEncounter','0').lower() in ('1','true','yes','on')
        if (include_raw or include_text or include_enc) and isinstance(quick, list):
            raw_items = []
            try:
                raw_items = T._get_nested_items(vpr)  # type: ignore
            except Exception:
                raw_items = []
            out = []
            for idx, q in enumerate(quick):
                obj = dict(q)
                if idx < len(raw_items):
                    r = raw_items[idx]
                    if include_raw:
                        obj['_raw'] = r
                    if include_text:
                        txt = _extract_full_text(r)
                        if txt:
                            obj['text'] = txt
                    if include_enc:
                        enc = _extract_encounter_info(r)
                        if enc:
                            obj['encounter'] = enc
                out.append(obj)
            quick = out
        return jsonify(quick)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@bp.get('/<dfn>/quick/documents')
def documents_quick(dfn: str):
    """Unified documents endpoint with filters and enrichment.
    Query params:
      - class: one or more document classes (e.g., PROGRESS NOTES, RADIOLOGY REPORTS, SURGICAL REPORTS, DISCHARGE SUMMARY).
               Accepts comma-separated values. Case-insensitive.
      - type: one or more document type names or codes (e.g., Progress Note or PN, Radiology Report or RA, Surgery Report or SR, Discharge Summary or DS).
               Comma-separated, case-insensitive.
      - includeText=1: include full text under 'text' when available.
      - includeEncounter=1: include encounter details under 'encounter'.
      - includeRaw=1: include _raw payload for each item.
    """
    svc = _get_patient_service()
    try:
        # Fetch raw and quick lists
        vpr = svc.get_vpr_raw(dfn, 'notes')  # alias -> documents
        quick_list = svc.get_documents_quick(dfn)

        include_raw = request.args.get('includeRaw','0').lower() in ('1','true','yes','on')
        include_text = request.args.get('includeText','0').lower() in ('1','true','yes','on')
        include_enc = request.args.get('includeEncounter','0').lower() in ('1','true','yes','on')

        # Normalize filters
        def _split_params(val: str | None) -> list[str]:
            if not val:
                return []
            parts = []
            for p in str(val).split(','):
                s = p.strip()
                if s:
                    parts.append(s)
            return parts

        class_filters = [s.lower() for s in _split_params(request.args.get('class'))]
        type_filters = [s.lower() for s in _split_params(request.args.get('type'))]

        raw_items = []
        try:
            raw_items = T._get_nested_items(vpr)  # type: ignore
        except Exception:
            raw_items = []

        # Pair quick with raw by original index to preserve alignment, then filter
        pairs: list[tuple[dict, dict | None]] = []
        if isinstance(quick_list, list):
            for idx, q in enumerate(quick_list):
                r = raw_items[idx] if idx < len(raw_items) else None
                if not isinstance(q, dict):
                    continue
                pairs.append((q, r if isinstance(r, dict) else None))

        # Apply class filter if provided
        if class_filters:
            def _class_matches(q: dict, r: dict | None) -> bool:
                qc = (q.get('documentClass') or '')
                rc = (r.get('documentClass') if isinstance(r, dict) else '')
                s = (qc or rc or '')
                return s.strip().lower() in class_filters
            pairs = [(q, r) for (q, r) in pairs if _class_matches(q, r)]

        # Apply type filter if provided (match by name or code)
        if type_filters:
            def _type_matches(q: dict, r: dict | None) -> bool:
                # Name from quick
                name = (q.get('documentType') or '')
                # Fallbacks from raw
                rname = (r.get('documentTypeName') if isinstance(r, dict) else '')
                rcode = (r.get('documentTypeCode') if isinstance(r, dict) else '')
                vals = [str(name).lower(), str(rname).lower(), str(rcode).lower()]
                return any(v in type_filters for v in vals if v)
            pairs = [(q, r) for (q, r) in pairs if _type_matches(q, r)]

        # Enrichment
        out = []
        for (q, r) in pairs:
            obj = dict(q)
            if include_raw and isinstance(r, dict):
                obj['_raw'] = r
            if include_text and isinstance(r, dict):
                txt = _extract_full_text(r)
                if txt:
                    obj['text'] = txt
            if include_enc and isinstance(r, dict):
                enc = _extract_encounter_info(r)
                if enc:
                    obj['encounter'] = enc
            out.append(obj)

        return jsonify(out if (include_raw or include_text or include_enc or class_filters or type_filters) else quick_list)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@bp.get('/<dfn>/quick/radiology')
def radiology_quick(dfn: str):
    svc = _get_patient_service()
    try:
        vpr = svc.get_vpr_raw(dfn, 'radiology')
        quick = svc.get_radiology_quick(dfn)
        include_raw = request.args.get('includeRaw','0').lower() in ('1','true','yes','on')
        include_text = request.args.get('includeText','0').lower() in ('1','true','yes','on')
        include_enc = request.args.get('includeEncounter','0').lower() in ('1','true','yes','on')
        if (include_raw or include_text or include_enc) and isinstance(quick, list):
            raw_items = []
            try:
                raw_items = T._get_nested_items(vpr)  # type: ignore
            except Exception:
                raw_items = []
            out = []
            for idx, q in enumerate(quick):
                obj = dict(q)
                if idx < len(raw_items):
                    r = raw_items[idx]
                    if include_raw:
                        obj['_raw'] = r
                    if include_text:
                        txt = _extract_full_text(r)
                        if txt:
                            obj['text'] = txt
                    if include_enc:
                        enc = _extract_encounter_info(r)
                        if enc:
                            obj['encounter'] = enc
                out.append(obj)
            quick = out
        return jsonify(quick)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@bp.get('/<dfn>/quick/procedures')
def procedures_quick(dfn: str):
    svc = _get_patient_service()
    try:
        vpr = svc.get_vpr_raw(dfn, 'procedures')
        quick = svc.get_procedures_quick(dfn)
        include_raw = request.args.get('includeRaw','0').lower() in ('1','true','yes','on')
        include_text = request.args.get('includeText','0').lower() in ('1','true','yes','on')
        include_enc = request.args.get('includeEncounter','0').lower() in ('1','true','yes','on')
        if (include_raw or include_text or include_enc) and isinstance(quick, list):
            raw_items = []
            try:
                raw_items = T._get_nested_items(vpr)  # type: ignore
            except Exception:
                raw_items = []
            out = []
            for idx, q in enumerate(quick):
                obj = dict(q)
                if idx < len(raw_items):
                    r = raw_items[idx]
                    if include_raw:
                        obj['_raw'] = r
                    if include_text:
                        txt = _extract_full_text(r)
                        if txt:
                            obj['text'] = txt
                    if include_enc:
                        enc = _extract_encounter_info(r)
                        if enc:
                            obj['encounter'] = enc
                out.append(obj)
            quick = out
        return jsonify(quick)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@bp.get('/<dfn>/quick/encounters')
def encounters_quick(dfn: str):
    svc = _get_patient_service()
    try:
        vpr = svc.get_vpr_raw(dfn, 'encounters')
        quick = svc.get_encounters_quick(dfn)
        if (request.args.get('includeRaw','0').lower() in ('1','true','yes','on')) and isinstance(quick, list):
            raw_items = []
            try:
                raw_items = T._get_nested_items(vpr)  # type: ignore
            except Exception:
                raw_items = []
            out = []
            for idx, q in enumerate(quick):
                obj = dict(q)
                if idx < len(raw_items):
                    obj['_raw'] = raw_items[idx]
                out.append(obj)
            quick = out
        return jsonify(quick)
    except Exception as e:
        return jsonify({'error': str(e)}), 500
# Raw VPR domain passthrough
@bp.get('/<dfn>/vpr/<domain>')
def vpr_raw(dfn: str, domain: str):
    svc = _get_patient_service()
    try:
        vpr = svc.get_vpr_raw(dfn, domain)
        return jsonify(vpr)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# Compare raw vs quick for supported domains
@bp.get('/<dfn>/compare/<domain>')
def compare_domain(dfn: str, domain: str):
    svc = _get_patient_service()
    try:
        vpr = svc.get_vpr_raw(dfn, domain)
        # Support both 'patient' and 'demographics' for convenience
        if domain in ('patient','demographics'):
            quick = svc.get_demographics_quick(dfn)
        elif domain == 'meds':
            quick = svc.get_medications_quick(dfn)
        elif domain == 'labs':
            quick = svc.get_labs_quick(dfn)
        elif domain == 'vitals':
            quick = svc.get_vitals_quick(dfn)
        elif domain == 'notes':
            quick = svc.get_notes_quick(dfn)
        elif domain == 'documents':
            quick = svc.get_documents_quick(dfn)
        elif domain == 'radiology':
            quick = svc.get_radiology_quick(dfn)
        elif domain == 'procedures':
            quick = svc.get_procedures_quick(dfn)
        elif domain == 'encounters':
            quick = svc.get_encounters_quick(dfn)
        elif domain == 'problems':
            quick = svc.get_problems_quick(dfn)
        elif domain == 'allergies':
            quick = svc.get_allergies_quick(dfn)
        else:
            return jsonify({'error': f"compare not implemented for domain '{domain}'"}), 501
        return jsonify({'raw': vpr, 'quick': quick})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# Default VPR shortcuts for common domains
@bp.get('/<dfn>/meds')
def meds_default_vpr(dfn: str):
    svc = _get_patient_service()
    try:
        vpr = svc.get_vpr_raw(dfn, 'meds')
        return jsonify(vpr)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# Default VPR shortcuts for other domains
@bp.get('/<dfn>/labs')
def labs_default_vpr(dfn: str):
    svc = _get_patient_service()
    try:
        vpr = svc.get_vpr_raw(dfn, 'labs')
        return jsonify(vpr)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@bp.get('/<dfn>/vitals')
def vitals_default_vpr(dfn: str):
    svc = _get_patient_service()
    try:
        vpr = svc.get_vpr_raw(dfn, 'vitals')
        return jsonify(vpr)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@bp.get('/<dfn>/notes')
def notes_default_vpr(dfn: str):
    svc = _get_patient_service()
    try:
        vpr = svc.get_vpr_raw(dfn, 'notes')
        return jsonify(vpr)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@bp.get('/<dfn>/radiology')
def radiology_default_vpr(dfn: str):
    svc = _get_patient_service()
    try:
        vpr = svc.get_vpr_raw(dfn, 'radiology')
        return jsonify(vpr)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@bp.get('/<dfn>/procedures')
def procedures_default_vpr(dfn: str):
    svc = _get_patient_service()
    try:
        vpr = svc.get_vpr_raw(dfn, 'procedures')
        return jsonify(vpr)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@bp.get('/<dfn>/encounters')
def encounters_default_vpr(dfn: str):
    svc = _get_patient_service()
    try:
        vpr = svc.get_vpr_raw(dfn, 'encounters')
        return jsonify(vpr)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@bp.get('/<dfn>/problems')
def problems_default_vpr(dfn: str):
    svc = _get_patient_service()
    try:
        vpr = svc.get_vpr_raw(dfn, 'problems')
        return jsonify(vpr)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@bp.get('/<dfn>/allergies')
def allergies_default_vpr(dfn: str):
    svc = _get_patient_service()
    try:
        vpr = svc.get_vpr_raw(dfn, 'allergies')
        return jsonify(vpr)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# Default VPR shortcut for unified documents
@bp.get('/<dfn>/documents')
def documents_default_vpr(dfn: str):
    svc = _get_patient_service()
    try:
        vpr = svc.get_vpr_raw(dfn, 'documents')
        return jsonify(vpr)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# Quick routes: problems & allergies
@bp.get('/<dfn>/quick/problems')
def problems_quick(dfn: str):
    svc = _get_patient_service()
    try:
        vpr = svc.get_vpr_raw(dfn, 'problems')
        quick = svc.get_problems_quick(dfn)
        include_raw = request.args.get('includeRaw','0').lower() in ('1','true','yes','on')
        include_comments = request.args.get('includeComments','0').lower() in ('1','true','yes','on')
        status_filter = (request.args.get('status') or 'all').strip().lower()  # 'active' | 'inactive' | 'all'
        if (include_raw or include_comments or status_filter != 'all') and isinstance(quick, list):
            raw_items = []
            try:
                raw_items = T._get_nested_items(vpr)  # type: ignore
            except Exception:
                raw_items = []
            out = []
            for idx, q in enumerate(quick):
                obj = dict(q)
                raw = raw_items[idx] if idx < len(raw_items) else None
                # status filtering
                if status_filter != 'all':
                    # Try quick status first
                    is_active = _is_problem_active(obj.get('status'))
                    if is_active is None and isinstance(raw, dict):
                        is_active = _is_problem_active(raw.get('statusName') or raw.get('status'))
                    # If still None, treat as unknown: only include in 'all'
                    if is_active is None:
                        if status_filter in ('active','inactive'):
                            continue
                    else:
                        if status_filter == 'active' and not is_active:
                            continue
                        if status_filter == 'inactive' and is_active:
                            continue
                # enrich
                if include_raw and isinstance(raw, dict):
                    obj['_raw'] = raw
                if include_comments and isinstance(raw, dict):
                    comments = _extract_problem_comments(raw)
                    if comments:
                        obj['comments'] = comments
                out.append(obj)
            quick = out
        return jsonify(quick)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@bp.get('/<dfn>/quick/allergies')
def allergies_quick(dfn: str):
    svc = _get_patient_service()
    try:
        vpr = svc.get_vpr_raw(dfn, 'allergies')
        quick = svc.get_allergies_quick(dfn)
        if (request.args.get('includeRaw','0').lower() in ('1','true','yes','on')) and isinstance(quick, list):
            raw_items = []
            try:
                raw_items = T._get_nested_items(vpr)  # type: ignore
            except Exception:
                raw_items = []
            out = []
            for idx, q in enumerate(quick):
                obj = dict(q)
                if idx < len(raw_items):
                    obj['_raw'] = raw_items[idx]
                out.append(obj)
            quick = out
        return jsonify(quick)
    except Exception as e:
        return jsonify({'error': str(e)}), 500
