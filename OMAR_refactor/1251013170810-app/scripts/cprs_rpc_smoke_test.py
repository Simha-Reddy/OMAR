#!/usr/bin/env python
"""
CPRS RPC Smoke Test
===================

This standalone script reuses the raw VistA Broker primitives from ``Socket_VPR_Test.py``
so we can validate every CPRS RPC that the refactored socket gateway relies on.
It logs into VistA using the OR CPRS GUI CHART context only, invokes each RPC one
after the other, and records whether the broker returned data (or an expected empty
payload) versus a context failure. The captured results are written to a JSON file
under ``OMAR_refactor/examples`` for quick inspection or attachment to defect reports.

Usage::

    OMAR_refactor\\python\\python.exe OMAR_refactor\\scripts\\cprs_rpc_smoke_test.py

Optional arguments allow overriding host, port, credentials, DFN, and output path.
Real deployments should **never** hardcode shared secrets; these defaults exist solely
for the local testing scenario the user requested.
"""

from __future__ import annotations

import argparse
import json
import random
import socket
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# --- Configuration Defaults (override with CLI args) ---
DEFAULT_HOST = "vista.puget-sound.med.va.gov"
DEFAULT_PORT = 19212
DEFAULT_CONTEXT = "OR CPRS GUI CHART"
DEFAULT_ACCESS = "sr3355"
DEFAULT_VERIFY = "L@scruce2025!"
DEFAULT_DFN = "7666361"
DEFAULT_NAME_PREFIX = "SCRUG"
DEFAULT_LAST5 = "S2025"
DEFAULT_MAX_DOCS = 25
END_MARK = chr(4)

# Copy of the legacy cipher table so the script is self-contained.
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
    "~A*>9 WidFN,1KsmwQ)GJM{I4:C%}#Ep(?HB/r;t.&U8o|l['Lg\"2hRDyZ5`nbf]qjc0!zS-TkYO<_=76a\\X@$Pe3+xVvu",
]


class VistaSocketClient:
    def __init__(self, host: str, port: int, access: str, verify: str, context: str, debug: bool = False):
        self.host = host
        self.port = port
        self.access = access
        self.verify = verify
        self.context = context
        self.sock: Optional[socket.socket] = None
        self.end_mark = END_MARK
        self.debug = debug

    def _dbg(self, message: str) -> None:
        if self.debug:
            print(f"[DEBUG] {message}")

    def connect(self) -> None:
        self.close()
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.connect((self.host, self.port))
        time.sleep(0.25)  # small delay to let the listener settle
        self._handshake()

    def close(self) -> None:
        if self.sock:
            try:
                self.sock.sendall(b"#BYE#")
            except Exception:
                pass
            try:
                self.sock.close()
            except Exception:
                pass
            self.sock = None

    def _handshake(self) -> None:
        if not self.sock:
            raise RuntimeError("Socket not connected")
        tcp = self._make_request(
            "TCPConnect",
            [socket.gethostbyname(socket.gethostname()), "0", "FMQL"],
            is_command=True,
        )
        self.sock.sendall(tcp.encode("utf-8"))
        reply = self._read_to_end()
        self._dbg(f"TCPConnect reply: {repr(reply)}")
        if "accept" not in reply.lower():
            raise RuntimeError(f"TCPConnect failed: {reply}")

        setup = self._make_request("XUS SIGNON SETUP", [])
        self.sock.sendall(setup.encode("utf-8"))
        _ = self._read_to_end()

        combined = f"{self.access};{self.verify}"
        encrypted = self._encrypt(combined).decode()
        av_req = self._make_request("XUS AV CODE", [encrypted])
        self.sock.sendall(av_req.encode("utf-8"))
        av_reply = self._read_to_end()
        self._dbg(f"AV encrypted reply: {repr(av_reply)}")
        if "not a valid" in av_reply.lower():
            plain_req = self._make_request("XUS AV CODE", [combined])
            self.sock.sendall(plain_req.encode("utf-8"))
            plain_reply = self._read_to_end()
            self._dbg(f"AV plain reply: {repr(plain_reply)}")
            if "not a valid" in plain_reply.lower():
                raise RuntimeError(f"Login failed: {plain_reply}")

        if self.context and not self._create_context(self.context):
            raise RuntimeError(f"Context failed for '{self.context}'")

    def _encrypt(self, value: str) -> bytes:
        left = random.randint(0, len(CIPHER) - 1)
        right = random.randint(0, len(CIPHER) - 1)
        while right == left:
            right = random.randint(0, len(CIPHER) - 1)
        table_left = CIPHER[left]
        table_right = CIPHER[right]
        encoded = chr(left + 32)
        for char in value:
            idx = table_left.find(char)
            encoded += table_right[idx] if idx != -1 else char
        encoded += chr(right + 32)
        return encoded.encode("utf-8")

    def _create_context(self, target: str) -> bool:
        plain_req = self._make_request("XWB CREATE CONTEXT", [target])
        self.sock.sendall(plain_req.encode("utf-8"))
        reply_plain = self._read_to_end()
        self._dbg(f"CREATE CONTEXT plain reply: {repr(reply_plain)}")
        if _is_context_success(reply_plain):
            self.context = target
            return True
        enc = self._encrypt(target).decode()
        enc_req = self._make_request("XWB CREATE CONTEXT", [enc])
        self.sock.sendall(enc_req.encode("utf-8"))
        reply_enc = self._read_to_end()
        self._dbg(f"CREATE CONTEXT encrypted reply: {repr(reply_enc)}")
        if _is_context_success(reply_enc):
            self.context = target
            return True
        return False

    def _make_request(self, name: str, params: List[str], is_command: bool = False) -> str:
        proto = "[XWB]1130"
        command_flag = "4" if is_command else "2" + chr(1) + "1"
        name_spec = chr(len(name)) + name
        if not params:
            param_spec = "54f"
        else:
            blocks = ["5"]
            for value in params:
                block = value if isinstance(value, str) else json.dumps(value)
                data = block.encode("utf-8")
                blocks.append("0" + str(len(data)).zfill(3) + block)
            blocks.append("f")
            param_spec = "".join(blocks)
        return proto + command_flag + name_spec + param_spec + END_MARK

    def _read_to_end(self) -> str:
        if not self.sock:
            raise RuntimeError("Socket not connected")
        chunks: List[str] = []
        while True:
            data = self.sock.recv(512)
            if not data:
                break
            chunk = data.decode("utf-8", errors="replace")
            if not chunks and chunk.startswith("\x00"):
                chunk = chunk.lstrip("\x00")
            if chunk.endswith(self.end_mark):
                chunks.append(chunk[:-1])
                break
            chunks.append(chunk)
        return "".join(chunks)

    def invoke(self, name: str, params: List[str]) -> str:
        if not self.sock:
            raise RuntimeError("Socket not connected")
        req = self._make_request(name, params)
        self.sock.sendall(req.encode("utf-8"))
        return self._read_to_end()


def build_search_mod(name_prefix: str) -> str:
    text = name_prefix.strip().upper()
    if not text:
        return "~"
    last = text[-1]
    if last == "A":
        new_last = "@"
    elif last.isalpha():
        new_last = chr(ord(last) - 1)
    else:
        new_last = last
    return text[:-1] + new_last + "~"


def _is_context_success(reply: str) -> bool:
    if not reply:
        return False
    cleaned = reply.strip()
    if cleaned.startswith("-1^"):
        return False
    lowered = cleaned.lower()
    if "application context has not been created" in lowered:
        return False
    if "does not exist on server" in lowered:
        return False
    return cleaned == "1"


def _split_lines(raw: str) -> List[str]:
    return [line.strip() for line in raw.replace("\r", "\n").split("\n") if line.strip()]


def _classify_payload(raw: str) -> Tuple[bool, Optional[str]]:
    text = str(raw or "")
    lowered = text.lower()
    if "application context has not been created" in lowered:
        return False, "application context has not been created"
    if "remote procedure" in lowered and "doesn't exist" in lowered:
        return False, "remote procedure missing"
    if "rpc not registered" in lowered:
        return False, "rpc not registered"
    if "not authorized" in lowered:
        return False, "not authorized"
    return True, None


def main() -> None:
    parser = argparse.ArgumentParser(description="CPRS RPC smoke test over the VistA Broker")
    parser.add_argument("--host", default=DEFAULT_HOST)
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    parser.add_argument("--access", default=DEFAULT_ACCESS)
    parser.add_argument("--verify", default=DEFAULT_VERIFY)
    parser.add_argument("--context", default=DEFAULT_CONTEXT)
    parser.add_argument("--dfn", default=DEFAULT_DFN)
    parser.add_argument("--name-prefix", default=DEFAULT_NAME_PREFIX)
    parser.add_argument("--last5", default=DEFAULT_LAST5)
    parser.add_argument("--max-docs", type=int, default=DEFAULT_MAX_DOCS)
    parser.add_argument("--out", default=None, help="Override output file path (JSON)")
    parser.add_argument("--debug", action="store_true")
    args = parser.parse_args()

    client = VistaSocketClient(
        host=args.host,
        port=args.port,
        access=args.access,
        verify=args.verify,
        context=args.context,
        debug=args.debug,
    )

    results: Dict[str, Any] = {
        "host": args.host,
        "port": args.port,
        "context": args.context,
        "dfn": args.dfn,
        "namePrefix": args.name_prefix,
        "last5": args.last5,
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "tests": [],
    }

    state: Dict[str, Any] = {}

    tests = [
        ("ORWU USERINFO", [], "Baseline user info"),
        ("ORQPT DEFAULT PATIENT LIST", [], "Default patient list"),
        (
            "ORWPT LIST ALL",
            [build_search_mod(args.name_prefix), "1"],
            f"Patient search for prefix '{args.name_prefix}'",
        ),
        ("ORWPT LAST5", [args.last5], f"Patient search by LAST5 '{args.last5}'"),
        ("ORWPT PTINQ", [args.dfn], "Patient demographics (PTINQ)"),
        ("ORWPS ACTIVE", [args.dfn], "Active medications"),
        ("ORWCV LAB", [args.dfn], "Recent labs"),
        ("ORQQVI VITALS", [args.dfn, "", ""], "Vitals without date window"),
        ("ORQQPL PROBLEM LIST", [args.dfn], "Problem list"),
        ("ORQQAL LIST", [args.dfn], "Allergies list"),
        (
            "TIU DOCUMENTS BY CONTEXT",
            [
                "3",  # Progress Notes context (per CPRS)
                "1",  # Patient class
                args.dfn,
                "-1",  # Start date (=-1 uses TIU default window)
                "-1",  # Stop date
                "0",   # Status filter: 0=ALL
                str(max(1, args.max_docs)),
                "D",   # Descending order
                "1",   # Start at beginning of list
                "0",   # Include addenda (0=no)
                "1",   # Occurrence flag (1=include signed)
                "",    # Service filter
            ],
            "Document headers",
        ),
    ]

    try:
        print(f"Connecting to {args.host}:{args.port} as context '{args.context}' ...")
        client.connect()
        print("Handshake complete.")

        for name, params, description in tests:
            started = time.time()
            try:
                raw = client.invoke(name, [str(p) for p in params])
                elapsed = time.time() - started
                lines = _split_lines(raw)
                ok, failure_reason = _classify_payload(raw)
                preview = lines[:3]
                entry: Dict[str, Any] = {
                    "rpc": name,
                    "description": description,
                    "params": params,
                    "ok": ok,
                    "lineCount": len(lines),
                    "elapsedMs": round(elapsed * 1000, 1),
                    "preview": preview,
                }
                if failure_reason:
                    entry["failureReason"] = failure_reason
                if name == "TIU DOCUMENTS BY CONTEXT" and ok and lines:
                    doc_ids = []
                    for line in lines:
                        parts = line.split("^")
                        if not parts:
                            continue
                        doc_id_token = parts[0].strip()
                        if doc_id_token.isdigit():
                            doc_ids.append(doc_id_token)
                    if doc_ids:
                        state["first_document_id"] = doc_ids[0]
                        entry["documentIds"] = doc_ids[:5]
                results["tests"].append(entry)
                status = "OK" if ok else "FAIL"
                detail = f" ({failure_reason})" if failure_reason else ""
                print(f"[{status}] {name} -> {len(lines)} line(s){detail}")
            except Exception as exc:
                elapsed = time.time() - started
                results["tests"].append(
                    {
                        "rpc": name,
                        "description": description,
                        "params": params,
                        "ok": False,
                        "error": str(exc),
                        "elapsedMs": round(elapsed * 1000, 1),
                    }
                )
                print(f"[FAIL] {name} raised {exc}")

        doc_id = state.get("first_document_id")
        if doc_id:
            print(f"Fetching TIU text for document {doc_id} ...")
            started = time.time()
            try:
                raw = client.invoke("TIU GET RECORD TEXT", [str(doc_id)])
                elapsed = time.time() - started
                lines = _split_lines(raw)
                ok, failure_reason = _classify_payload(raw)
                entry: Dict[str, Any] = {
                    "rpc": "TIU GET RECORD TEXT",
                    "description": f"Document text for {doc_id}",
                    "params": [doc_id],
                    "ok": ok,
                    "lineCount": len(lines),
                    "elapsedMs": round(elapsed * 1000, 1),
                    "preview": lines[:3],
                }
                if failure_reason:
                    entry["failureReason"] = failure_reason
                results["tests"].append(entry)
                status = "OK" if ok else "FAIL"
                detail = f" ({failure_reason})" if failure_reason else ""
                print(f"[{status}] TIU GET RECORD TEXT -> {len(lines)} line(s){detail}")
            except Exception as exc:
                elapsed = time.time() - started
                results["tests"].append(
                    {
                        "rpc": "TIU GET RECORD TEXT",
                        "description": f"Document text for {doc_id}",
                        "params": [doc_id],
                        "ok": False,
                        "error": str(exc),
                        "elapsedMs": round(elapsed * 1000, 1),
                    }
                )
                print(f"[FAIL] TIU GET RECORD TEXT raised {exc}")
        else:
            print("No TIU document IDs returned; skipping TIU GET RECORD TEXT.")
            results["tests"].append(
                {
                    "rpc": "TIU GET RECORD TEXT",
                    "description": "Document text (skipped, no headers)",
                    "params": [],
                    "ok": False,
                    "error": "TIU DOCUMENTS returned no document IDs",
                }
            )

    finally:
        client.close()

    if args.out:
        out_path = Path(args.out)
    else:
        examples_dir = Path(__file__).resolve().parent.parent / "examples"
        timestamp = time.strftime("%Y%m%d_%H%M%S", time.localtime())
        out_path = examples_dir / f"cprs_rpc_smoke_{timestamp}.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(results, indent=2), encoding="utf-8")
    print(f"Results written to {out_path}")


if __name__ == "__main__":
    main()
