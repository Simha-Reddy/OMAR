from app.services.transforms import vpr_to_quick_labs


def _wrap_items(items):
    return {
        "data": {
            "items": items
        }
    }


def test_labs_quick_maps_core_fields_and_abnormal():
    vpr_item = {
        "displayName": "INR",
        "observed": 202310252318,
        "result": 1,
        "units": "",
        "specimen": "BLOOD",
        "low": 2.0,
        "high": 3.0,
    }
    quick = vpr_to_quick_labs(_wrap_items([vpr_item]))
    assert isinstance(quick, list) and len(quick) == 1
    it = quick[0]
    assert it.get("name") == "INR"
    assert it.get("test") == "INR"
    assert it.get("result") == 1
    assert it.get("units") == ""
    assert it.get("unit") == ""
    assert it.get("specimen") == "BLOOD"
    assert it.get("referenceRange") == "2.0 - 3.0"
    # 1 is below 2.0 => abnormal True
    assert it.get("abnormal") is True
    # Dates
    assert it.get("observed") == 202310252318
    assert it.get("observedDate") and isinstance(it.get("observedDate"), str)
    assert it.get("resulted") == it.get("observedDate")


def test_labs_quick_abnormal_null_without_range():
    vpr_item = {
        "displayName": "Calcium",
        "observed": 202310252318,
        "result": 9.0,
        "units": "mg/dL",
        # No low/high present
    }
    quick = vpr_to_quick_labs(_wrap_items([vpr_item]))
    it = quick[0]
    assert it.get("referenceRange") is None
    assert it.get("abnormal") is None
