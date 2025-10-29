from app.services.transforms import map_vpr_patient_to_quick_demographics


def sample_vpr_patient():
    return {
        "data": {
            "items": [
                {
                    "fullName": "DOE,JOHN",
                    "familyName": "DOE",
                    "givenNames": "JOHN",
                    "localId": "123",
                    "icn": "123V456789",
                    "dateOfBirth": "19700115",
                    "genderName": "Male",
                    "ssn": "123456789",
                    "addresses": [
                        {
                            "streetLine1": "1 MAIN ST",
                            "city": "ANYTOWN",
                            "stateProvince": "VA",
                            "postalCode": "22031",
                        }
                    ],
                    "telecoms": [
                        {"usageName": "MC", "telecom": "555-111-2222"},
                        {"usageName": "WP", "telecom": "555-333-4444"}
                    ],
                }
            ]
        }
    }


def test_vpr_quick_demographics_only():
    vpr = sample_vpr_patient()
    quick = map_vpr_patient_to_quick_demographics(vpr)
    assert quick.get('Name') in ('DOE, JOHN', 'DOE,JOHN')
    assert quick.get('DOB_ISO') == '1970-01-15'
    assert quick.get('Gender') == 'Male'
    assert quick.get('DFN') == '123'
    assert quick.get('ICN') == '123V456789'


def test_direct_vpr_quick():
    vpr = sample_vpr_patient()
    quick = map_vpr_patient_to_quick_demographics(vpr)
    assert quick.get('SSN') == '123-45-6789'
    assert quick.get('Address') and 'ANYTOWN' in quick['Address']