from __future__ import annotations
from typing import Protocol, Dict, Any

class QueryModel(Protocol):
    """Model contract for Hey OMAR query models.

    Required attributes:
      - model_id: str (unique)
      - name: str (display)
    Required methods:
      - answer(payload: Dict[str, Any]) -> Dict[str, Any]
        Expects at least { "prompt": str, "patient": Optional[Dict], ... }
        Returns { "answer": str, "citations": list[Dict], "model_id": str }
    """

    model_id: str
    name: str

    def answer(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        ...
