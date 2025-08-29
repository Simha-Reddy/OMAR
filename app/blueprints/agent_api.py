from flask import Blueprint, request, jsonify, current_app, session
import os, json, time, hashlib
from datetime import datetime, timezone, timedelta
import re
from rag_index import hybrid_query_patient  # added: for notes_search results

try:
    from jsonschema import validate as jsonschema_validate, ValidationError
except Exception:  # jsonschema may not be installed yet
    jsonschema_validate = None
    class ValidationError(Exception):
        pass

bp = Blueprint('agent_api', __name__, url_prefix='/api/agent')

SCHEMA_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), '..', 'web', 'modules', 'agent', 'plan.schema.json')
SCHEMA_PATH = os.path.abspath(SCHEMA_PATH)

PLANNER_PROMPT_PATH = os.path.abspath(os.path.join(os.path.dirname(os.path.dirname(__file__)), 'prompts', 'agent_planner.txt'))
RENDERER_PROMPT_PATH = os.path.abspath(os.path.join(os.path.dirname(os.path.dirname(__file__)), 'prompts', 'agent_renderer.txt'))

_cached_schema = None
_cached_planner_prompt = None
_cached_renderer_prompt = None

ALLOWED_TOOLS = {"get_labs", "get_vitals", "get_meds", "get_problems", "get_notes", "get_notes_search_results"}

MODULES_STORE = os.path.abspath(os.path.join(os.path.dirname(os.path.dirname(__file__)), '..', 'modules', 'agent_modules.json'))

def _feature_enabled():
    return bool(current_app.config.get('SAFE_MODULES_ENABLED', False))


def _load_plan_schema():
    global _cached_schema
    if _cached_schema is None:
        try:
            with open(SCHEMA_PATH, 'r', encoding='utf-8') as f:
                _cached_schema = json.load(f)
        except FileNotFoundError:
            _cached_schema = None
    return _cached_schema


def _load_planner_prompt():
    global _cached_planner_prompt
    if _cached_planner_prompt is None:
        try:
            with open(PLANNER_PROMPT_PATH, 'r', encoding='utf-8') as f:
                _cached_planner_prompt = f.read()
        except Exception:
            _cached_planner_prompt = None
    return _cached_planner_prompt


def _load_renderer_prompt():
    global _cached_renderer_prompt
    if _cached_renderer_prompt is None:
        try:
            with open(RENDERER_PROMPT_PATH, 'r', encoding='utf-8') as f:
                _cached_renderer_prompt = f.read()
        except Exception:
            _cached_renderer_prompt = None
    return _cached_renderer_prompt


def _extract_json(text: str):
    # Strip common markdown code fences first
    try:
        m = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", text or '', re.I)
        if m:
            text = m.group(1).strip()
    except Exception:
        pass
    try:
        return json.loads(text)
    except Exception:
        pass
    # Try to find the first plausible JSON object (best-effort)
    try:
        m = re.search(r"\{[\s\S]*\}", text)
        if m:
            return json.loads(m.group(0))
    except Exception:
        return None


# Prefer JSON-mode responses when available; gracefully fall back if unsupported
def _chat_json(messages, *, temperature=0.1, max_tokens=800):
    client = current_app.config.get('OPENAI_CLIENT')
    model = current_app.config.get('DEPLOY_CHAT')
    if not client or not model:
        raise RuntimeError('LLM_NOT_CONFIGURED')
    try:
        return client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
            response_format={"type": "json_object"}
        )
    except Exception:
        # Fallback for models/servers that don't support response_format
        return client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens
        )


def _iso_z(dt: datetime) -> str:
    try:
        return dt.astimezone(timezone.utc).replace(microsecond=0).isoformat().replace('+00:00', 'Z')
    except Exception:
        return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace('+00:00', 'Z')


def _minus_years(dt: datetime, years: int) -> datetime:
    y = dt.year - int(years)
    m, d = dt.month, dt.day
    try:
        return dt.replace(year=y)
    except ValueError:
        # Handle Feb 29 -> Feb 28, etc.
        while True:
            try:
                return datetime(y, m, d, dt.hour, dt.minute, dt.second, tzinfo=timezone.utc)
            except ValueError:
                d -= 1
                if d <= 0:
                    # Fallback: Jan 1
                    return datetime(y, 1, 1, dt.hour, dt.minute, dt.second, tzinfo=timezone.utc)


def _minus_months(dt: datetime, months: int) -> datetime:
    total = (dt.year * 12 + (dt.month - 1)) - int(months)
    y = total // 12
    m = (total % 12) + 1
    d = min(dt.day, 28)  # keep simple to avoid month-end overflows
    try:
        return datetime(y, m, d, dt.hour, dt.minute, dt.second, tzinfo=timezone.utc)
    except Exception:
        return datetime(y, m, 1, dt.hour, dt.minute, dt.second, tzinfo=timezone.utc)


def _coerce_relative_date_range(token: str):
    if not isinstance(token, str) or not token:
        return None
    t = token.strip().lower()
    now = datetime.now(timezone.utc)
    start = None
    end = now
    # Patterns: last_N_years, last_N_months, last_N_days
    m = re.match(r'^last_(\d+)_years?$', t)
    if m:
        start = _minus_years(now, int(m.group(1)))
        return { 'start': _iso_z(start), 'end': _iso_z(end) }
    m = re.match(r'^last_(\d+)_months?$', t)
    if m:
        start = _minus_months(now, int(m.group(1)))
        return { 'start': _iso_z(start), 'end': _iso_z(end) }
    m = re.match(r'^last_(\d+)_days?$', t)
    if m:
        start = now - timedelta(days=int(m.group(1)))
        return { 'start': _iso_z(start), 'end': _iso_z(end) }
    # Common aliases
    if t in ('last_year', 'past_year'):
        start = _minus_years(now, 1)
        return { 'start': _iso_z(start), 'end': _iso_z(end) }
    if t in ('last_5_years', 'past_5_years'):
        start = _minus_years(now, 5)
        return { 'start': _iso_z(start), 'end': _iso_z(end) }
    if t in ('last_12_months', 'past_12_months'):
        start = _minus_months(now, 12)
        return { 'start': _iso_z(start), 'end': _iso_z(end) }
    if t in ('last_90_days', 'past_90_days'):
        start = now - timedelta(days=90)
        return { 'start': _iso_z(start), 'end': _iso_z(end) }
    if t in ('last_30_days', 'past_30_days'):
        start = now - timedelta(days=30)
        return { 'start': _iso_z(start), 'end': _iso_z(end) }
    if t in ('last_7_days', 'past_week'):
        start = now - timedelta(days=7)
        return { 'start': _iso_z(start), 'end': _iso_z(end) }
    return None


def _safe_usage(resp):
    """Return a JSON-serializable subset of token usage from an OpenAI response.
    Only includes primitive counts to avoid non-serializable nested objects.
    """
    try:
        u = getattr(resp, 'usage', None)
        if not u:
            return None
        d = {}
        for k in ('prompt_tokens', 'completion_tokens', 'total_tokens'):
            try:
                v = getattr(u, k, None)
                if isinstance(v, (int, float)):
                    d[k] = v
            except Exception:
                pass
        return d or None
    except Exception:
        return None


def _llm_create_plan(query: str, patient_id: str, debug: bool=False):
    client = current_app.config.get('OPENAI_CLIENT')
    model = current_app.config.get('DEPLOY_CHAT')
    prompt = _load_planner_prompt()
    if not client or not model or not prompt:
        return None, 'LLM_NOT_CONFIGURED', None
    try:
        now_iso = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace('+00:00', 'Z')
        messages = [
            {"role": "system", "content": prompt},
            {"role": "user", "content": f"query: {query}\npatient_id: {patient_id}\nnow_utc_iso: {now_iso}\nImportant: All params.date_range values MUST be objects of the form {{\"start\": \"YYYY-MM-DDThh:mm:ssZ\", \"end\": \"YYYY-MM-DDThh:mm:ssZ\"}}. Do not use relative strings like 'last_5_years'."}
        ]
        resp = client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=0.1,
            max_tokens=800
        )
        content = (resp.choices[0].message.content or '').strip()
        plan = _extract_json(content) if content else None
        trace = None
        if debug:
            # Collect a lightweight trace for UI
            usage = _safe_usage(resp)
            trace = {
                'stage': 'plan',
                'model': model,
                'messages': messages,
                'response_content': content,
                'usage': usage
            }
        if not plan:
            return None, 'LLM_INVALID_JSON', trace
        return plan, None, trace
    except Exception as e:
        return None, f'LLM_ERROR: {e}', ({'stage': 'plan', 'error': str(e)} if debug else None)


def _llm_render_code(datasets: dict, render_spec: dict, debug: bool=False):
    client = current_app.config.get('OPENAI_CLIENT')
    model = current_app.config.get('DEPLOY_CHAT')
    prompt = _load_renderer_prompt()
    if not client or not model or not prompt:
        return None, 'LLM_NOT_CONFIGURED', None
    try:
        # Keep payload small
        # Cap notes_search_results to at most 20 chunks to control token size
        trimmed_datasets = {}
        for k, v in (datasets or {}).items():
            if isinstance(v, list):
                if k == 'notes_search_results':
                    trimmed = v[:20]
                else:
                    trimmed = v[:50]
                trimmed_datasets[k] = trimmed
            else:
                trimmed_datasets[k] = v
        payload = {
            "render_spec": render_spec or {},
            "datasets": trimmed_datasets
        }
        messages = [
            {"role": "system", "content": prompt},
            {"role": "user", "content": json.dumps(payload)}
        ]
        # Use JSON mode when supported; allow a larger completion budget for render step
        resp = _chat_json(messages, temperature=0.1, max_tokens=2200)
        content = (resp.choices[0].message.content or '').strip()
        obj = None
        try:
            obj = json.loads(content)
        except Exception:
            obj = _extract_json(content) if content else None
        trace = None
        if debug:
            usage = _safe_usage(resp)
            trace = {
                'stage': 'render',
                'model': model,
                'messages': messages,
                'response_content': content,
                'usage': usage
            }
        # First pass: if not JSON or missing code, try format-fix
        if not obj or 'render_code' not in obj or not obj.get('render_code'):
            obj2, err2, tr2 = _llm_render_fix_format(content, debug=debug)
            if debug and trace is not None and tr2 is not None:
                trace['refine_format'] = tr2
            if not obj2:
                return None, (err2 or 'LLM_INVALID_JSON'), trace
            obj = obj2
        code = obj.get('render_code') or ''
        # Server static checks; if banned, try to fix
        ok, errs = _server_static_check(code)
        if not ok:
            banned = [e for e in errs if e.lower().startswith('banned token')]
            if banned:
                obj3, err3, tr3 = _llm_render_fix_banned(code, debug=debug)
                if debug and trace is not None and tr3 is not None:
                    trace['refine_banned'] = tr3
                if obj3 and obj3.get('render_code'):
                    code = obj3['render_code']
                    ok2, errs2 = _server_static_check(code)
                    if ok2:
                        text = obj3.get('explanatory_text') or obj.get('explanatory_text') or ''
                        return { 'render_code': code, 'explanatory_text': text }, None, trace
                    else:
                        return None, 'SERVER_STATIC_CHECK_FAILED: ' + '; '.join(errs2[:3]), trace
                else:
                    return None, (err3 or 'LLM_INVALID_JSON_RETRY'), trace
            else:
                # Other static failures (missing function, size) -> return error
                return None, 'SERVER_STATIC_CHECK_FAILED: ' + '; '.join(errs[:3]), trace
        text = obj.get('explanatory_text') or ''
        return { 'render_code': code, 'explanatory_text': text }, None, trace
    except Exception as e:
        return None, f'LLM_ERROR: {e}', ({'stage': 'render', 'error': str(e)} if debug else None)


def _basic_plan_checks(plan: dict):
    required_top = ["schema_version", "purpose", "budget", "data_requests", "render_spec", "acceptance_criteria"]
    for k in required_top:
        if k not in plan:
            return False, f"missing field: {k}"
    b = plan.get('budget') or {}
    for k in ["rows", "bytes", "timeout_ms"]:
        if k not in b:
            return False, f"budget missing {k}"
    if not isinstance(plan.get('data_requests'), list):
        return False, "data_requests must be an array"
    for dr in plan['data_requests']:
        if not isinstance(dr, dict):
            return False, "data_requests items must be objects"
        if dr.get('tool') not in ALLOWED_TOOLS:
            return False, f"tool not allowed: {dr.get('tool')}"
        if not isinstance(dr.get('params'), dict):
            return False, "params must be an object"
    if not isinstance(plan.get('acceptance_criteria'), list) or not plan['acceptance_criteria']:
        return False, "acceptance_criteria must be a non-empty array"
    return True, None


def _validate_plan(plan: dict):
    schema = _load_plan_schema()
    if jsonschema_validate and schema:
        try:
            jsonschema_validate(instance=plan, schema=schema)
            return True, None
        except ValidationError as e:
            return False, str(e)
    # Fallback to basic checks
    ok, msg = _basic_plan_checks(plan)
    if ok:
        return True, None
    return False, msg or "Plan failed basic validation"


def _hash_plan(plan: dict) -> str:
    return hashlib.sha256(json.dumps(plan, sort_keys=True).encode('utf-8')).hexdigest()


def _modules_store_load():
    os.makedirs(os.path.dirname(MODULES_STORE), exist_ok=True)
    if not os.path.isfile(MODULES_STORE):
        return []
    try:
        with open(MODULES_STORE, 'r', encoding='utf-8') as f:
            data = json.load(f)
            return data if isinstance(data, list) else []
    except Exception:
        return []


def _modules_store_save(items):
    os.makedirs(os.path.dirname(MODULES_STORE), exist_ok=True)
    with open(MODULES_STORE, 'w', encoding='utf-8') as f:
        json.dump(items, f, indent=2)


def _execute_plan_stub(plan: dict):
    """Create stub datasets and enforce budgets similar to execute_plan endpoint."""
    # Budgets
    max_rows = int(plan.get('budget', {}).get('rows', 1000))
    max_bytes = int(plan.get('budget', {}).get('bytes', 250000))

    now = datetime.now(timezone.utc).isoformat()

    # Mock fixtures (small)
    labs = [
        {"code": "4548-4", "display": "Hemoglobin A1c", "value": 7.2, "unit": "%", "referenceRange": "4.0-5.6%", "effectiveDateTime": "2025-07-10T09:20:00Z", "source": {"system": "fixtures", "updated": now}},
        {"code": "4548-4", "display": "Hemoglobin A1c", "value": 7.9, "unit": "%", "referenceRange": "4.0-5.6%", "effectiveDateTime": "2025-05-12T08:00:00Z", "source": {"system": "fixtures", "updated": now}}
    ]
    vitals = [
        {"type": "Weight", "value": 82.5, "unit": "kg", "effectiveDateTime": "2025-08-01T10:00:00Z", "source": {"system": "fixtures", "updated": now}},
        {"type": "Weight", "value": 83.0, "unit": "kg", "effectiveDateTime": "2025-06-01T10:00:00Z", "source": {"system": "fixtures", "updated": now}}
    ]
    meds = [
        {"name": "Metformin", "dose": "1000 mg", "route": "PO", "frequency": "BID", "startDate": "2024-11-01", "status": "active", "source": {"system": "fixtures", "updated": now}},
        {"name": "Semaglutide", "dose": "0.5 mg", "route": "SC", "frequency": "weekly", "startDate": "2025-02-15", "status": "active", "source": {"system": "fixtures", "updated": now}}
    ]

    problems = [
        {"text": "Type 2 diabetes mellitus", "status": "active", "onset": "2014-05-01", "source": {"system": "fixtures", "updated": now}}
    ]

    notes = [
        {"date": "2025-08-01", "title": "Endocrinology Follow-up", "service": "ENDO", "snippet": "Discussed A1c trends.", "summary": "A1c worsened modestly; adjusted meds.", "source": {"system": "fixtures", "updated": now}}
    ]

    notes_search_results = [
        {"note_id": "N1", "chunk_id": "c0", "text": "Patient reports cough possibly related to ACE inhibitor.", "rank": 1, "score": 0.72, "source": {"system": "fixtures", "updated": now}}
    ]

    datasets = {"labs": labs, "vitals": vitals, "meds": meds, "problems": problems, "notes": notes, "notes_search_results": notes_search_results}

    # Enforce row/byte budgets (simple truncation)
    truncated = {}
    total_bytes = 0
    for k in list(datasets.keys()):
        arr = datasets[k]
        if isinstance(arr, list):
            if len(arr) > max_rows:
                datasets[k] = arr[:max_rows]
                truncated[k] = True
            else:
                truncated[k] = False
        # size count
        bs = len(json.dumps(datasets[k]).encode('utf-8'))
        total_bytes += bs

    if total_bytes > max_bytes:
        # naive: drop text-heavy first
        for k in ["notes_search_results", "notes", "problems", "meds", "vitals", "labs"]:
            if total_bytes <= max_bytes:
                break
            bs = len(json.dumps(datasets.get(k, [])).encode('utf-8'))
            if bs == 0:
                continue
            datasets[k] = []
            truncated[k] = True
            total_bytes -= bs

    meta = {
        "plan_hash": _hash_plan(plan),
        "sizes": {k: len(v) if isinstance(v, list) else 1 for k, v in datasets.items()},
        "truncated": truncated,
        "generated": now
    }

    return datasets, meta


def _parse_iso_dt(s: str):
    if not s:
        return None
    try:
        from datetime import datetime
        return datetime.fromisoformat(s.replace('Z', '+00:00'))
    except Exception:
        return None


def _within_range(dt_str: str, date_range: dict | None) -> bool:
    if not date_range:
        return True
    dt = _parse_iso_dt(dt_str)
    if not dt:
        return False
    start = _parse_iso_dt((date_range or {}).get('start')) if isinstance(date_range, dict) else None
    end = _parse_iso_dt((date_range or {}).get('end')) if isinstance(date_range, dict) else None
    if start and dt < start:
        return False
    if end and dt > end:
        return False
    return True


def _limit_list(arr, n):
    try:
        n_int = int(n)
        if n_int <= 0:
            return []
        return arr[:min(n_int, 1000)]
    except Exception:
        return arr


def _get_meta_updated_iso():
    try:
        from datetime import datetime, timezone
        ts = (session.get('vpr_retrieval_meta') or {}).get('timestamp')
        if ts:
            return datetime.fromtimestamp(float(ts), tz=timezone.utc).replace(microsecond=0).isoformat().replace('+00:00','Z')
    except Exception:
        pass
    try:
        from datetime import datetime, timezone
        return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace('+00:00','Z')
    except Exception:
        return None


def _dataset_from_get_labs(params: dict):
    labs_all = session.get('fhir_labs') or []
    loinc_index = session.get('fhir_labs_loinc_index') or {}
    codes = params.get('codes') if isinstance(params.get('codes'), list) else None
    date_range = params.get('date_range') if isinstance(params.get('date_range'), dict) else None
    limit = params.get('limit')
    items = []
    if codes:
        seen_ids = set()
        for code in codes[:50]:
            for r in (loinc_index.get(code) or []):
                rid = r.get('id') or f"{r.get('test')}|{r.get('resulted') or r.get('collected')}"
                if rid in seen_ids:
                    continue
                seen_ids.add(rid)
                items.append(r)
    else:
        items = list(labs_all)
    # Map and filter
    out = []
    updated_iso = _get_meta_updated_iso()
    for r in items:
        eff = r.get('resulted') or r.get('collected')
        if not _within_range(eff, date_range):
            continue
        low = r.get('low')
        high = r.get('high')
        rr = None
        if isinstance(low, (int, float)) or isinstance(high, (int, float)):
            low_s = '' if low is None else str(low)
            high_s = '' if high is None else str(high)
            if low_s or high_s:
                rr = f"{low_s}-{high_s}".strip('-')
        out.append({
            'code': r.get('loinc'),
            'display': r.get('test') or r.get('localName'),
            'value': r.get('result'),
            'unit': r.get('unit'),
            'referenceRange': rr,
            'effectiveDateTime': eff,
            'abnormal': r.get('abnormal'),
            'source': {'system': 'vpr', 'updated': updated_iso}
        })
    # Already sorted desc by resulted in index; keep order
    if isinstance(limit, (int, str)):
        out = _limit_list(out, limit)
    return out


def _dataset_from_get_vitals(params: dict):
    vitals_idx = session.get('fhir_vitals') or {}
    date_range = params.get('date_range') if isinstance(params.get('date_range'), dict) else None
    limit = params.get('limit')
    types = params.get('types') if isinstance(params.get('types'), list) else None
    # Map friendly names
    key_map = {
        'WEIGHT': 'weight',
        'HEIGHT': 'height',
        'BMI': 'bmi',
        'BP': 'bloodPressure',
        'BLOOD PRESSURE': 'bloodPressure',
        'HR': 'heartRate',
        'HEARTRATE': 'heartRate',
        'HEART RATE': 'heartRate',
        'RESP': 'respiratoryRate',
        'RESPIRATORY RATE': 'respiratoryRate',
        'TEMP': 'temperature',
        'TEMPERATURE': 'temperature',
        'SPO2': 'oxygenSaturation',
        'OXYGEN SATURATION': 'oxygenSaturation'
    }
    allowed_keys = None
    if types:
        allowed_keys = set()
        for t in types:
            if not isinstance(t, str):
                continue
            k = key_map.get(t.strip().upper())
            if k:
                allowed_keys.add(k)
    rows = []
    updated_iso = _get_meta_updated_iso()
    for k, arr in (vitals_idx or {}).items():
        if allowed_keys and k not in allowed_keys:
            continue
        if k == 'bloodPressure':
            for bp in arr:
                eff = bp.get('effectiveDateTime')
                if not _within_range(eff, date_range):
                    continue
                sys_v = bp.get('systolic')
                dia_v = bp.get('diastolic')
                val = None
                try:
                    if sys_v is not None and dia_v is not None:
                        val = f"{sys_v}/{dia_v}"
                    else:
                        val = sys_v if sys_v is not None else dia_v
                except Exception:
                    val = None
                rows.append({
                    'type': 'BP',
                    'value': val,
                    'systolic': sys_v,
                    'diastolic': dia_v,
                    'unit': bp.get('unit') or 'mmHg',
                    'effectiveDateTime': eff,
                    'abnormal': bp.get('abnormal'),
                    'source': {'system': 'vpr', 'updated': updated_iso}
                })
        else:
            for v in arr:
                eff = v.get('effectiveDateTime')
                if not _within_range(eff, date_range):
                    continue
                rows.append({
                    'type': k[0].upper() + k[1:],
                    'value': v.get('value'),
                    'unit': v.get('unit'),
                    'effectiveDateTime': eff,
                    'abnormal': v.get('abnormal'),
                    'source': {'system': 'vpr', 'updated': updated_iso}
                })
    # Keep natural chronological order from index; apply limit
    if isinstance(limit, (int, str)):
        rows = _limit_list(rows, limit)
    return rows


def _dataset_from_get_meds(params: dict):
    meds = session.get('fhir_meds') or []
    status = (params.get('status') or '').strip().lower()
    date_range = params.get('date_range') if isinstance(params.get('date_range'), dict) else None
    limit = params.get('limit')
    updated_iso = _get_meta_updated_iso()
    out = []
    for m in meds:
        st = (m.get('status') or '').lower()
        if status:
            # Map tool's "stopped" to non-active statuses
            if status == 'active' and st != 'active':
                continue
            if status in ('stopped', 'completed') and st not in ('stopped', 'completed'):
                continue
        start_dt = m.get('startDate')
        if date_range and not _within_range(start_dt, date_range):
            continue
        out.append({
            'name': m.get('name'),
            'dose': m.get('dose'),
            'route': m.get('route'),
            'frequency': m.get('frequency'),
            'startDate': m.get('startDate'),
            'status': m.get('status'),
            'source': {'system': 'vpr', 'updated': updated_iso}
        })
    if isinstance(limit, (int, str)):
        out = _limit_list(out, limit)
    return out


def _dataset_from_get_problems(params: dict):
    problems = session.get('fhir_problems') or []
    status = (params.get('status') or '').strip().lower()
    limit = params.get('limit')
    updated_iso = _get_meta_updated_iso()
    out = []
    for p in problems:
        active = bool(p.get('active'))
        # Map inactive->resolved for tool schema
        st = 'active' if active else 'resolved'
        if status and status != st:
            continue
        out.append({
            'text': p.get('name'),
            'status': st,
            'onset': p.get('onsetDateTime') or p.get('recordedDate'),
            'source': {'system': 'vpr', 'updated': updated_iso}
        })
    if isinstance(limit, (int, str)):
        out = _limit_list(out, limit)
    return out


def _dataset_from_get_notes(params: dict):
    bundle = session.get('patient_record') or {}
    date_range = params.get('date_range') if isinstance(params.get('date_range'), dict) else None
    limit = params.get('limit')
    updated_iso = _get_meta_updated_iso()
    out = []
    try:
        for e in (bundle.get('entry') or []):
            res = (e or {}).get('resource') or {}
            if res.get('resourceType') != 'DocumentReference':
                continue
            date_str = res.get('date')
            if date_range and not _within_range(date_str, date_range):
                continue
            title = res.get('description') or ((res.get('type') or {}).get('text'))
            service = ((res.get('type') or {}).get('text'))
            out.append({
                'date': date_str,
                'title': title,
                'service': service,
                'snippet': None,
                'summary': None,
                'source': {'system': 'vpr', 'updated': updated_iso}
            })
    except Exception:
        out = []
    # Sort desc by date
    try:
        out.sort(key=lambda r: r.get('date') or '', reverse=True)
    except Exception:
        pass
    if isinstance(limit, (int, str)):
        out = _limit_list(out, limit)
    return out


def _dataset_from_get_notes_search_results(params: dict):
    query = (params.get('query') or '').strip()
    top_k = int(params.get('top_k') or 8)
    # cap to prevent large payloads
    if top_k > 20:
        top_k = 20
    doc_ids = params.get('doc_ids') if isinstance(params.get('doc_ids'), list) else None
    meta = session.get('patient_meta') or {}
    patient_id = meta.get('dfn') or 'unknown'
    updated_iso = _get_meta_updated_iso()

    client = current_app.config.get('OPENAI_CLIENT')
    deploy_embed = current_app.config.get('DEPLOY_EMBED')
    if not client or not deploy_embed:
        return []
    if not patient_id or patient_id == 'unknown' or not query:
        return []

    try:
        result = hybrid_query_patient(str(patient_id), query, client, deploy_embed, top_k=top_k)
    except Exception:
        result = {'error': 'search_failed'}
    if result.get('error'):
        return []
    matches = result.get('matches') or []
    if doc_ids:
        want = set(str(d) for d in doc_ids if d is not None)
        matches = [m for m in matches if str(m.get('note_id')) in want]
    # Map to flat dataset rows
    rows = []
    for m in matches:
        rows.append({
            'note_id': m.get('note_id'),
            'chunk_id': m.get('chunk_id'),
            'text': m.get('text'),
            'rank': m.get('rank'),
            'score': m.get('score'),
            'source': {'system': 'rag', 'updated': updated_iso}
        })
    return rows


def _execute_plan_real(plan: dict):
    # Budgets
    max_rows = int(plan.get('budget', {}).get('rows', 500))
    max_bytes = int(plan.get('budget', {}).get('bytes', 150000))

    datasets = {}
    tool_dispatch = {
        'get_labs': _dataset_from_get_labs,
        'get_vitals': _dataset_from_get_vitals,
        'get_meds': _dataset_from_get_meds,
        'get_problems': _dataset_from_get_problems,
        'get_notes': _dataset_from_get_notes,
        'get_notes_search_results': _dataset_from_get_notes_search_results,
    }
    # Execute each request in order; merge by tool id -> named dataset keys
    for dr in plan.get('data_requests', []) or []:
        tool = dr.get('tool')
        params = dr.get('params') or {}
        func = tool_dispatch.get(tool)
        if not func:
            continue
        try:
            data = func(params)
        except Exception as e:
            data = []
        key = None
        if tool == 'get_labs':
            key = 'labs'
        elif tool == 'get_vitals':
            key = 'vitals'
        elif tool == 'get_meds':
            key = 'meds'
        elif tool == 'get_problems':
            key = 'problems'
        elif tool == 'get_notes':
            key = 'notes'
        elif tool == 'get_notes_search_results':
            key = 'notes_search_results'
        if key:
            # Concatenate if multiple requests for same dataset
            if key in datasets and isinstance(datasets[key], list) and isinstance(data, list):
                datasets[key].extend(data)
            else:
                datasets[key] = data
    # Enforce per-dataset row cap
    for k in list(datasets.keys()):
        arr = datasets[k]
        if isinstance(arr, list) and len(arr) > max_rows:
            datasets[k] = arr[:max_rows]
    # Byte budget enforcement: drop in order
    order = ['notes_search_results', 'notes', 'problems', 'meds', 'vitals', 'labs']
    def size_bytes(obj):
        try:
            import json
            return len(json.dumps(obj).encode('utf-8'))
        except Exception:
            return 0
    total_bytes = sum(size_bytes(v) for v in datasets.values())
    truncated = {k: False for k in datasets.keys()}
    for k in order:
        if total_bytes <= max_bytes:
            break
        if k in datasets and datasets[k]:
            total_bytes -= size_bytes(datasets[k])
            datasets[k] = []
            truncated[k] = True
    meta = {
        'plan_hash': _hash_plan(plan),
        'sizes': {k: (len(v) if isinstance(v, list) else 1) for k, v in datasets.items()},
        'truncated': truncated,
        'generated': _iso_z(__import__('datetime').datetime.now(__import__('datetime').timezone.utc)),
    }
    return datasets, meta


@bp.route('/plan', methods=['POST'])
def plan():
    if not _feature_enabled():
        return jsonify({"error": "SAFE_MODULES_DISABLED"}), 403
    body = request.get_json(silent=True) or {}
    query = (body.get('query') or '').strip()
    patient_id = (body.get('patient_id') or 'demo').strip()
    debug = bool(body.get('debug'))

    # Try LLM-based planning first
    use_stub = False
    plan_obj = None
    llm_trace = None
    if query:
        plan_obj, llm_err, llm_trace = _llm_create_plan(query, patient_id, debug=debug)
        if plan_obj is None:
            # Fall back to deterministic stub
            use_stub = True
            print(f"[agent.plan] LLM planning failed: {llm_err}")
    else:
        use_stub = True

    if use_stub:
        lower_q = query.lower()
        is_diabetes = 'diabetes' in lower_q or 'a1c' in lower_q or 'hba1c' in lower_q
        plan_obj = {
            "schema_version": "1.0.0",
            "purpose": "Provide a concise snapshot of diabetes control and related vitals/meds for clinical review." if is_diabetes else (f"Plan for query: {query}" if query else "Empty query plan"),
            "budget": {"rows": 1000 if is_diabetes else 200, "bytes": 250000 if is_diabetes else 100000, "timeout_ms": 5000 if is_diabetes else 3000},
            "data_requests": [],
            "render_spec": {"tables": [], "charts": []},
            "acceptance_criteria": [
                "All numeric values display units and dates",
                "No external network access",
                "Row/byte/time budgets respected"
            ]
        }
        if is_diabetes:
            plan_obj["data_requests"] = [
                {"tool": "get_labs", "params": {"patient_id": patient_id, "codes": ["4548-4"], "limit": 200}},
                {"tool": "get_vitals", "params": {"patient_id": patient_id, "types": ["Weight"], "limit": 365}},
                {"tool": "get_meds", "params": {"patient_id": patient_id, "status": "active", "limit": 200}},
            ]
            plan_obj["render_spec"] = {
                "tables": [
                    {"id": "meds", "title": "Active Diabetes Medications", "columns": ["name","dose","route","frequency","startDate","status","source.updated"]}
                ],
                "charts": [
                    {"id": "a1c_trend", "type": "line", "dataset": "labs", "x": "effectiveDateTime", "y": "value", "groupBy": "code"},
                    {"id": "weight_trend", "type": "line", "dataset": "vitals", "x": "effectiveDateTime", "y": "value", "filter": {"type": "Weight"}}
                ],
                "notes": "Show A1c and weight trends with dates and units."
            }
        if debug:
            llm_trace = { 'stage': 'plan', 'used_stub': True }

    # Normalize common LLM deviations before validation
    rs = plan_obj.get('render_spec')
    if isinstance(rs, str):
        plan_obj['render_spec'] = { 'notes': rs }
        print('[agent.plan] coerced string render_spec -> object')
    elif rs is None or isinstance(rs, list):
        plan_obj['render_spec'] = {}
        print('[agent.plan] replaced invalid render_spec with empty object')

    # Coerce relative date_range tokens to required object
    for dr in plan_obj.get('data_requests', []) or []:
        try:
            params = dr.get('params') or {}
            dr['params'] = params
            if 'date_range' in params and isinstance(params['date_range'], str):
                coerced = _coerce_relative_date_range(params['date_range'])
                if coerced:
                    params['date_range'] = coerced
                    print(f"[agent.plan] coerced date_range token -> object for tool={dr.get('tool')}")
        except Exception:
            pass

    # Ensure required defaults if LLM omitted some fields
    plan_obj.setdefault('schema_version', '1.0.0')
    plan_obj.setdefault('budget', {"rows": 500, "bytes": 150000, "timeout_ms": 4000})
    plan_obj.setdefault('data_requests', [])
    plan_obj.setdefault('render_spec', {"tables": [], "charts": []})
    plan_obj.setdefault('acceptance_criteria', [
        "All numeric values display units and dates",
        "No external network access",
        "Row/byte/time budgets respected"
    ])

    # NEW: Normalize acceptance_criteria into an array of strings
    try:
        ac = plan_obj.get('acceptance_criteria')
        # If object like {"checks": [...]}, pick the array value
        if isinstance(ac, dict):
            for key in ('checks', 'criteria', 'items', 'list', 'values'):
                v = ac.get(key)
                if isinstance(v, list):
                    ac = v
                    print(f"[agent.plan] coerced acceptance_criteria.{key} -> array")
                    break
        # If string, split into bullet lines
        if isinstance(ac, str):
            import re as _re
            parts = [p.strip().lstrip('-•').strip() for p in _re.split(r"[\n;]+", ac) if p.strip()]
            ac = parts
            print('[agent.plan] split string acceptance_criteria -> array')
        # If array, extract strings from possible dicts
        if isinstance(ac, list):
            norm = []
            for it in ac:
                if isinstance(it, str) and it.strip():
                    norm.append(it.strip())
                elif isinstance(it, dict):
                    for k in ('text','check','criterion','value','desc','description'):
                        val = it.get(k)
                        if isinstance(val, str) and val.strip():
                            norm.append(val.strip())
                            break
            # Trim, enforce max 10 and max length 300 per schema
            norm = [s[:300] for s in norm if s][:10]
            if not norm:
                norm = ["Row/byte/time budgets respected"]
            plan_obj['acceptance_criteria'] = norm
    except Exception:
        # On any error, ensure a safe default
        plan_obj['acceptance_criteria'] = [
            "All numeric values display units and dates",
            "Row/byte/time budgets respected"
        ]

    # Enforce allowed tools and simple normalization
    for dr in plan_obj.get('data_requests', [])[:]:
        if dr.get('tool') not in ALLOWED_TOOLS:
            dr['tool'] = None
    plan_obj['data_requests'] = [dr for dr in plan_obj.get('data_requests', []) if dr.get('tool')]

    valid, err = _validate_plan(plan_obj)
    if not valid:
        return jsonify({"error": "PLAN_VALIDATION_FAILED", "detail": err}), 400

    # Audit log
    print(f"[agent.plan] hash={_hash_plan(plan_obj)} patient={patient_id} via={'LLM' if not use_stub else 'STUB'} query={query!r}")

    resp_obj = plan_obj.copy()
    if debug and llm_trace:
        resp_obj = { **resp_obj, 'llm_trace': llm_trace }
    return jsonify(resp_obj)


@bp.route('/execute-plan', methods=['POST'])
def execute_plan():
    if not _feature_enabled():
        return jsonify({"error": "SAFE_MODULES_DISABLED"}), 403
    body = request.get_json(silent=True) or {}
    plan = body.get('plan') or body  # allow raw plan

    valid, err = _validate_plan(plan)
    if not valid:
        return jsonify({"error": "PLAN_VALIDATION_FAILED", "detail": err}), 400

    # Prefer real executor; fall back to stub if session lacks data
    try:
        datasets, meta = _execute_plan_real(plan)
        # If everything empty and no patient selected, use stub to demonstrate
        any_data = any(isinstance(v, list) and v for v in (datasets or {}).values())
        if not any_data and not session.get('patient_record'):
            datasets, meta = _execute_plan_stub(plan)
    except Exception as e:
        print(f"[agent.execute] real executor failed: {e}")
        datasets, meta = _execute_plan_stub(plan)

    # Simple audit log (stdout for now)
    print(f"[agent.execute] hash={meta['plan_hash']} sizes={meta['sizes']} ")

    return jsonify({"datasets": datasets, "meta": meta})


@bp.route('/render', methods=['POST'])
def render():
    if not _feature_enabled():
        return jsonify({"error": "SAFE_MODULES_DISABLED"}), 403
    body = request.get_json(silent=True) or {}
    datasets = body.get('datasets') or {}
    render_spec = body.get('render_spec') or {}
    debug = bool(body.get('debug'))

    obj, err, llm_trace = _llm_render_code(datasets, render_spec, debug=debug)
    if obj is None:
        # Fallback stub with failure reason included
        print(f"[agent.render] LLM renderer failed: {err}")
        reason = str(err or 'unknown')[:240]
        render_code = (
            "function render({datasets, container, Tabulator, SimplePlots, Formatter}) {\n"
            "  const rows = (datasets && datasets.meds) || [];\n"
            "  const h = document.createElement('h3'); h.textContent = 'Medications'; container.appendChild(h);\n"
            "  if (Tabulator && Tabulator.createTable) {\n"
            "    Tabulator.createTable(container, rows, {title: 'Medications'});\n"
            "  } else {\n"
            "    const pre = document.createElement('pre');\n"
            "    pre.textContent = JSON.stringify(rows, null, 2);\n"
            "    container.appendChild(pre);\n"
            "  }\n"
            "  const p = document.createElement('p'); p.style.color='#666'; p.style.marginTop='8px'; p.textContent = 'Note: renderer fallback used.'; container.appendChild(p);\n"
            "}"
        )
        explanatory_text = f"Renderer fallback used. Reason: {reason}"
        obj = {"render_code": render_code, "explanatory_text": explanatory_text}
        if debug and not llm_trace:
            llm_trace = {'stage': 'render', 'used_stub': True, 'error': reason}

    if debug and llm_trace:
        return jsonify({ **obj, 'llm_trace': llm_trace })

    return jsonify(obj)


@bp.route('/modules/save', methods=['POST'])
def save_module():
    if not _feature_enabled():
        return jsonify({"error": "SAFE_MODULES_DISABLED"}), 403
    body = request.get_json(silent=True) or {}
    plan = body.get('plan') or {}
    render_code = body.get('render_code') or ''
    title = (body.get('title') or '').strip() or (plan.get('purpose') or 'Untitled Module')
    approved = bool(body.get('approved_by_user'))

    if not approved:
        return jsonify({"error": "NOT_APPROVED", "detail": "User approval required to save module."}), 400

    valid, err = _validate_plan(plan)
    if not valid:
        return jsonify({"error": "PLAN_VALIDATION_FAILED", "detail": err}), 400

    if not isinstance(render_code, str) or not render_code.strip():
        return jsonify({"error": "RENDER_CODE_REQUIRED"}), 400

    saved_at = datetime.now(timezone.utc).isoformat()
    plan_hash = _hash_plan(plan)
    # Short stable id from plan hash + title
    preferred_id = (body.get('id') or '').strip()

    def _slugify(text: str) -> str:
        s = ''.join(ch.lower() if ch.isalnum() else '-' for ch in text).strip('-')
        while '--' in s:
            s = s.replace('--', '-')
        return s or 'module'

    items = _modules_store_load()

    # Update existing by explicit id if provided
    if preferred_id:
        for it in items:
            if it.get('id') == preferred_id:
                it.update({
                    'title': title,
                    'plan': plan,
                    'plan_hash': plan_hash,
                    'render_code': render_code,
                    'updated_at': saved_at
                })
                _modules_store_save(items)
                print(f"[agent.modules.save] updated id={preferred_id} hash={plan_hash}")
                return jsonify({"ok": True, "module": it})
        # If preferred id not found, we'll create a new one with that id
        base_id = preferred_id
    else:
        base_id = f"{_slugify(title)}-{plan_hash[:10]}"

    # Ensure unique id
    new_id = base_id
    suffix = 1
    existing_ids = {it.get('id') for it in items}
    while new_id in existing_ids:
        suffix += 1
        new_id = f"{base_id}-{suffix}"

    new_item = {
        'id': new_id,
        'title': title,
        'plan': plan,
        'plan_hash': plan_hash,
        'render_code': render_code,
        'created_at': saved_at,
        'updated_at': saved_at,
        'version': 1
    }
    items.append(new_item)
    _modules_store_save(items)
    print(f"[agent.modules.save] created id={new_id} hash={plan_hash}")

    return jsonify({"ok": True, "module": new_item})


@bp.route('/modules/list', methods=['GET'])
def list_modules():
    if not _feature_enabled():
        return jsonify({"error": "SAFE_MODULES_DISABLED"}), 403
    items = _modules_store_load()
    # Sort by updated_at desc
    try:
        items.sort(key=lambda x: x.get('updated_at') or x.get('created_at') or '', reverse=True)
    except Exception:
        pass
    return jsonify({"modules": items, "count": len(items)})


@bp.route('/modules/run', methods=['POST'])
def run_module():
    if not _feature_enabled():
        return jsonify({"error": "SAFE_MODULES_DISABLED"}), 403
    body = request.get_json(silent=True) or {}
    module_id = (body.get('id') or body.get('module_id') or '').strip()
    if not module_id:
        return jsonify({"error": "MODULE_ID_REQUIRED"}), 400

    items = _modules_store_load()
    mod = next((it for it in items if it.get('id') == module_id), None)
    if not mod:
        return jsonify({"error": "MODULE_NOT_FOUND"}), 404

    plan = mod.get('plan') or {}
    valid, err = _validate_plan(plan)
    if not valid:
        return jsonify({"error": "PLAN_VALIDATION_FAILED", "detail": err}), 400

    # Use real executor with fallback to stub
    try:
        datasets, meta = _execute_plan_real(plan)
        any_data = any(isinstance(v, list) and v for v in (datasets or {}).values())
        if not any_data and not session.get('patient_record'):
            datasets, meta = _execute_plan_stub(plan)
    except Exception as e:
        print(f"[agent.modules.run] real executor failed: {e}")
        datasets, meta = _execute_plan_stub(plan)

    # Simple audit log
    print(f"[agent.modules.run] id={module_id} hash={meta['plan_hash']} sizes={meta['sizes']}")

    return jsonify({
        "datasets": datasets,
        "meta": meta,
        "module": {
            "id": mod.get('id'),
            "title": mod.get('title'),
            "plan_hash": mod.get('plan_hash'),
            "render_code": mod.get('render_code'),
        }
    })


# -------------------- Server-side static checks for render_code --------------------
BANNED_PATTERNS = [
    re.compile(r"\beval\s*\(", re.I),
    re.compile(r"\bFunction\s*\(", re.I),
    re.compile(r"\bimport\s*\(", re.I),
    re.compile(r"\bfetch\b", re.I),
    re.compile(r"XMLHttpRequest", re.I),
    re.compile(r"\bWebSocket\b", re.I),
    re.compile(r"\bWorker\b", re.I),
    re.compile(r"SharedArrayBuffer", re.I),
    re.compile(r"\bpostMessage\s*\(", re.I),
    re.compile(r"\bsetTimeout\s*\(", re.I),
    re.compile(r"\bsetInterval\s*\(", re.I),
    re.compile(r"localStorage", re.I),
    re.compile(r"sessionStorage", re.I),
    re.compile(r"indexedDB", re.I),
    re.compile(r"document\.cookie", re.I),
    re.compile(r"window\.top", re.I),
    re.compile(r"window\.parent", re.I),
    re.compile(r"<[^>]*\\son[a-z0-9_:-]+\\s*=", re.I),
    re.compile(r"\bsetAttribute\s*\(\s*['\"]on[a-z0-9_:-]+['\"]\s*,", re.I),
]

def _server_static_check(code: str):
    errs = []
    if not isinstance(code, str) or not code.strip():
        errs.append('Empty render_code')
        return False, errs
    if len(code) > 200_000:
        errs.append('Code too large (>200KB)')
    if 'function render' not in code:
        errs.append('Missing function render(...) definition')
    for pat in BANNED_PATTERNS:
        m = pat.search(code)
        if m:
            s = max(0, m.start() - 20)
            e = min(len(code), m.end() + 60)
            snippet = re.sub(r"\s+", ' ', code[s:e])
            errs.append(f"Banned token: {pat.pattern} near: {snippet}")
    return (len(errs) == 0), errs


# -------------------- LLM helpers for render JSON fixups --------------------

def _llm_render_fix_format(raw_content: str, debug: bool=False):
    """Ask the LLM to reformat previous non-JSON content into strict JSON with render_code and explanatory_text only."""
    client = current_app.config.get('OPENAI_CLIENT')
    model = current_app.config.get('DEPLOY_CHAT')
    if not client or not model:
        return None, 'LLM_NOT_CONFIGURED', None
    system = (
        "You are a strict formatter. Convert the user's content into a SINGLE JSON object with exactly two keys: "
        "render_code (a JavaScript function named render with signature function render({datasets, container, Tabulator, SimplePlots, Formatter}) { ... }) "
        "and explanatory_text (short plaintext). Do not include markdown, backticks, or any other fields. Ensure render_code contains NO banned tokens such as eval(, Function(, import(, fetch, XMLHttpRequest, WebSocket, Worker, SharedArrayBuffer, postMessage(, setTimeout(, setInterval(, storage APIs, window.top/parent, inline on*)."
    )
    try:
        messages = [
            {"role": "system", "content": system},
            {"role": "user", "content": str(raw_content or '')}
        ]
        resp = _chat_json(messages, temperature=0.0, max_tokens=700)
        content = (resp.choices[0].message.content or '').strip()
        try:
            obj = json.loads(content)
        except Exception:
            obj = None
        trace = None
        if debug:
            trace = {
                'stage': 'render-refine-format',
                'model': model,
                'messages': messages,
                'response_content': content,
                'usage': _safe_usage(resp)
            }
        if obj and isinstance(obj, dict) and 'render_code' in obj:
            return obj, None, trace
        return None, 'LLM_INVALID_JSON_RETRY', trace
    except Exception as e:
        return None, f'LLM_ERROR: {e}', ({'stage': 'render-refine-format', 'error': str(e)} if debug else None)


def _llm_render_fix_banned(code: str, debug: bool=False):
    """Ask the LLM to minimally edit code to remove banned tokens while preserving behavior. Returns JSON with fields as required."""
    client = current_app.config.get('OPENAI_CLIENT')
    model = current_app.config.get('DEPLOY_CHAT')
    if not client or not model:
        return None, 'LLM_NOT_CONFIGURED', None
    system = (
        "You are a secure code fixer. Given JavaScript for a function named render, remove/replace any banned tokens "
        "(eval, Function, import, fetch, XMLHttpRequest, WebSocket, Worker, SharedArrayBuffer, postMessage, setTimeout, setInterval, storage APIs, document.cookie, window.top/parent, inline on*). "
        "Return STRICT JSON ONLY with keys render_code (full function) and explanatory_text. Do not add markdown or extra fields."
    )
    try:
        payload = {
            'render_code': str(code or '')
        }
        messages = [
            {"role": "system", "content": system},
            {"role": "user", "content": json.dumps(payload)}
        ]
        resp = _chat_json(messages, temperature=0.0, max_tokens=800)
        content = (resp.choices[0].message.content or '').strip()
        try:
            obj = json.loads(content)
        except Exception:
            obj = None
        trace = None
        if debug:
            trace = {
                'stage': 'render-refine-banned',
                'model': model,
                'messages': messages,
                'response_content': content,
                'usage': _safe_usage(resp)
            }
        if obj and isinstance(obj, dict) and 'render_code' in obj:
            return obj, None, trace
        return None, 'LLM_INVALID_JSON_RETRY', trace
    except Exception as e:
        return None, f'LLM_ERROR: {e}', ({'stage': 'render-refine-banned', 'error': str(e)} if debug else None)
