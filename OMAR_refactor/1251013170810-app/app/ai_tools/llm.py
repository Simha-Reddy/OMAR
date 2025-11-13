from __future__ import annotations
import os
from typing import Optional

# Minimal LLM chat helper. If Azure OpenAI is not configured, echoes the prompt for development.

def chat(prompt: str, deployment: Optional[str] = None, temperature: float = 0.2) -> str:
    try:
        from openai import AzureOpenAI
    except Exception:
        AzureOpenAI = None  # type: ignore

    if not prompt:
        return ""

    if AzureOpenAI is None or not os.getenv("AZURE_OPENAI_API_KEY"):
        return f"[DEV ECHO] {prompt[:2000]}"

    client = AzureOpenAI(
        api_key=os.getenv("AZURE_OPENAI_API_KEY"),
        api_version=os.getenv("AZURE_API_VERSION", "2024-02-15-preview"),
        azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT") or os.getenv("AZURE_ENDPOINT"),
    )
    model = deployment or os.getenv("AZURE_DEPLOYMENT_NAME")
    if not model:
        return f"[DEV ECHO] {prompt[:2000]}"

    resp = client.chat.completions.create(
        model=model,
        temperature=temperature,
        messages=[
            {"role": "system", "content": "You are a helpful clinical assistant."},
            {"role": "user", "content": prompt},
        ],
    )
    return (resp.choices[0].message.content or "").strip()
