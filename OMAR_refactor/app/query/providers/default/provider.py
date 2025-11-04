from __future__ import annotations

# Default Query Provider (stub)
# This placeholder eliminates {"error": "'default'"} by exposing a minimal provider
# that conforms to ModelProvider and returns a safe response. It will be replaced
# by the full RAG implementation described in the plan.

from typing import Dict, Any


class _DefaultQueryProvider:
	provider_id = "default"
	name = "OMAR Default (stub)"

	def answer(self, payload: Dict[str, Any]) -> Dict[str, Any]:
		prompt = (payload or {}).get("prompt") or ""
		patient = (payload or {}).get("patient") or {}
		dfn = patient.get("DFN") or patient.get("dfn") or ""
		# Return a clear, non-failing placeholder with the required shape
		msg = (
			"Default query model not yet implemented in this build. "
			"Your request was received and routed correctly."
		)
		if prompt:
			msg += f"\n\nPrompt: {prompt[:400]}{'…' if len(prompt) > 400 else ''}"
		if dfn:
			msg += f"\nPatient DFN: {dfn}"
		return {
			"answer": msg,
			"citations": [],
			"provider_id": self.provider_id,
		}


# Registry entrypoint
provider = _DefaultQueryProvider()

