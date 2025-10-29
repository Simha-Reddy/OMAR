import sys
import os
# Avoid importing the full `app` package (which triggers Flask deps).
# Import the transforms module directly by path.
ROOT = os.path.join(os.path.dirname(__file__), '..')
SERVICES_DIR = os.path.join(ROOT, 'app', 'services')
sys.path.insert(0, os.path.abspath(SERVICES_DIR))
import transforms as T

vpr = {"data": {"items": [{
    "fullName": "DOE,JOHN",
    "familyName": "DOE",
    "givenNames": "JOHN",
    "localId": "123",
    "icn": "123V456789",
    "dateOfBirth": "19700115",
    "genderName": "Male",
    "ssn": "123456789",
    "addresses": [{
        "streetLine1": "1 MAIN ST",
        "city": "ANYTOWN",
        "stateProvince": "VA",
        "postalCode": "22031",
    }],
    "telecoms": [
        {"usageName": "MC", "telecom": "555-111-2222"},
        {"usageName": "WP", "telecom": "555-333-4444"}
    ],
}]}}

quick = T.map_vpr_patient_to_quick_demographics(vpr)
assert quick.get('Name') in ('DOE, JOHN', 'DOE,JOHN')
assert quick.get('DOB_ISO') == '1970-01-15'
assert quick.get('Gender') == 'Male'
assert quick.get('DFN') == '123'
assert quick.get('ICN') == '123V456789'
assert quick.get('SSN') == '123-45-6789'
print('OK')
