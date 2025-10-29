from app.services.transforms import vpr_to_quick_medications


def sample_vpr_meds():
    return {
        "data": {"items": [
            {
                "display": "ATORVASTATIN 20MG TAB",
                "vaStatus": "ACTIVE",
                "overallStart": "20230101",
                "overallStop": "20231231",
            },
            {
                "qualifiedName": "LISINOPRIL 10MG TAB",
                "statusName": "Discontinued",
                "start": "20220115",
                "stop": "20220701",
            }
        ]}
    }


def test_meds_quick_only():
    vpr = sample_vpr_meds()
    quick = vpr_to_quick_medications(vpr)
    assert len(quick) == 2
    names = {m['name'] for m in quick}
    assert 'ATORVASTATIN 20MG TAB' in names
    assert 'LISINOPRIL 10MG TAB' in names


def test_meds_direct_quick():
    vpr = sample_vpr_meds()
    quick = vpr_to_quick_medications(vpr)
    assert len(quick) == 2
    assert quick[0]['startDate'].startswith('2023-01-01')