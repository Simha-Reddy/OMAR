import sys, os
ROOT = os.path.join(os.path.dirname(__file__), '..')
SERVICES_DIR = os.path.join(ROOT, 'app', 'services')
sys.path.insert(0, os.path.abspath(SERVICES_DIR))
import transforms as T

vpr = {"data": {"items": [
    {"display": "ATORVASTATIN 20MG TAB", "vaStatus": "ACTIVE", "overallStart": "20230101", "overallStop": "20231231"},
    {"qualifiedName": "LISINOPRIL 10MG TAB", "statusName": "Discontinued", "start": "20220115", "stop": "20220701"}
]}}

quick = T.vpr_to_quick_medications(vpr)
print('Quick meds:', quick)
