from __future__ import annotations
from typing import Any, Dict, Protocol, Tuple

class DataGateway(Protocol):
    """Abstract interface for patient data reads."""
    def get_demographics(self, dfn: str) -> Dict[str, Any]:
        ...

class GatewayError(RuntimeError):
    pass
