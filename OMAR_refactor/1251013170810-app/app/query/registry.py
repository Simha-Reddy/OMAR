from __future__ import annotations
from typing import Dict
import importlib
import pkgutil

from .contracts import QueryModel

# Registry that auto-discovers query models under app.query.query_models.*

class QueryModelRegistry:
    def __init__(self):
        self._models: Dict[str, QueryModel] = {}
        self._discover()

    def _discover(self):
        base_pkg = 'app.query.query_models'
        try:
            base = importlib.import_module(base_pkg)
            pkg_paths = base.__path__  # type: ignore[attr-defined]
        except Exception:
            pkg_paths = []
        for _, modname, ispkg in pkgutil.iter_modules(pkg_paths):  # type: ignore[arg-type]
            if not ispkg:
                continue
            # Try provider.py then query_model.py, expect symbol `model`
            loaded = None
            for entry in ('provider', 'query_model'):
                try:
                    module = importlib.import_module(f"{base_pkg}.{modname}.{entry}")
                    loaded = getattr(module, 'model', None)
                    if loaded is not None:
                        break
                except Exception:
                    loaded = None
            if loaded is None:
                continue
            mid = getattr(loaded, 'model_id', None) or getattr(loaded, 'provider_id', None)
            if not mid:
                continue
            self._models[str(mid)] = loaded
        # Ensure default exists if present on disk
        if 'default' not in self._models:
            for entry in ('provider', 'query_model'):
                try:
                    module = importlib.import_module(f"{base_pkg}.default.{entry}")
                    loaded = getattr(module, 'model', None)
                    if loaded is not None:
                        mid = getattr(loaded, 'model_id', None) or 'default'
                        self._models[str(mid)] = loaded
                        break
                except Exception:
                    continue

    def get(self, model_id: str) -> QueryModel:
        mid = model_id or 'default'
        if mid not in self._models:
            mid = 'default'
        return self._models[mid]

    @property
    def models(self):
        return self._models

# Backward-compatible alias
ModelRegistry = QueryModelRegistry
