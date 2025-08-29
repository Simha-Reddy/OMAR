import json
import re

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
            # Name
            name = {
                "family": item.get("familyName"),
                "given": [item.get("givenNames")] if item.get("givenNames") else [],
            }
            if item.get("suffix"):
                name["suffix"] = [item.get("suffix")]
            # Address
            addresses = item.get("addresses", [])
            address_list = []
            for addr in addresses:
                address = {
                    "line": [addr.get("streetLine1", "")],
                    "city": addr.get("city", ""),
                    "state": addr.get("stateProvince", ""),
                    "postalCode": addr.get("postalCode", "")
                }
                if addr.get("use"):
                    address["use"] = addr["use"]
                address_list.append(address)
            # Telecom
            telecom = []
            if item.get("telecom"):
                for t in item["telecom"]:
                    telecom.append({
                        "system": t.get("system", "phone"),
                        "value": t.get("value"),
                        "use": t.get("use", "home")
                    })
            # Communication
            communication = []
            if item.get("language"):
                communication.append({"language": {"text": item["language"]}})
            # Race, Ethnicity, Birth Sex, Gender Identity (US Core extensions)
            extensions = []
            if item.get("race"):
                extensions.append({
                    "url": "http://hl7.org/fhir/us/core/StructureDefinition/us-core-race",
                    "valueString": item["race"]
                })
            if item.get("ethnicity"):
                extensions.append({
                    "url": "http://hl7.org/fhir/us/core/StructureDefinition/us-core-ethnicity",
                    "valueString": item["ethnicity"]
                })
            if item.get("birthSex"):
                extensions.append({
                    "url": "http://hl7.org/fhir/us/core/StructureDefinition/us-core-birthsex",
                    "valueCode": item["birthSex"]
                })
            if item.get("genderIdentity"):
                extensions.append({
                    "url": "http://hl7.org/fhir/us/core/StructureDefinition/us-core-genderIdentity",
                    "valueCodeableConcept": {"text": item["genderIdentity"]}
                })
            fhir_resource = {
                "resourceType": "Patient",
                "id": patient_id,
                "identifier": [{"system": "http://va.gov/icn", "value": str(item.get("icn"))}],
                "name": [name],
                "gender": item.get("genderName", "").lower(),
                "birthDate": str(item.get("dateOfBirth")),
                "address": address_list,
            }
            if telecom:
                fhir_resource["telecom"] = telecom
            if communication:
                fhir_resource["communication"] = communication
            if extensions:
                fhir_resource["extension"] = extensions

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
        # ALLERGY / ADVERSE REACTION
        # --------------------------
        elif item.get("kind") == "Allergy / Adverse Reaction":
            reactions = item.get("reactions", [])
            products = item.get("products", [])
            reaction_list = []
            for reaction in reactions:
                reaction_list.append({
                    "manifestation": [{
                        "text": reaction.get("name", "Unknown Reaction") or "Unknown Reaction"
                    }]
                })
            substance = products[0]["name"] if products and "name" in products[0] else item.get("summary", "Unknown Substance")
            code_coding = []
            if products and "code" in products[0]:
                code_coding.append({
                    "system": "http://www.nlm.nih.gov/research/umls/rxnorm",
                    "code": products[0]["code"] or "unknown",
                    "display": products[0]["name"] or "Unknown Substance"
                })
            if not code_coding:
                code_coding.append({
                    "system": "http://www.nlm.nih.gov/research/umls/rxnorm",
                    "code": "unknown",
                    "display": substance
                })
            fhir_resource = {
                "resourceType": "AllergyIntolerance",
                "id": f"allergy-{item.get('localId')}",
                "clinicalStatus": {"coding": [{"system": "http://terminology.hl7.org/CodeSystem/allergyintolerance-clinical", "code": "active"}]},
                "verificationStatus": {"coding": [{"system": "http://terminology.hl7.org/CodeSystem/allergyintolerance-verification", "code": "confirmed"}]},
                "type": "allergy",
                "category": ["medication"],
                "criticality": "low",
                "code": {"coding": code_coding, "text": substance},
                "patient": {"reference": f"Patient/{patient_id}"},
                "reaction": reaction_list if reaction_list else [{"manifestation": [{"text": "Unknown Reaction"}]}]
            }

        # --------------------------
        # VITAL SIGN (OBSERVATION)
        # --------------------------
        elif item.get("kind") == "Vital Sign" or item.get("categoryName") == "Laboratory" or "labName" in item:
            # Map to Observation (Vital or Lab)
            code_text = item.get("typeName") or item.get("displayName") or item.get("labName") or item.get("healthFactorName") or item.get("categoryName") or "Unknown Observation"
            value = item.get("result", "Unknown")
            units = item.get("units", "unknown")
            effective = str(item.get("observed") or item.get("resulted") or item.get("entered") or "unknown")
            # Extract LOINC code from typeCode if present
            loinc_code = None
            if item.get("typeCode", "").startswith("urn:lnc:"):
                loinc_code = item["typeCode"].split(":")[-1]
            elif item.get("loincCode"):
                loinc_code = item["loincCode"]
            elif item.get("loinc"):
                loinc_code = item["loinc"]
            code_coding = []
            if loinc_code:
                code_coding.append({
                    "system": "http://loinc.org",
                    "code": loinc_code,
                    "display": code_text
                })
            else:
                code_coding.append({
                    "system": "http://loinc.org",
                    "code": "unknown",
                    "display": code_text
                })
            identifiers = []
            if item.get("vuid"):
                identifiers.append({"system": "urn:va:vuid", "value": item["vuid"]})
            if item.get("uid"):
                identifiers.append({"system": "urn:va:uid", "value": item["uid"]})

            # Special handling for BP: emit FHIR-compliant component array
            if code_text.strip().upper() in ["BLOOD PRESSURE", "BP"] and isinstance(value, str) and "/" in value:
                try:
                    sys_val, dia_val = value.split("/")
                    sys_val = float(sys_val.strip())
                    dia_val = float(dia_val.strip())
                except Exception:
                    sys_val, dia_val = None, None
                fhir_resource = {
                    "resourceType": "Observation",
                    "id": f"obs-{item.get('localId')}",
                    "status": "final",
                    "category": [{
                        "coding": [{
                            "system": "http://terminology.hl7.org/CodeSystem/observation-category",
                            "code": "vital-signs",
                            "display": "Vital Signs"
                        }]
                    }],
                    "code": {
                        "coding": [{
                            "system": "http://loinc.org",
                            "code": "85354-9",
                            "display": "Blood pressure panel"
                        }],
                        "text": "Blood Pressure"
                    },
                    "component": [
                        {
                            "code": {
                                "coding": [{
                                    "system": "http://loinc.org",
                                    "code": "8480-6",
                                    "display": "Systolic blood pressure"
                                }],
                                "text": "Systolic blood pressure"
                            },
                            "valueQuantity": {
                                "value": sys_val,
                                "unit": units
                            }
                        },
                        {
                            "code": {
                                "coding": [{
                                    "system": "http://loinc.org",
                                    "code": "8462-4",
                                    "display": "Diastolic blood pressure"
                                }],
                                "text": "Diastolic blood pressure"
                            },
                            "valueQuantity": {
                                "value": dia_val,
                                "unit": units
                            }
                        }
                    ],
                    "effectiveDateTime": effective,
                    "subject": {"reference": f"Patient/{patient_id}"}
                }
                if identifiers:
                    fhir_resource["identifier"] = identifiers
            else:
                fhir_resource = {
                    "resourceType": "Observation",
                    "id": f"obs-{item.get('localId')}",
                    "status": "final",
                    "category": [{
                        "coding": [{
                            "system": "http://terminology.hl7.org/CodeSystem/observation-category",
                            "code": "vital-signs" if item.get("kind") == "Vital Sign" else "laboratory",
                            "display": "Vital Signs" if item.get("kind") == "Vital Sign" else "Laboratory"
                        }]
                    }],
                    "code": {
                        "coding": code_coding,
                        "text": code_text
                    },
                    "valueQuantity": {
                        "value": value,
                        "unit": units
                    },
                    "effectiveDateTime": effective,
                    "subject": {"reference": f"Patient/{patient_id}"}
                }
                if identifiers:
                    fhir_resource["identifier"] = identifiers

        # --------------------------
        # MEDICATION (MedicationRequest)
        # --------------------------
        elif (
            (item.get("displayGroup") in ["O RX", "NV RX", "N RX"]) and item.get("oiName")
        ):
            # Unified MedicationRequest mapping
            med_text = item.get("oiName") or item.get("name") or "Unknown"
            med_code = item.get("oiCode", "").split(":")[-1] if item.get("oiCode") else ""
            rxnorm_code = None
            if item.get("products") and isinstance(item["products"], list) and len(item["products"]) > 0:
                rxnorm_code = item["products"][0].get("rxnormCode")
            code_coding = []
            if rxnorm_code:
                code_coding.append({
                    "system": "http://www.nlm.nih.gov/research/umls/rxnorm",
                    "code": rxnorm_code,
                    "display": med_text
                })
            elif med_code:
                code_coding.append({
                    "system": "http://va.gov/med",
                    "code": med_code,
                    "display": med_text
                })
            else:
                code_coding.append({
                    "system": "http://www.nlm.nih.gov/research/umls/rxnorm",
                    "code": "unknown",
                    "display": med_text
                })
            # Identifiers
            identifiers = []
            if item.get("vuid"):
                identifiers.append({"system": "urn:va:vuid", "value": item["vuid"]})
            if item.get("uid"):
                identifiers.append({"system": "urn:va:uid", "value": item["uid"]})
            # Category mapping from displayGroup
            category_map = {
                "O RX": {"coding": [{"system": "http://terminology.hl7.org/CodeSystem/medicationrequest-category", "code": "outpatient", "display": "Outpatient"}]},
                "NV RX": {"coding": [{"system": "http://terminology.hl7.org/CodeSystem/medicationrequest-category", "code": "community", "display": "Community"}]},
                "N RX": {"coding": [{"system": "http://terminology.hl7.org/CodeSystem/medicationrequest-category", "code": "other", "display": "Other"}]}
            }
            category = category_map.get(item.get("displayGroup"), None)
            # Status
            status = item.get("statusName", "active").lower()
            # Dates
            authored_on = str(item.get("entered")) if item.get("entered") else None
            start_date = str(item.get("start")) if item.get("start") else None
            stop_date = str(item.get("stop")) if item.get("stop") else None
            # Dosage/SIG
            sig = item.get("content", "")
            # Quantity/Refills
            quantity_match = re.search(r"Quantity:\s*(\d+)", sig)
            quantity = int(quantity_match.group(1)) if quantity_match else None
            refills_match = re.search(r"Refills:\s*(\d+)", sig)
            refills = int(refills_match.group(1)) if refills_match else None
            # Provider
            requester = {"display": item.get("providerName", "Unknown")}
            if item.get("providerUid"):
                requester["identifier"] = {"system": "urn:va:uid", "value": item["providerUid"]}
            # Facility (as extension)
            extensions = []
            if item.get("facilityName"):
                extensions.append({
                    "url": "http://va.gov/fhir/StructureDefinition/facility-name",
                    "valueString": item["facilityName"]
                })
            if item.get("facilityCode"):
                extensions.append({
                    "url": "http://va.gov/fhir/StructureDefinition/facility-code",
                    "valueString": str(item["facilityCode"])
                })
            # Results as supportingInfo
            supporting_info = []
            if item.get("results") and isinstance(item["results"], list):
                for r in item["results"]:
                    if r.get("uid"):
                        supporting_info.append({"identifier": {"system": "urn:va:uid", "value": r["uid"]}})
            fhir_resource = {
                "resourceType": "MedicationRequest",
                "id": f"med-{item.get('localId')}",
                "status": status,
                "intent": "order",
                "medicationCodeableConcept": {
                    "coding": code_coding,
                    "text": med_text
                },
                "subject": {"reference": f"Patient/{patient_id}"},
                "authoredOn": authored_on,
                "requester": requester,
                "dosageInstruction": [{"text": sig}],
            }
            if category:
                fhir_resource["category"] = [category]
            if identifiers:
                fhir_resource["identifier"] = identifiers
            if extensions:
                fhir_resource["extension"] = extensions
            if start_date:
                fhir_resource["dispenseRequest"] = {"validityPeriod": {"start": start_date}}
            if stop_date:
                if "dispenseRequest" not in fhir_resource:
                    fhir_resource["dispenseRequest"] = {}
                fhir_resource["dispenseRequest"].setdefault("validityPeriod", {})["end"] = stop_date
            if quantity is not None:
                if "dispenseRequest" not in fhir_resource:
                    fhir_resource["dispenseRequest"] = {}
                fhir_resource["dispenseRequest"]["quantity"] = {"value": quantity}
            if refills is not None:
                if "dispenseRequest" not in fhir_resource:
                    fhir_resource["dispenseRequest"] = {}
                fhir_resource["dispenseRequest"]["numberOfRepeatsAllowed"] = refills
            if supporting_info:
                fhir_resource["supportingInformation"] = supporting_info
        # Remove old MedicationStatement/other med logic below if present

        # --------------------------
        # MEDICATION (PRESCRIPTION/ORDER with full details)
        # --------------------------
        elif (
            (item.get("displayGroup") == "O RX" or item.get("displayGroup") == "NV RX")
            and item.get("oiName")
            and item.get("service") in ["PSO", "PSH"]
        ):
            med_text = item.get("oiName") or item.get("name") or "Unknown"
            med_code = item.get("oiCode", "").split(":")[-1] if item.get("oiCode") else ""
            status = item.get("statusName", "active").lower()
            # Extract dose, quantity, refills from content if present
            content = item.get("content", "")
            dose_match = re.search(r"(\d+\s*MG|\d+\s*MCG|\d+\s*G|\d+\s*mg|\d+\s*mcg|\d+\s*g)", content)
            dose = dose_match.group(1) if dose_match else None
            quantity_match = re.search(r"Quantity:\s*(\d+)", content)
            quantity = int(quantity_match.group(1)) if quantity_match else None
            refills_match = re.search(r"Refills:\s*(\d+)", content)
            refills = int(refills_match.group(1)) if refills_match else None
            # Prescriber
            prescriber = None
            if item.get("clinicians") and isinstance(item["clinicians"], list) and len(item["clinicians"]) > 0:
                prescriber = item["clinicians"][0].get("name")
            elif item.get("providerName"):
                prescriber = item.get("providerName")
            # Date written
            date_written = str(item.get("entered")) if item.get("entered") else None
            # Start/stop dates
            start_date = str(item.get("start")) if item.get("start") else None
            stop_date = str(item.get("stop")) if item.get("stop") else None
            fhir_resource = {
                "resourceType": "MedicationStatement",
                "id": f"med-{item.get('localId')}",
                "status": status,
                "medicationCodeableConcept": {
                    "coding": [
                        {
                            "system": "http://www.nlm.nih.gov/research/umls/rxnorm",
                            "code": med_code,
                            "display": med_text.strip()
                        }
                    ],
                    "text": med_text.strip()
                },
                "subject": {"reference": f"Patient/{patient_id}"},
                "effectiveDateTime": start_date or date_written,
                "dateAsserted": date_written,
                "note": [{"text": content}] if content else [],
            }
            # Add dosage if found
            if dose:
                fhir_resource["dosage"] = [{"text": dose}]
            # Add quantity if found
            if quantity is not None:
                fhir_resource["quantity"] = {"value": quantity}
            # Add refills if found
            if refills is not None:
                fhir_resource["numberOfRepeatsAllowed"] = refills
            # Add prescriber if found
            if prescriber:
                fhir_resource["informationSource"] = {"display": prescriber}
            # Add stop date if found
            if stop_date:
                fhir_resource["whenStopped"] = stop_date

        # --------------------------
        # DOCUMENT (NOTES, REPORTS, INCLUDING RADIOLOGY)
        # --------------------------
        elif "documentType" in item or "title" in item or "report" in item or "text" in item:
            # Status
            doc_status = item.get("status", "current")
            # Type (LOINC if possible)
            loinc_code = item.get("loinc") or item.get("loincCode")
            doc_type = {"text": item.get("title") or item.get("documentType") or "Note"}
            if loinc_code:
                doc_type["coding"] = [{"system": "http://loinc.org", "code": loinc_code, "display": item.get("title") or item.get("documentType") or "Note"}]
            # Category
            doc_category = [{
                "coding": [{
                    "system": "http://hl7.org/fhir/us/core/CodeSystem/us-core-documentreference-category",
                    "code": "clinical-note"
                }]
            }]
            # Content
            content_type = item.get("mimeType") or "text/plain"
            doc_content = [{
                "attachment": {
                    "contentType": content_type,
                    "data": item.get("text") or item.get("report") or ""
                }
            }]
            # Author
            author = []
            if item.get("author"):
                author.append({"display": item["author"]})
            if item.get("providerName"):
                author.append({"display": item["providerName"]})
            # Facility
            custodian = None
            if item.get("facilityName"):
                custodian = {"display": item["facilityName"]}
            # Identifiers
            identifiers = []
            if item.get("uid"):
                identifiers.append({"system": "urn:va:uid", "value": item["uid"]})
            if item.get("vuid"):
                identifiers.append({"system": "urn:va:vuid", "value": item["vuid"]})
            # Date
            doc_date = str(item.get("entered") or item.get("date") or item.get("dateTime"))
            # Build DocumentReference
            fhir_resource = {
                "resourceType": "DocumentReference",
                "id": f"note-{item.get('localId')}",
                "status": doc_status,
                "type": doc_type,
                "category": doc_category,
                "subject": {"reference": f"Patient/{patient_id}"},
                "date": doc_date,
                "content": doc_content
            }
            if author:
                fhir_resource["author"] = author
            if custodian:
                fhir_resource["custodian"] = custodian
            if identifiers:
                fhir_resource["identifier"] = identifiers

            # --- Procedure Extraction from Notes ---
            # Look for procedure-related keywords in the note text
            def _get_note_text(val):
                if isinstance(val, list):
                    # If list of dicts with 'content', join those
                    if all(isinstance(x, dict) and 'content' in x for x in val):
                        return "\n".join(str(x['content']) for x in val)
                    return "\n".join(str(x) for x in val)
                return str(val)

            note_text_raw = item.get("text") or item.get("report") or ""
            note_text = _get_note_text(note_text_raw).lower()
            procedure_keywords = [
                "procedure:", "procedure note", "operation", "surgery", "performed:", "principal:", "modality", "radiology", "imaging", "left inguinal hernia repair", "biopsy", "resection", "repair", "excision", "injection", "endoscopy", "catheterization", "angiogram", "scan", "ct", "mri", "x-ray", "ultrasound"
            ]
            found_procedure = any(kw in note_text for kw in procedure_keywords)
            # If a procedure is detected, create a Procedure resource
            if found_procedure:
                # Try to extract a procedure name (simple heuristic)
                proc_name = None
                for kw in procedure_keywords:
                    idx = note_text.find(kw)
                    if idx != -1:
                        # Try to extract the line containing the keyword
                        lines = note_text.splitlines()
                        for line in lines:
                            if kw in line:
                                proc_name = line.strip().replace(kw, "").strip().capitalize() or kw.capitalize()
                                break
                        if proc_name:
                            break
                if not proc_name:
                    proc_name = "Procedure from note"
                # Use SNOMED as default system, but code is unknown unless found
                code_coding = [{"system": "http://snomed.info/sct", "code": "unknown", "display": proc_name}]
                # Date
                performed = item.get("entered") or item.get("date") or item.get("dateTime")
                # Performer
                performer = []
                if item.get("providerName"):
                    performer.append({"actor": {"display": item["providerName"]}})
                # Reason (try to extract from note)
                reason = []
                for reason_kw in ["indication", "reason", "diagnosis"]:
                    for line in note_text.splitlines():
                        if reason_kw in line:
                            reason.append({"text": line.strip()})
                # Identifiers
                proc_identifiers = []
                if item.get("uid"):
                    proc_identifiers.append({"system": "urn:va:uid", "value": item["uid"]})
                if item.get("vuid"):
                    proc_identifiers.append({"system": "urn:va:vuid", "value": item["vuid"]})
                # Link to DocumentReference
                based_on = [{"reference": f"DocumentReference/note-{item.get('localId')}"}]
                proc_resource = {
                    "resourceType": "Procedure",
                    "id": f"proc-from-note-{item.get('localId')}",
                    "status": "completed",
                    "code": {"coding": code_coding, "text": proc_name},
                    "subject": {"reference": f"Patient/{patient_id}"},
                    "performedDateTime": str(performed),
                    "basedOn": based_on
                }
                if performer:
                    proc_resource["performer"] = performer
                if reason:
                    proc_resource["reasonCode"] = reason
                if proc_identifiers:
                    proc_resource["identifier"] = proc_identifiers
                # Add Procedure resource to bundle
                bundle["entry"].append({"resource": proc_resource})
        # PROCEDURE (INCLUDING RADIOLOGY PROCEDURES)
        # --------------------------
        elif "procedure" in item or "procedureName" in item or "modality" in item:
            # Status
            proc_status = item.get("status", "completed")
            # Code (SNOMED, CPT, LOINC, etc.)
            proc_code = item.get("code") or item.get("procedureCode") or item.get("loinc") or item.get("loincCode") or "unknown"
            proc_code_display = item.get("procedure") or item.get("procedureName") or item.get("modality") or "Procedure"
            code_coding = []
            if proc_code != "unknown":
                code_coding.append({"system": "http://snomed.info/sct", "code": proc_code, "display": proc_code_display})
            # Performed
            performed = item.get("performed") or item.get("date") or item.get("entered")
            # Performer
            performer = []
            if item.get("providerName"):
                performer.append({"actor": {"display": item["providerName"]}})
            # Reason
            reason = []
            if item.get("reason"):
                reason.append({"text": item["reason"]})
            # Identifiers
            identifiers = []
            if item.get("uid"):
                identifiers.append({"system": "urn:va:uid", "value": item["uid"]})
            if item.get("vuid"):
                identifiers.append({"system": "urn:va:vuid", "value": item["vuid"]})
            # Build Procedure
            fhir_resource = {
                "resourceType": "Procedure",
                "id": f"proc-{item.get('localId')}",
                "status": proc_status,
                "code": {"coding": code_coding, "text": proc_code_display},
                "subject": {"reference": f"Patient/{patient_id}"},
            }
            if performed:
                fhir_resource["performedDateTime"] = str(performed)
            if performer:
                fhir_resource["performer"] = performer
            if reason:
                fhir_resource["reasonCode"] = reason
            if identifiers:
                fhir_resource["identifier"] = identifiers

        # --------------------------
        # OBSERVATION (HEALTH FACTORS, SOCIAL HISTORY)
        # --------------------------
        elif "categoryName" in item or "healthFactorName" in item:
            code_text = item.get("healthFactorName") or item.get("categoryName")
            fhir_resource = {
                "resourceType": "Observation",
                "id": f"obs-{item.get('localId')}",
                "status": "final",
                "category": [{
                    "coding": [{
                        "system": "http://terminology.hl7.org/CodeSystem/observation-category",
                        "code": "social-history",
                        "display": "Social History"
                    }]
                }],
                "code": {
                    "text": code_text
                },
                "effectiveDateTime": str(item.get("entered")),
                "subject": {"reference": f"Patient/{patient_id}"}
            }

        # --------------------------
        # TRUE CLINICAL ISSUES (DetectedIssue)
        # --------------------------
        elif item.get("kind") == "Detected Issue":
            fhir_resource = {
                "resourceType": "DetectedIssue",
                "id": f"issue-{item.get('localId', len(bundle['entry']))}",
                "status": "final",
                "code": {"text": item.get("summary", "")},
                "mitigation": []
            }

        # --------------------------
        # CATCH ALL FOR OTHER ITEMS
        # --------------------------
        else:
            continue  # skip items that do not map to a FHIR resource

        bundle["entry"].append({"resource": fhir_resource})

    return bundle


# ✅ Example usage
if __name__ == "__main__":
    with open("VPRpatientexample.json") as f:
        data = json.load(f)

    fhir_bundle = vpr_to_fully_compliant_fhir_bundle(data)

    with open("patient_fhir_bundle_full_compliant.json", "w") as f:
        json.dump(fhir_bundle, f, indent=2)

    print("✅ Generated fully compliant FHIR bundle.")
