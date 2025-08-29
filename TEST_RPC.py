import os
import sys
import time
import json
import datetime as dt
from typing import Tuple, List, Dict, Any

# Reuse OMAR's socket client
from vista_api import VistaRPCClient, VistaRPCLogger

# Load environment from .env if present
try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    pass

# Collect per-call timings
CALL_TIMINGS: List[Dict[str, Any]] = []


def _param_sig(params: List[Any]) -> str:
    sig = []
    for p in params:
        if isinstance(p, dict):
            sig.append(f"list({len(p)})")
        else:
            s = str(p)
            sig.append(s if len(s) <= 24 else s[:21] + '...')
    return '[' + ', '.join(sig) + ']'


def _record_timing(rpc: str, ctx: str, duration: float, status: str, note: str = '') -> None:
    CALL_TIMINGS.append({
        'rpc': rpc,
        'context': ctx,
        'duration': duration,
        'status': status,
        'note': note,
    })


def _invoke_with_context(vista_client: VistaRPCClient, rpc_name: str, params: List[str], context_candidates: List[str]) -> Tuple[str, str]:
    """Attempt an RPC under one of the provided contexts, similar to the web app's helper.
    Returns (raw_result, used_context).
    """
    last_err = None
    # Minimal serialization using the client's conn_lock if available
    lock = getattr(vista_client, 'conn_lock', None)
    if not lock:
        # Fallback to the instance lock; this is fine in a CLI
        import threading
        lock = threading.RLock()
        try:
            setattr(vista_client, 'conn_lock', lock)
        except Exception:
            pass
    with lock:
        # Ensure connection is alive if method exists
        try:
            if hasattr(vista_client, 'ensure_connected'):
                vista_client.ensure_connected()
        except Exception:
            try:
                vista_client.reconnect()
            except Exception as e:
                last_err = e
        for ctx in context_candidates:
            if not ctx:
                continue
            tries = 0
            while tries < 2:
                try:
                    if hasattr(vista_client, 'call_in_context'):
                        raw = vista_client.call_in_context(rpc_name, params, ctx)
                    else:
                        if getattr(vista_client, 'context', None) != ctx:
                            vista_client.setContext(ctx)
                        raw = vista_client.invokeRPC(rpc_name, params)
                    return raw, ctx
                except Exception as e:
                    last_err = e
                    # Attempt reconnect once on common socket errors
                    try:
                        if hasattr(vista_client, '_is_reconnectable_error') and vista_client._is_reconnectable_error(e):
                            vista_client.reconnect()
                            tries += 1
                            continue
                    except Exception:
                        pass
                    break
    raise Exception(f"All contexts failed for {rpc_name}: {context_candidates}. Last error: {last_err}")


# --- New: Category-specific RPC helpers (first-pass discovery & logging) ---

def _now_utc() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc)


def _to_fileman(dt_obj: dt.datetime) -> str:
    """Convert a datetime to FileMan format YYYMMDD(.HHMMSS)."""
    try:
        z = dt_obj.astimezone(dt.timezone.utc)
        y = z.year - 1700
        return f"{y:03d}{z.month:02d}{z.day:02d}.{z.hour:02d}{z.minute:02d}{z.second:02d}"
    except Exception:
        return ""


def _to_fileman_minute(dt_obj: dt.datetime) -> str:
    """Convert a datetime to FileMan format with minute precision YYYMMDD(.HHMM)."""
    try:
        z = dt_obj.astimezone(dt.timezone.utc)
        y = z.year - 1700
        return f"{y:03d}{z.month:02d}{z.day:02d}.{z.hour:02d}{z.minute:02d}"
    except Exception:
        return ""


def _try_category_rpcs(client: VistaRPCClient, dfn: str, base_context: str) -> Dict[str, Dict[str, Any]]:
    """Try faster, category-specific RPCs. Returns mapping of category -> {
        'rpc': 'NAME', 'context': 'CTX', 'raw': 'raw string', 'ok': bool
    } for each attempted category. Does not attempt to normalize results.
    """
    results: Dict[str, Dict[str, Any]] = {}
    if not dfn:
        # Without DFN, we cannot query patient-scoped data; return empty
        return results
    # Common context candidates prioritizing CPRS
    CPRS_CTX = [base_context, 'OR CPRS GUI CHART', 'JLV WEB SERVICES']
    now = _now_utc()
    six_months_ago = now - dt.timedelta(days=180)
    fm_start = _to_fileman(six_months_ago)
    fm_end = _to_fileman(now)

    # Helper to attempt one RPC with several parameter variants
    def attempt(name: str, ctxs: List[str], param_variants: List[List[str]]) -> Tuple[bool, str, str, str]:
        last_err = None
        for params in param_variants:
            for ctx in ctxs:
                t0 = time.time()
                try:
                    raw, used = _invoke_with_context(client, name, params, [ctx])
                    dt_s = time.time() - t0
                    txt = (raw or '').strip()
                    # Consider empty or obvious error markers as failure
                    if not txt:
                        _record_timing(name, used, dt_s, 'FAIL', _param_sig(params))
                        continue
                    low = txt.lower()
                    if ('error' in low) or ('not registered to the option' in low) or ('<undefined>' in low) or ('application context has not been created' in low) or ("doesn't exist" in low) or ('does not exist' in low):
                        last_err = txt
                        _record_timing(name, used, dt_s, 'FAIL', _param_sig(params))
                        continue
                    _record_timing(name, used, dt_s, 'OK', _param_sig(params))
                    return True, name, used, raw
                except Exception as e:
                    last_err = e
                    _record_timing(name, ctx, time.time() - t0, 'ERROR', f"{_param_sig(params)} | {e}")
                    continue
        # Final attempt failed
        return False, name, ctxs[0] if ctxs else '', f"ERROR: {last_err}"

    # Allergies (unchanged)
    ok, rpcn, used_ctx, raw = attempt('ORQQAL LIST', CPRS_CTX, [[dfn]])
    results['allergies'] = {'rpc': rpcn, 'context': used_ctx, 'raw': raw, 'ok': ok}

    # Problems (unchanged)
    ok, rpcn, used_ctx, raw = attempt('ORQQPL PROBLEM LIST', CPRS_CTX, [[dfn]])
    if not ok:
        ok, rpcn, used_ctx, raw = attempt('ORQQPL ACTIVE PROBLEMS', CPRS_CTX, [[dfn]])
    results['problems'] = {'rpc': rpcn, 'context': used_ctx, 'raw': raw, 'ok': ok}

    # Medications (unchanged)
    ok, rpcn, used_ctx, raw = attempt('ORWPS ACTIVE', CPRS_CTX, [[dfn]])
    if not ok:
        ok, rpcn, used_ctx, raw = attempt('ORWPS ALL', CPRS_CTX, [[dfn]])
    results['medications'] = {'rpc': rpcn, 'context': used_ctx, 'raw': raw, 'ok': ok}

    # Vitals (unchanged)
    ok, rpcn, used_ctx, raw = attempt('ORQQVI VITALS FOR DATE RANGE', CPRS_CTX, [[dfn, fm_start, fm_end]])
    if not ok:
        ok, rpcn, used_ctx, raw = attempt('ORQQVI VITALS', CPRS_CTX, [[dfn]])
    results['vitals'] = {'rpc': rpcn, 'context': used_ctx, 'raw': raw, 'ok': ok}

    # Labs: skipped per user request
    # results['labs'] intentionally omitted

    # Visits (unchanged)
    ok, rpcn, used_ctx, raw = attempt('ORWCV VST', CPRS_CTX, [[dfn, fm_start, fm_end], [dfn]])
    results['visits'] = {'rpc': rpcn, 'context': used_ctx, 'raw': raw, 'ok': ok}

    # Documents: use TIU DOCUMENTS BY CONTEXT with params pattern provided; then fallback to older variants
    TIU_CTX = ['OR CPRS GUI CHART', base_context]
    # As provided by user example: returns last 300 for DFN
    params_last_300 = ['3', '1', dfn, '-1', '-1', '0', '300', 'D', '1', '0', '1', '']
    ok, rpcn, used_ctx, raw = attempt('TIU DOCUMENTS BY CONTEXT', TIU_CTX, [
        params_last_300,
    ])
    if not ok:
        # Previous variants as fallback
        ok, rpcn, used_ctx, raw = attempt('TIU DOCUMENTS BY CONTEXT', TIU_CTX, [
            [dfn, 'ALL', fm_start, fm_end, '200', '1'],  # Ascending=1
            [dfn, 'ALL', fm_start, fm_end, '200', '0'],  # Ascending=0
            [dfn, 'ALL', fm_start, fm_end, '200'],
            [dfn, 'ALL', '', '', '200'],
            [dfn, 'PROGRESS NOTES', fm_start, fm_end, '200', '1'],
            [dfn, 'PROGRESS NOTES', fm_start, fm_end, '200', '0'],
        ])
    results['documents'] = {'rpc': rpcn, 'context': used_ctx, 'raw': raw, 'ok': ok}

    return results


def _build_orwlrr_grid_testlist() -> Dict[str, str]:
    """Return the test list mapping index->"<TestID>^<Name>" for ORWLRR GRID.
    This mirrors the user's CPRS selection.
    """
    return {
        '1': '1^Wbc',
        '2': '1668^Ne %',
        '3': '4^Hct',
        '4': '3^Hgb',
        '5': '5^Mcv',
        '6': '9^Plt',
        '7': '176^Sodium',
        '8': '177^Potassium',
        '9': '178^Chloride',
        '10': '179^Co2',
        '11': '175^Glucose',
        '12': '174^Urea Nitrogen',
        '13': '173^Creatinine ',
        '14': '8479^Egfr 2021',
        '15': '180^Calcium',
        '16': '185^Albumin',
        '17': '186^Tot Bilirubin',
        '18': '188^Alkaline Phosphatase',
        '19': '184^Protein',
        '20': '191^Sgpt',
        '21': '190^Sgot',
        '22': '7701^Anion Gap',
        '23': '1616^Inr',
        '24': '183^Cholesterol',
        '25': '205^Triglycerides',
        '26': '1361^Hdl Cholesterol',
        '27': '901^Ldl, Calculated',
        '28': '5439^Ldl, Direct',
        '29': '5438^Hemoglobin A1c',
        '30': '5550^Microalbumin Excr Ratio',
        '31': '1336^Psa Prostate Specific Ag',
        '32': '7396^Hiv 1/2ab&p24ag Combo Screen',
        '33': '1665^Hepatitis C Antibody ',
    }


def _call_orwlrr_grid_last_year(client: VistaRPCClient, dfn: str, base_context: str) -> Tuple[bool, str, str]:
    """Call ORWLRR GRID for the past year for the user's specified test set.
    Returns (ok, used_context, raw). Falls back to 2x6-month windows on failure.
    """
    now = _now_utc()
    one_year_ago = now - dt.timedelta(days=365)
    # Use minute-precision to mirror working sample
    fm_end = _to_fileman_minute(now)
    fm_start = _to_fileman(one_year_ago)
    tests = _build_orwlrr_grid_testlist()
    params_full = [dfn, fm_end, fm_start, '0', tests]
    ctxs = ['OR CPRS GUI CHART', base_context]
    # First try full year
    t0 = time.time()
    try:
        raw, used = _invoke_with_context(client, 'ORWLRR GRID', params_full, ctxs)
        dt_s = time.time() - t0
        if raw and raw.strip() and 'error' not in raw.lower():
            _record_timing('ORWLRR GRID', used, dt_s, 'OK', _param_sig(params_full))
            return True, used, raw
        _record_timing('ORWLRR GRID', used, dt_s, 'FAIL', _param_sig(params_full))
    except Exception as e:
        _record_timing('ORWLRR GRID', ctxs[0], time.time() - t0, 'ERROR', f"{_param_sig(params_full)} | {e}")
    # Fallback: two 6-month windows
    try:
        mid = now - dt.timedelta(days=180)
        fm_mid = _to_fileman_minute(mid)
        # Window A: last 6 months
        p_a = [dfn, _to_fileman_minute(now), fm_mid, '0', tests]
        # Window B: prior 6 months
        p_b = [dfn, fm_mid, _to_fileman(one_year_ago), '0', tests]
        ok_a = ok_b = False
        used_ctx = ctxs[0]
        agg_raw = ''
        # A
        t1 = time.time()
        try:
            raw_a, used_a = _invoke_with_context(client, 'ORWLRR GRID', p_a, ctxs)
            ok_a = bool(raw_a and raw_a.strip() and 'error' not in raw_a.lower())
            _record_timing('ORWLRR GRID', used_a, time.time() - t1, 'OK' if ok_a else 'FAIL', _param_sig(p_a))
            used_ctx = used_a
            agg_raw += raw_a or ''
        except Exception as e:
            _record_timing('ORWLRR GRID', ctxs[0], time.time() - t1, 'ERROR', f"{_param_sig(p_a)} | {e}")
        # B
        t2 = time.time()
        try:
            raw_b, used_b = _invoke_with_context(client, 'ORWLRR GRID', p_b, ctxs)
            ok_b = bool(raw_b and raw_b.strip() and 'error' not in raw_b.lower())
            _record_timing('ORWLRR GRID', used_b, time.time() - t2, 'OK' if ok_b else 'FAIL', _param_sig(p_b))
            used_ctx = used_b
            agg_raw += ("\n" if agg_raw else "") + (raw_b or '')
        except Exception as e:
            _record_timing('ORWLRR GRID', ctxs[0], time.time() - t2, 'ERROR', f"{_param_sig(p_b)} | {e}")
        return (ok_a and ok_b), used_ctx, agg_raw
    except Exception as e:
        return False, ctxs[0], f"ERROR: {e}"


def _call_orwlrr_grid_last_3months(client: VistaRPCClient, dfn: str, base_context: str) -> Tuple[bool, str, str]:
    """Call ORWLRR GRID for the past 3 months for the user's specified test set.
    Returns (ok, used_context, raw).
    """
    now = _now_utc()
    start = now - dt.timedelta(days=90)
    fm_end = _to_fileman_minute(now)
    fm_start = _to_fileman(start)
    tests = _build_orwlrr_grid_testlist()
    params = [dfn, fm_end, fm_start, '0', tests]
    ctxs = ['OR CPRS GUI CHART', base_context]
    t0 = time.time()
    try:
        raw, used = _invoke_with_context(client, 'ORWLRR GRID', params, ctxs)
        dt_s = time.time() - t0
        ok = bool(raw and raw.strip() and 'error' not in (raw.lower()))
        _record_timing('ORWLRR GRID', used, dt_s, 'OK' if ok else 'FAIL', _param_sig(params))
        return ok, used, raw
    except Exception as e:
        _record_timing('ORWLRR GRID', ctxs[0], time.time() - t0, 'ERROR', f"{_param_sig(params)} | {e}")
        return False, ctxs[0], f"ERROR: {e}"


def _parse_orwcv_lab_raw(raw: str) -> List[Dict[str, Any]]:
    items: List[Dict[str, Any]] = []
    if not raw:
        return items
    for line in raw.splitlines():
        line = line.strip()
        if not line or '^' not in line:
            continue
        parts = line.split('^')
        try:
            ident = parts[0].strip()
            name = (parts[1].strip() if len(parts) > 1 else '')
            fm_date = (parts[2].strip() if len(parts) > 2 else '')
            status = (parts[3].strip() if len(parts) > 3 else '')
            if ident:
                items.append({'id': ident, 'name': name, 'fmDate': fm_date, 'status': status})
        except Exception:
            continue
    return items


def _call_orwcv_lab(client: VistaRPCClient, dfn: str, base_context: str) -> Tuple[bool, str, str, List[Dict[str, Any]]]:
    """Get recent lab accessions/panels for the patient via ORWCV LAB."""
    ctxs = ['OR CPRS GUI CHART', base_context]
    t0 = time.time()
    try:
        raw, used = _invoke_with_context(client, 'ORWCV LAB', [dfn], ctxs)
        dt_s = time.time() - t0
        ok = bool(raw and raw.strip() and 'error' not in raw.lower())
        _record_timing('ORWCV LAB', used, dt_s, 'OK' if ok else 'FAIL', _param_sig([dfn]))
        parsed = _parse_orwcv_lab_raw(raw)
        return ok, used, raw, parsed
    except Exception as e:
        _record_timing('ORWCV LAB', ctxs[0], time.time() - t0, 'ERROR', f"[{dfn}] | {e}")
        return False, ctxs[0], f"ERROR: {e}", []


def _call_orwor_results(client: VistaRPCClient, dfn: str, ids: List[str], base_context: str, limit: int = None) -> Tuple[int, int, str, str]:
    """Call ORWOR RESULT for each id in ids (optionally limited). Returns (ok_count, fail_count, used_context, combined_raw)."""
    ctxs = ['OR CPRS GUI CHART', base_context]
    ok_count = 0
    fail_count = 0
    used_ctx = ctxs[0]
    out_chunks: List[str] = []
    take = ids[:limit] if limit else ids
    for ident in take:
        params = [dfn, '0', ident]
        t0 = time.time()
        try:
            raw, used = _invoke_with_context(client, 'ORWOR RESULT', params, ctxs)
            dt_s = time.time() - t0
            ok = bool(raw and raw.strip() and 'error' not in (raw.lower()))
            _record_timing('ORWOR RESULT', used, dt_s, 'OK' if ok else 'FAIL', _param_sig(params))
            used_ctx = used
            if ok:
                ok_count += 1
            else:
                fail_count += 1
            out_chunks.append(f"===== ORWOR RESULT for {ident} (ctx={used}) =====\n{raw or ''}\n")
        except Exception as e:
            _record_timing('ORWOR RESULT', ctxs[0], time.time() - t0, 'ERROR', f"{_param_sig(params)} | {e}")
            fail_count += 1
            out_chunks.append(f"===== ORWOR RESULT for {ident} (ERROR) =====\n{e}\n")
    return ok_count, fail_count, used_ctx, '\n'.join(out_chunks)


def main():
    # Load config from env (no hardcoded defaults)
    host = os.getenv('VISTA_HOST')
    port_env = os.getenv('VISTA_PORT')
    access = os.getenv('VISTA_ACCESS_CODE')
    verify = os.getenv('VISTA_VERIFY_CODE')
    base_context = os.getenv('VISTA_RPC_CONTEXT')
    dfn = os.getenv('TEST_DFN')  # optional; required for some RPCs

    missing = [k for k, v in [
        ('VISTA_HOST', host),
        ('VISTA_PORT', port_env),
        ('VISTA_ACCESS_CODE', access),
        ('VISTA_VERIFY_CODE', verify),
        ('VISTA_RPC_CONTEXT', base_context)
    ] if not v]
    if missing:
        print('[ERROR] Missing required environment variables:', ', '.join(missing))
        print('Please create a .env file (see .env.example) with your VistA settings, including cipher via VISTARPC_CIPHER or VISTARPC_CIPHER_FILE.')
        raise SystemExit(1)

    try:
        port = int(port_env)
    except Exception:
        print('[ERROR] VISTA_PORT must be an integer')
        raise SystemExit(1)

    logger = VistaRPCLogger()
    client = VistaRPCClient(host, port, access, verify, base_context, logger)

    timings: Dict[str, float] = {}

    try:
        t0 = time.time()
        # Connect/login with base context
        t_connect = time.time()
        client.connect()
        timings['connect'] = time.time() - t_connect

        # Category-specific RPC discovery (only if DFN provided)
        t_cat = time.time()
        cat_results = _try_category_rpcs(client, dfn or '', base_context)
        timings['category_rpcs'] = time.time() - t_cat

        # Labs: optional single ORWOR RESULT call via env
        out_dir = os.path.dirname(os.path.abspath(__file__))
        orwcv_ok, orwcv_ctx, orwcv_raw, labs_list = False, '', '', []
        orwor_single_out_path = ''
        single_lab_id = os.getenv('ORWOR_SINGLE_LAB_ID')
        if dfn and single_lab_id:
            params_single = [dfn, '0', single_lab_id]
            t_orwor_single = time.time()
            try:
                raw_single, orwor_ctx_single = _invoke_with_context(client, 'ORWOR RESULT', params_single, ['OR CPRS GUI CHART', base_context])
                timings['labs_orwor_single'] = time.time() - t_orwor_single
                ok_single = bool(raw_single and raw_single.strip() and 'error' not in raw_single.lower())
                _record_timing('ORWOR RESULT', orwor_ctx_single, timings['labs_orwor_single'], 'OK' if ok_single else 'FAIL', _param_sig(params_single))
            except Exception as e:
                timings['labs_orwor_single'] = time.time() - t_orwor_single
                raw_single = f"ERROR: {e}"
                orwor_ctx_single = 'OR CPRS GUI CHART'
                ok_single = False
                _record_timing('ORWOR RESULT', orwor_ctx_single, timings['labs_orwor_single'], 'ERROR', f"{_param_sig(params_single)} | {e}")
            # Persist raw for the single ORWOR RESULT
            safe_id = single_lab_id.replace(';', '-').replace(':', '-')
            orwor_single_out_path = os.path.join(out_dir, f"DFN{dfn}_ORWOR_RESULT_{safe_id}.txt")
            try:
                with open(orwor_single_out_path, 'w', encoding='utf-8') as f:
                    f.write(raw_single or '')
            except Exception as e:
                print(f"[WARN] Failed to write single ORWOR RESULT raw: {e}")

        # Recent labs index via ORWCV LAB (optional if DFN provided)
        if dfn:
            t_orwcv = time.time()
            orwcv_ok, orwcv_ctx, orwcv_raw, labs_list = _call_orwcv_lab(client, dfn, base_context)
            timings['labs_orwcv_idx'] = time.time() - t_orwcv
            orwcv_out_path = os.path.join(out_dir, f"DFN{dfn}_ORWCV_LAB.raw.txt")
            try:
                with open(orwcv_out_path, 'w', encoding='utf-8') as f:
                    f.write(orwcv_raw or '')
            except Exception as e:
                print(f"[WARN] Failed to write ORWCV LAB raw: {e}")

        # Save raw discovery results to JSON for inspection
        raw_out_path = os.path.join(out_dir, f"DFN{dfn or 'unknown'}_CategoryRPCsRaw.json")
        try:
            with open(raw_out_path, 'w', encoding='utf-8') as f:
                json.dump(cat_results, f, indent=2)
        except Exception as e:
            print(f"[WARN] Failed to write raw JSON: {e}")

        # Build and write concise summary
        summary_lines = []
        summary_lines.append(f"Patient DFN: {dfn or 'unknown'}")
        summary_lines.append(f"Base Context Requested: {base_context}")
        summary_lines.append(f"Connected to {host}:{port} in {timings.get('connect', 0):.2f}s")
        summary_lines.append("")
        summary_lines.append("Category-specific RPC attempts (no VPR fallback):")
        order = [
            'vitals', 'medications', 'allergies', 'problems',
            'visits', 'documents'
        ]
        names = {
            'vitals': 'Vitals',
            'medications': 'Medications',
            'allergies': 'Allergies',
            'problems': 'Problems',
            'visits': 'Visits/Encounters',
            'documents': 'Documents'
        }
        for key in order:
            r = (cat_results or {}).get(key) or {}
            ok = r.get('ok')
            status = 'OK' if ok else 'FAIL'
            rpcn = r.get('rpc') or ''
            ctx = r.get('context') or ''
            summary_lines.append(f"- {names.get(key, key)}: {status} | {rpcn} | context: {ctx}")
        summary_lines.append("")
        if dfn:
            summary_lines.append(f"- Recent Labs Index: {'OK' if orwcv_ok else 'FAIL'} | ORWCV LAB | context: {orwcv_ctx} | {timings.get('labs_orwcv_idx', 0):.2f}s | count: {len(labs_list)}")
            if single_lab_id:
                summary_lines.append(f"- Single Lab Result: {'OK' if 'ok_single' in locals() and ok_single else 'FAIL'} | ORWOR RESULT | id: {single_lab_id} | context: {locals().get('orwor_ctx_single','')} | {timings.get('labs_orwor_single', 0):.2f}s")
                summary_lines.append(f"  Raw: {orwor_single_out_path}")
        summary_lines.append("")

        # Write summary to a clear filename
        sum_path = os.path.join(out_dir, f"DFN{dfn or 'unknown'}_CategoryRPCsSummary.txt")
        with open(sum_path, 'w', encoding='utf-8') as f:
            f.write('\n'.join(summary_lines) + '\n')

        # Also print to console
        print('\n'.join(summary_lines))

        # Write per-call timings report and print top 5 slowest
        timings_path = os.path.join(out_dir, f"DFN{dfn or 'unknown'}_RPCCallTimings.txt")
        try:
            sorted_calls = sorted(CALL_TIMINGS, key=lambda x: x.get('duration', 0), reverse=True)
            lines = [
                f"{c['duration']:.3f}s | {c['status']:5} | {c['rpc']} | ctx={c['context']} | {c.get('note','')}"
                for c in sorted_calls
            ]
            with open(timings_path, 'w', encoding='utf-8') as f:
                f.write('\n'.join(lines) + '\n')
            print("\nTop 5 slowest calls:")
            for c in sorted_calls[:5]:
                print(f"  {c['duration']:.3f}s | {c['status']:5} | {c['rpc']} | ctx={c['context']} | {c.get('note','')}")
            print(f"\nDetailed timings: {timings_path}")
        except Exception as e:
            print(f"[WARN] Failed to write timings report: {e}")

    except Exception as e:
        print(f"[ERROR] {e}")
        sys.exit(1)
    finally:
        try:
            client.close()
        except Exception:
            pass


if __name__ == '__main__':
    main()
