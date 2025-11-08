from __future__ import annotations
import os
import json
from pathlib import Path
from datetime import datetime, timezone
from dotenv import load_dotenv

# Ensure project root (containing 'app/') is on sys.path when running as a script
import sys
ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

# Load .env BEFORE importing gateway modules that read env at import time
load_dotenv()

# Use application services directly
from app.services.patient_service import PatientService
from app.gateways.vista_api_x_gateway import VistaApiXGateway


def generate_compare_snapshot(dfn: str = "237", station: str = "500", duz: str = "983", out_dir: str | os.PathLike = "examples", filename: str | None = None) -> Path:
    """
    Fetch raw VPR and quick transforms for key domains for a given DFN,
    and save a JSON snapshot for review and transform tuning.

    Returns the path to the written file.
    """
    # Load .env (VISTA_API_BASE_URL, VISTA_API_KEY, etc.)
    load_dotenv()

    # Prepare service
    gw = VistaApiXGateway(station=station, duz=duz)
    svc = PatientService(gateway=gw)

    # Domains to compare (route names, PatientService handles alias mapping)
    domains = [
        "demographics",  # maps to VPR 'patient'
        "meds",
        "labs",
        "vitals",
        "notes",        # maps to VPR 'documents'
        "radiology",
        "procedures",
        "encounters",   # maps to VPR 'visits'
        "problems",
        "allergies",
    ]

    # Build results
    results: dict[str, dict] = {}
    for dom in domains:
        try:
            raw = svc.get_vpr_raw(dfn, dom)
            if dom in ("patient", "demographics"):
                quick = svc.get_demographics_quick(dfn)
            elif dom == "meds":
                quick = svc.get_medications_quick(dfn)
            elif dom == "labs":
                quick = svc.get_labs_quick(dfn)
            elif dom == "vitals":
                quick = svc.get_vitals_quick(dfn)
            elif dom == "notes":
                quick = svc.get_notes_quick(dfn)
            elif dom == "radiology":
                quick = svc.get_radiology_quick(dfn)
            elif dom == "procedures":
                quick = svc.get_procedures_quick(dfn)
            elif dom == "encounters":
                quick = svc.get_encounters_quick(dfn)
            elif dom == "problems":
                quick = svc.get_problems_quick(dfn)
            elif dom == "allergies":
                quick = svc.get_allergies_quick(dfn)
            else:
                quick = None
            results[dom] = {"raw": raw, "quick": quick}
        except Exception as e:
            results[dom] = {"error": str(e)}

    # Write to examples/
    out_path = Path(out_dir)
    out_path.mkdir(parents=True, exist_ok=True)
    if not filename:
        ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        filename = f"compare_{dfn}_{ts}.json"
    file_path = out_path / filename
    with file_path.open("w", encoding="utf-8") as f:
        json.dump({
            "dfn": dfn,
            "station": station,
            "duz": duz,
            "generatedAt": datetime.now(timezone.utc).isoformat().replace("+00:00","Z"),
            "domains": results,
        }, f, indent=2)
    return file_path


if __name__ == "__main__":
    # Defaults: DFN 237, station 500, duz 983; override via env or CLI args
    import argparse

    parser = argparse.ArgumentParser(description="Generate compare snapshot for a patient")
    parser.add_argument("--dfn", default=os.getenv("TEST_DFN", "237"))
    parser.add_argument("--station", default=os.getenv("TEST_STATION", "500"))
    parser.add_argument("--duz", default=os.getenv("TEST_DUZ", "983"))
    parser.add_argument("--out", default=os.getenv("SNAPSHOT_OUTDIR", "examples"))
    parser.add_argument("--file", default=None, help="Optional output filename")
    args = parser.parse_args()

    p = generate_compare_snapshot(dfn=args.dfn, station=args.station, duz=args.duz, out_dir=args.out, filename=args.file)
    print(f"Wrote snapshot to: {p}")
