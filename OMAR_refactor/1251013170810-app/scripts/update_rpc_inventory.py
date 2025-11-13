#!/usr/bin/env python3
"""
Update docs/rpc_inventory.md summary table based on RPC usages found in the codebase.

- Scans OMAR_refactor/app and OMAR_refactor/scripts for:
  * gateway.call_rpc(context='...', rpc='...')
  * call_in_context(<ctx>, 'RPC NAME', ...)
  * the gateway-embedded strings 'VPR GET PATIENT DATA JSON' and 'VPR GET PATIENT DATA'
- Builds an alphabetized table of unique RPCs with contexts.
- Preserves existing 'Purpose' text from the current table between markers.

Usage:
  python OMAR_refactor/scripts/update_rpc_inventory.py
or (recommended Windows embedded python)
    OMAR_refactor\\python\\python.exe OMAR_refactor\\scripts\\update_rpc_inventory.py
"""
from __future__ import annotations
import re
import sys
from pathlib import Path
from collections import defaultdict
from datetime import datetime

ROOT = Path(__file__).resolve().parents[1]  # OMAR_refactor/
DOC_PATH = ROOT / "docs" / "rpc_inventory.md"
SEARCH_DIRS = [ROOT / "app", ROOT / "scripts"]
EXCLUDE_DIR_NAMES = {"python", "__pycache__"}
TABLE_START = "<!-- RPC_TABLE_START -->"
TABLE_END = "<!-- RPC_TABLE_END -->"

# Known default contexts to infer when variables are used
INFERRED_CONTEXTS = {
    # VistaSocketGateway VPR XML default
    "self.vpr_context": "JLV WEB SERVICES",
}

# Seed purpose descriptions (only used for new RPCs)
SEED_PURPOSE = {
    "VPR GET PATIENT DATA JSON": "Fetch patient domain or full chart (JSON; DEMO HTTP mode)",
    "VPR GET PATIENT DATA": "Fetch patient domain (XML variant; socket mode)",
}

CALL_RPC_ARGS_RE = re.compile(r"call_rpc\((?P<args>[^)]*)\)", re.DOTALL)
ARG_KV_RE = re.compile(r"(rpc|context)\s*=\s*([\'\"])(?P<val>.+?)\2")
# Pattern retained for future expansion (currently unused)
RPC_LITERAL_RE = re.compile(r"[\'\"](?P<rpc>(?:[A-Z0-9 ]|[-_#])+)[\'\"]")
CALL_IN_CONTEXT_RE = re.compile(r"call_in_context\(\s*(?P<ctx>[^,\)]+?)\s*,\s*['\"](?P<rpc>[^'\"]+)['\"]")

# Also pick up these literals anywhere in files
VPR_JSON_LIT = "VPR GET PATIENT DATA JSON"
VPR_XML_LIT = "VPR GET PATIENT DATA"


def iter_py_files():
    for base in SEARCH_DIRS:
        if not base.exists():
            continue
        for p in base.rglob("*.py"):
            if any(part in EXCLUDE_DIR_NAMES for part in p.parts):
                continue
            yield p


def scan_file(path: Path):
    text = path.read_text(encoding="utf-8", errors="ignore")
    found = []  # list of tuples (rpc, context or None)

    # call_rpc(...)
    for m in CALL_RPC_ARGS_RE.finditer(text):
        args = m.group("args") or ""
        rpc = None
        ctx = None
        for m2 in ARG_KV_RE.finditer(args):
            key = m2.group(1)
            val = m2.group("val")
            if key == "rpc":
                rpc = val
            elif key == "context":
                ctx = val
        if rpc:
            found.append((rpc.strip(), (ctx or "").strip() or None))

    # call_in_context(ctx, 'RPC', ...)
    for m in CALL_IN_CONTEXT_RE.finditer(text):
        ctx_expr = (m.group("ctx") or "").strip()
        rpc = (m.group("rpc") or "").strip()
        ctx = INFERRED_CONTEXTS.get(ctx_expr)
        # Try literal string context like 'OR CPRS GUI CHART'
        if not ctx and (ctx_expr.startswith("'") or ctx_expr.startswith('"')):
            ctx = ctx_expr.strip().strip("'\"")
        found.append((rpc, ctx))

    # Raw literals for VPR JSON/XML in gateways
    if VPR_JSON_LIT in text:
        found.append((VPR_JSON_LIT, "LHS RPC CONTEXT"))
    if VPR_XML_LIT in text:
        found.append((VPR_XML_LIT, "JLV WEB SERVICES"))

    return found


def build_inventory():
    rpc_to_contexts: dict[str, set[str]] = defaultdict(set)
    for f in iter_py_files():
        try:
            for rpc, ctx in scan_file(f):
                if rpc:
                    if ctx:
                        rpc_to_contexts[rpc].add(ctx)
                    else:
                        rpc_to_contexts[rpc]  # ensure key exists
        except Exception:
            continue
    return rpc_to_contexts


def parse_existing_table(md_text: str):
    """Return (before, table, after, rows_dict) where rows_dict maps RPC->(contexts, purpose)."""
    start = md_text.find(TABLE_START)
    end = md_text.find(TABLE_END)
    if start == -1 or end == -1 or end < start:
        # No markers; return whole doc as before, no table
        return md_text, "", "", {}
    before = md_text[: start + len(TABLE_START)]
    table = md_text[start + len(TABLE_START) : end]
    after = md_text[end:]
    rows = {}
    lines = [ln.strip() for ln in table.strip().splitlines() if ln.strip()]
    # Expect header, separator, then rows
    for ln in lines:
        if ln.startswith("|") and ("---" not in ln):
            parts = [p.strip() for p in ln.strip("|").split("|")]
            if len(parts) >= 3:
                rpc = parts[0]
                ctxs = parts[1]
                purpose = parts[2]
                rows[rpc] = (ctxs, purpose)
    return before, table, after, rows


def render_table(rpc_to_contexts: dict[str, set[str]], existing_rows: dict[str, tuple[str,str]]):
    header = (
        "\n| RPC Name                     | Context(s)            | Purpose                                                     |\n"
        "|------------------------------|-----------------------|-------------------------------------------------------------|\n"
    )
    lines = []
    for rpc in sorted(rpc_to_contexts.keys(), key=lambda s: s.upper()):
        ctxs = sorted([c for c in rpc_to_contexts[rpc] if c])
        ctx_str = ", ".join(ctxs) if ctxs else ""
        # Preserve purpose if present
        if rpc in existing_rows:
            _, purpose = existing_rows[rpc]
        else:
            purpose = SEED_PURPOSE.get(rpc, "-")
        lines.append(f"| {rpc:<28} | {ctx_str:<21} | {purpose:<59} |")
    return "\n" + header + "\n".join(lines) + "\n"


def update_doc():
    md = DOC_PATH.read_text(encoding="utf-8")
    before, _table, after, existing_rows = parse_existing_table(md)
    inv = build_inventory()
    new_table = render_table(inv, existing_rows)
    # Update last updated date near the top of the file
    today = datetime.utcnow().date().isoformat()
    md_updated = md
    md_updated = re.sub(r"(?m)^Last updated: .*", f"Last updated: {today}", md_updated)
    # Inject table between markers
    if TABLE_START in md_updated and TABLE_END in md_updated:
        start = md_updated.find(TABLE_START) + len(TABLE_START)
        end = md_updated.find(TABLE_END)
        md_updated = md_updated[:start] + new_table + md_updated[end:]
    else:
        # Fallback: append markers and table at end
        md_updated = md_updated.rstrip() + f"\n\n{TABLE_START}{new_table}{TABLE_END}\n"
    DOC_PATH.write_text(md_updated, encoding="utf-8")
    print(f"Updated RPC inventory table with {len(inv)} unique RPC(s).")


if __name__ == "__main__":
    try:
        update_doc()
    except Exception as e:
        print(f"[ERROR] Failed to update RPC inventory: {e}", file=sys.stderr)
        sys.exit(1)
