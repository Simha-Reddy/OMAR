"""Thin wrappers for RAG helpers used by the template model.

These functions are re-exported from the default provider's RAG utilities to keep
the template small. If you want a fully independent provider, copy the code and
modify it here.
"""

from omar.query.query_models.default.services.rag import (
    sliding_window_chunk,
    remove_boilerplate_phrases,
    build_bm25_index,
    hybrid_search,
)

__all__ = [
    'sliding_window_chunk',
    'remove_boilerplate_phrases',
    'build_bm25_index',
    'hybrid_search',
]
