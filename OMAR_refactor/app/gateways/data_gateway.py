from __future__ import annotations
from typing import Any, Dict, List, Protocol, Tuple, Optional

class DataGateway(Protocol):
    """Abstract interface for patient data reads."""
    def get_demographics(self, dfn: str) -> Dict[str, Any]:
        ...
    def get_vpr_domain(self, dfn: str, domain: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        ...
    def get_vpr_fullchart(self, dfn: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Return full VPR JSON by omitting the domain filter (large payload).
        Optional params can include start/stop or other supported flags.
        """
        ...

    # Lab RPC supplemental helpers (ORWCV/ORWOR)
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
        """Return full text lines for the requested TIU document ids.

        Implementations may use different transport strategies (single VPR call vs.
        individual TIU RPCs). The return value maps each requested doc id to the
        corresponding list of text lines. Any ids that cannot be resolved should be
        omitted from the result.
        """
        ...

    # Optional: generic RPC for CPRS-style calls (patient search, sensitive check)
    def call_rpc(self, *, context: str, rpc: str, parameters: Optional[list[dict]] = None, json_result: bool = False, timeout: int = 60) -> Any:  # type: ignore[override]
        ...

class GatewayError(RuntimeError):
    pass
