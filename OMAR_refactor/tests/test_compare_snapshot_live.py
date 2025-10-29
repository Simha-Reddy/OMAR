import os
import json
import pytest
from pathlib import Path

from scripts.compare_snapshot import generate_compare_snapshot


@pytest.mark.integration
def test_generate_compare_snapshot_live(tmp_path: Path):
    """
    Live integration snapshot for DFN 237 at station 500 and DUZ 983.
    This test is skipped unless LIVE_VISTA=1 and VISTA_API_KEY is set in the env.
    Writes a JSON snapshot under examples/.
    """
    if os.getenv("LIVE_VISTA", "0").lower() not in ("1", "true", "yes", "on"):
        pytest.skip("LIVE_VISTA not enabled; set LIVE_VISTA=1 to run this live test")
    if not os.getenv("VISTA_API_KEY"):
        pytest.skip("VISTA_API_KEY is not configured")

    # Write to a temp file under examples/ to avoid naming collisions
    examples_dir = Path(__file__).resolve().parents[1] / "examples"
    examples_dir.mkdir(parents=True, exist_ok=True)
    out_file = examples_dir / "compare_237_test.json"
    if out_file.exists():
        out_file.unlink()

    p = generate_compare_snapshot(dfn="237", station="500", duz="983", out_dir=examples_dir, filename=out_file.name)
    assert p.exists(), "Snapshot file was not created"

    # Basic structure checks
    with p.open("r", encoding="utf-8") as f:
        data = json.load(f)
    assert data.get("dfn") == "237"
    domains = data.get("domains") or {}
    # Ensure all expected domains are present
    for dom in [
        "demographics","meds","labs","vitals","notes","radiology","procedures","encounters","problems","allergies"
    ]:
        assert dom in domains, f"Missing domain in snapshot: {dom}"
