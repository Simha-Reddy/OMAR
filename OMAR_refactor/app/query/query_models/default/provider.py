from __future__ import annotations
from typing import Dict, Any, List
from ...contracts import QueryModel
from ....ai_tools import llm
from pathlib import Path
from ....gateways.vista_api_x_gateway import VistaApiXGateway
from ....services.patient_service import PatientService
from ...services.rag import RagEngine
from ...services.rag_store import store as rag_store

class DefaultQueryModelImpl:
    model_id = 'default'
    name = 'Default Hey OMAR Model'

    def __init__(self):
        self._prompt_path = Path(__file__).parent / 'PROMPT_answer.md'

    def answer(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        prompt = (payload.get('prompt') or '').strip()
        patient = payload.get('patient')  # optional dict expected to contain DFN/localId
        if not prompt:
            return { 'answer': '', 'citations': [], 'model_id': self.model_id }

        # 1) Fetch documents via VPR
        dfn = None
        try:
            if isinstance(patient, dict):
                dfn = patient.get('DFN') or patient.get('dfn') or patient.get('localId') or patient.get('patientId')
        except Exception:
            dfn = None
        gateway = VistaApiXGateway()
        # Prefer the shared RagStore when a DFN is provided (patient-scoped cache and lexical-first behavior)
        top_chunks = []
        if dfn:
            vpr_docs = gateway.get_vpr_domain(str(dfn), domain='documents')
            rag_store.ensure_index(str(dfn), vpr_docs)
            # Attempt semantic upgrade opportunistically (no-op if Azure not configured)
            rag_store.embed_now(str(dfn))
            top_chunks = rag_store.retrieve(str(dfn), prompt, top_k=10)
        else:
            # Fallback: ad-hoc RAG on provided documents (empty by default)
            vpr_docs = {'data': {'items': []}}
            rag = RagEngine(window_size=1600, step_size=800)
            chunks = rag.build_chunks_from_vpr_documents(vpr_docs)
            rag.index()
            top_chunks = rag.retrieve(prompt, top_k=10)

        # 3) Compose a compact prompt with citations expectations
        try:
            system = (self._prompt_path.read_text(encoding='utf-8')).strip()
        except Exception:
            system = (
                'You are a clinical assistant. Use the provided excerpts to answer succinctly. '
                'Cite each fact with (Excerpt N) matching the excerpt number shown.'
            )
        context_blobs: List[str] = []
        for c in top_chunks:
            pg = c.get('page', '?')
            dt = c.get('date') or ''
            ttl = c.get('title') or ''
            hdr = f"### Source: (Excerpt {pg}{', Date: ' + dt if dt else ''}{', Title: ' + ttl if ttl else ''})"
            context_blobs.append(hdr + "\n" + (c.get('text') or '')[:1600])
        context = "\n\n".join(context_blobs)
        final_prompt = f"{system}\n\nQuestion: \"{prompt}\"\n\nBelow are excerpts from the chart:\n{context}"
        answer_text = llm.chat(final_prompt)

        # 4) Prepare citations list
        citations = []
        for c in top_chunks:
            citations.append({
                'excerpt': c.get('page', '?'),
                'note_id': c.get('note_id'),
                'title': c.get('title'),
                'date': c.get('date'),
                'preview': (c.get('text') or '')[:200]
            })

        return { 'answer': answer_text, 'citations': citations, 'model_id': self.model_id }

# Export symbol for registry
model: QueryModel = DefaultQueryModelImpl()
