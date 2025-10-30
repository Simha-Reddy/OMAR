from __future__ import annotations
from typing import Any, Dict
from ..gateways.data_gateway import DataGateway
from .transforms import (
    map_vpr_patient_to_quick_demographics,
    vpr_to_quick_medications,
    vpr_to_quick_labs,
    vpr_to_quick_vitals,
    vpr_to_quick_notes,
    vpr_to_quick_radiology,
    vpr_to_quick_procedures,
    vpr_to_quick_encounters,
    vpr_to_quick_problems,
    vpr_to_quick_allergies,
)

class PatientService:
    def __init__(self, gateway: DataGateway):
        self.gateway = gateway
        # Route-friendly to VPR domain mapping when names differ
        # Map friendly route names to VPR JSON domain tokens (singular per VPR 1.0 Guide)
        # Keep common plural aliases to avoid breaking callers.
        self.domain_alias = {
            'demographics': 'patient',
            'patient': 'patient',
            # Medications
            'meds': 'med',
            'med': 'med',
            # Labs
            'labs': 'lab',
            'lab': 'lab',
            # Vitals
            'vitals': 'vital',
            'vital': 'vital',
            # Documents (TIU)
            'notes': 'document',
            'documents': 'document',
            'document': 'document',
            # Radiology/Nuclear Medicine images
            'radiology': 'image',
            'image': 'image',
            # Procedures
            'procedures': 'procedure',
            'procedure': 'procedure',
            # Encounters/Visits
            'encounters': 'visit',
            'visits': 'visit',
            'visit': 'visit',
            # Problems & Allergies
            'problems': 'problem',
            'problem': 'problem',
            'allergies': 'allergy',
            'allergy': 'allergy',
            # Scheduling & others (future use)
            'appointments': 'appointment',
            'appointment': 'appointment',
            'surgery': 'surgery',
            'consult': 'consult',
            'order': 'order',
            'orders': 'order',
            # Additional VPR domains
            'immunization': 'immunization',
            'immunizations': 'immunization',
            'obs': 'obs',
            'observations': 'obs',
            'cpt': 'cpt',
            'exam': 'exam',
            'exams': 'exam',
            'education': 'education',
            'factor': 'factor',
            'factors': 'factor',
            'pov': 'pov',
            'skin': 'skin',
            'ptf': 'ptf',
        }

    def get_demographics(self, dfn: str) -> Dict[str, Any]:
        # In future: normalize to quick/ shape
        return self.gateway.get_demographics(dfn)

    # New: quick flattened demographics (direct VPR mapping)
    def get_demographics_quick(self, dfn: str) -> Dict[str, Any]:
        vpr = self.gateway.get_vpr_domain(dfn, domain='patient')
        return map_vpr_patient_to_quick_demographics(vpr)

    # --- Medications ---
    def get_medications_quick(self, dfn: str):
        vpr = self.gateway.get_vpr_domain(dfn, domain=self.domain_alias['meds'])
        return vpr_to_quick_medications(vpr)

    # --- Labs ---
    def get_labs_quick(self, dfn: str):
        vpr = self.gateway.get_vpr_domain(dfn, domain=self.domain_alias['labs'])
        return vpr_to_quick_labs(vpr)

    # --- Vitals ---
    def get_vitals_quick(self, dfn: str):
        vpr = self.gateway.get_vpr_domain(dfn, domain=self.domain_alias['vitals'])
        return vpr_to_quick_vitals(vpr)

    # --- Notes ---
    def get_notes_quick(self, dfn: str):
        vpr = self.gateway.get_vpr_domain(dfn, domain=self.domain_alias['notes'])
        return vpr_to_quick_notes(vpr)

    # --- Documents (unified) ---
    def get_documents_quick(self, dfn: str):
        """Unified documents quick list from VPR 'documents' domain.
        Uses the document-centric notes transform.
        """
        vpr = self.gateway.get_vpr_domain(dfn, domain=self.domain_alias['document'])
        return vpr_to_quick_notes(vpr)

    # --- Radiology ---
    def get_radiology_quick(self, dfn: str):
        vpr = self.gateway.get_vpr_domain(dfn, domain=self.domain_alias['radiology'])
        return vpr_to_quick_radiology(vpr)

    # --- Procedures ---
    def get_procedures_quick(self, dfn: str):
        vpr = self.gateway.get_vpr_domain(dfn, domain=self.domain_alias['procedures'])
        return vpr_to_quick_procedures(vpr)

    # --- Encounters ---
    def get_encounters_quick(self, dfn: str):
        vpr = self.gateway.get_vpr_domain(dfn, domain=self.domain_alias['encounters'])
        return vpr_to_quick_encounters(vpr)

    # --- Problems ---
    def get_problems_quick(self, dfn: str):
        vpr = self.gateway.get_vpr_domain(dfn, domain=self.domain_alias['problems'])
        return vpr_to_quick_problems(vpr)

    # --- Allergies ---
    def get_allergies_quick(self, dfn: str):
        vpr = self.gateway.get_vpr_domain(dfn, domain=self.domain_alias['allergies'])
        return vpr_to_quick_allergies(vpr)

    # Raw VPR passthrough
    def get_vpr_raw(self, dfn: str, domain: str, params: dict | None = None):
        # Map incoming alias to VPR canonical domain when known
        dom = self.domain_alias.get(domain, domain)
        return self.gateway.get_vpr_domain(dfn, domain=dom, params=params)

    # Full chart (no domain filter)
    def get_fullchart(self, dfn: str):
        return self.gateway.get_vpr_fullchart(dfn)
