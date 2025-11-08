from __future__ import annotations
import os
import socket
import time
import json
from typing import Any, Dict, Optional, Tuple, List

try:
    import xmltodict  # type: ignore
except Exception:
    xmltodict = None  # soft dependency; validated at runtime

from .data_gateway import DataGateway, GatewayError
from .vpr_xml_parser import parse_vpr_results_xml, DOMAIN_TAGS


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
        self.set_context(self.context)

    def close(self):
        try:
            if self.sock:
                try:
                    self.sock.send('#BYE#'.encode('utf-8'))
                except Exception:
                    pass
                self.sock.close()
        finally:
            self.sock = None

    def set_context(self, ctx: str):
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

    def invoke(self, name: str, params: List[Any]) -> str:
        if not self.sock:
            raise OSError('socket not connected')
        self.sock.send(self._make_request(name, params, False).encode('utf-8'))
        return self._read_to_end()

    def call_in_context(self, ctx: str, name: str, params: List[Any]) -> str:
        cur = self.context
        if ctx != cur:
            self.set_context(ctx)
        try:
            return self.invoke(name, params)
        finally:
            if ctx != cur:
                self.set_context(cur)


# ---- VistaSocketGateway ----

def _ensure_xml_lib():
    if xmltodict is None:
        raise GatewayError("xmltodict is required for socket gateway XML parsing. Add 'xmltodict' to requirements.")


def _normalize_vpr_xml_to_items(xml_text: str) -> Dict[str, Any]:
    """Parse VPR XML text into a dict with an 'items' list compatible with transforms.
    Strategy: xmltodict.parse -> look for data.items.item; coerce to list; return {'items': [...]}.
    Leaves field names as-is (VPR XML uses camelCase names matching JSON schema).
    """
    _ensure_xml_lib()
    try:
        from typing import cast
        xtd = cast(Any, xmltodict)
        obj = xtd.parse(xml_text)
    except Exception as e:
        raise GatewayError(f'Failed to parse VPR XML: {e}')
    # Navigate common VPR shape
    # Expected: {'data': {'items': {'item': [ {...}, {...} ]}}}
    d = obj
    for k in ('data', 'Data'):
        if k in d:
            d = d[k]
            break
    else:
        # fallback: return whole object as one item
        return {'items': [obj]}
    items = None
    # Support both 'items' and 'Items'
    if isinstance(d, dict):
        itwrap = d.get('items') or d.get('Items')
        if isinstance(itwrap, dict):
            items = itwrap.get('item') or itwrap.get('Item')
        elif isinstance(itwrap, list):
            items = itwrap
    # Coerce
    if items is None:
        items = []
    if isinstance(items, dict):
        items = [items]
    # xmltodict returns OrderedDicts; we can cast to plain dicts recursively
    def _to_plain(x):
        if isinstance(x, dict):
            return {k: _to_plain(v) for k, v in x.items()}
        if isinstance(x, list):
            return [ _to_plain(v) for v in x ]
        return x
    plain_items = _to_plain(items)
    # Some VPR XML nests value under '@attr' or '#text'; prefer '#text' for simple nodes
    def _flatten_special(dct: Any) -> Any:
        if not isinstance(dct, dict):
            return dct
        out = {}
        for k, v in dct.items():
            if isinstance(v, dict) and '#text' in v and len(v) <= 2:
                # keep attributes only if useful; primary is text value
                out[k] = v['#text']
            else:
                out[k] = _flatten_special(v)
        return out
    plain_items = [ _flatten_special(it) for it in plain_items ]
    return {'items': plain_items}


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
        self._logger.info('VistaSocketGateway', f"Invoking VPR GET PATIENT DATA (positional) for domain '{domain}' TYPE='{type_val}' (DFN {dfn})")
        raw_xml_positional = ''
        try:
            raw_xml_positional = self._client.call_in_context(self.vpr_context, 'VPR GET PATIENT DATA', positional_params)
            parsed_results = parse_vpr_results_xml(raw_xml_positional, domain=domain)
            if parsed_results.get('items'):  # Successful domain parse
                return self._wrap_domain_response(domain, dfn, parsed_results)
        except Exception as e:
            self._logger.error('VistaSocketGateway', f"Positional domain call failed: {e}")
        # Fallback: namedArray approach used previously
        named = self._vpr_named_array(dfn, domain=domain, params=params)
        self._logger.info('VistaSocketGateway', f"Fallback namedArray invocation for domain '{domain}' (DFN {dfn})")
        raw_xml = self._client.call_in_context(self.vpr_context, 'VPR GET PATIENT DATA', [ { 'namedArray': named } ])
        # Try results parser second time (some deployments may still return <results>)
        try:
            parsed_results_2 = parse_vpr_results_xml(raw_xml, domain=domain)
            if parsed_results_2.get('items'):
                return self._wrap_domain_response(domain, dfn, parsed_results_2)
        except Exception:
            pass
        legacy = _normalize_vpr_xml_to_items(raw_xml)
        return self._wrap_domain_response(domain, dfn, legacy)

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
            meta = parsed.get('meta') if isinstance(parsed, dict) else None
            if not isinstance(meta, dict):
                meta = {}
            total = meta.get('total')
            if not isinstance(total, int):
                total = len(items)
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
