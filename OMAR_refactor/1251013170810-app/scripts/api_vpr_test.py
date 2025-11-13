from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv

# Ensure project root is importable before loading app modules
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

load_dotenv()

# Embedded vista-api-x defaults keep this script self-contained for diagnostics
EMBED_VISTA_API_BASE_URL = 'https://vista-api-x.vetext.app/api'
EMBED_VISTA_API_KEY = 'THRcjCj3WuSZoMW1.fAAD6srSpwcvwIH'
EMBED_VISTA_API_VERIFY_SSL = False

os.environ.setdefault('VISTA_API_BASE_URL', EMBED_VISTA_API_BASE_URL)
if EMBED_VISTA_API_KEY and not os.environ.get('VISTA_API_KEY'):
    os.environ['VISTA_API_KEY'] = EMBED_VISTA_API_KEY
os.environ.setdefault('VISTA_API_VERIFY_SSL', 'true' if EMBED_VISTA_API_VERIFY_SSL else 'false')

from app.gateways.vista_api_x_gateway import VistaApiXGateway  # noqa: E402


def dump_documents_domain(dfn: str, station: str, duz: str, outdir: str) -> Path:
    gw = VistaApiXGateway(station=station, duz=duz)
    documents_payload = gw.get_vpr_domain(dfn, domain='document')

    out_path = Path(outdir)
    out_path.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    target = out_path / f"vpr_documents_{dfn}_{timestamp}.json"

    with target.open('w', encoding='utf-8') as fh:
        json.dump(documents_payload, fh, indent=2)

    return target


if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser(description='Dump VPR documents domain JSON via vista-api-x')
    parser.add_argument('--dfn', default=os.getenv('TEST_DFN', '237'))
    parser.add_argument('--station', default=os.getenv('TEST_STATION', '500'))
    parser.add_argument('--duz', default=os.getenv('TEST_DUZ', '983'))
    parser.add_argument('--out', default=os.getenv('SNAPSHOT_OUTDIR', 'examples'))
    args = parser.parse_args()

    output_file = dump_documents_domain(
        dfn=str(args.dfn),
        station=str(args.station),
        duz=str(args.duz),
        outdir=args.out,
    )
    print(f"Wrote documents JSON snapshot to {output_file}")
