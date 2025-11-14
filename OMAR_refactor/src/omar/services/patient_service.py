from __future__ import annotations
from typing import Any, Dict, List, Optional, Tuple
from ..gateways.data_gateway import DataGateway, GatewayError
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
    vpr_to_quick_orders,
)
from .labs_rpc import rpc_panel_to_quick_tests

class PatientService:
    def __init__(self, gateway: DataGateway):
        self.gateway = gateway
        self._vpr_cache: Dict[Tuple[str, str, Tuple[Tuple[str, str], ...]], Any] = {}
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
    def _freeze_params(self, params: Optional[dict]) -> Tuple[Tuple[str, str], ...]:
        if not params:
            return ()
        frozen: List[Tuple[str, str]] = []
        for key, value in params.items():
            if isinstance(value, (list, tuple, set)):
                joined = ','.join(str(v) for v in value)
                frozen.append((str(key), joined))
            else:
                frozen.append((str(key), str(value)))
        frozen.sort(key=lambda kv: kv[0])
        return tuple(frozen)

    def _get_vpr_cached(self, dfn: str, domain: str, params: dict | None = None):
        dom = self.domain_alias.get(domain, domain)
        cache_key = (str(dfn), str(dom), self._freeze_params(params))
        if cache_key in self._vpr_cache:
            return self._vpr_cache[cache_key]
        payload = self.gateway.get_vpr_domain(dfn, domain=dom, params=params)
        self._vpr_cache[cache_key] = payload
        return payload

    def get_demographics_quick(self, dfn: str) -> Dict[str, Any]:
        vpr = self._get_vpr_cached(dfn, domain='patient')
        return map_vpr_patient_to_quick_demographics(vpr)

    # --- Medications ---
    def get_medications_quick(self, dfn: str, params: dict | None = None):
        vpr = self._get_vpr_cached(dfn, domain=self.domain_alias['meds'], params=params)
        return vpr_to_quick_medications(vpr)

    # --- Labs ---
    def get_labs_quick(
        self,
        dfn: str,
        params: dict | None = None,
        *,
        filters: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        vpr = self._get_vpr_cached(dfn, domain=self.domain_alias['labs'], params=params)
        quick_vpr = vpr_to_quick_labs(vpr)

        start_iso = None
        end_iso = None
        max_panels: Optional[int] = None
        if filters:
            if filters.get('start'):
                start_iso = str(filters['start']).strip() or None
            if filters.get('end'):
                end_iso = str(filters['end']).strip() or None
            if filters.get('max_panels') is not None:
                try:
                    max_panels = int(filters['max_panels'])
                except Exception:
                    max_panels = None
        if max_panels is None:
            try:
                max_panels = int((params or {}).get('max') or 0) or None
            except Exception:
                max_panels = None

        panels: List[Dict[str, Any]] = []
        rpc_rows: List[Dict[str, Any]] = []
        panel_ids_with_detail: set[str] = set()
        try:
            panels = self.gateway.get_lab_panels(dfn, start=start_iso, end=end_iso, max_panels=max_panels)
        except GatewayError:
            panels = []

        for panel in panels:
            lab_id_raw = panel.get('labId') or panel.get('id')
            lab_id = str(lab_id_raw).strip() if lab_id_raw is not None else ''
            if not lab_id:
                continue
            try:
                detail = self.gateway.get_lab_panel_detail(dfn, lab_id)
            except GatewayError:
                continue
            panel_ids_with_detail.add(lab_id)
            if ';' in lab_id:
                panel_ids_with_detail.add(lab_id.split(';', 1)[0])
            rows = rpc_panel_to_quick_tests(panel, detail)
            panel_name = panel.get('displayName') or panel.get('name')
            panel_status = panel.get('status')
            panel_resulted = panel.get('resulted') or panel.get('observed')
            for row in rows:
                row['source'] = 'rpc'
                row['panelId'] = lab_id
                row['panelName'] = panel_name
                row['panelStatus'] = panel_status
                if not row.get('observedDate') and panel_resulted:
                    row['observedDate'] = panel_resulted
                if not row.get('resulted') and panel_resulted:
                    row['resulted'] = panel_resulted
                rpc_rows.append(row)

        if not rpc_rows:
            return quick_vpr

        combined: List[Dict[str, Any]] = []
        for row in rpc_rows:
            combined.append(row)

        for item in quick_vpr:
            panel_id = str(item.get('panelId') or '').strip()
            if panel_id and panel_id in panel_ids_with_detail:
                continue
            combined.append(item)

        def _sort_key(entry: Dict[str, Any]) -> str:
            return str(entry.get('resulted') or entry.get('observedDate') or entry.get('observed') or '')

        combined.sort(key=_sort_key, reverse=True)
        return combined

    # --- Vitals ---
    def get_vitals_quick(self, dfn: str, params: dict | None = None):
        vpr = self._get_vpr_cached(dfn, domain=self.domain_alias['vitals'], params=params)
        return vpr_to_quick_vitals(vpr)

    # --- Notes ---
    def get_notes_quick(self, dfn: str, params: dict | None = None):
        vpr = self._get_vpr_cached(dfn, domain=self.domain_alias['notes'], params=params)
        return vpr_to_quick_notes(vpr)

    # --- Documents (unified) ---
    def get_documents_quick(self, dfn: str, params: dict | None = None):
        """Unified documents quick list from VPR 'documents' domain.
        Uses the document-centric notes transform.
        """
        vpr = self._get_vpr_cached(dfn, domain=self.domain_alias['document'], params=params)
        return vpr_to_quick_notes(vpr)

    def get_document_texts(self, dfn: str, doc_ids: list[str]) -> Dict[str, list[str]]:
        """Fetch full text for the requested TIU document identifiers."""
        return self.gateway.get_document_texts(dfn, doc_ids)

    # --- Radiology ---
    def get_radiology_quick(self, dfn: str, params: dict | None = None):
        vpr = self._get_vpr_cached(dfn, domain=self.domain_alias['radiology'], params=params)
        return vpr_to_quick_radiology(vpr)

    # --- Procedures ---
    def get_procedures_quick(self, dfn: str, params: dict | None = None):
        vpr = self._get_vpr_cached(dfn, domain=self.domain_alias['procedures'], params=params)
        return vpr_to_quick_procedures(vpr)

    # --- Encounters ---
    def get_encounters_quick(self, dfn: str, params: dict | None = None):
        vpr = self._get_vpr_cached(dfn, domain=self.domain_alias['encounters'], params=params)
        return vpr_to_quick_encounters(vpr)

    # --- Problems ---
    def get_problems_quick(self, dfn: str, params: dict | None = None):
        vpr = self._get_vpr_cached(dfn, domain=self.domain_alias['problems'], params=params)
        return vpr_to_quick_problems(vpr)

    # --- Allergies ---
    def get_allergies_quick(self, dfn: str, params: dict | None = None):
        vpr = self._get_vpr_cached(dfn, domain=self.domain_alias['allergies'], params=params)
        return vpr_to_quick_allergies(vpr)

    # --- Orders ---
    def get_orders_quick(self, dfn: str, params: dict | None = None):
        vpr = self._get_vpr_cached(dfn, domain=self.domain_alias['orders'], params=params)
        return vpr_to_quick_orders(vpr)

    # Raw VPR passthrough
    def get_vpr_raw(self, dfn: str, domain: str, params: dict | None = None):
        # Map incoming alias to VPR canonical domain when known
        return self._get_vpr_cached(dfn, domain, params=params)

    # Full chart (no domain filter)
    def get_fullchart(self, dfn: str):
        return self.gateway.get_vpr_fullchart(dfn)
