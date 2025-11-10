#!/usr/bin/env python
"""
VistA Broker Socket Example (Educational)
=========================================

This script shows how to open a raw VistA Broker (XWB) socket connection and invoke Remote
Procedure Calls (RPCs) against a VistA instance. It is intentionally self‑contained and is
commented for developers new to VistA.

CONFIGURATION FIRST – READ THIS
--------------------------------
Below (search for "Configuration Defaults") you will find constants for:
  DEFAULT_HOST      : VistA listener hostname or IP.
  DEFAULT_PORT      : VistA listener TCP port.
  DEFAULT_ACCESS    : ACCESS CODE (like a username – NEVER share real codes).
  DEFAULT_VERIFY    : VERIFY CODE (like a password – treat as secret).
  DEFAULT_CONTEXT   : The initial RPC context (an application namespace / security domain).
Update these values or provide them via CLI flags. If any are wrong the handshake will fail.

KEY VistA BROKER CONCEPTS
-------------------------
1. ACCESS / VERIFY CODE
    Classic VistA authentication pair. After successful validation, the server associates a DUZ
    (internal user identifier) with the connection.

2. CONTEXT (XWB CREATE CONTEXT)
    An application permission boundary. Each context (e.g. "OR CPRS GUI CHART", "JLV WEB SERVICES")
    grants access to a set of RPCs. You must switch/create context after login before calling most
    application RPCs. If the context does not exist or the user lacks permission, it fails.

3. RPC (Remote Procedure Call)
    A named procedure published by the VistA system (e.g. "ORWPT LIST ALL", "VPR GET PATIENT DATA").
    RPCs take ordered parameters (sometimes lists or literal strings) encoded by the Broker framing.
    The response can be caret-delimited text, plain lines, or structured data (XML, JSON, etc.).

4. BROKER PROTOCOL FRAMING
        This is the transport envelope for ALL RPCs (not unique to any one). It tells VistA what you're
        calling and packages the parameters.

        Structure (simplified):
            [XWB]1130            -> Protocol signature.
            2\x011               -> "2" means RPC call ("4" is command). Then a separator (0x01) and version digit.
            <len>RPCNAME         -> Single byte length of RPC name followed immediately by the name.
            5 ... f              -> Parameter block. For each literal parameter:
                                                             0 LLL VALUE
                                                             where 0 = literal tag, LLL = zero‑padded byte length of UTF‑8 VALUE.
                                                         After the last parameter, an 'f' terminates the list. Empty list variants
                                                         historically appear as '54f' or '5' + '4f'.
            \x04                 -> ASCII EOT (end of transmission) sentinel.

        Example (conceptual) – ORWPT LIST ALL with params ['ZZTES~', '1']:
            [XWB]1130 2\x011 \x0EORWPT LIST ALL 5 0 006ZZTES~ 0 0011 f \x04
            (Spaces added for readability; real stream is contiguous)

        The framing does NOT define the semantic meaning of each parameter; it only conveys them.
        To learn what parameters a specific RPC expects, consult the RPC catalog (see reference link).

5. ENCRYPTION OF SENSITIVE FIELDS
    ACCESS/VERIFY and optionally CONTEXT may be sent encrypted. The algorithm uses two randomly
    chosen substitution rows (see CIPHER table) and wraps the transformed string with indices.
    This is NOT modern cryptographic security – it matches legacy expectations only.

WHAT THIS SCRIPT DEMONSTRATES
------------------------------
* Handshake sequence: TCPConnect -> XUS SIGNON SETUP -> XUS AV CODE -> XWB CREATE CONTEXT.
* Patient name prefix search via "ORWPT LIST ALL" (decrement last letter + '~' per CPRS behavior).
* Retrieval of raw VPR XML via "VPR GET PATIENT DATA" and persistence to `examples/` for analysis.
* Fallback to alternate contexts if the first fails.

FURTHER RPC REFERENCE
---------------------
For parameter and response details of thousands of RPCs, browse:
    https://vivian.worldvista.org/vivian-data/8994/All-RPC.html
Use that index to confirm names, expected parameter counts, and formats before implementing new calls.

SECURITY NOTES
--------------
* Never commit real ACCESS or VERIFY codes to source control.
* Treat socket connections as sensitive; use a secure environment.
* This example omits auditing, logging redaction, and robust XML parsing – add before production use.

DISCLAIMER
----------
This is a teaching aid. Production-grade clients need hardened error handling, connection pooling,
timeouts, DUZ/context validation, and proper XML/JSON parsing.
"""
import argparse
import socket
import re
import sys
import time
from pathlib import Path
from typing import List, Tuple, Optional, Dict, Any

# --- Configuration Defaults (override with CLI args) ---
# These defaults MUST be reviewed before use. Provide real values via CLI whenever possible.
# If ACCESS/VERIFY are blank you will receive a login failure. Context must be one the user is
# authorized for; multiple contexts can be listed with --contexts to fall back.
DEFAULT_HOST = 'vista.puget-sound.med.va.gov'
DEFAULT_PORT = 19212
DEFAULT_CONTEXT = 'OR CPRS GUI CHART'
DEFAULT_CONTEXTS_FALLBACK = [
    'OR CPRS GUI CHART',
    'JLV WEB SERVICES',
    'LHS RPC CONTEXT',
    'SDECRPC',
    'XUS SIGNON',
]
# ACCESS/VERIFY provided here for local testing per user request
DEFAULT_ACCESS = 'sr3355'
DEFAULT_VERIFY = 'L@scruce2025!'

DEFAULT_VPR_CONTEXT = 'JLV WEB SERVICES'
DEFAULT_DFN = '7666361'  # Demo DFN used for local testing; replace via --dfn as needed.

END_MARK = chr(4)

# Cipher table from existing clients (unchanged). Used for legacy substitution encryption of:
#   * ACCESS;VERIFY pair
#   * (optionally) context value when plaintext creation fails
# Each row is a 94-ish character mapping across the visible ASCII range expected by VistA.
CIPHER = [
    "wkEo-ZJt!dG)49K{nX1BS$vH<&:Myf*>Ae0jQW=;|#PsO`'%+rmb[gpqN,l6/hFC@DcUa ]z~R}\"V\\iIxu?872.(TYL5_3",
    "rKv`R;M/9BqAF%&tSs#Vh)dO1DZP> *fX'u[.4lY=-mg_ci802N7LTG<]!CWo:3?{+,5Q}(@jaExn$~p\\IyHwzU\"|k6Jeb",
    "\\pV(ZJk\"WQmCn!Y,y@1d+~8s?[lNMxgHEt=uw|X:qSLjAI*}6zoF{T3#;ca)/h5%`P4$r]G'9e2if_>UDKb7<v0&- RBO.",
    "depjt3g4W)qD0V~NJar\\B \"?OYhcu[<Ms%Z`RIL_6:]AX-zG.#}$@vk7/5x&*m;(yb2Fn+l'PwUof1K{9,|EQi>H=CT8S!",
    "NZW:1}K$byP;jk)7'`x90B|cq@iSsEnu,(l-hf.&Y_?J#R]+voQXU8mrV[!p4tg~OMez CAaGFD6H53%L/dT2<*>\"{\\wI=",
    "vCiJ<oZ9|phXVNn)m K`t/SI%]A5qOWe\\&?;jT~M!fz1l>[D_0xR32c*4.P\"G{r7}E8wUgyudF+6-:B=$(sY,LkbHa#'@Q",
    "hvMX,'4Ty;[a8/{6l~F_V\"}qLI\\!@x(D7bRmUH]W15J%N0BYPkrs&9:$)Zj>u|zwQ=ieC-oGA.#?tfdcO3gp`S+En K2*<",
    "jd!W5[];4'<C$/&x|rZ(k{>?ghBzIFN}fAK\"#`p_TqtD*1E37XGVs@0nmSe+Y6Qyo-aUu%i8c=H2vJ\\) R:MLb.9,wlO~P",
    "2ThtjEM+!=xXb)7,ZV{*ci3\"8@_l-HS69L>]\\AUF/Q%:qD?1~m(yvO0e'<#o$p4dnIzKP|`NrkaGg.ufCRB[; sJYwW}5&",
    "vB\\5/zl-9y:Pj|=(R'7QJI *&CTX\"p0]_3.idcuOefVU#omwNZ`$Fs?L+1Sk<,b)hM4A6[Y%aDrg@~KqEW8t>H};n!2xG{",
    "sFz0Bo@_HfnK>LR}qWXV+D6`Y28=4Cm~G/7-5A\\b9!a#rP.l&M$hc3ijQk;),TvUd<[:I\"u1'NZSOw]*gxtE{eJp|y (?%",
    "M@,D}|LJyGO8`$*ZqH .j>c~h<d=fimszv[#-53F!+a;NC'6T91IV?(0x&/{B)w\"]Q\\YUWprk4:ol%g2nE7teRKbAPuS_X",
    ".mjY#_0*H<B=Q+FML6]s;r2:e8R}[ic&KA 1w{)vV5d,$u\"~xD/Pg?IyfthO@CzWp%!`N4Z'3-(o|J9XUE7k\\TlqSb>anG",
    "xVa1']_GU<X`|\\NgM?LS9{\"jT%s$}y[nvtlefB2RKJW~(/cIDCPow4,>#zm+:5b@06O3Ap8=*7ZFY!H-uEQk; .q)i&rhd",
    "I]Jz7AG@QX.%3Lq>METUo{Pp_ |a6<0dYVSv8:b)~W9NK`(r'4fs&wim\\kReC2hg=HOj$1B*/nxt,;c#y+![?lFuZ-5D}",
    "Rr(Ge6F Hx>q$m&C%M~Tn,:\"o'tX/*yP.{lZ!YkiVhuw_<KE5a[;}W0gjsz3]@7cI2\\QN?f#4p|vb1OUBD9)=-LJA+d`S8",
    "I~k>y|m};d)-7DZ\"Fe/Y<B:xwojR,Vh]O0Sc[`$sg8GXE!1&Qrzp._W%TNK(=J 3i*2abuHA4C'?Mv\\Pq{n#56LftUl@9+",
    "~A*>9 WidFN,1KsmwQ)GJM{I4:C%}#Ep(?HB/r;t.&U8o|l['Lg\"2hRDyZ5`nbf]qjc0!zS-TkYO<_=76a\\X@$Pe3+xVvu"
]

VPR_TYPE_ALIASES: Dict[str, str] = {
    'patient': 'demographics',
    'demographics': 'demographics',
    'vital': 'vitals',
    'vitals': 'vitals',
    'lab': 'labs',
    'labs': 'labs',
    'med': 'meds',
    'meds': 'meds',
    'medication': 'meds',
    'medications': 'meds',
    'document': 'documents',
    'documents': 'documents',
    'note': 'documents',
    'notes': 'documents',
    'image': 'images',
    'procedure': 'procedures',
    'procedures': 'procedures',
    'visit': 'visits',
    'visits': 'visits',
    'encounter': 'visits',
    'encounters': 'visits',
    'problem': 'problems',
    'problems': 'problems',
    'allergy': 'reactions',
    'allergies': 'reactions',
}

class VistaSocketClient:
    def __init__(self, host: str, port: int, access: str, verify: str, context: str, debug: bool = False):
        self.host = host
        self.port = port
        self.access = access
        self.verify = verify
        self.context = context
        self.sock: Optional[socket.socket] = None
        self.endMark = END_MARK
        self.debug = debug

    def _dbg(self, msg: str):
        if self.debug:
            print(f"[DEBUG] {msg}")

    def connect(self):
        self.close()
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.connect((self.host, self.port))
        time.sleep(0.3)
        self._handshake()

    def _handshake(self):
        if not self.sock:
            raise RuntimeError('Socket not connected')
        # (1) TCPConnect: establishes protocol version and basic acceptance.
        tcp = self._make_request("TCPConnect", [socket.gethostbyname(socket.gethostname()), "0", "FMQL"], is_command=True)
        self.sock.send(tcp.encode('utf-8'))
        reply = self._read_to_end()
        self._dbg(f"TCPConnect reply: {repr(reply)}")
        if not re.match(r'accept', reply):
            raise RuntimeError(f"TCPConnect failed: {reply}")
        # (2) XUS SIGNON SETUP: prepares environment (returns site info, greeting, etc.).
        setup = self._make_request("XUS SIGNON SETUP", [])
        self.sock.send(setup.encode('utf-8'))
        setup_reply = self._read_to_end()
        self._dbg(f"SIGNON SETUP reply: {repr(setup_reply)}")
        # (3) XUS AV CODE: submit ACCESS;VERIFY with encrypted-then-plaintext fallback.
        av_plain = self.access + ";" + self.verify
        av_enc = self._encrypt(av_plain).decode()
        av_req = self._make_request("XUS AV CODE", [av_enc])
        self.sock.send(av_req.encode('utf-8'))
        av_reply = self._read_to_end()
        self._dbg(f"AV enc reply: {repr(av_reply)}")
        if re.search(r'Not a valid ACCESS CODE/VERIFY CODE pair', av_reply, re.IGNORECASE):
            av_req2 = self._make_request("XUS AV CODE", [av_plain])
            self.sock.send(av_req2.encode('utf-8'))
            av_reply2 = self._read_to_end()
            self._dbg(f"AV plain reply: {repr(av_reply2)}")
            if re.search(r'Not a valid ACCESS CODE/VERIFY CODE pair', av_reply2, re.IGNORECASE):
                raise RuntimeError(f"Login failed: {av_reply2}")
        # (4) XWB CREATE CONTEXT: activate initial application context with encrypted fallback if needed.
        if self.context:
            if not self._create_context(self.context):
                raise RuntimeError(f"Context failed for '{self.context}' during handshake.")

    def _is_context_success(self, reply: str) -> bool:
        """Return True if the CREATE CONTEXT reply indicates success.

        Typical success is a single '1'. Some servers may include leading/trailing control chars.
        Anything starting with '-1^' or containing 'Application context has not been created' or
        'does not exist on server' is a failure.
        """
        if not reply:
            return False
        s = reply.strip()
        if s.startswith('-1^'):
            return False
        if re.search(r'Application context has not been created', s, re.IGNORECASE):
            return False
        if re.search(r'does not exist on server', s, re.IGNORECASE):
            return False
        # Success commonly is just '1'
        return s == '1'

    def _create_context(self, target: str) -> bool:
        if not target:
            return False
        if not self.sock:
            raise RuntimeError('Socket not connected')
        req_plain = self._make_request("XWB CREATE CONTEXT", [target])
        self.sock.send(req_plain.encode('utf-8'))
        reply_plain = self._read_to_end()
        self._dbg(f"CREATE CONTEXT plaintext reply: {repr(reply_plain)}")
        if self._is_context_success(reply_plain):
            self.context = target
            return True
        enc_target = self._encrypt(target).decode()
        req_enc = self._make_request("XWB CREATE CONTEXT", [enc_target])
        self.sock.send(req_enc.encode('utf-8'))
        reply_enc = self._read_to_end()
        self._dbg(f"CREATE CONTEXT encrypted reply: {repr(reply_enc)}")
        if self._is_context_success(reply_enc):
            self.context = target
            return True
        return False

    def set_context(self, target: str):
        if not target:
            raise ValueError('Context name must be non-empty')
        if target == self.context:
            return
        if not self._create_context(target):
            raise RuntimeError(f"Context failed for '{target}'")

    def _encrypt(self, val: str) -> bytes:
        """Legacy substitution encryption used by the Broker for ACCESS/VERIFY (and sometimes context).

        Mechanism:
          * Pick two distinct cipher rows (ra, rb).
          * Prefix output with (ra + 32) and suffix with (rb + 32).
          * For each character in input, find its index in row 'ra'; if present, substitute the
            character at same index from row 'rb'. If absent, pass through unchanged.
        NOTE: This is NOT secure cryptography; purpose is compatibility with VistA expectations.
        """
        import random
        ra = random.randint(0, len(CIPHER)-1)
        rb = random.randint(0, len(CIPHER)-1)
        # Ensure distinct rows; allow rb=0 (no special restriction) but not equal to ra
        while rb == ra:
            rb = random.randint(0, len(CIPHER)-1)
        cra = CIPHER[ra]
        crb = CIPHER[rb]
        enc = chr(ra + 32)
        for c in val:
            idx = cra.find(c)
            if idx == -1 or idx >= len(crb):
                enc += c
            else:
                enc += crb[idx]
        enc += chr(rb + 32)
        return enc.encode('utf-8')

    def _make_request(self, name: str, params: List[str], is_command: bool = False) -> str:
        protocoltoken = "[XWB]1130"
        commandtoken = "4" if is_command else "2" + chr(1) + "1"
        namespec = chr(len(name)) + name
        if not params:
            paramsspecs = "54f"  # empty list
        else:
            paramsspecs = "5"
            for p in params:
                if isinstance(p, str):
                    b = p.encode('utf-8')
                    paramsspecs += "0" + str(len(b)).zfill(3) + p
            paramsspecs += "f"
        endtoken = chr(4)
        return protocoltoken + commandtoken + namespec + paramsspecs + endtoken

    def _read_to_end(self) -> str:
        if not self.sock:
            raise RuntimeError('Socket not connected')
        sock = self.sock
        chunks: List[str] = []
        while True:
            data = sock.recv(256)
            if not data:
                break
            chunk = data.decode('utf-8', errors='replace')
            if not chunks and chunk.startswith("\x00"):
                chunk = chunk.lstrip("\x00")
            if chunk.endswith(self.endMark):
                chunks.append(chunk[:-1])
                break
            chunks.append(chunk)
        return ''.join(chunks)

    def invoke(self, name: str, params: List[str]) -> str:
        if not self.sock:
            raise RuntimeError('Socket not connected')
        req = self._make_request(name, params)
        self.sock.send(req.encode('utf-8'))
        return self._read_to_end()

    def close(self):
        if self.sock:
            try:
                self.sock.send("#BYE#".encode('utf-8'))
            except Exception:
                pass
            try:
                self.sock.close()
            except Exception:
                pass
            self.sock = None

# --- High-level helpers ---

def build_search_mod(name_prefix: str) -> str:
    """Transform a name prefix for ORWPT LIST ALL.

    CPRS behavior: decrement final alphabetic character (A -> @, B -> A, etc.) then append '~'.
    This produces an inclusive range start when the RPC enumerates names.
    Examples:
        'SMITH' -> 'SMITG~'
        'A'     -> '@~'
    """
    s = name_prefix.strip().upper()
    if not s:
        return '~'
    last = s[-1]
    if last == 'A':
        new_last = '@'
    elif last.isalpha():
        new_last = chr(ord(last) - 1)
    else:
        new_last = last
    return s[:-1] + new_last + '~'

def search_patients(client: VistaSocketClient, name_prefix: str) -> List[Tuple[str, str, str]]:
    """Invoke ORWPT LIST ALL to get patient matches.

    Returns list of tuples: (DFN, display_name, raw_line). Raw lines are caret-delimited with
    patient identifiers and name, sometimes followed by additional fields (ignored here).
    """
    search_mod = build_search_mod(name_prefix)
    raw = client.invoke('ORWPT LIST ALL', [search_mod, '1'])
    lines = [l for l in raw.split('\n') if l.strip()]
    patients = []
    for line in lines:
        parts = line.split('^')
        if len(parts) >= 2:
            dfn = parts[0].strip()
            pname = parts[1].strip()
            if dfn and pname:
                patients.append((dfn, pname, line))
    return patients

def fetch_vpr_xml(client: VistaSocketClient, dfn: str, domain: Optional[str] = None, type_token: Optional[str] = None) -> str:
    """Invoke VPR GET PATIENT DATA and return raw XML text."""
    params: List[str] = [str(dfn)]
    resolved_type = None
    if type_token:
        resolved_type = type_token
    elif domain:
        resolved_type = VPR_TYPE_ALIASES.get(domain.lower(), domain)
    if resolved_type:
        params.append(resolved_type)
    return client.invoke('VPR GET PATIENT DATA', params)

# --- CLI Flow ---

def main():
    parser = argparse.ArgumentParser(description='Minimal VistA socket patient lookup (educational)')
    parser.add_argument('--host', default=DEFAULT_HOST)
    parser.add_argument('--port', type=int, default=DEFAULT_PORT)
    parser.add_argument('--access', default=DEFAULT_ACCESS)
    parser.add_argument('--verify', default=DEFAULT_VERIFY)
    parser.add_argument('--context', default=DEFAULT_CONTEXT)
    parser.add_argument('--vpr-context', default=DEFAULT_VPR_CONTEXT,
                        help='Context used for VPR XML (default: JLV WEB SERVICES)')
    parser.add_argument('--debug', action='store_true', help='Enable debug prints of raw replies')
    parser.add_argument('--dfn', default=DEFAULT_DFN,
                        help=f'Patient DFN to fetch via VPR XML (default: {DEFAULT_DFN})')
    parser.add_argument('--domain', default=None,
                        help='Optional VPR domain alias (e.g. patient, med, labs) to populate TYPE parameter')
    parser.add_argument('--type', dest='type_token', default=None,
                        help='Explicit TYPE literal for VPR GET PATIENT DATA (overrides --domain)')
    parser.add_argument('--xml-out', default=None,
                        help='Output path for raw XML (default: OMAR_refactor/examples/vpr_<dfn>.xml)')
    parser.add_argument('--preview', type=int, default=160,
                        help='Number of characters to preview from the XML payload (default: 160)')
    parser.add_argument('--av-plain', action='store_true', help='Force plaintext ACCESS;VERIFY (skip encryption)')
    args = parser.parse_args()

    if not args.access or not args.verify:
        print('ERROR: Provide --access and --verify codes.')
        sys.exit(1)

    client = VistaSocketClient(args.host, args.port, args.access, args.verify, args.context, debug=args.debug)
    try:
        print(f"Connecting to {args.host}:{args.port} context='{args.context}' ...")
        # If user forces plaintext AV, temporarily bypass encryption
        if args.av_plain:
            orig_encrypt = client._encrypt
            client._encrypt = lambda s: s.encode('utf-8')  # type: ignore
            try:
                client.connect()
            finally:
                client._encrypt = orig_encrypt
        else:
            client.connect()
        print(f"Handshake complete; active context: {client.context}")
        dfn = args.dfn
        original_context = client.context
        candidate_contexts: List[str] = [args.vpr_context] if args.vpr_context else [DEFAULT_VPR_CONTEXT]
        selected_vpr_context: Optional[str] = None
        context_errors: List[str] = []
        for ctx in candidate_contexts:
            if not ctx:
                continue
            if ctx == original_context:
                selected_vpr_context = ctx
                break
            try:
                print(f"Switching to context '{ctx}' for VPR XML ...")
                client.set_context(ctx)
                selected_vpr_context = ctx
                break
            except Exception as err:
                context_errors.append(f"{ctx}: {err}")
        if selected_vpr_context is None:
            attempts = '; '.join(context_errors) if context_errors else 'no alternate contexts succeeded'
            print(f"ERROR: Unable to establish VPR context. Attempts -> {attempts}")
            print("Tip: run with --vpr-context '<context name>' to supply the correct application context.")
            raise RuntimeError('Unable to select VPR context')
        xml_text = ''
        context_switched = selected_vpr_context != original_context
        try:
            if context_switched:
                print(f"Active VPR context: '{selected_vpr_context}'")
            print(f"Invoking VPR GET PATIENT DATA for DFN {dfn} ...")
            if args.domain:
                print(f"Using domain alias '{args.domain}' (TYPE -> {VPR_TYPE_ALIASES.get(args.domain.lower(), args.domain)})")
            if args.type_token:
                print(f"Using explicit TYPE '{args.type_token}'")
            xml_text = fetch_vpr_xml(client, dfn, domain=args.domain, type_token=args.type_token)
        finally:
            if context_switched and original_context:
                try:
                    print(f"Restoring context '{original_context}' ...")
                    client.set_context(original_context)
                except Exception as ctx_err:
                    print(f"WARNING: failed to restore context '{original_context}': {ctx_err}")
        if not xml_text:
            print('WARNING: VPR GET PATIENT DATA returned an empty payload.')
        output_path = Path(args.xml_out) if args.xml_out else (
            Path(__file__).resolve().parent.parent / 'examples' / f'vpr_{dfn}.xml'
        )
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(xml_text, encoding='utf-8')
        print(f"Saved {len(xml_text)} characters of XML to {output_path}")
        preview_src = xml_text.strip().replace('\r', ' ').replace('\n', ' ')
        if preview_src:
            preview_len = max(1, min(args.preview, len(preview_src)))
            print(f"Preview: {preview_src[:preview_len]}{'...' if len(preview_src) > preview_len else ''}")
    finally:
        client.close()

if __name__ == '__main__':
    main()
