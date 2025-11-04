from app.services.transforms import vpr_to_quick_allergies


def _wrap_items(items):
    return {
        "data": {
            "items": items
        }
    }


def test_allergies_quick_uses_products_name_for_substance():
    # VPR-like allergy item where substance is under products[0].name
    vpr_item = {
        "entered": 200503171910,
        "facilityCode": 500,
        "facilityName": "CAMP MASTER",
        "historical": True,
        "kind": "Allergy / Adverse Reaction",
        "localId": 744,
        "products": [
            {"name": "PENICILLIN", "vuid": "urn:va:vuid:"}
        ],
        "reactions": [
            {"name": "ITCHING,WATERING EYES", "vuid": "urn:va:vuid:"}
        ],
        "reference": "125;GMRD(120.82,",
        "summary": "PENICILLIN",
        "uid": "urn:va:allergy:84F0:237:744",
        "verified": 20050317191042
    }
    vpr_payload = _wrap_items([vpr_item])

    quick = vpr_to_quick_allergies(vpr_payload)
    assert isinstance(quick, list) and len(quick) == 1
    a = quick[0]
    assert a.get("substance") == "PENICILLIN"
    # reactions should be a list of strings
    reactions = a.get("reactions") or []
    assert isinstance(reactions, list)
    assert "ITCHING,WATERING EYES" in reactions
    # status should reflect historical when not otherwise provided
    assert a.get("status") == "historical"
