from __future__ import annotations
from typing import Dict
import importlib
import pkgutil

from .contracts import ModelProvider

# Simple registry that auto-discovers providers under app.query.providers.*

class ModelRegistry:
    def __init__(self):
        self._providers: Dict[str, ModelProvider] = {}
        self._discover()

    def _discover(self):
        pkg = 'app.query.providers'
        for _, modname, ispkg in pkgutil.iter_modules(importlib.import_module(pkg).__path__):  # type: ignore
            if not ispkg:
                continue
            try:
                module = importlib.import_module(f"{pkg}.{modname}.provider")
                # Expect a symbol named `provider` that implements ModelProvider
                candidate = getattr(module, 'provider', None)
                if candidate is None:
                    continue
                pid = getattr(candidate, 'provider_id', None)
                if not pid:
                    continue
                self._providers[pid] = candidate
            except Exception:
                continue
        # Ensure there is a default
        if 'default' not in self._providers:
            try:
                module = importlib.import_module(f"{pkg}.default.provider")
                candidate = getattr(module, 'provider', None)
                if candidate is not None:
                    self._providers[candidate.provider_id] = candidate
            except Exception:
                pass

    def get(self, provider_id: str) -> ModelProvider:
        pid = provider_id or 'default'
        if pid not in self._providers:
            pid = 'default'
        return self._providers[pid]

    @property
    def providers(self):
        return self._providers
