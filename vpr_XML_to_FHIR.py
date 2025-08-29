import sys
import os
import re
import json
from xml.etree import ElementTree as ET
import datetime

def get_value(root, tag):
    el = root.find(tag)
    if el is not None:
        return el.attrib.get('value', '') or (el.text or '')
    return ''

def get_problems_as_conditions(vpr_text):
    """
    Extracts <problem>...</problem> blocks from VPR text and converts them to FHIR Condition resources.
    Returns a list of FHIR Condition dicts.
    Adds debug output to show extracted values for troubleshooting.
    """
    problems = re.findall(r'<problem>(.*?)</problem>', vpr_text, re.DOTALL)
    conditions = []
    for prob_xml in problems:
        # Wrap in <problem> for XML parsing
        prob_xml_full = f'<problem>{prob_xml}</problem>'
        try:
            root = ET.fromstring(prob_xml_full)
        except Exception as e:
            print(f'Could not parse problem XML: {e}')
            continue
        icd = get_value(root, 'icd')
        icdd = get_value(root, 'icdd')
        name = get_value(root, 'name')
        sctt = get_value(root, 'sctt')
        status = root.find('status').attrib.get('name').lower() if root.find('status') is not None and root.find('status').attrib.get('name') else 'unknown'
        entered = fileman_to_iso8601(get_value(root, 'entered'))
        provider = root.find('provider').attrib.get('name') if root.find('provider') is not None else ''
        facility = root.find('facility').attrib.get('name') if root.find('facility') is not None else ''
        # Collect notes: sctt plus each commentText from <comments><comment>
        notes = []
        if sctt:
            notes.append({"text": sctt})
        comments_el = root.find('comments')
        if comments_el is not None:
            for com in comments_el.findall('comment'):
                ctext = com.attrib.get('commentText', '').strip()
                entered_by = com.attrib.get('enteredBy', '')
                entered_date = fileman_to_iso8601(com.attrib.get('entered', '')) if com.attrib.get('entered') else ''
                if ctext:
                    note_text = ctext
                    meta = []
                    if entered_by:
                        meta.append(f"by {entered_by}")
                    if entered_date and entered_date != com.attrib.get('entered',''):
                        meta.append(f"on {entered_date}")
                    if meta:
                        note_text = f"{note_text} ({'; '.join(meta)})"
                    notes.append({"text": note_text})
        # Debug: print extracted values
        print(f"Extracted: icd={icd}, icdd={icdd}, name={name}, status={status}, provider={provider}, facility={facility}, notes_count={len(notes)}")
        # Map to FHIR Condition resource
        condition = {
            "resourceType": "Condition",
            "clinicalStatus": {
                "coding": [{
                    "system": "http://terminology.hl7.org/CodeSystem/condition-clinical",
                    "code": status
                }]
            },
            "code": {
                "coding": [
                    {"system": "http://hl7.org/fhir/sid/icd-10", "code": icd, "display": icdd}
                ],
                "text": name
            },
            "asserter": {"display": provider} if provider else None,
            "recordedDate": entered if entered else None,
            "note": notes,
            "encounter": {"display": facility} if facility else None
        }
        # Remove None fields
        condition = {k: v for k, v in condition.items() if v is not None}
        conditions.append(condition)
    return conditions

def get_labs_as_observations(vpr_text):
    """
    Extracts <lab>...</lab> blocks from VPR text and converts them to FHIR Observation resources.
    Returns a list of FHIR Observation dicts.
    """
    labs = re.findall(r'<lab>(.*?)</lab>', vpr_text, re.DOTALL)
    observations = []
    for lab_xml in labs:
        lab_xml_full = f'<lab>{lab_xml}</lab>'
        try:
            root = ET.fromstring(lab_xml_full)
        except Exception as e:
            print(f'Could not parse lab XML: {e}')
            continue
        # Extract fields using get_value helper
        loinc = get_value(root, 'loinc')
        result = get_value(root, 'result')
        units = get_value(root, 'units')
        test = get_value(root, 'test')
        status = get_value(root, 'status')
        provider = root.find('provider').attrib.get('name') if root.find('provider') is not None else ''
        facility = root.find('facility').attrib.get('name') if root.find('facility') is not None else ''
        specimen = root.find('specimen').attrib.get('name') if root.find('specimen') is not None else ''
        collected = fileman_to_iso8601(get_value(root, 'collected'))
        resulted = fileman_to_iso8601(get_value(root, 'resulted'))
        interpretation = get_value(root, 'interpretation')
        high = get_value(root, 'high')
        low = get_value(root, 'low')
        # Debug: print extracted values
        print(f"Extracted LAB: loinc={loinc}, result={result}, units={units}, test={test}, status={status}, provider={provider}, facility={facility}, specimen={specimen}, collected={collected}, resulted={resulted}, interpretation={interpretation}, high={high}, low={low}")
        # Build FHIR Observation resource
        observation = {
            "resourceType": "Observation",
            "status": status or "unknown",
            "category": [{
                "coding": [{
                    "system": "http://terminology.hl7.org/CodeSystem/observation-category",
                    "code": "laboratory",
                    "display": "Laboratory"
                }]
            }],
            "code": {
                "coding": [
                    {"system": "http://loinc.org", "code": loinc, "display": test}
                ],
                "text": test
            },
            "valueQuantity": {
                "value": result,
                "unit": units
            } if result and units else None,
            "valueString": result if result and not units else None,
            "referenceRange": [{
                "high": {"value": high} if high else None,
                "low": {"value": low} if low else None
            }] if high or low else [],
            "interpretation": [{
                "coding": [{
                    "system": "http://terminology.hl7.org/CodeSystem/v3-ObservationInterpretation",
                    "code": interpretation
                }]
            }] if interpretation else [],
            "effectiveDateTime": collected if collected else None,
            "issued": resulted if resulted else None,
            "performer": [{"display": provider}] if provider else [],
            "encounter": {"display": facility} if facility else None,
            "specimen": {"display": specimen} if specimen else None
        }
        # Remove None fields and empty dicts
        observation = {k: v for k, v in observation.items() if v not in [None, [], {}]}
        observations.append(observation)
    return observations

def get_vitals_as_observations(vpr_text):
    """
    Extract <vital> blocks and produce FHIR Observation resources aligned with the
    Vital Signs profile (LOINC based codes). Handles composite Blood Pressure
    and derives BMI if present on weight entries.
    """
    vitals = re.findall(r'<vital>(.*?)</vital>', vpr_text, re.DOTALL)
    observations = []

    # Map VistA measurement names to LOINC (code, display)
    name_to_loinc = {
        'BLOOD PRESSURE': ('85354-9', 'Blood pressure panel with all children optional'),
        'PULSE': ('8867-4', 'Heart rate'),
        'PULSE OXIMETRY': ('59408-5', 'Oxygen saturation in Arterial blood by Pulse oximetry'),
        'RESPIRATION': ('9279-1', 'Respiratory rate'),
        'TEMPERATURE': ('8310-5', 'Body temperature'),
        'WEIGHT': ('29463-7', 'Body Weight'),
        'HEIGHT': ('8302-2', 'Body height'),
        'BMI': ('39156-5', 'Body mass index (BMI)')
    }

    def _as_float(val):
        try:
            return float(val)
        except Exception:
            return None

    for vital_xml in vitals:
        vital_xml_full = f'<vital>{vital_xml}</vital>'
        try:
            root = ET.fromstring(vital_xml_full)
        except Exception as e:
            print(f'Could not parse vital XML: {e}')
            continue
        entered = fileman_to_iso8601(get_value(root, 'entered'))
        taken = fileman_to_iso8601(get_value(root, 'taken'))
        facility = root.find('facility').attrib.get('name') if root.find('facility') is not None else ''
        location = root.find('location').attrib.get('name') if root.find('location') is not None else ''

        measurements_parent = root.find('measurements')
        if measurements_parent is None:
            continue
        for meas in measurements_parent.findall('measurement'):
            m_name = (meas.attrib.get('name') or '').upper()
            raw_value = meas.attrib.get('value', '')
            units = meas.attrib.get('units', '')
            ucum = meas.attrib.get('ucumUnits', '')
            high = meas.attrib.get('high', '')
            low = meas.attrib.get('low', '')
            mid = meas.attrib.get('id', '')
            metric_value = meas.attrib.get('metricValue')
            metric_units = meas.attrib.get('metricUnits')
            bmi_attr = meas.attrib.get('bmi')  # appears on weight measurement

            loinc_code, loinc_display = name_to_loinc.get(m_name, (None, None))

            # Blood Pressure composite handling
            if m_name == 'BLOOD PRESSURE' and raw_value and '/' in raw_value:
                try:
                    sys_str, dia_str = raw_value.split('/', 1)
                    systolic = _as_float(sys_str.strip())
                    diastolic = _as_float(dia_str.strip())
                except Exception:
                    systolic = diastolic = None
                bp_obs = {
                    'resourceType': 'Observation',
                    'status': 'final',
                    'category': [{
                        'coding': [{
                            'system': 'http://terminology.hl7.org/CodeSystem/observation-category',
                            'code': 'vital-signs',
                            'display': 'Vital Signs'
                        }]
                    }],
                    'code': {
                        'coding': ([{
                            'system': 'http://loinc.org',
                            'code': loinc_code or '85354-9',
                            'display': loinc_display or 'Blood pressure panel'
                        }]),
                        'text': 'Blood Pressure'
                    },
                    'effectiveDateTime': taken or entered,
                    'encounter': {'display': facility} if facility else None,
                    'bodySite': {'display': location} if location else None,
                    'identifier': [{'value': mid}] if mid else None,
                    'component': []
                }
                if systolic is not None:
                    bp_obs['component'].append({
                        'code': {'coding': [{'system': 'http://loinc.org', 'code': '8480-6', 'display': 'Systolic blood pressure'}]},
                        'valueQuantity': {
                            'value': systolic,
                            'unit': 'mmHg',
                            'system': 'http://unitsofmeasure.org',
                            'code': 'mm[Hg]'
                        }
                    })
                if diastolic is not None:
                    bp_obs['component'].append({
                        'code': {'coding': [{'system': 'http://loinc.org', 'code': '8462-4', 'display': 'Diastolic blood pressure'}]},
                        'valueQuantity': {
                            'value': diastolic,
                            'unit': 'mmHg',
                            'system': 'http://unitsofmeasure.org',
                            'code': 'mm[Hg]'
                        }
                    })
                # Reference range (panel-level not standard; skip unless both high/low parse)
                bp_obs = {k: v for k, v in bp_obs.items() if v not in [None, [], {}]}
                observations.append(bp_obs)
                continue

            # Decide which value & unit to surface (prefer metric if provided and recognized)
            val_used = None
            unit_used = None
            code_used = None
            if metric_value and metric_units and metric_units.lower() in ['c', 'kg', 'cm', 'mmol/l', 'g/l']:
                val_used = _as_float(metric_value) or metric_value
                unit_used = metric_units
                # ucum code for Celsius is 'Cel' but incoming 'C'; keep original as text
                code_used = {'c': 'Cel', 'kg': 'kg', 'cm': 'cm'}.get(metric_units.lower(), metric_units)
            else:
                val_used = _as_float(raw_value) or raw_value
                unit_used = units
                code_used = ucum or units

            obs = {
                'resourceType': 'Observation',
                'status': 'final',
                'category': [{
                    'coding': [{
                        'system': 'http://terminology.hl7.org/CodeSystem/observation-category',
                        'code': 'vital-signs',
                        'display': 'Vital Signs'
                    }]
                }],
                'code': {
                    'coding': ([{
                        'system': 'http://loinc.org',
                        'code': loinc_code,
                        'display': loinc_display
                    }] if loinc_code else []),
                    'text': m_name.title()
                },
                'effectiveDateTime': taken or entered,
                'valueQuantity': {
                    'value': val_used,
                    'unit': unit_used,
                    'system': 'http://unitsofmeasure.org',
                    'code': code_used
                } if val_used not in [None, ''] and unit_used else None,
                'referenceRange': [{
                    'high': {'value': _as_float(high) if _as_float(high) is not None else high} if high else None,
                    'low': {'value': _as_float(low) if _as_float(low) is not None else low} if low else None
                }] if high or low else [],
                'encounter': {'display': facility} if facility else None,
                'bodySite': {'display': location} if location else None,
                'identifier': [{'value': mid}] if mid else None
            }
            # Retain original imperial reading as component if metric was substituted
            if metric_value and metric_units and raw_value and metric_value != raw_value:
                obs.setdefault('component', []).append({
                    'code': {'text': 'Original Reading'},
                    'valueQuantity': {
                        'value': _as_float(raw_value) or raw_value,
                        'unit': units,
                        'system': 'http://unitsofmeasure.org',
                        'code': ucum or units
                    }
                })

            obs = {k: v for k, v in obs.items() if v not in [None, [], {}]}
            observations.append(obs)

            # Derive BMI Observation if present on weight measurement
            if m_name == 'WEIGHT' and bmi_attr:
                bmi_val = _as_float(bmi_attr) or bmi_attr
                bmi_obs = {
                    'resourceType': 'Observation',
                    'status': 'final',
                    'category': [{
                        'coding': [{
                            'system': 'http://terminology.hl7.org/CodeSystem/observation-category',
                            'code': 'vital-signs',
                            'display': 'Vital Signs'
                        }]
                    }],
                    'code': {
                        'coding': [{
                            'system': 'http://loinc.org',
                            'code': name_to_loinc['BMI'][0],
                            'display': name_to_loinc['BMI'][1]
                        }],
                        'text': 'BMI'
                    },
                    'effectiveDateTime': taken or entered,
                    'valueQuantity': {
                        'value': bmi_val,
                        'unit': 'kg/m2',
                        'system': 'http://unitsofmeasure.org',
                        'code': 'kg/m2'
                    },
                    'encounter': {'display': facility} if facility else None,
                    'bodySite': {'display': location} if location else None
                }
                observations.append(bmi_obs)

    return observations

def get_documents_as_fhir(vpr_text):
    """
    Extracts <document>...</document> blocks from VPR text and converts them to FHIR DocumentReference resources.
    Returns a list of FHIR DocumentReference dicts.
    """
    documents = re.findall(r'<document>(.*?)</document>', vpr_text, re.DOTALL)
    doc_refs = []
    for doc_xml in documents:
        doc_xml_full = f'<document>{doc_xml}</document>'
        try:
            root = ET.fromstring(doc_xml_full)
        except Exception as e:
            print(f'Could not parse document XML: {e}')
            continue
        doc_id = get_value(root, 'id')
        title = get_value(root, 'localTitle')
        date = fileman_to_iso8601(get_value(root, 'referenceDateTime'))
        # Find author: first clinician with role='A'
        author = None
        clinicians = root.find('clinicians')
        if clinicians is not None:
            for cl in clinicians.findall('clinician'):
                if cl.attrib.get('role') == 'A':
                    author = cl.attrib.get('name')
                    break
        # Debug print
        print(f"Extracted DOCUMENT: id={doc_id}, title={title}, author={author}, date={date}")
        doc_ref = {
            "resourceType": "DocumentReference",
            "status": "current",
            "type": {"text": title} if title else None,
            "description": title if title else None,
            "author": [{"display": author}] if author else None,
            "date": date if date else None,
            "masterIdentifier": {"value": doc_id} if doc_id else None
        }
        doc_ref = {k: v for k, v in doc_ref.items() if v not in [None, [], {}]}
        doc_refs.append(doc_ref)
    return doc_refs
    

def get_radiology_procedures_as_fhir(vpr_text):
    """
    Extracts <procedure>...</procedure> blocks with <category value='RA' /> (Radiology) and converts them to FHIR Procedure resources.
    Returns a list of FHIR Procedure dicts.
    """
    procedures = re.findall(r'<procedure>(.*?)</procedure>', vpr_text, re.DOTALL)
    rad_procs = []
    for proc_xml in procedures:
        proc_xml_full = f'<procedure>{proc_xml}</procedure>'
        try:
            root = ET.fromstring(proc_xml_full)
        except Exception as e:
            print(f'Could not parse procedure XML: {e}')
            continue
        # Only include radiology procedures
        category_el = root.find('category')
        if not (category_el is not None and category_el.attrib.get('value') == 'RA'):
            continue
        proc_id = get_value(root, 'id')
        case = get_value(root, 'case')
        dateTime = fileman_to_iso8601(get_value(root, 'dateTime'))
        status = get_value(root, 'status')
        name = get_value(root, 'name')
        type_name = root.find('type').attrib.get('name') if root.find('type') is not None else ''
        type_code = root.find('type').attrib.get('code') if root.find('type') is not None else ''
        provider = root.find('provider').attrib.get('name') if root.find('provider') is not None else ''
        facility = root.find('facility').attrib.get('name') if root.find('facility') is not None else ''
        location = root.find('location').attrib.get('name') if root.find('location') is not None else ''
        imaging_type = root.find('imagingType').attrib.get('name') if root.find('imagingType') is not None else ''
        urgency = get_value(root, 'urgency')
        # Debug print
        print(f"Extracted RADIOLOGY PROCEDURE: id={proc_id}, case={case}, dateTime={dateTime}, status={status}, name={name}, type_name={type_name}, type_code={type_code}, provider={provider}, facility={facility}, location={location}, imaging_type={imaging_type}, urgency={urgency}")
        proc = {
            "resourceType": "Procedure",
            "status": status.lower() if status else "unknown",
            "code": {
                "coding": [
                    {"system": "http://www.ama-assn.org/go/cpt", "code": type_code, "display": type_name}
                ],
                "text": name
            },
            "performedDateTime": dateTime if dateTime else None,
            "performer": [{"actor": {"display": provider}}] if provider else [],
            "location": {"display": location} if location else None,
            "encounter": {"display": facility} if facility else None,
            "category": {
                "coding": [{
                    "system": "http://terminology.hl7.org/CodeSystem/procedure-category",
                    "code": "imaging",
                    "display": imaging_type or "Radiology"
                }]
            },
            "identifier": [{"value": proc_id}] if proc_id else None,
            "note": [{"text": f"Urgency: {urgency}"}] if urgency else []
        }
        proc = {k: v for k, v in proc.items() if v not in [None, [], {}]}
        rad_procs.append(proc)
    return rad_procs

def get_consults_as_fhir(vpr_text):
    """
    Extracts <consult>...</consult> blocks from VPR text and converts them to FHIR ServiceRequest resources.
    Returns a list of FHIR ServiceRequest dicts.
    """
    consults = re.findall(r'<consult>(.*?)</consult>', vpr_text, re.DOTALL)
    service_requests = []
    for consult_xml in consults:
        consult_xml_full = f'<consult>{consult_xml}</consult>'
        try:
            root = ET.fromstring(consult_xml_full)
        except Exception as e:
            print(f'Could not parse consult XML: {e}')
            continue
        consult_id = get_value(root, 'id')
        name = get_value(root, 'name')
        order_id = get_value(root, 'orderID')
        procedure = get_value(root, 'procedure')
        status = get_value(root, 'status')
        urgency = get_value(root, 'urgency')
        requested = fileman_to_iso8601(get_value(root, 'requested'))
        service = get_value(root, 'service')
        reason = get_value(root, 'reason')
        facility = root.find('facility').attrib.get('name') if root.find('facility') is not None else ''
        provider = root.find('provider').attrib.get('name') if root.find('provider') is not None else ''
        provDx = root.find('provDx').attrib.get('name') if root.find('provDx') is not None else ''
        provDx_code = root.find('provDx').attrib.get('code') if root.find('provDx') is not None else ''
        # Debug print
        print(f"Extracted CONSULT: id={consult_id}, name={name}, order_id={order_id}, procedure={procedure}, status={status}, urgency={urgency}, requested={requested}, service={service}, reason={reason}, facility={facility}, provider={provider}, provDx={provDx}, provDx_code={provDx_code}")
        # Build FHIR ServiceRequest resource
        sr = {
            "resourceType": "ServiceRequest",
            "status": status.lower() if status else "unknown",
            "intent": "order",
            "code": {
                "text": name
            },
            "subject": {"display": provider} if provider else None,
            "authoredOn": requested if requested else None,
            "priority": urgency.lower() if urgency else None,
            "reasonCode": [{
                "text": reason
            }] if reason else [],
            "encounter": {"display": facility} if facility else None,
            "identifier": [{"value": consult_id}] if consult_id else None,
            "orderDetail": [{"text": procedure}] if procedure else [],
            "note": [{"text": f"Diagnosis: {provDx} ({provDx_code})"}] if provDx or provDx_code else []
        }
        sr = {k: v for k, v in sr.items() if v not in [None, [], {}]}
        service_requests.append(sr)
    return service_requests

def get_meds_as_fhir(vpr_text):
    """
    Extracts <med>...</med> blocks from VPR text and converts them to FHIR MedicationRequest resources.
    Returns a list of FHIR MedicationRequest dicts.
    """
    meds = re.findall(r'<med>(.*?)</med>', vpr_text, re.DOTALL)
    med_requests = []
    for med_xml in meds:
        med_xml_full = f'<med>{med_xml}</med>'
        try:
            root = ET.fromstring(med_xml_full)
        except Exception as e:
            print(f'Could not parse med XML: {e}')
            continue
        med_id = get_value(root, 'id')
        name = get_value(root, 'name')
        status = get_value(root, 'status')
        va_status = get_value(root, 'vaStatus')
        va_type = get_value(root, 'vaType')
        start = fileman_to_iso8601(get_value(root, 'start'))
        stop = fileman_to_iso8601(get_value(root, 'stop'))
        ordered = fileman_to_iso8601(get_value(root, 'ordered'))
        quantity = get_value(root, 'quantity')
        days_supply = get_value(root, 'daysSupply')
        form = get_value(root, 'form')
        route = ''
        sig = get_value(root, 'sig')
        pt_instructions = get_value(root, 'ptInstructions')
        facility = root.find('facility').attrib.get('name') if root.find('facility') is not None else ''
        provider = root.find('currentProvider').attrib.get('name') if root.find('currentProvider') is not None else ''
        # Get product info (first product with role='D')
        product_name = ''
        product_code = ''
        product_class = ''
        products = root.find('products')
        if products is not None:
            for prod in products.findall('product'):
                if prod.attrib.get('role') == 'D':
                    product_name = prod.attrib.get('name', '')
                    product_code = prod.attrib.get('code', '')
                    prod_class = prod.find('class')
                    if prod_class is not None:
                        product_class = prod_class.attrib.get('name', '')
                    break
        # Get dose info (first dose)
        dose = ''
        dose_units = ''
        schedule = ''
        doses = root.find('doses')
        if doses is not None:
            first_dose = doses.find('dose')
            if first_dose is not None:
                dose = first_dose.attrib.get('dose', '')
                dose_units = first_dose.attrib.get('units', '')
                route = first_dose.attrib.get('route', '')
                schedule = first_dose.attrib.get('schedule', '')
        # Debug print
        print(f"Extracted MED: id={med_id}, name={name}, product_name={product_name}, product_code={product_code}, product_class={product_class}, status={status}, va_status={va_status}, va_type={va_type}, start={start}, stop={stop}, ordered={ordered}, quantity={quantity}, days_supply={days_supply}, form={form}, route={route}, dose={dose}, dose_units={dose_units}, schedule={schedule}, sig={sig}, pt_instructions={pt_instructions}, facility={facility}, provider={provider}")
        # Build FHIR MedicationRequest resource
        med_req = {
            "resourceType": "MedicationRequest",
            "status": va_status.lower() if va_status else (status.lower() if status else "unknown"),
            "intent": "order",
            "medicationCodeableConcept": {
                "coding": [
                    {"system": "http://www.nlm.nih.gov/research/umls/rxnorm", "code": product_code, "display": product_name}
                ],
                "text": name
            },
            "subject": {"display": provider} if provider else None,
            "authoredOn": ordered if ordered else None,
            "dosageInstruction": [{
                "text": sig,
                "patientInstruction": pt_instructions,
                "timing": {"code": {"text": schedule}} if schedule else None,
                "route": {"text": route} if route else None,
                "doseAndRate": [{
                    "doseQuantity": {
                        "value": dose,
                        "unit": dose_units
                    } if dose and dose_units else None
                }]
            }],
            "dispenseRequest": {
                "quantity": {"value": quantity},
                "expectedSupplyDuration": {"value": days_supply, "unit": "days"} if days_supply else None
            },
            "form": {"text": form} if form else None,
            "note": [{"text": product_class}] if product_class else [],
            "encounter": {"display": facility} if facility else None,
            "identifier": [{"value": med_id}] if med_id else None,
            "groupIdentifier": {"value": get_value(root, 'medID')} if get_value(root, 'medID') else None,
            "category": [{"text": va_type}] if va_type else []
        }
        # Remove None/empty fields and empty dicts/lists
        def clean(obj):
            if isinstance(obj, dict):
                return {k: clean(v) for k, v in obj.items() if v not in [None, [], {}]}
            elif isinstance(obj, list):
                return [clean(i) for i in obj if i not in [None, [], {}]]
            else:
                return obj
        med_req = clean(med_req)
        med_requests.append(med_req)
    return med_requests

def get_allergies_as_fhir(vpr_text):
    """
    Extracts <allergy>...</allergy> blocks from VPR text and converts them to FHIR AllergyIntolerance resources.
    Returns a list of FHIR AllergyIntolerance dicts.
    """
    allergies = re.findall(r'<allergy>(.*?)</allergy>', vpr_text, re.DOTALL)
    allergy_resources = []
    for allergy_xml in allergies:
        allergy_xml_full = f'<allergy>{allergy_xml}</allergy>'
        try:
            root = ET.fromstring(allergy_xml_full)
        except Exception as e:
            print(f'Could not parse allergy XML: {e}')
            continue
        # Allergen substance
        substance = get_value(root, 'name')
        # Severity (maps to criticality in FHIR)
        severity = get_value(root, 'severity')
        # Drug classes (all)
        drug_classes = []
        drugClasses_el = root.find('drugClasses')
        if drugClasses_el is not None:
            for dc in drugClasses_el.findall('drugClass'):
                dc_name = dc.attrib.get('name', '')
                if dc_name:
                    drug_classes.append(dc_name)
        # Drug ingredients (all)
        drug_ingredients = []
        drugIngredients_el = root.find('drugIngredients')
        if drugIngredients_el is not None:
            for di in drugIngredients_el.findall('drugIngredient'):
                di_name = di.attrib.get('name', '')
                if di_name:
                    drug_ingredients.append(di_name)
        # Reactions (all names)
        reactions = []
        reactions_el = root.find('reactions')
        if reactions_el is not None:
            for react in reactions_el.findall('reaction'):
                react_name = react.attrib.get('name', '')
                if react_name:
                    reactions.append({"manifestation": [{"text": react_name}]})
        # Comments (all, as notes)
        notes = []
        comments_el = root.find('comments')
        if comments_el is not None:
            for comment in comments_el.findall('comment'):
                comment_text = comment.attrib.get('commentText', '')
                entered_by = comment.attrib.get('enteredBy', '')
                if comment_text:
                    notes.append({"text": comment_text.strip() + (f" (by {entered_by})" if entered_by else '')})
        # Onset/entered/verified
        onset = fileman_to_iso8601(get_value(root, 'entered'))
        verified = fileman_to_iso8601(get_value(root, 'verified'))
        # Facility
        facility = root.find('facility').attrib.get('name') if root.find('facility') is not None else ''
        # Mechanism/type
        mechanism = get_value(root, 'mechanism')
        type_name = root.find('type').attrib.get('name') if root.find('type') is not None else ''
        # Build FHIR AllergyIntolerance resource
        allergy = {
            "resourceType": "AllergyIntolerance",
            "code": {"text": substance} if substance else None,
            "criticality": severity.lower() if severity else None,
            "reaction": reactions if reactions else [],
            "note": notes if notes else [],
            "onsetDateTime": onset if onset else None,
            "recorder": {"display": facility} if facility else None,
            "verificationStatus": {"text": "confirmed" if verified else "unconfirmed"},
            "category": [type_name] if type_name else [],
            "extension": (
                ([{"url": "http://va.gov/mechanism", "valueString": mechanism}] if mechanism else []) +
                ([{"url": "http://va.gov/drugClass", "valueString": dc} for dc in drug_classes] if drug_classes else []) +
                ([{"url": "http://va.gov/drugIngredient", "valueString": di} for di in drug_ingredients] if drug_ingredients else [])
            )
        }
        allergy = {k: v for k, v in allergy.items() if v not in [None, [], {}]}
        allergy_resources.append(allergy)
    return allergy_resources

def get_immunizations_as_fhir(vpr_text):
    """
    Extracts <immunization>...</immunization> blocks from VPR text and converts them to FHIR Immunization resources.
    Returns a list of FHIR Immunization dicts.
    """
    immunizations = re.findall(r'<immunization>(.*?)</immunization>', vpr_text, re.DOTALL)
    imm_resources = []
    for imm_xml in immunizations:
        imm_xml_full = f'<immunization>{imm_xml}</immunization>'
        try:
            root = ET.fromstring(imm_xml_full)
        except Exception as e:
            print(f'Could not parse immunization XML: {e}')
            continue
        # Extract fields
        vaccine_name = get_value(root, 'name')
        administered = fileman_to_iso8601(get_value(root, 'administered'))
        lot = get_value(root, 'lot')
        manufacturer = get_value(root, 'manufacturer')
        dose = get_value(root, 'dose')
        units = get_value(root, 'units')
        expiration = fileman_to_iso8601(get_value(root, 'expirationDate'))
        facility = root.find('facility').attrib.get('name') if root.find('facility') is not None else ''
        # Provider: always extract from <provider> tag
        provider = ''
        provider_el = root.find('provider')
        if provider_el is not None:
            provider = provider_el.attrib.get('name', '')
        route = ''
        route_el = root.find('route')
        if route_el is not None:
            route = route_el.attrib.get('name', '')
        body_site = ''
        body_site_el = root.find('bodySite')
        if body_site_el is not None:
            body_site = body_site_el.attrib.get('name', '')
        cpt = ''
        cpt_el = root.find('cpt')
        if cpt_el is not None:
            cpt = cpt_el.attrib.get('code', '')
        cvx = get_value(root, 'cvx')
        series = get_value(root, 'series')
        vis_sheets = []
        vis = root.find('vis')
        if vis is not None:
            for sheet in vis.findall('sheet'):
                vis_sheets.append({
                    "name": sheet.attrib.get('name', ''),
                    "date": fileman_to_iso8601(sheet.attrib.get('date', '')),
                    "editionDate": fileman_to_iso8601(sheet.attrib.get('editionDate', '')),
                    "language": sheet.attrib.get('language', '')
                })
        # Debug print
        print(f"Extracted IMMUNIZATION: vaccine_name={vaccine_name}, administered={administered}, lot={lot}, manufacturer={manufacturer}, dose={dose}, units={units}, expiration={expiration}, facility={facility}, provider={provider}, route={route}, body_site={body_site}, cpt={cpt}, cvx={cvx}, series={series}, vis_sheets={vis_sheets}")
        imm = {
            "resourceType": "Immunization",
            "status": "completed",
            "vaccineCode": {
                "coding": [
                    {"system": "http://hl7.org/fhir/sid/cvx", "code": cvx, "display": vaccine_name},
                    {"system": "http://www.ama-assn.org/go/cpt", "code": cpt} if cpt else None
                ],
                "text": vaccine_name
            },
            "occurrenceDateTime": administered if administered else None,
            "lotNumber": lot if lot else None,
            "expirationDate": expiration if expiration else None,
            "manufacturer": {"display": manufacturer} if manufacturer else None,
            "doseQuantity": {"value": dose, "unit": units} if dose and units else None,
            "performer": [{"actor": {"display": provider}}] if provider else [],
            "location": {"display": facility} if facility else None,
            "route": {"text": route} if route else None,
            "site": {"text": body_site} if body_site else None,
            "protocolApplied": [{"series": series}] if series else [],
            "education": vis_sheets if vis_sheets else []
        }
        # Remove None/empty fields and empty dicts/lists
        def clean(obj):
            if isinstance(obj, dict):
                return {k: clean(v) for k, v in obj.items() if v not in [None, [], {}]}
            elif isinstance(obj, list):
                return [clean(i) for i in obj if i not in [None, [], {}]]
            else:
                return obj
        imm = clean(imm)
        imm_resources.append(imm)
    return imm_resources

def get_encounters_as_fhir(vpr_text):
    """
    Extracts <visit>...</visit> blocks from VPR text and converts them to FHIR Encounter resources (Lighthouse style).
    Returns a list of FHIR Encounter dicts.
    """
    visits = re.findall(r'<visit>(.*?)</visit>', vpr_text, re.DOTALL)
    encounter_resources = []
    for visit_xml in visits:
        visit_xml_full = f'<visit>{visit_xml}</visit>'
        try:
            root = ET.fromstring(visit_xml_full)
        except Exception as e:
            print(f'Could not parse visit XML: {e}')
            continue
        enc_id = get_value(root, 'id')
        date = fileman_to_iso8601(get_value(root, 'dateTime'))
        type_name = root.find('type').attrib.get('name') if root.find('type') is not None else ''
        status = 'finished'  # VPR visits are always completed
        facility = root.find('facility').attrib.get('name') if root.find('facility') is not None else ''
        location = get_value(root, 'location')
        patient_class = get_value(root, 'patientClass')
        service_category = root.find('serviceCategory').attrib.get('name') if root.find('serviceCategory') is not None else ''
        stop_code = root.find('stopCode').attrib.get('name') if root.find('stopCode') is not None else ''
        credit_stop_code = root.find('creditStopCode').attrib.get('name') if root.find('creditStopCode') is not None else ''
        # Providers (all, with role)
        participants = []
        providers_el = root.find('providers')
        if providers_el is not None:
            for prov in providers_el.findall('provider'):
                prov_name = prov.attrib.get('name', '')
                prov_role = prov.attrib.get('role', '')
                if prov_name:
                    participants.append({
                        "individual": {"display": prov_name},
                        "type": [{"text": prov_role}] if prov_role else []
                    })
        # Reason
        reason = ''
        reason_el = root.find('reason')
        if reason_el is not None:
            reason = reason_el.attrib.get('name', '')
        # Diagnoses (icds)
        diagnosis = []
        icds_el = root.find('icds')
        if icds_el is not None:
            for icd in icds_el.findall('icd'):
                icd_name = icd.attrib.get('name', '')
                icd_code = icd.attrib.get('code', '')
                if icd_name or icd_code:
                    diagnosis.append({
                        "condition": {
                            "coding": [{"system": "http://hl7.org/fhir/sid/icd-10", "code": icd_code, "display": icd_name}],
                            "text": icd_name
                        }
                    })
        # CPTs (as serviceType)
        service_type = ''
        cpts_el = root.find('cpts')
        if cpts_el is not None:
            cpt = cpts_el.find('cpt')
            if cpt is not None:
                service_type = cpt.attrib.get('name', '')
        # Debug print
        print(f"Extracted VISIT: id={enc_id}, date={date}, type={type_name}, facility={facility}, location={location}, patient_class={patient_class}, service_category={service_category}, stop_code={stop_code}, credit_stop_code={credit_stop_code}, reason={reason}, participants={participants}, diagnosis={diagnosis}, service_type={service_type}")
        enc = {
            "resourceType": "Encounter",
            "identifier": [{"value": enc_id}] if enc_id else None,
            "status": status,
            "class": {"code": patient_class} if patient_class else None,
            "type": [{"text": type_name}] if type_name else [],
            "serviceType": {"text": service_type} if service_type else None,
            "serviceCategory": [{"text": service_category}] if service_category else [],
            "period": {"start": date} if date else None,
            "location": [{"location": {"display": location}}] if location else [],
            "serviceProvider": {"display": facility} if facility else None,
            "participant": participants if participants else [],
            "reasonCode": [{"text": reason}] if reason else [],
            "diagnosis": diagnosis if diagnosis else [],
            "extension": [
                {"url": "http://va.gov/fhir/StructureDefinition/stop-code", "valueString": stop_code} if stop_code else None,
                {"url": "http://va.gov/fhir/StructureDefinition/credit-stop-code", "valueString": credit_stop_code} if credit_stop_code else None
            ]
        }
        # Remove None/empty fields and extensions
        enc["extension"] = [e for e in enc["extension"] if e]
        enc = {k: v for k, v in enc.items() if v not in [None, [], {}]}
        encounter_resources.append(enc)
    return encounter_resources

def get_surgeries_as_fhir(vpr_text):
    """
    Extracts <procedure>...</procedure> blocks that are NOT radiology and converts them to FHIR Procedure resources.
    Returns a list of FHIR Procedure dicts.
    """
    procedures = re.findall(r'<procedure>(.*?)</procedure>', vpr_text, re.DOTALL)
    surg_procs = []
    for proc_xml in procedures:
        proc_xml_full = f'<procedure>{proc_xml}</procedure>'
        try:
            root = ET.fromstring(proc_xml_full)
        except Exception as e:
            print(f'Could not parse procedure XML: {e}')
            continue
        category_el = root.find('category')
        if category_el is not None and category_el.attrib.get('value') == 'RA':
            continue  # skip radiology
        proc_id = get_value(root, 'id')
        dateTime = fileman_to_iso8601(get_value(root, 'dateTime'))
        status = get_value(root, 'status')
        name = get_value(root, 'name')
        type_name = root.find('type').attrib.get('name') if root.find('type') is not None else ''
        type_code = root.find('type').attrib.get('code') if root.find('type') is not None else ''
        provider = root.find('provider').attrib.get('name') if root.find('provider') is not None else ''
        facility = root.find('facility').attrib.get('name') if root.find('facility') is not None else ''
        location = root.find('location').attrib.get('name') if root.find('location') is not None else ''
        urgency = get_value(root, 'urgency')
        # Debug print
        print(f"Extracted SURGERY/PROCEDURE: id={proc_id}, dateTime={dateTime}, status={status}, name={name}, type_name={type_name}, type_code={type_code}, provider={provider}, facility={facility}, location={location}, urgency={urgency}")
        proc = {
            "resourceType": "Procedure",
            "status": status.lower() if status else "unknown",
            "code": {
                "coding": [
                    {"system": "http://www.ama-assn.org/go/cpt", "code": type_code, "display": type_name}
                ],
                "text": name
            },
            "performedDateTime": dateTime if dateTime else None,
            "performer": [{"actor": {"display": provider}}] if provider else [],
            "location": {"display": location} if location else None,
            "encounter": {"display": facility} if facility else None,
            "identifier": [{"value": proc_id}] if proc_id else None,
            "note": [{"text": f"Urgency: {urgency}"}] if urgency else []
        }
        proc = {k: v for k, v in proc.items() if v not in [None, [], {}]}
        surg_procs.append(proc)
    return surg_procs

def get_patient_demographics_as_fhir(vpr_text):
    """
    Extracts <patient>...</patient> block from VPR text and converts it to a FHIR Patient resource.
    Returns a list with one FHIR Patient dict (if found).
    """
    match = re.search(r'<patient>(.*?)</patient>', vpr_text, re.DOTALL)
    if not match:
        return []
    patient_xml = f'<patient>{match.group(1)}</patient>'
    try:
        root = ET.fromstring(patient_xml)
    except Exception as e:
        print(f'Could not parse patient XML: {e}')
        return []
    pid = get_value(root, 'id')
    icn = get_value(root, 'icn')
    name = get_value(root, 'fullName')
    dob = fileman_to_iso8601(get_value(root, 'dob'))
    gender = get_value(root, 'gender')
    ssn = get_value(root, 'ssn')
    # Address extraction (support multiple addresses with use)
    addresses = []
    for addr_el in root.findall('address'):
        address = {
            "line": [addr_el.attrib.get('streetLine1', '')],
            "city": addr_el.attrib.get('city', ''),
            "state": addr_el.attrib.get('stateProvince', ''),
            "postalCode": addr_el.attrib.get('postalCode', '')
        }
        # Try to infer use from an attribute or context (not present in your sample, but placeholder for future)
        if 'use' in addr_el.attrib:
            address["use"] = addr_el.attrib['use']
        addresses.append({k: v for k, v in address.items() if v})
    # Telecom extraction (support multiple)
    telecoms = []
    telecomList_el = root.find('telecomList')
    if telecomList_el is not None:
        for tel in telecomList_el.findall('telecom'):
            usage = tel.attrib.get('usageType', '')
            value = tel.attrib.get('value', '')
            if value:
                telecoms.append({"system": "phone", "value": value, "use": usage.lower() if usage else None})
    # Service connection
    sc = get_value(root, 'sc')
    sc_percent = get_value(root, 'scPercent')
    # Build FHIR Patient resource
    patient = {
        "resourceType": "Patient",
        "identifier": [
            {"system": "http://va.gov/mpi/ICN", "value": icn} if icn else None,
            {"system": "http://va.gov/dfn", "value": pid} if pid else None
        ],
        "name": [{"text": name}] if name else None,
        "birthDate": dob if dob else None,
        "gender": gender.lower() if gender else None,
        "address": addresses if addresses else None,
        "telecom": telecoms if telecoms else None,
        "extension": [
            {"url": "http://va.gov/fhir/StructureDefinition/service-connected-indicator", "valueBoolean": sc == '1'},
            {"url": "http://va.gov/fhir/StructureDefinition/service-connected-percentage", "valueInteger": int(sc_percent)} if sc_percent else None,
            {"url": "http://hl7.org/fhir/StructureDefinition/patient-mothersMaidenName", "valueString": ssn} if ssn else None
        ]
    }
    # Remove None/empty fields and extensions
    patient["identifier"] = [i for i in patient["identifier"] if i]
    patient["extension"] = [e for e in patient["extension"] if e]
    patient = {k: v for k, v in patient.items() if v not in [None, [], {}]}
    return [patient]

def get_primary_care_provider_and_team_as_fhir(vpr_text):
    """
    Extracts <pcProvider> and <pcTeam> blocks from VPR text and converts them to FHIR Practitioner and CareTeam resources.
    Returns a list of FHIR resources (Practitioner and CareTeam).
    """
    resources = []
    # Extract pcProvider
    pc_provider_match = re.search(r'<pcProvider([^>]*)>(.*?)</pcProvider>', vpr_text, re.DOTALL)
    if pc_provider_match:
        attrs_str = pc_provider_match.group(1)
        address_xml = pc_provider_match.group(2)
        attrs = dict(re.findall(r'(\w+)=[\'\"]([^\'\"]+)[\'\"]', attrs_str))
        name = attrs.get('name', '')
        code = attrs.get('code', '')
        email = attrs.get('email', '')
        phone = attrs.get('officePhone', '')
        taxonomy = attrs.get('taxonomyCode', '')
        provider_type = attrs.get('providerType', '')
        classification = attrs.get('classification', '')
        service = attrs.get('service', '')
        # Address
        address_match = re.search(r'<address ([^>]*)/>', address_xml)
        address = ''
        if address_match:
            address_attrs = dict(re.findall(r'(\w+)=[\'\"]([^\'\"]+)[\'\"]', address_match.group(1)))
            address = ', '.join([address_attrs.get('streetLine1', ''), address_attrs.get('city', ''), address_attrs.get('stateProvince', ''), address_attrs.get('postalCode', '')]).strip(', ')
        # Debug print
        print(f"Extracted PCP: code={code}, name={name}, email={email}, phone={phone}, taxonomy={taxonomy}, provider_type={provider_type}, classification={classification}, service={service}, address={address}")
        practitioner = {
            "resourceType": "Practitioner",
            "identifier": [{"value": code}] if code else None,
            "name": [{"text": name}] if name else None,
            "telecom": [{"value": phone}] if phone else None,
            "qualification": [{"code": {"text": provider_type}, "identifier": [{"value": taxonomy}]}] if provider_type or taxonomy else [],
            "address": [{"text": address}] if address else None,
            "email": email if email else None,
            "extension": [
                {"url": "http://hl7.org/fhir/StructureDefinition/practitioner-classification", "valueString": classification},
                {"url": "http://hl7.org/fhir/StructureDefinition/practitioner-service", "valueString": service}
            ] if classification or service else []
        }
        practitioner = {k: v for k, v in practitioner.items() if v not in [None, [], {}]}
        resources.append(practitioner)
    # Extract pcTeam
    pc_team_match = re.search(r'<pcTeam ([^>]*)/>', vpr_text)
    if pc_team_match:
        team_attrs = dict(re.findall(r'(\w+)=[\'\"]([^\'\"]+)[\'\"]', pc_team_match.group(1)))
        team_id = team_attrs.get('code', '')
        team_name = team_attrs.get('name', '')
        # Debug print
        print(f"Extracted PCTEAM: code={team_id}, name={team_name}")
        careteam = {
            "resourceType": "CareTeam",
            "identifier": [{"value": team_id}] if team_id else None,
            "name": team_name if team_name else None
        }
        careteam = {k: v for k, v in careteam.items() if v not in [None, [], {}]}
        resources.append(careteam)
    return resources

def fileman_to_iso8601(fileman_str):
    """
    Converts a VistA FileMan date/time string (e.g., 3250519.1247) to ISO 8601 format (e.g., 2025-05-19T12:47:00).
    Returns the ISO 8601 string, or the original string if conversion fails.
    """
    try:
        if not fileman_str or not re.match(r'^\d{7}(\.\d+)?$', fileman_str):
            return fileman_str
        date_part = fileman_str.split('.')[0]
        time_part = fileman_str.split('.')[1] if '.' in fileman_str else ''
        year = int(date_part[:3]) + 1700
        month = int(date_part[3:5])
        day = int(date_part[5:7])
        hour = int(time_part[:2]) if len(time_part) >= 2 else 0
        minute = int(time_part[2:4]) if len(time_part) >= 4 else 0
        second = int(time_part[4:6]) if len(time_part) >= 6 else 0
        dt = datetime.datetime(year, month, day, hour, minute, second)
        return dt.isoformat()
    except Exception:
        return fileman_str

def main():
    if len(sys.argv) < 2:
        print('Usage: python vpr_soap_to_FHIR.py <vpr_response_txt_file>')
        sys.exit(1)
    input_path = sys.argv[1]
    if not os.path.exists(input_path):
        print(f'File not found: {input_path}')
        sys.exit(1)
    with open(input_path, 'r', encoding='utf-8') as f:
        vpr_text = f.read()
    # Extract DFN from filename
    match = re.search(r'(\d+)', os.path.basename(input_path))
    dfn = match.group(1) if match else 'unknown'
    # Start FHIR Bundle
    bundle = {
        "resourceType": "Bundle",
        "type": "collection",
        "entry": []
    }
    # Add Conditions
    conditions = get_problems_as_conditions(vpr_text)
    for cond in conditions:
        bundle["entry"].append({"resource": cond})
    # Add Observations (Labs)
    observations = get_labs_as_observations(vpr_text)
    for obs in observations:
        bundle["entry"].append({"resource": obs})
    # Add Observations (Vitals)
    vital_observations = get_vitals_as_observations(vpr_text)
    for vobs in vital_observations:
        bundle["entry"].append({"resource": vobs})
    # Add DocumentReferences
    document_refs = get_documents_as_fhir(vpr_text)
    for doc in document_refs:
        bundle["entry"].append({"resource": doc})
    # Add Radiology Procedures
    radiology_procs = get_radiology_procedures_as_fhir(vpr_text)
    for proc in radiology_procs:
        bundle["entry"].append({"resource": proc})
    # Add Consults as ServiceRequests
    consults = get_consults_as_fhir(vpr_text)
    for sr in consults:
        bundle["entry"].append({"resource": sr})
    # Add Medications as MedicationRequests
    meds = get_meds_as_fhir(vpr_text)
    for med in meds:
        bundle["entry"].append({"resource": med})
    # Add Patient Demographics
    patients = get_patient_demographics_as_fhir(vpr_text)
    for pat in patients:
        bundle["entry"].append({"resource": pat})
    # Add Primary Care Provider and Team
    pcp_team = get_primary_care_provider_and_team_as_fhir(vpr_text)
    for res in pcp_team:
        bundle["entry"].append({"resource": res})
    # Add Allergies
    allergies = get_allergies_as_fhir(vpr_text)
    for allergy in allergies:
        bundle["entry"].append({"resource": allergy})
    # Add Immunizations
    immunizations = get_immunizations_as_fhir(vpr_text)
    for imm in immunizations:
        bundle["entry"].append({"resource": imm})
    # Add Encounters
    encounters = get_encounters_as_fhir(vpr_text)
    for enc in encounters:
        bundle["entry"].append({"resource": enc})
    # Add Surgeries/Procedures (non-radiology)
    surgeries = get_surgeries_as_fhir(vpr_text)
    for surg in surgeries:
        bundle["entry"].append({"resource": surg})
    # Write to output JSON file
    output_path = f'fhir_bundle_{dfn}.json'
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(bundle, f, indent=2)
    print(f'Wrote FHIR bundle to {output_path}')

def vpr_xml_to_fhir_bundle(xml_string):
    """
    Accepts VPR XML as a string, returns a FHIR bundle as a Python dict.
    """
    # Debug: log type and sample
    print(f"[DEBUG] vpr_xml_to_fhir_bundle input type: {type(xml_string)}")
    try:
        sample = xml_string[:100] if isinstance(xml_string, (str, bytes)) else str(type(xml_string))
        print(f"[DEBUG] vpr_xml_to_fhir_bundle input sample: {repr(sample)}")
    except Exception as e:
        print(f"[DEBUG] Could not print sample: {e}")
    # Robust decode/sanitize
    try:
        if isinstance(xml_string, bytes):
            try:
                xml_string = xml_string.decode("utf-8")
            except UnicodeDecodeError:
                print("[DEBUG] utf-8 decode failed, trying latin-1")
                xml_string = xml_string.decode("latin-1")
        elif isinstance(xml_string, str):
            try:
                # Try to encode/decode as utf-8
                xml_string = xml_string.encode("utf-8").decode("utf-8")
            except UnicodeEncodeError:
                print("[DEBUG] utf-8 encode failed, trying latin-1")
                xml_string = xml_string.encode("latin-1", errors="replace").decode("utf-8", errors="replace")
        else:
            xml_string = str(xml_string)
    except Exception as e:
        print(f"[ERROR] XML sanitization failed: {e}")
        xml_string = str(xml_string)
    # Remove any leading BOM or whitespace
    xml_string = xml_string.lstrip("\ufeff\n\r ")
    vpr_text = xml_string
    # --- Begin main logic from original main() ---
    bundle = {
        "resourceType": "Bundle",
        "type": "collection",
        "entry": []
    }
    # Add Conditions
    conditions = get_problems_as_conditions(vpr_text)
    for cond in conditions:
        bundle["entry"].append({"resource": cond})
    # Add Observations (Labs)
    observations = get_labs_as_observations(vpr_text)
    for obs in observations:
        bundle["entry"].append({"resource": obs})
    # Add Observations (Vitals)
    vital_observations = get_vitals_as_observations(vpr_text)
    for vobs in vital_observations:
        bundle["entry"].append({"resource": vobs})
    # Add DocumentReferences
    document_refs = get_documents_as_fhir(vpr_text)
    for doc in document_refs:
        bundle["entry"].append({"resource": doc})
    # Add Radiology Procedures
    radiology_procs = get_radiology_procedures_as_fhir(vpr_text)
    for proc in radiology_procs:
        bundle["entry"].append({"resource": proc})
    # Add Consults as ServiceRequests
    consults = get_consults_as_fhir(vpr_text)
    for sr in consults:
        bundle["entry"].append({"resource": sr})
    # Add Medications as MedicationRequests
    meds = get_meds_as_fhir(vpr_text)
    for med in meds:
        bundle["entry"].append({"resource": med})
    # Add Patient Demographics
    patients = get_patient_demographics_as_fhir(vpr_text)
    for pat in patients:
        bundle["entry"].append({"resource": pat})
    # Add Primary Care Provider and Team
    pcp_team = get_primary_care_provider_and_team_as_fhir(vpr_text)
    for res in pcp_team:
        bundle["entry"].append({"resource": res})
    # Add Allergies
    allergies = get_allergies_as_fhir(vpr_text)
    for allergy in allergies:
        bundle["entry"].append({"resource": allergy})
    # Add Immunizations
    immunizations = get_immunizations_as_fhir(vpr_text)
    for imm in immunizations:
        bundle["entry"].append({"resource": imm})
    # Add Encounters
    encounters = get_encounters_as_fhir(vpr_text)
    for enc in encounters:
        bundle["entry"].append({"resource": enc})
    # Add Surgeries/Procedures (non-radiology)
    surgeries = get_surgeries_as_fhir(vpr_text)
    for surg in surgeries:
        bundle["entry"].append({"resource": surg})
    return bundle
if __name__ == '__main__':
    main()