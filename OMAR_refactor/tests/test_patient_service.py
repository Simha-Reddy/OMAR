from app.services.patient_service import PatientService

class FakeGateway:
    def get_demographics(self, dfn: str):
        return {"data": {"items": [{"localId": dfn, "fullName": "Test, Patient"}]}}

def test_demographics_min():
    svc = PatientService(FakeGateway())
    out = svc.get_demographics("123")
    assert out["data"]["items"][0]["localId"] == "123"
