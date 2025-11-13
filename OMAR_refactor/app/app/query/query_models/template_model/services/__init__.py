"""Basic services for the template query model.

This package intentionally keeps things minimal and reuses the default model's
RAG utilities so you don't have to copy complex code. You can replace these
re-exports with your own implementations later.
"""

from .rag_simple import (
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
