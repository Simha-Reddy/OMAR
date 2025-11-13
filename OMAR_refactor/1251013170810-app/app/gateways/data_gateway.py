from __future__ import annotations

from typing import Any, Dict, List, Optional, Protocol


class DataGateway(Protocol):
    """Abstract interface for patient data reads."""

    def get_demographics(self, dfn: str) -> Dict[str, Any]:
        ...

    def get_vpr_domain(self, dfn: str, domain: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        ...

    def get_vpr_fullchart(self, dfn: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Return full VPR JSON by omitting the domain filter (large payload)."""
        ...

    def get_lab_panels(
        self,
        dfn: str,
        *,
        start: Optional[str] = None,
        end: Optional[str] = None,
        max_panels: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """Return recent lab panels (ORWCV LAB) with optional ISO range filtering."""
        ...

    def get_lab_panel_detail(self, dfn: str, lab_id: str) -> Dict[str, Any]:
        """Return detailed analyte data for a specific lab panel via ORWOR RESULT."""
        ...

    def get_document_texts(self, dfn: str, doc_ids: List[str]) -> Dict[str, List[str]]:
        """Return full text lines for requested TIU document ids."""
        ...

    def get_document_index_entries(
        self,
        dfn: str,
        params: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        """Return normalized document entries that include hydrated note content when available."""
        ...

    def call_rpc(
        self,
        *,
        context: str,
        rpc: str,
        parameters: Optional[list[dict]] = None,
        json_result: bool = False,
        timeout: int = 60,
    ) -> Any:
        ...


class GatewayError(RuntimeError):
    pass
