from __future__ import annotations
from typing import List, Optional
import os

# Minimal embedding helper. If Azure OpenAI is not configured, returns unit vectors.

def get_embeddings(texts: List[str], deployment: Optional[str] = None) -> List[List[float]]:
    try:
        from openai import AzureOpenAI
    except Exception:
        AzureOpenAI = None  # type: ignore

    if not texts:
        return []

    if AzureOpenAI is None or not os.getenv("AZURE_OPENAI_API_KEY"):
        # Fallback: deterministic placeholder vectors (length 3) to keep pipelines testable without Azure
        return [[1.0, 0.0, 0.0] for _ in texts]

    client = AzureOpenAI(
        api_key=os.getenv("AZURE_OPENAI_API_KEY"),
        api_version=os.getenv("AZURE_API_VERSION", "2024-02-15-preview"),
        azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT") or os.getenv("AZURE_ENDPOINT"),
    )
    deployment_name = deployment or os.getenv("AZURE_EMBEDDING_DEPLOYMENT_NAME")
    if not deployment_name:
        # No deployment configured; return placeholders
        return [[1.0, 0.0, 0.0] for _ in texts]

    resp = client.embeddings.create(input=texts, model=deployment_name)
    return [d.embedding for d in resp.data]
