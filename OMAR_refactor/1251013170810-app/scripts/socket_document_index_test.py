#!/usr/bin/env python
"""VistA Broker socket probe for document metadata and note text.

The script connects directly to a VistA Broker listener, invokes
``VPR GET PATIENT DATA`` for the ``documents`` domain, counts the
returned notes, parses the first entry into the OMAR quick/raw
structure, and hydrates it with TIU note text for validation.
"""

import argparse
import json
import socket
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Tuple, Optional, Dict, Any
import xml.etree.ElementTree as ET

# --- Configuration Defaults (override with CLI args) ---
DEFAULT_HOST = 'vista.puget-sound.med.va.gov'
DEFAULT_PORT = 19212
DEFAULT_CONTEXT = 'JLV WEB SERVICES'
DEFAULT_CONTEXTS_FALLBACK = [
    'JLV WEB SERVICES',
    'OR CPRS GUI CHART',
    'LHS RPC CONTEXT',
    'SDECRPC',
    'XUS SIGNON',
]
DEFAULT_ACCESS = 'sr3355'
DEFAULT_VERIFY = 'L@scruce2025!'
DEFAULT_TIU_CONTEXT = 'OR CPRS GUI CHART'
DEFAULT_DFN = '154510'

END_MARK = chr(4)

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

def fetch_vpr_xml(client: VistaSocketClient, dfn: str) -> str:
    """Invoke VPR GET PATIENT DATA (documents domain) and return raw XML text."""
    return client.invoke('VPR GET PATIENT DATA', [str(dfn), 'documents'])


def _iter_document_elements(root: ET.Element) -> int:
    count = 0
    for elem in root.iter():
        tag = elem.tag
        if not isinstance(tag, str):
            continue
        if '}' in tag:
            tag = tag.split('}', 1)[1]
        if tag.lower() == 'document':
            count += 1
    return count


def count_documents_in_vpr_xml(xml_text: str) -> int:
    cleaned = (xml_text or '').strip()
    if not cleaned:
        return 0
    try:
        root = ET.fromstring(cleaned)
    except ET.ParseError:
        # Fallback: simple pattern match when XML is malformed
        return len(re.findall(r'<document\b', cleaned, flags=re.IGNORECASE))
    return _iter_document_elements(root)


def fileman_to_iso(value: Optional[str]) -> Optional[str]:
    if not value:
        return None
    text = str(value).strip()
    if not text:
        return None
    head, _, tail = text.partition('.')
    if not head.isdigit() or len(head) != 7:
        return text
    year = int(head[:3]) + 1700
    month = int(head[3:5])
    day = int(head[5:7])
    hour = minute = second = 0
    if tail:
        digits = ''.join(ch for ch in tail if ch.isdigit())
        if len(digits) >= 2:
            hour = int(digits[0:2])
        if len(digits) >= 4:
            minute = int(digits[2:4])
        if len(digits) >= 6:
            second = int(digits[4:6])
    try:
        dt_obj = datetime(year, month, day, hour, minute, second, tzinfo=timezone.utc)
    except ValueError:
        return text
    return dt_obj.isoformat().replace('+00:00', 'Z')


def _attrs(element: Optional[ET.Element]) -> Dict[str, Any]:
    if element is None:
        return {}
    return {k: v for k, v in element.attrib.items() if v is not None}


def _value(element: Optional[ET.Element]) -> Optional[str]:
    if element is None:
        return None
    if 'value' in element.attrib:
        return element.get('value')
    return element.text


def _collect_clinicians(element: Optional[ET.Element]) -> List[Dict[str, Any]]:
    if element is None:
        return []
    clinicians: List[Dict[str, Any]] = []
    for clinician_elem in element.findall('clinician'):
        clinicians.append(_attrs(clinician_elem))
    return clinicians


def _collect_national_entry(element: Optional[ET.Element]) -> Dict[str, Any]:
    return _attrs(element)


def _select_author(element: Optional[ET.Element]) -> Optional[Dict[str, Any]]:
    if element is None:
        return None
    for clinician_elem in element.findall('clinician'):
        attrs = _attrs(clinician_elem)
        role = (attrs.get('role') or attrs.get('roleName') or '').strip().upper()
        if role == 'A' or role.startswith('A^'):
            author: Dict[str, Any] = {}
            name = attrs.get('name') or attrs.get('displayName') or attrs.get('providerName')
            if name:
                author['name'] = name
            provider_type = attrs.get('providerType') or attrs.get('type')
            if provider_type:
                author['providerType'] = provider_type
            classification = attrs.get('classification') or attrs.get('personClass') or attrs.get('classCode')
            if classification:
                author['classification'] = classification
            if author:
                return author
    return None


def _parse_document_element(element: ET.Element) -> Dict[str, Any]:
    doc_id = _value(element.find('id')) or ''
    reference_dt = _value(element.find('referenceDateTime'))
    iso_date = fileman_to_iso(reference_dt)

    quick: Dict[str, Any] = {
        'title': _value(element.find('localTitle')) or _value(element.find('title')) or '',
        'status': _value(element.find('status')),
        'date': iso_date or reference_dt,
    }

    doc_type = _value(element.find('type')) or None
    doc_class = _value(element.find('documentClass')) or None
    if doc_type:
        quick['documentType'] = doc_type
    if doc_class:
        quick['documentClass'] = doc_class

    national_title = element.find('nationalTitle')
    if national_title is not None:
        name = national_title.get('name')
        if name:
            quick['nationalTitle'] = name

    facility = element.find('facility')
    if facility is not None and facility.get('name'):
        quick['facility'] = facility.get('name')

    encounter = element.find('encounter')
    if encounter is not None and encounter.get('value'):
        quick['encounter'] = encounter.get('value')

    author = _select_author(element.find('clinicians'))
    if author:
        quick['author'] = author

    raw: Dict[str, Any] = {
        'id': _value(element.find('id')),
        'localTitle': _value(element.find('localTitle')),
        'documentClass': _value(element.find('documentClass')),
        'documentType': _value(element.find('type')),
        'category': _value(element.find('category')),
        'referenceDateTime': reference_dt,
        'referenceDateTimeIso': iso_date,
        'status': _value(element.find('status')),
        'facility': _attrs(facility) if facility is not None else None,
        'encounter': _attrs(encounter) if encounter is not None else None,
        'nationalTitle': _collect_national_entry(element.find('nationalTitle')),
        'nationalTitleRole': _collect_national_entry(element.find('nationalTitleRole')),
        'nationalTitleType': _collect_national_entry(element.find('nationalTitleType')),
        'clinicians': _collect_clinicians(element.find('clinicians')),
    }

    rpc_id = raw.get('id')

    return {
        'doc_id': str(doc_id or rpc_id or ''),
        'quick': quick,
        'raw': raw,
        'text': '',
        'rpc_id': str(rpc_id or doc_id or ''),
    }


def parse_all_documents(xml_text: str) -> List[Dict[str, Any]]:
    documents: List[Dict[str, Any]] = []
    cleaned = (xml_text or '').strip()
    if not cleaned:
        return documents
    try:
        root = ET.fromstring(cleaned)
    except ET.ParseError:
        return documents
    for element in root.iter():
        tag = element.tag
        if not isinstance(tag, str):
            continue
        if '}' in tag:
            tag = tag.split('}', 1)[1]
        if tag.lower() == 'document':
            documents.append(_parse_document_element(element))
    return documents


def parse_first_document(xml_text: str) -> Optional[Dict[str, Any]]:
    documents = parse_all_documents(xml_text)
    return documents[0] if documents else None


def _normalize_doc_id_for_rpc(value: Optional[str]) -> Optional[str]:
    text = str(value or '').strip()
    if not text:
        return None
    lowered = text.lower()
    if lowered.startswith('urn:va:document:'):
        parts = text.split(':')
        if len(parts) >= 5:
            text = parts[-1].strip()
    for separator in (';', ':'):
        if separator in text:
            candidate = text.rsplit(separator, 1)[-1].strip()
            if candidate:
                text = candidate
    if '-' in text:
        tail = text.rsplit('-', 1)[-1].strip()
        if tail.isdigit():
            text = tail
    return text or None


def fetch_document_text(client: VistaSocketClient, doc_id: Optional[str]) -> Optional[str]:
    rpc_token = _normalize_doc_id_for_rpc(doc_id)
    if not rpc_token:
        return None
    try:
        raw = client.invoke('TIU GET RECORD TEXT', [rpc_token])
    except Exception as exc:
        print(f"WARNING: TIU GET RECORD TEXT failed for '{rpc_token}': {exc}")
        return None
    if not isinstance(raw, str):
        return None
    text = raw.strip('\r\n ')
    if not text:
        return None
    lowered = text.lower()
    if lowered.startswith('-1^') or 'not authorized' in lowered or 'does not exist' in lowered:
        return None
    lines = [line.rstrip('\r') for line in raw.splitlines()]
    return '\n'.join(lines).strip('\n\r ')

# --- CLI Flow ---

def main():
    parser = argparse.ArgumentParser(description='VistA document index probe (socket)')
    parser.add_argument('--host', default=DEFAULT_HOST)
    parser.add_argument('--port', type=int, default=DEFAULT_PORT)
    parser.add_argument('--access', default=DEFAULT_ACCESS)
    parser.add_argument('--verify', default=DEFAULT_VERIFY)
    parser.add_argument('--context', default=DEFAULT_CONTEXT,
                        help='Context used for VPR GET PATIENT DATA (default: JLV WEB SERVICES)')
    parser.add_argument('--tiu-context', default=DEFAULT_TIU_CONTEXT,
                        help='Context used for TIU note text retrieval (default: OR CPRS GUI CHART)')
    parser.add_argument('--debug', action='store_true', help='Enable debug prints of raw replies')
    parser.add_argument('--dfn', default=DEFAULT_DFN,
                        help=f'Patient DFN to fetch via VPR XML (default: {DEFAULT_DFN})')
    parser.add_argument('--xml-out', default=None,
                        help='Output path for raw XML (default: OMAR_refactor/examples/vpr_<dfn>.xml)')
    parser.add_argument('--documents-out', default=None,
                        help='Output path for parsed documents JSON (default: OMAR_refactor/examples/vpr_documents_<dfn>.json)')
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
        vpr_context = args.context
        tiu_context = args.tiu_context
        dfn = args.dfn

        if client.context != vpr_context:
            try:
                print(f"Switching to VPR context '{vpr_context}' ...")
                client.set_context(vpr_context)
            except Exception as ctx_err:
                raise RuntimeError(f"Unable to switch to VPR context '{vpr_context}': {ctx_err}") from ctx_err

        print(f"Invoking VPR GET PATIENT DATA (documents) for DFN {dfn} ...")
        xml_text = fetch_vpr_xml(client, dfn)
        if not xml_text:
            print('WARNING: VPR GET PATIENT DATA returned an empty payload.')

        documents = parse_all_documents(xml_text)
        if documents:
            doc_count = len(documents)
        else:
            doc_count = count_documents_in_vpr_xml(xml_text)
        print(f"Document count detected in VPR payload: {doc_count}")

        parsed_document = documents[0] if documents else None
        if parsed_document:
            text_context_entered = False
            try:
                if tiu_context:
                    if client.context != tiu_context:
                        print(f"Switching to TIU context '{tiu_context}' for note text ...")
                    client.set_context(tiu_context)
                    text_context_entered = True
                text_token = parsed_document.get('rpc_id') or parsed_document.get('doc_id')
                note_text = fetch_document_text(client, text_token)
                if not note_text and parsed_document.get('doc_id') and parsed_document.get('doc_id') != text_token:
                    note_text = fetch_document_text(client, parsed_document.get('doc_id'))
                if note_text:
                    parsed_document['text'] = note_text
                    print(f"Hydrated note text from TIU GET RECORD TEXT ({len(note_text.splitlines())} lines).")
                else:
                    print('WARNING: Unable to hydrate note text for the first document.')
            except Exception as text_err:
                print(f"WARNING: TIU note text retrieval failed: {text_err}")
            finally:
                if text_context_entered and vpr_context:
                    try:
                        if client.context != vpr_context:
                            print(f"Restoring VPR context '{vpr_context}' ...")
                        client.set_context(vpr_context)
                    except Exception as restore_err:
                        print(f"WARNING: Unable to restore VPR context '{vpr_context}': {restore_err}")
            print("First document parsed to gateway-style structure:")
            print(json.dumps(parsed_document, indent=2))
        else:
            print('No <document> element found to parse in the VPR payload.')

        output_path = Path(args.xml_out) if args.xml_out else (
            Path(__file__).resolve().parent.parent / 'examples' / f'vpr_{dfn}.xml'
        )
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(xml_text, encoding='utf-8')
        print(f"Saved {len(xml_text)} characters of XML to {output_path}")

        documents_out_path = Path(args.documents_out) if args.documents_out else (
            Path(__file__).resolve().parent.parent / 'examples' / f'vpr_documents_{dfn}.json'
        )
        documents_out_path.parent.mkdir(parents=True, exist_ok=True)
        documents_out_path.write_text(json.dumps(documents, indent=2), encoding='utf-8')
        print(f"Saved {len(documents)} parsed document entries to {documents_out_path}")

        preview_src = xml_text.strip().replace('\r', ' ').replace('\n', ' ')
        if preview_src and args.preview:
            preview_len = max(1, min(args.preview, len(preview_src)))
            print(f"Preview: {preview_src[:preview_len]}{'...' if len(preview_src) > preview_len else ''}")
    finally:
        client.close()


if __name__ == '__main__':
    main()
