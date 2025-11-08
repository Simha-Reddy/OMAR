from __future__ import annotations
from typing import Any, Dict, Protocol, Tuple, Optional

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

    # Optional: generic RPC for CPRS-style calls (patient search, sensitive check)
    def call_rpc(self, *, context: str, rpc: str, parameters: Optional[list[dict]] = None, json_result: bool = False, timeout: int = 60) -> Any:  # type: ignore[override]
        ...

class GatewayError(RuntimeError):
    pass
