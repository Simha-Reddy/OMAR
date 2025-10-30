from __future__ import annotations
from typing import Dict, Any
from ...contracts import QueryModel
from pathlib import Path

class TemplateQueryModelImpl:
    model_id = 'template'
    name = 'Template Query Model (Copy Me)'

    def __init__(self):
        self._prompt_path = Path(__file__).parent / 'PROMPT_answer.md'

    def answer(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        # Implement your logic here. You can import from app.ai_tools for LLM/embeddings.
        prompt = (payload.get('prompt') or '').strip()
        # Example: just echo the prompt for now
        return {
            'answer': f"[Template] You asked: {prompt}",
            'citations': [],
            'model_id': self.model_id,
        }

# Export symbol for registry
model: QueryModel = TemplateQueryModelImpl()
