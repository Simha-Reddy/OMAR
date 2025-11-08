#!/usr/bin/env python3
"""
Fetch VPR GET PATIENT DATA (XML) via vista-api-x and write it to OMAR_refactor/examples.

Requirements:
- Environment variables for vista-api-x (at minimum VISTA_API_KEY).
  Optional: VISTA_API_BASE_URL, VISTA_API_VERIFY_SSL (true/false).
- Network access to the vista-api-x service.

Usage examples:
  python scripts/fetch_vpr_xml.py                  # DFN 237, default station/user, default output path
  python scripts/fetch_vpr_xml.py --dfn 123        # Different DFN
  python scripts/fetch_vpr_xml.py --domain meds    # Restrict by domain
  python scripts/fetch_vpr_xml.py --output OMAR_refactor/examples/my.xml

This script imports the existing OMAR/vista_api_x.py helper by adding the OMAR folder to sys.path.
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path
from typing import Optional

# Load .env from OMAR_refactor by default so VISTA_API_KEY and friends are available
try:
    from dotenv import load_dotenv  # type: ignore
except Exception:
    load_dotenv = None  # will handle gracefully

# --- vista-api-x (required for patient reads) ---
# Base URL of the vista-api-x HTTP facade (not the VistA socket). Example includes /api suffix.
VISTA_API_BASE_URL='https://vista-api-x.vetext.app/api'
# API key used to obtain a short-lived JWT from vista-api-x.
VISTA_API_KEY='THRcjCj3WuSZoMW1.fAAD6srSpwcvwIH'
# Verify TLS certificates on HTTPS calls. Use true in production.
VISTA_API_VERIFY_SSL=False

# Add the sibling OMAR directory to sys.path so we can import vista_api_x
HERE = Path(__file__).resolve()
OMAR_REFACTOR_DIR = HERE.parents[1]
WORKSPACE_ROOT = OMAR_REFACTOR_DIR.parent
OMAR_DIR = WORKSPACE_ROOT / "OMAR"
if str(OMAR_DIR) not in sys.path:
    sys.path.insert(0, str(OMAR_DIR))

# Make sure environment variables are set so vista_api_x picks them up at import-time.
# Prefer existing environment or .env values; fall back to hardcoded constants.
try:
    # Load .env files early so import-time constants in vista_api_x see them
    if load_dotenv is not None:
        for _env_path in [OMAR_REFACTOR_DIR / ".env", WORKSPACE_ROOT / ".env"]:
            if _env_path.exists():
                load_dotenv(dotenv_path=str(_env_path), override=False)
except Exception:
    pass

os.environ.setdefault("VISTA_API_BASE_URL", VISTA_API_BASE_URL)
if VISTA_API_KEY:
    os.environ.setdefault("VISTA_API_KEY", VISTA_API_KEY)
os.environ.setdefault("VISTA_API_VERIFY_SSL", "true" if bool(VISTA_API_VERIFY_SSL) else "false")

try:
    # Now we can import the web gateway helper
    import vista_api_x  # type: ignore
except Exception as e:
    print(f"[ERROR] Failed to import vista_api_x from {OMAR_DIR}: {e}")
    sys.exit(1)


def _load_env_files(explicit_env: Optional[Path] = None) -> None:
    """Load environment variables from .env files if python-dotenv is present.

    Priority:
    1) explicit --env path, if provided
    2) OMAR_refactor/.env
    3) workspace root .env (if present)
    """
    if load_dotenv is None:
        # python-dotenv not installed, silently skip
        return
    candidates = []
    if explicit_env:
        candidates.append(explicit_env)
    candidates.append(OMAR_REFACTOR_DIR / ".env")
    candidates.append(WORKSPACE_ROOT / ".env")
    for path in candidates:
        try:
            if path and path.exists():
                load_dotenv(dotenv_path=str(path), override=False)
        except Exception:
            # Non-fatal; continue to next candidate
            continue


def fetch_vpr_xml(
    *,
    dfn: str,
    station: str = "500",
    user_id: str = "983",
    domain: Optional[str] = None,
    timeout: int = 120,
    token: Optional[str] = None,
) -> str:
    """Call VPR GET PATIENT DATA (XML) via vista-api-x and return the raw XML string.

    Contract:
    - Inputs: DFN (patient_id), station, user_id, optional domain, optional existing JWT token.
    - Output: raw XML string (raises exception on error).
    - Errors: raises vista_api_x.VistaAPIError on transport or 4xx/5xx; ValueError for bad inputs.
    """
    if not dfn:
        raise ValueError("dfn is required")

    # Acquire token if not provided
    # Prefer an explicit token, then env var, then embedded constant fallback
    embedded_or_env_key = os.getenv("VISTA_API_KEY") or VISTA_API_KEY
    tok = token or vista_api_x.get_jwt_token(api_key=embedded_or_env_key)

    # For the XML RPC variant, pass the DFN as a single string parameter (literal).
    # The JSON variant uses a named array, but XML accepts just the DFN.
    context = "LHS RPC CONTEXT"
    rpc_name = "VPR GET PATIENT DATA"

    result_text, tok2 = vista_api_x.call_rpc(
        tok,
        station=station,
        user_id=user_id,
        context=context,
        rpc=rpc_name,
        parameters=[{"string": str(dfn)}],
        json_result=False,
        timeout=timeout,
    )

    if not isinstance(result_text, str):
        # Defensive: call_rpc with json_result=False should return text
        result_text = str(result_text)

    # Basic sanity: ensure we got non-empty payload
    if not result_text.strip():
        raise vista_api_x.VistaAPIError("Empty response from VPR GET PATIENT DATA")

    return result_text


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Fetch VPR GET PATIENT DATA (XML) via vista-api-x")
    parser.add_argument("--dfn", default="237", help="Patient DFN (default: 237)")
    parser.add_argument("--station", default="500", help="VistA station/site number (default: 500)")
    parser.add_argument("--user-id", default="983", help="VistA user DUZ for the proxy user (default: 983)")
    parser.add_argument("--domain", default=None, help="Optional domain filter (e.g., 'meds', 'problems', etc.)")
    parser.add_argument("--timeout", type=int, default=120, help="HTTP timeout in seconds (default: 120)")
    parser.add_argument(
        "--output",
        default=str(OMAR_REFACTOR_DIR / "examples" / "237_VPR_GET_PATIENT_DATA_XML_example.xml"),
        help="Output file path for the XML payload",
    )
    parser.add_argument(
        "--env",
        default=None,
        help="Optional path to a .env file to load (defaults to OMAR_refactor/.env)",
    )
    parser.add_argument(
        "--print",
        action="store_true",
        help="Also print a short preview of the XML to stdout",
    )
    args = parser.parse_args(argv)

    # Load .env so vista_api_x can pick up VISTA_API_KEY, etc.
    _load_env_files(Path(args.env) if args.env else None)

    try:
        xml_text = fetch_vpr_xml(
            dfn=args.dfn,
            station=args.station,
            user_id=args.user_id,
            domain=args.domain,
            timeout=args.timeout,
        )
    except Exception as e:
        print(f"[ERROR] Failed to fetch VPR XML: {e}")
        return 2

    out_path = Path(args.output)
    try:
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(xml_text, encoding="utf-8")
    except Exception as e:
        print(f"[ERROR] Failed to write output to {out_path}: {e}")
        return 3

    size_kb = out_path.stat().st_size / 1024.0
    print(f"[OK] Wrote VPR XML for DFN {args.dfn} to: {out_path} ({size_kb:.1f} KB)")

    if args.print:
        preview = xml_text.strip().splitlines()[:20]
        print("\nPreview (first 20 lines):\n" + "\n".join(preview))

    # Helpful hint for the next step
    json_example = OMAR_REFACTOR_DIR / "examples" / "237_VPR_GET_PATIENT_DATA_JSON_example.json"
    if json_example.exists():
        print(f"\nJSON example for comparison: {json_example}")
    else:
        print("\nNote: JSON example file not found; expected at OMAR_refactor/examples/237_VPR_GET_PATIENT_DATA_JSON_example.json")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
