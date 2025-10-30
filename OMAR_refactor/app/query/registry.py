from __future__ import annotations
from typing import Dict
import importlib
import pkgutil

from .contracts import QueryModel

# Simple registry that auto-discovers query models under app.query.query_models.*

class ModelRegistry:
    def __init__(self):
        self._models: Dict[str, QueryModel] = {}
        self._discover()

    def _discover(self):
        pkg = 'app.query.query_models'
        for _, modname, ispkg in pkgutil.iter_modules(importlib.import_module(pkg).__path__):  # type: ignore
            if not ispkg:
                continue
            try:
                module = importlib.import_module(f"{pkg}.{modname}.provider")
                # Expect a symbol named `model` that implements QueryModel
                candidate = getattr(module, 'model', None)
                if candidate is None:
                    continue
                mid = getattr(candidate, 'model_id', None)
                if not mid:
                    continue
                self._models[mid] = candidate
            except Exception:
                continue
        # Ensure there is a default
        if 'default' not in self._models:
            try:
                module = importlib.import_module(f"{pkg}.default.provider")
                candidate = getattr(module, 'model', None)
                if candidate is not None:
                    self._models[candidate.model_id] = candidate
            except Exception:
                pass

    def get(self, model_id: str) -> QueryModel:
        mid = model_id or 'default'
        if mid not in self._models:
            mid = 'default'
        return self._models[mid]

    @property
    def models(self):
        return self._models
