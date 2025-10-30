from __future__ import annotations
from typing import Any, Dict, Protocol, Tuple, Optional

class DataGateway(Protocol):
    """Abstract interface for patient data reads."""
    def get_demographics(self, dfn: str) -> Dict[str, Any]:
        ...
    def get_vpr_fullchart(self, dfn: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Return full VPR JSON by omitting the domain filter (large payload).
        Optional params can include start/stop or other supported flags.
        """
        ...

class GatewayError(RuntimeError):
    pass
