import json

def vpr_to_fully_compliant_fhir_bundle(vpr_json):
    items = vpr_json.get("payload", {}).get("data", {}).get("items", [])
    bundle = {
        "resourceType": "Bundle",
        "type": "collection",
        "entry": []
    }

    patient_id = None

    for item in items:
        fhir_resource = None

        # --------------------------
        # PATIENT
        # --------------------------
        if "givenNames" in item or "fullName" in item:
            patient_id = f"patient-{item.get('localId')}"
            fhir_resource = {
                "resourceType": "Patient",
                "id": patient_id,
                "identifier": [{"system": "http://va.gov/icn", "value": str(item.get("icn"))}],
                "name": [{"family": item.get("familyName"), "given": [item.get("givenNames")]}],
                "gender": item.get("genderName", "").lower(),
                "birthDate": str(item.get("dateOfBirth")),
                "address": [{
                    "line": [item.get("addresses", [{}])[0].get("streetLine1", "")],
                    "city": item.get("addresses", [{}])[0].get("city", ""),
                    "state": item.get("addresses", [{}])[0].get("stateProvince", ""),
                    "postalCode": item.get("addresses", [{}])[0].get("postalCode", "")
                }]
            }

        # --------------------------
        # CONDITION
        # --------------------------
        elif "problemText" in item or "icdName" in item:
            fhir_resource = {
                "resourceType": "Condition",
                "id": f"condition-{item.get('localId')}",
                "clinicalStatus": {
                    "coding": [{
                        "system": "http://terminology.hl7.org/CodeSystem/condition-clinical",
                        "code": "active" if item.get("statusName","").upper()=="ACTIVE" else "inactive"
                    }]
                },
                "verificationStatus": {
                    "coding": [{
                        "system": "http://terminology.hl7.org/CodeSystem/condition-ver-status",
                        "code": "confirmed"
                    }]
                },
                "category": [{
                    "coding": [{
                        "system": "http://terminology.hl7.org/CodeSystem/condition-category",
                        "code": "problem-list-item"
                    }]
                }],
                "code": {
                    "coding": [
                        {
                            "system": "http://hl7.org/fhir/sid/icd-10",
                            "code": item.get("icdCode", "").split(":")[-1],
                            "display": item.get("icdName")
                        },
                        {
                            "system": "http://snomed.info/sct",
                            "code": item.get("problemText", "").split("SCT")[-1].strip("() "),
                            "display": item.get("problemText", "")
                        }
                    ],
                    "text": item.get("problemText", "")
                },
                "subject": {"reference": f"Patient/{patient_id}"},
                "onsetDateTime": str(item.get("entered"))
            }

        # --------------------------
        # MEDICATION
        # --------------------------
        elif "oiName" in item or "service" in item:
            fhir_resource = {
                "resourceType": "MedicationStatement",
                "id": f"med-{item.get('localId')}",
                "status": item.get("statusName", "active").lower(),
                "medicationCodeableConcept": {
                    "coding": [{
                        "system": "http://www.nlm.nih.gov/research/umls/rxnorm",
                        "code": item.get("oiCode","").split(":")[-1],
                        "display": item.get("oiName")
                    }],
                    "text": item.get("oiName")
                },
                "subject": {"reference": f"Patient/{patient_id}"},
                "effectiveDateTime": str(item.get("start"))
            }

        # --------------------------
        # DOCUMENT (PROGRESS NOTE)
        # --------------------------
        elif "documentType" in item or "title" in item:
            fhir_resource = {
                "resourceType": "DocumentReference",
                "id": f"note-{item.get('localId')}",
                "status": "current",
                "type": {"text": item.get("title")},
                "subject": {"reference": f"Patient/{patient_id}"},
                "date": str(item.get("entered")),
                "content": [{
                    "attachment": {
                        "contentType": "text/plain",
                        "data": item.get("text", "")
                    }
                }]
            }

        # --------------------------
        # OBSERVATION (LABS, VITALS, HEALTH FACTORS)
        # --------------------------
        elif "categoryName" in item or "healthFactorName" in item or "labName" in item or "vitalName" in item:
            code_text = item.get("healthFactorName") or item.get("labName") or item.get("vitalName") or item.get("categoryName")
            fhir_resource = {
                "resourceType": "Observation",
                "id": f"obs-{item.get('localId')}",
                "status": "final",
                "category": [{
                    "coding": [{
                        "system": "http://terminology.hl7.org/CodeSystem/observation-category",
                        "code": "laboratory" if "labName" in item else "social-history",
                        "display": "Lab" if "labName" in item else "Social History"
                    }]
                }],
                "code": {
                    "text": code_text
                },
                "effectiveDateTime": str(item.get("entered")),
                "subject": {"reference": f"Patient/{patient_id}"}
            }

        # --------------------------
        # CATCH ALL FOR OTHER ITEMS
        # --------------------------
        else:
            fhir_resource = {
                "resourceType": "DetectedIssue",
                "id": f"other-{item.get('localId', len(bundle['entry']))}",
                "status": "final",
                "code": {"text": json.dumps(item)},
                "mitigation": []
            }

        bundle["entry"].append({"resource": fhir_resource})

    return bundle


# ✅ Example usage
if __name__ == "__main__":
    with open("rpcresult_237_VPR_GET_PATIENT_DATA_JSON.json") as f:
        data = json.load(f)

    fhir_bundle = vpr_to_fully_compliant_fhir_bundle(data)

    with open("patient_fhir_bundle_full_compliant.json", "w") as f:
        json.dump(fhir_bundle, f, indent=2)

    print("✅ Generated fully compliant FHIR bundle.")
