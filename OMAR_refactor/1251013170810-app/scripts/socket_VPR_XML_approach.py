"""Archived reference of the pre-transition VPR XML socket gateway.

This module intentionally preserves the full source of the prior implementation
that issued `VPR GET PATIENT DATA` (XML) calls and performed XML normalization
before exposing domain payloads.  It also embeds the companion VPR XML parser
utility so that future comparisons or reversions can be performed without
trawling git history.  The content is stored as raw strings for reference and is
not imported anywhere in the runtime path.
"""

SOCKET_GATEWAY_SOURCE = r'''from __future__ import annotations
import os
import socket
import time
import json
import threading
from datetime import datetime, timezone
from typing import Any, Dict, Optional, Tuple, List

try:
    import xmltodict  # type: ignore
except Exception:
    xmltodict = None  # soft dependency; validated at runtime

from .data_gateway import DataGateway, GatewayError
from .vpr_xml_parser import parse_vpr_results_xml, DOMAIN_TAGS


def _coerce_boolish(val: Any) -> Any:
    if isinstance(val, str):
        trimmed = val.strip().lower()
        if trimmed in ('true', 'false'):
            return trimmed == 'true'
        if trimmed in ('1', '0'):
            return trimmed == '1'
    return val


def _fileman_date_to_ymd(val: Any) -> Optional[int]:
    try:
        s = str(val or '').strip()
        if not s:
            return None
        if '.' in s:
            s = s.split('.', 1)[0]
        if not s.isdigit():
            return None
        if len(s) == 8:
            return int(s)
        if len(s) == 7:
            yyy = int(s[0:3])
            month = int(s[3:5])
            day = int(s[5:7])
            year = yyy + 1700
            return year * 10000 + month * 100 + day
    except Exception:
        return None
    return None


def _fileman_datetime_to_iso(val: Any) -> Optional[str]:
    try:
        s = str(val or '').strip()
        if not s:
            return None
        head = s
        tail = ''
        if '.' in s:
            head, tail = s.split('.', 1)
        elif len(s) > 7 and s[:7].isdigit():
            head = s[:7]
            tail = s[7:]
        if not head.isdigit() or len(head) != 7:
            return None
        year = int(head[0:3]) + 1700
        month = int(head[3:5])
        day = int(head[5:7])
        digits = ''.join(ch for ch in tail if ch.isdigit())
        hour = int(digits[0:2]) if len(digits) >= 2 else 0
        minute = int(digits[2:4]) if len(digits) >= 4 else 0
        second = int(digits[4:6]) if len(digits) >= 6 else 0
        stamp = datetime(year, month, day, hour, minute, second, tzinfo=timezone.utc)
        return stamp.isoformat().replace('+00:00', 'Z')
    except Exception:
        return None


def _to_fileman_datetime(val: Any) -> Optional[str]:
    try:
        if val is None:
            return None
        s = str(val).strip()
        if not s:
            return None
        if s.isdigit() and len(s) == 7:
            return s
        if '.' in s:
            head, tail = s.split('.', 1)
            digits = ''.join(ch for ch in tail if ch.isdigit())
            if head.isdigit() and len(head) == 7:
                if digits:
                    return head + '.' + digits
                return head
        # ISO date/time handling
        try:
            iso = s.replace('Z', '+00:00')
            ts = datetime.fromisoformat(iso)
            year = ts.year
            yyy = year - 1700
            if yyy < 0:
                return None
            date_part = f"{yyy:03d}{ts.month:02d}{ts.day:02d}"
            if ts.hour or ts.minute or ts.second:
                if ts.second:
                    return f"{date_part}.{ts.hour:02d}{ts.minute:02d}{ts.second:02d}"
                return f"{date_part}.{ts.hour:02d}{ts.minute:02d}"
            return date_part
        except Exception:
            pass
        digits = ''.join(ch for ch in s if ch.isdigit())
        if len(digits) >= 8:
            year = int(digits[0:4])
            month = int(digits[4:6])
            day = int(digits[6:8])
            yyy = year - 1700
            date_part = f"{yyy:03d}{month:02d}{day:02d}"
            if len(digits) >= 12:
                hour = int(digits[8:10])
                minute = int(digits[10:12])
                if len(digits) >= 14:
                    second = int(digits[12:14])
                    return f"{date_part}.{hour:02d}{minute:02d}{second:02d}"
                return f"{date_part}.{hour:02d}{minute:02d}"
            return date_part
        return None
    except Exception:
        return None


def _looks_like_fileman_datetime(val: Any) -> bool:
    try:
        s = str(val or '').strip()
        if not s:
            return False
        if '.' in s:
            head, tail = s.split('.', 1)
            if not head.isdigit() or len(head) != 7:
                return False
            digits = ''.join(ch for ch in tail if ch.isdigit())
            return bool(digits) or tail == ''
        return s.isdigit() and len(s) == 7
    except Exception:
        return False


def _strip_xml_attrs(obj: Any) -> Any:
    if isinstance(obj, dict):
        result: Dict[str, Any] = {}
        text_value: Any = None
        for key, value in obj.items():
            if key == '#text':
                text_value = _strip_xml_attrs(value)
                continue
            cleaned = _strip_xml_attrs(value)
            if key.startswith('@'):
                result[key[1:]] = cleaned
            else:
                result[key] = cleaned
        if text_value is not None:
            if result:
                result.setdefault('value', text_value)
            else:
                return text_value
        if len(result) == 1 and 'value' in result:
            single = result['value']
            return _coerce_boolish(single)
        return {k: (_coerce_boolish(v) if not isinstance(v, (dict, list)) else v) for k, v in result.items()}
    if isinstance(obj, list):
        return [_strip_xml_attrs(v) for v in obj]
    return _coerce_boolish(obj)


_COLLECTION_CHILD_MAP: Dict[str, str] = {
    'addresses': 'address',
    'comments': 'comment',
    'drugClasses': 'drugClass',
    'drugIngredients': 'drugIngredient',
    'eligibilities': 'eligibility',
    'ethnicities': 'ethnicity',
    'exposures': 'exposure',
    'facilities': 'facility',
    'flags': 'flag',
    'patients': 'patient',
    'products': 'product',
    'providers': 'provider',
    'reactions': 'reaction',
    'results': 'result',
    'supports': 'support',
    'telecomList': 'telecom',
    'telecoms': 'telecom',
    'orders': 'order',
    'doses': 'dose',
    'fills': 'fill',
    'participants': 'participant',
    'documents': 'document',
    'notes': 'note',
    'immunizations': 'immunization',
}

_COLLECTION_RENAME: Dict[str, str] = {
    'telecomList': 'telecoms',
}


def _normalize_collections(obj: Any) -> Any:
    if isinstance(obj, dict):
        for key in list(obj.keys()):
            obj[key] = _normalize_collections(obj[key])
        for key in list(obj.keys()):
            child_key = _COLLECTION_CHILD_MAP.get(key)
            if not child_key:
                continue
            rename_to = _COLLECTION_RENAME.get(key, key)
            value = obj[key]
            if isinstance(value, dict) and child_key in value:
                payload = value[child_key]
            else:
                payload = value
            if payload is None:
                seq: List[Any] = []
            elif isinstance(payload, list):
                seq = payload
            else:
                seq = [payload]
            obj[rename_to] = [_normalize_collections(item) for item in seq]
            if rename_to != key:
                del obj[key]
            else:
                obj[key] = obj[rename_to]
        return obj
    if isinstance(obj, list):
        return [_normalize_collections(v) for v in obj]
    return obj


def _normalize_telecom_entry(entry: Dict[str, Any]) -> Dict[str, Any]:
    out = dict(entry)
    if 'value' in out and 'telecom' not in out:
        out['telecom'] = out.pop('value')
    if 'usageType' in out and 'usageCode' not in out:
        usage = str(out.pop('usageType'))
        out['usageCode'] = usage
    if 'usageCode' in out and 'usageName' not in out:
        code = str(out['usageCode']).upper()
        usage_names = {
            'MC': 'mobile contact',
            'CP': 'cell phone',
            'H': 'home',
            'HP': 'home phone',
            'WP': 'work place',
            'EC': 'emergency contact',
        }
        if code in usage_names:
            out['usageName'] = usage_names[code]
    return out


def _normalize_telecoms_recursive(obj: Any) -> Any:
    if isinstance(obj, dict):
        for key, value in list(obj.items()):
            if key == 'telecoms' and isinstance(value, list):
                obj[key] = [_normalize_telecom_entry(v) if isinstance(v, dict) else v for v in value]
            else:
                obj[key] = _normalize_telecoms_recursive(value)
        return obj
    if isinstance(obj, list):
        return [_normalize_telecoms_recursive(v) for v in obj]
    return obj


def _normalize_patient_item(item: Dict[str, Any]) -> Dict[str, Any]:
    data = dict(item)
    if 'bid' in data and 'briefId' not in data:
        data['briefId'] = data.pop('bid')
    dob_val = None
    if 'dob' in data:
        dob_val = data.pop('dob')
    if 'dateOfBirth' not in data and dob_val is not None:
        converted = _fileman_date_to_ymd(dob_val)
        data['dateOfBirth'] = converted if converted is not None else dob_val
    if 'id' in data and 'localId' not in data:
        data['localId'] = data.pop('id')
    if isinstance(data.get('localId'), str) and data['localId'].isdigit():
        try:
            data['localId'] = int(data['localId'])
        except Exception:
            pass
    if 'gender' in data and 'genderName' not in data:
        gender_val = data.pop('gender')
        if isinstance(gender_val, dict):
            gender_code = gender_val.get('code') or gender_val.get('value')
            gender_text = gender_val.get('name') or gender_val.get('value')
        else:
            gender_code = str(gender_val)
            gender_text = str(gender_val)
        if gender_code:
            upper_code = str(gender_code).upper()
            code_map = {
                'M': ('urn:va:pat-gender:M', 'Male'),
                'F': ('urn:va:pat-gender:F', 'Female'),
                'U': ('urn:va:pat-gender:U', 'Unknown'),
                'O': ('urn:va:pat-gender:O', 'Other'),
            }
            match = code_map.get(upper_code)
            if match:
                data.setdefault('genderCode', match[0])
                data['genderName'] = match[1]
            else:
                data['genderName'] = gender_text
        elif gender_text:
            data['genderName'] = gender_text
    language = data.pop('language', None)
    if isinstance(language, dict):
        if language.get('name'):
            data.setdefault('languageName', language['name'])
        if language.get('code'):
            data.setdefault('languageCode', language['code'])
    marital = data.pop('maritalStatus', None)
    if marital:
        entry: Dict[str, Any] = {}
        if isinstance(marital, dict):
            code_val = marital.get('code') or marital.get('value')
            name_val = marital.get('name') or marital.get('value')
            if code_val:
                entry['code'] = code_val
            if name_val:
                entry['name'] = name_val
        else:
            entry['name'] = marital
        if entry:
            data.setdefault('maritalStatuses', []).append(entry)
    if 'address' in data and 'addresses' not in data:
        addr = data.pop('address')
        if isinstance(addr, list):
            data['addresses'] = addr
        elif addr is None:
            data['addresses'] = []
        else:
            data['addresses'] = [addr]
    if 'telecomList' in data and 'telecoms' not in data:
        holder = data.pop('telecomList')
        if isinstance(holder, dict) and 'telecom' in holder:
            tele = holder['telecom']
        else:
            tele = holder
        if tele is None:
            data['telecoms'] = []
        elif isinstance(tele, list):
            data['telecoms'] = tele
        else:
            data['telecoms'] = [tele]
    if 'telecoms' in data:
        data['telecoms'] = [_normalize_telecom_entry(t) for t in data['telecoms'] if isinstance(t, dict)]
    if 'inpatient' in data:
        data['inpatient'] = _coerce_boolish(data['inpatient'])
    veteran_blob = data.pop('veteran', None)
    veteran: Dict[str, Any] = {}
    if veteran_blob is not None:
        veteran['isVet'] = 1 if _coerce_boolish(veteran_blob) else 0
    if 'lrdfn' in data:
        veteran['lrdfn'] = data.pop('lrdfn')
    if 'sc' in data:
        sc_val = _coerce_boolish(data.pop('sc'))
        if sc_val is not None:
            veteran['serviceConnected'] = bool(sc_val)
    if 'scPercent' in data:
        sc_percent = data.pop('scPercent')
        try:
            veteran['serviceConnectionPercent'] = int(sc_percent)
        except Exception:
            veteran['serviceConnectionPercent'] = sc_percent
    if veteran:
        data['veteran'] = veteran
    if 'sensitive' in data:
        data['sensitive'] = bool(_coerce_boolish(data['sensitive']))
    return _normalize_telecoms_recursive(data)


def _normalize_domain_item(domain: Optional[str], item: Dict[str, Any]) -> Dict[str, Any]:
    base = _strip_xml_attrs(item)
    base = _normalize_collections(base)
    if domain == 'patient':
        return _normalize_patient_item(base)
    if domain == 'problem' and isinstance(base, dict):
        status_val = base.get('status')
        if isinstance(status_val, dict):
            name = status_val.get('name') or status_val.get('value') or status_val.get('status')
            code = status_val.get('code') or status_val.get('abbr')
            if name and not base.get('statusName'):
                base['statusName'] = name
            if code and not base.get('statusCode'):
                base['statusCode'] = code
            if name:
                base['status'] = name
            elif code:
                base['status'] = code
        elif isinstance(status_val, str):
            base.setdefault('statusName', status_val)
        return base
    if isinstance(base, dict):
        if 'telecomList' in base and 'telecoms' not in base:
            holder = base.pop('telecomList')
            if isinstance(holder, dict) and 'telecom' in holder:
                tele = holder['telecom']
            else:
                tele = holder
            if tele is None:
                base['telecoms'] = []
            elif isinstance(tele, list):
                base['telecoms'] = tele
            else:
                base['telecoms'] = [tele]
        base = _normalize_telecoms_recursive(base)
    else:
        base = _normalize_telecoms_recursive(base)
    return base


# ---- Minimal Vista RPC client adapted for OMAR_refactor ----

class _VistaRPCLogger:
    def info(self, tag: str, msg: str):
        try:
            print(f"[INFO] {tag}: {msg}")
        except Exception:
            pass
    def error(self, tag: str, msg: str):
        try:
            print(f"[ERROR] {tag}: {msg}")
        except Exception:
            pass


def _parse_cipher_blob(blob: str) -> Optional[List[str]]:
    if not blob:
        return None
    txt = blob.strip()
    # Try JSON list first
    try:
        data = json.loads(txt)
        if isinstance(data, list) and all(isinstance(x, str) for x in data) and len(data) >= 2:
            return data
    except Exception:
        pass
    # Fallback newline rows
    rows = [ln for ln in txt.replace('\r','').split('\n') if ln.strip()]
    if len(rows) >= 2:
        return rows
    return None


def _load_cipher_from_env() -> List[str]:
    path = os.getenv('VISTARPC_CIPHER_FILE')
    if path and os.path.exists(path):
        try:
            with open(path, 'r', encoding='utf-8') as f:
                parsed = _parse_cipher_blob(f.read())
            if parsed:
                return parsed
        except Exception:
            pass
    blob = os.getenv('VISTARPC_CIPHER')
    parsed = _parse_cipher_blob(blob or '')
    if parsed:
        return parsed
    raise GatewayError('VISTARPC_CIPHER not configured. Set VISTARPC_CIPHER or VISTARPC_CIPHER_FILE to the cipher table.')


class _VistaRPCClient:
    CIPHER: Optional[List[str]] = None

    def __init__(self, host: str, port: int, access: str, verify: str, context: str, logger: Optional[_VistaRPCLogger] = None):
        self.host = host
        self.port = int(port)
        self.access = access
        self.verify = verify
        self.context = context
        self.sock: Optional[socket.socket] = None
        self.logger = logger or _VistaRPCLogger()
        self._end = chr(4)
        # Single socket connection must be serialized across threads to avoid context mix-ups and interleaved frames.
        self._lock = threading.RLock()

    # --- Wire protocol helpers (trimmed) ---
    def _get_cipher(self) -> List[str]:
        if not _VistaRPCClient.CIPHER:
            _VistaRPCClient.CIPHER = _load_cipher_from_env()
        return _VistaRPCClient.CIPHER  # type: ignore

    def _encrypt(self, val: str) -> bytes:
        import random
        cipher = self._get_cipher()
        ra = random.randint(0, len(cipher) - 1)
        rb = random.randint(0, len(cipher) - 1)
        while rb == ra or rb == 0:
            rb = random.randint(0, len(cipher) - 1)
        cra = cipher[ra]
        crb = cipher[rb]
        cval = chr(ra + 32)
        for c in val:
            idx = cra.find(c)
            cval += (crb[idx] if idx != -1 else c)
        cval += chr(rb + 32)
        return cval.encode('utf-8')

    def _make_request(self, name: str, params: List[Any], is_command: bool = False) -> str:
        proto = "[XWB]1130"
        command = ("4" if is_command else ("2" + chr(1) + "1"))
        namespec = chr(len(name)) + name
        if not params:
            params_spec = "54f"
        else:
            params_spec = "5"
            for p in params:
                s = json.dumps(p) if isinstance(p, dict) else str(p)
                b = s.encode('utf-8')
                params_spec += "0" + str(len(b)).zfill(3) + s
            params_spec += "f"
        return proto + command + namespec + params_spec + self._end

    def _read_to_end(self) -> str:
        chunks: List[str] = []
        while True:
            if not self.sock:
                raise OSError('socket not connected')
            buf = self.sock.recv(256)
            if not buf:
                raise OSError('socket closed')
            part = buf.decode('utf-8', errors='replace')
            # Some Broker responses prefix one or two NULL (\x00) bytes.
            # Previous logic stripped two bytes unconditionally when the first was NULL,
            # which could truncate the first real character (e.g. 'J' in 'JLV WEB SERVICES').
            # Fix: remove only the leading NULL bytes while preserving the first non-NULL.
            if not chunks and part.startswith("\x00"):
                if part.startswith("\x00\x00"):
                    part = part[2:]  # double null prefix
                else:
                    part = part[1:]  # single null prefix
            if part and part[-1] == self._end:
                chunks.append(part[:-1])
                break
            chunks.append(part)
        return ''.join(chunks)

    def connect(self):
        with self._lock:
            # Fresh socket each time
            if self.sock:
                try:
                    self.sock.close()
                except Exception:
                    pass
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            # Basic keepalive
            try:
                self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)
            except Exception:
                pass
            self.sock.connect((self.host, self.port))
            self.logger.info('VistaRPC', f'Connected {self.host}:{self.port}')
            # Handshake
            tcp_params = [socket.gethostbyname(socket.gethostname()), "0", "FMQL"]
            self.sock.send(self._make_request('TCPConnect', tcp_params, True).encode('utf-8'))
            rep = self._read_to_end()
            if 'accept' not in rep:
                raise GatewayError(f'TCPConnect failed: {rep}')
            # Signon setup
            self.sock.send(self._make_request('XUS SIGNON SETUP', []).encode('utf-8'))
            _ = self._read_to_end()
            enc = self._encrypt(self.access + ';' + self.verify).decode()
            self.sock.send(self._make_request('XUS AV CODE', [enc]).encode('utf-8'))
            rep = self._read_to_end()
            if 'Not a valid ACCESS CODE/VERIFY CODE pair' in rep:
                raise GatewayError('Login failed: invalid ACCESS/VERIFY')
            # default context (plaintext then encrypted fallback)
            self._set_context_locked(self.context)

    def close(self):
        with self._lock:
            try:
                if self.sock:
                    try:
                        self.sock.send('#BYE#'.encode('utf-8'))
                    except Exception:
                        pass
                    self.sock.close()
            finally:
                self.sock = None

    def _set_context_locked(self, ctx: str):
        if not self.sock:
            raise OSError('socket not connected')
        self.sock.send(self._make_request('XWB CREATE CONTEXT', [ctx]).encode('utf-8'))
        rep = self._read_to_end()
        if ('has not been created' in rep) or ('does not exist' in rep):
            ectx = self._encrypt(ctx).decode()
            self.sock.send(self._make_request('XWB CREATE CONTEXT', [ectx]).encode('utf-8'))
            rep = self._read_to_end()
            if ('has not been created' in rep) or ('does not exist' in rep):
                raise GatewayError(f'Context failed: {rep}')
        self.context = ctx
        try:
            self.logger.info('VistaRPC', f"Context set to '{ctx}'")
        except Exception:
            pass

    def set_context(self, ctx: str):
        with self._lock:
            self._set_context_locked(ctx)

    def invoke(self, name: str, params: List[Any]) -> str:
        with self._lock:
            return self._invoke_locked(name, params)

    def _invoke_locked(self, name: str, params: List[Any]) -> str:
        if not self.sock:
            raise OSError('socket not connected')
        self.sock.send(self._make_request(name, params, False).encode('utf-8'))
        return self._read_to_end()

    def call_in_context(self, ctx: str, name: str, params: List[Any]) -> str:
        with self._lock:
            cur = self.context
            if ctx != cur:
                self._set_context_locked(ctx)
            try:
                return self._invoke_locked(name, params)
            finally:
                if ctx != cur:
                    self._set_context_locked(cur)


# ---- VistaSocketGateway ----

def _ensure_xml_lib():
    if xmltodict is None:
        raise GatewayError("xmltodict is required for socket gateway XML parsing. Add 'xmltodict' to requirements.")


def _normalize_vpr_xml_to_items(xml_text: str, domain: Optional[str] = None) -> Dict[str, Any]:
    """Parse generic VPR XML payload into normalized items using domain heuristics."""
    _ensure_xml_lib()
    text = (xml_text or '').strip()
    if not text:
        return {'items': []}
    lower = text.lower()
    if '<results' in lower:
        try:
            parsed = parse_vpr_results_xml(text, domain=domain)
            items = parsed.get('items') if isinstance(parsed, dict) else []
            normalized_items: List[Dict[str, Any]] = []
            if isinstance(items, list):
                for entry in items:
                    if isinstance(entry, dict):
                        normalized_items.append(_normalize_domain_item(domain, entry))
                    else:
                        normalized_items.append({'value': entry})
            result: Dict[str, Any] = {'items': normalized_items}
            if isinstance(parsed, dict) and parsed.get('meta'):
                result['meta'] = parsed['meta']
            return result
        except Exception:
            pass
    try:
        parsed = xmltodict.parse(text)  # type: ignore[attr-defined]
    except Exception as exc:
        raise GatewayError(f'Failed to parse VPR XML: {exc}')
    data_section: Optional[Any] = None
    if isinstance(parsed, dict):
        data_section = parsed.get('data') or parsed.get('Data')
    if not isinstance(data_section, dict):
        items_raw: List[Any]
        if isinstance(parsed, list):
            items_raw = parsed
        else:
            items_raw = [parsed]
    else:
        wrapper = data_section.get('items') or data_section.get('Items')
        if isinstance(wrapper, dict):
            items_candidate = wrapper.get('item') or wrapper.get('Item')
        else:
            items_candidate = wrapper
        if items_candidate is None:
            items_raw = []
        elif isinstance(items_candidate, list):
            items_raw = items_candidate
        else:
            items_raw = [items_candidate]
    normalized_items: List[Dict[str, Any]] = []
    for entry in items_raw:
        if isinstance(entry, dict):
            normalized_items.append(_normalize_domain_item(domain, entry))
        else:
            normalized_items.append({'value': entry})
    return {'items': normalized_items}


class VistaSocketGateway(DataGateway):
    """Gateway that calls VistA directly via the Broker socket.
    For patient data, uses JLV WEB SERVICES context to call VPR GET PATIENT DATA (XML),
    then normalizes to a JSON-like dict with 'items' to feed existing transforms.
    For general CPRS flows (patient search, sensitive check), uses OR CPRS GUI CHART.
    """

    def __init__(self, *, host: str, port: int, access: str, verify: str,
                 default_context: Optional[str] = None,
                 vpr_context: Optional[str] = None):
        self.host = host
        self.port = int(port)
        self.access = access
        self.verify = verify
        self.default_context = default_context or os.getenv('VISTA_DEFAULT_CONTEXT') or 'OR CPRS GUI CHART'
        # JLV for VPR XML
        self.vpr_context = vpr_context or 'JLV WEB SERVICES'
        self._logger = _VistaRPCLogger()
        self._client = _VistaRPCClient(host, int(port), access, verify, self.default_context, self._logger)
        self._connected = False

    # ---- lifecycle ----
    def connect(self):
        if not self._connected:
            self._client.connect()
            self._connected = True

    def close(self):
        try:
            self._client.close()
        finally:
            self._connected = False

    def _context_for_domain(self, domain: Optional[str]) -> str:
        # Document text retrieval needs OR CPRS GUI CHART privileges to surface full note bodies.
        if domain == 'document':
            return self.default_context
        return self.vpr_context

    # ---- Generic RPC ----
    def call_rpc(self, *, context: str, rpc: str, parameters: Optional[list[dict]] = None, json_result: bool = False, timeout: int = 60) -> Any:  # type: ignore[override]
        self.connect()
        # Socket path ignores timeout here (blocking socket). Could add per-call timeouts via settimeout.
        params = []
        for p in (parameters or []):
            # vista-api-x accepts dicts like {'string': '...'}; socket expects literal params list
            if 'string' in p:
                params.append(str(p.get('string') or ''))
            elif 'literal' in p:
                params.append(str(p.get('literal') or ''))
            elif 'namedArray' in p:
                params.append(p.get('namedArray') or {})
            else:
                params.append(p)
        raw = self._client.call_in_context(context, rpc, params)
        # vista-api-x sometimes returns wrapper JSON; socket returns raw caret/newline strings
        if json_result:
            try:
                return json.loads(raw)
            except Exception:
                return {'raw': raw}
        return raw

    # ---- VPR helpers ----
    def _vpr_named_array(self, dfn: str, domain: Optional[str] = None, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        body: Dict[str, Any] = { 'patientId': str(dfn) }
        if domain:
            body['domain'] = str(domain)
        if params and isinstance(params, dict):
            # Pass through whitelisted keys only; server ignores unknowns
            for k, v in params.items():
                if v is not None:
                    body[str(k)] = v
        return body

    def get_demographics(self, dfn: str) -> Dict[str, Any]:
        # Fetch via VPR XML patient domain and normalize
        return self.get_vpr_domain(dfn, domain='patient')

    def get_vpr_domain(self, dfn: str, domain: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:  # type: ignore[override]
        """Fetch a single domain via VPR GET PATIENT DATA (XML).

        Strategy:
        1. Prefer the native positional parameter signature (DFN, TYPE, START, STOP, MAX, ITEM, FILTER list)
           because the RPC definition (Vivian site 8994-2917) expects ordered literals.
        2. If the positional call yields a <results> domain section, parse with parse_vpr_results_xml.
        3. Fallback to legacy namedArray invocation then normalize with _normalize_vpr_xml_to_items.
        """
        if domain == 'document':
            return self._get_tiu_document_domain(dfn, params)
        self.connect()
        # Map internal domain name to TYPE value (RPC expects semicolon-delimited kinds). For single domain we send one.
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
        positional_params: List[Any] = [str(dfn)]
        if type_val:
            positional_params.append(type_val)
        # Optional future: map params keys start/stop/max/item/filter -> append in order. Presently only support start/stop/max.
        if params and isinstance(params, dict):
            # START (3rd), STOP (4th), MAX (5th), ITEM (6th) - maintain order by placeholders if earlier ones missing.
            start = params.get('start') or params.get('START')
            stop = params.get('stop') or params.get('STOP')
            max_items = params.get('max') or params.get('MAX')
            item_id = params.get('item') or params.get('ITEM')
            # Append respecting sequence; blank values become '' to preserve positional alignment only when later params used.
            if any(v is not None for v in (start, stop, max_items, item_id)):
                positional_params.append(str(start) if start else '')
                positional_params.append(str(stop) if stop else '')
                positional_params.append(str(max_items) if max_items else '')
                positional_params.append(str(item_id) if item_id else '')
            # FILTER list unsupported here; would require list param structure; leave for future.
        context = self._context_for_domain(domain)
        self._logger.info('VistaSocketGateway', f"Invoking VPR GET PATIENT DATA (positional) for domain '{domain}' TYPE='{type_val}' (DFN {dfn}) using context '{context}'")
        raw_xml_positional = ''
        try:
            raw_xml_positional = self._client.call_in_context(context, 'VPR GET PATIENT DATA', positional_params)
            parsed_results = parse_vpr_results_xml(raw_xml_positional, domain=domain)
            if parsed_results.get('items'):  # Successful domain parse
                return self._wrap_domain_response(domain, dfn, parsed_results)
        except Exception as e:
            self._logger.error('VistaSocketGateway', f"Positional domain call failed: {e}")
        # Fallback: namedArray approach used previously
        named = self._vpr_named_array(dfn, domain=domain, params=params)
        self._logger.info('VistaSocketGateway', f"Fallback namedArray invocation for domain '{domain}' (DFN {dfn}) using context '{context}'")
        raw_xml = self._client.call_in_context(context, 'VPR GET PATIENT DATA', [ { 'namedArray': named } ])
        # Try results parser second time (some deployments may still return <results>)
        try:
            parsed_results_2 = parse_vpr_results_xml(raw_xml, domain=domain)
            if parsed_results_2.get('items'):
                return self._wrap_domain_response(domain, dfn, parsed_results_2)
        except Exception:
            pass
        legacy = _normalize_vpr_xml_to_items(raw_xml, domain)
        return self._wrap_domain_response(domain, dfn, legacy)

        def _get_tiu_document_domain(self, dfn: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
            """Build a VPR-shaped response for documents using TIU RPCs only."""
            try:
                items = self._fetch_tiu_document_index(dfn, params=params)
            except Exception as exc:
                raise GatewayError(f'TIU DOCUMENTS failed for DFN {dfn}: {exc}')
            total = len(items)
            meta: Dict[str, Any] = {
                'domain': 'document',
                'dfn': str(dfn),
                'source': 'TIU DOCUMENTS',
                'total': total,
            }
            if params:
                for key in ('start', 'stop', 'max', 'status'):
                    if key in params and params[key] is not None:
                        meta[key] = params[key]
            data_block = {
                'items': items,
                'totalItems': total,
            }
            return {
                'items': items,
                'meta': meta,
                'data': data_block,
            }

        def _fetch_tiu_document_index(self, dfn: str, params: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
            self.connect()
            start_param = None
            stop_param = None
            status_param = None
            max_results = 200
            if params:
                start_param = params.get('start') or params.get('START')
                stop_param = params.get('stop') or params.get('STOP')
                status_param = params.get('status') or params.get('STATUS')
                try:
                    if params.get('max') or params.get('MAX'):
                        max_results = int(str(params.get('max') or params.get('MAX')))
                except Exception:
                    pass
            start_fm = _to_fileman_datetime(start_param) if start_param else ''
            stop_fm = _to_fileman_datetime(stop_param) if stop_param else ''
            if start_fm and not stop_fm:
                stop_fm = ''
            status_filter = ''
            if status_param:
                if isinstance(status_param, (list, tuple)):
                    status_filter = ';'.join(str(s) for s in status_param if s)
                else:
                    status_filter = str(status_param)
            rpc_params: List[Any] = [
                str(dfn),
                '[CLINICAL DOCUMENTS]',
                start_fm or '',
                stop_fm or '',
                '-1',  # newest first
                str(max_results),
                '',   # pagination placeholder (FROM IEN)
                status_filter,
            ]
            self._logger.info('VistaSocketGateway', f"Invoking TIU DOCUMENTS for DFN {dfn} (max {max_results})")
            raw = self._client.call_in_context(self.default_context, 'TIU DOCUMENTS', rpc_params)
            return self._parse_tiu_document_index(raw)

        def _parse_tiu_document_index(self, payload: Any) -> List[Dict[str, Any]]:
            text = payload if isinstance(payload, str) else str(payload or '')
            if not text:
                return []
            lines = [ln.strip() for ln in text.replace('\r', '').split('\n') if ln.strip()]
            items: List[Dict[str, Any]] = []
            for line in lines:
                if line.startswith('~'):
                    # CPRS prepends tildes for header/grouping rows; skip them.
                    continue
                parsed = self._parse_tiu_document_line(line)
                if parsed:
                    items.append(parsed)
            return items

        def _parse_tiu_document_line(self, line: str) -> Optional[Dict[str, Any]]:
            parts = [seg.strip() for seg in line.split('^')]
            if not parts:
                return None
            doc_id = parts[0]
            if not doc_id:
                return None
            ref_idx: Optional[int] = None
            reference_iso: Optional[str] = None
            for idx in range(1, len(parts)):
                if _looks_like_fileman_datetime(parts[idx]):
                    ref_idx = idx
                    reference_iso = _fileman_datetime_to_iso(parts[idx])
                    break
            if ref_idx is None and len(parts) > 2 and _looks_like_fileman_datetime(parts[2]):
                ref_idx = 2
                reference_iso = _fileman_datetime_to_iso(parts[2])
            title = ''
            if ref_idx is not None:
                if ref_idx >= 2:
                    title = parts[ref_idx - 1]
                elif ref_idx + 1 < len(parts):
                    title = parts[ref_idx + 1]
            elif len(parts) > 1:
                title = parts[1]
            status = parts[ref_idx + 1] if (ref_idx is not None and ref_idx + 1 < len(parts)) else ''
            author = parts[ref_idx + 2] if (ref_idx is not None and ref_idx + 2 < len(parts)) else ''
            facility = parts[ref_idx + 3] if (ref_idx is not None and ref_idx + 3 < len(parts)) else ''
            doc_class = parts[ref_idx + 4] if (ref_idx is not None and ref_idx + 4 < len(parts)) else ''
            doc_type = parts[ref_idx + 5] if (ref_idx is not None and ref_idx + 5 < len(parts)) else ''
            encounter = parts[ref_idx + 6] if (ref_idx is not None and ref_idx + 6 < len(parts)) else ''
            item: Dict[str, Any] = {
                'id': doc_id,
                'localId': doc_id,
                'uid': f'urn:va:document:{doc_id}',
            }
            if title:
                item['localTitle'] = title
            if doc_type:
                item['documentTypeName'] = doc_type
            if doc_class:
                item['documentClass'] = doc_class
            if status:
                item['statusName'] = status
                item['status'] = status
            if reference_iso:
                item['referenceDateTime'] = reference_iso
                item['dateTime'] = reference_iso
            if author:
                item['authorDisplayName'] = author
            if facility:
                item['facilityName'] = facility
            if encounter:
                item['encounterName'] = encounter
            return item if item else None

    def get_vpr_fullchart(self, dfn: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Aggregate common domains to emulate fullchart when JSON endpoint is unavailable.
        Domains: patient, med, lab, vital, document, image, procedure, visit, problem, allergy.
        Returns {'items': [...]} concatenated for simplicity.
        """
        domains = ['patient','med','lab','vital','document','image','procedure','visit','problem','allergy']
        items: List[Dict[str, Any]] = []
        for dom in domains:
            try:
                part = self.get_vpr_domain(dfn, dom, params=params)
                arr = part.get('items') if isinstance(part, dict) else []
                if isinstance(arr, list):
                    items.extend(arr)
            except Exception:
                continue
        return {'items': items}

    def get_document_texts(self, dfn: str, doc_ids: List[str]) -> Dict[str, List[str]]:  # type: ignore[override]
        if not doc_ids:
            return {}

        requested = [str(doc_id).strip() for doc_id in doc_ids if str(doc_id).strip()]
        if not requested:
            return {}

        self.connect()
        results: Dict[str, List[str]] = {}
        for doc_id in requested:
            lines = self._fetch_tiu_text(doc_id)
            if lines:
                results[doc_id] = lines
        return results

    def _fetch_tiu_text(self, doc_id: str) -> List[str]:
        contexts: List[str] = []
        for ctx in ('OR CPRS GUI CHART', self.default_context, 'TIU AUTHORIZATION', self.vpr_context, 'JLV WEB SERVICES'):
            if ctx and ctx not in contexts:
                contexts.append(ctx)
        failure_markers = (
            'Application context has not been created',
            'Context switch failed',
            'does not exist on server',
            'rpc not registered',
            'not authorized to use this option',
        )
        for ctx in contexts:
            try:
                raw = self._client.call_in_context(ctx, 'TIU GET RECORD TEXT', [doc_id])
                if isinstance(raw, (bytes, bytearray)):
                    try:
                        raw = raw.decode('utf-8', errors='ignore')
                    except Exception:
                        raw = str(raw)
                if isinstance(raw, str):
                    trimmed = raw.strip()
                    if not trimmed:
                        continue
                    low = trimmed.lower()
                    if any(marker in low for marker in (m.lower() for m in failure_markers)):
                        continue
                    return trimmed.splitlines()
            except Exception:
                continue
        return []

    # ---- Internal helpers ----
    def _wrap_domain_response(self, domain: str, dfn: str, parsed: Dict[str, Any]) -> Dict[str, Any]:
        """Return a structure closer to the VPR GET PATIENT DATA JSON domain envelope while
        preserving backward compatibility with existing transforms.

        JSON VPR domain (vista-api-x) roughly provides:
            { 'apiVersion': '1.01', 'params': {...}, 'data': { 'updated': 'TS', 'totalItems': N, 'items': [...] } }

        Our socket XML path currently returns just { 'items': [...], 'meta': {...} }.
        To enable drop-in parity we synthesize a minimal superset:
            {
              'items': [...],                 # existing transform fast-path
              'meta': {...},                  # original meta (version, timeZone, domain, total)
              'data': {
                  'totalItems': N,
                  'items': [...],
                  'version': meta.version?,   # surfaced for troubleshooting
                  'timeZone': meta.timeZone?  # surfaced for troubleshooting
              }
            }

        We intentionally omit apiVersion/params/systemId since they are transport-specific; these can
        be added later if needed for strict diffing. Keeping root 'items' ensures no callers break.
        """
        try:
            items = []
            if isinstance(parsed, dict):
                items = parsed.get('items') or []
                if not isinstance(items, list):
                    items = []
                else:
                    normalized_items: List[Any] = []
                    for it in items:
                        if isinstance(it, dict):
                            normalized_items.append(_normalize_domain_item(domain, it))
                        else:
                            normalized_items.append(it)
                    items = normalized_items
            meta = parsed.get('meta') if isinstance(parsed, dict) else None
            if not isinstance(meta, dict):
                meta = {}
            total = meta.get('total')
            if not isinstance(total, int):
                try:
                    total = int(str(total))
                except Exception:
                    total = len(items)
            meta['total'] = total
            data_block: Dict[str, Any] = {
                'totalItems': total,
                'items': items,
            }
            # surface version/timeZone if present (non-standard but helpful)
            for k in ('version','timeZone','updated'):
                if meta.get(k) and k not in data_block:
                    data_block[k] = meta.get(k)
            # Provide domain hint for debugging
            if meta.get('domain') is None and domain:
                meta['domain'] = domain
            # Provide patient hint if absent
            if 'dfn' not in meta:
                meta['dfn'] = str(dfn)
            wrapped = {
                'items': items,  # legacy consumers
                'meta': meta,
                'data': data_block,
            }
            return wrapped
        except Exception:
            # Best-effort fallback: return original parsed
            return parsed
'''

VPR_XML_PARSER_SOURCE = r'''"""VPR XML parsing utilities.

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
'''
