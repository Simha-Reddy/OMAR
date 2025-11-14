from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
from typing import Any, Dict, Iterable, Mapping, MutableMapping, Optional, Tuple

from flask import current_app, session as flask_session


class UserSettingsError(RuntimeError):
    """Raised when user settings cannot be read or written."""


_JSONType = Dict[str, Any]


def _users_root() -> Path:
    root = current_app.config.get("USERS_ROOT")
    if root:
        return Path(root)
    return Path(current_app.config["PACKAGE_ROOT"]) / "users"


def _default_user_dir() -> Path:
    return _users_root() / "default"


def ensure_default_user_folder() -> Path:
    """Ensure the shared default user asset directory exists."""
    default_dir = _default_user_dir()
    default_dir.mkdir(parents=True, exist_ok=True)
    return default_dir


def _clean_segment(value: Optional[str], fallback: str = "default") -> str:
    text = str(value or "").strip()
    if not text:
        return fallback
    normalized = "".join(ch for ch in text if ch.isalnum() or ch in ("-", "_"))
    return normalized or fallback


def resolve_user_identity(
    *, station: Optional[str] = None, duz: Optional[str] = None
) -> Tuple[str, str]:
    sess_station = flask_session.get("station") if flask_session else None
    sess_duz = flask_session.get("duz") if flask_session else None
    resolved_station = _clean_segment(station or sess_station)
    resolved_duz = _clean_segment(duz or sess_duz)
    return resolved_station, resolved_duz


def ensure_user_directory(
    *, station: Optional[str] = None, duz: Optional[str] = None
) -> Path:
    """Create and memoize the per-user settings directory when needed."""
    ensure_default_user_folder()
    resolved_station, resolved_duz = resolve_user_identity(station=station, duz=duz)
    user_path = _user_dir(resolved_station, resolved_duz)
    created = False
    if not user_path.exists():
        user_path.mkdir(parents=True, exist_ok=True)
        created = True
    _remember_session_user_marker(resolved_station, resolved_duz)
    if created:
        try:
            current_app.logger.debug(
                "Created user settings directory",
                extra={
                    "station": resolved_station,
                    "duz": resolved_duz,
                    "user_settings_path": str(user_path),
                },
            )
        except Exception:
            pass
    return user_path


def _user_dir(station: str, duz: str) -> Path:
    return _users_root() / station / duz


def _remember_session_user_marker(station: str, duz: str) -> None:
    try:
        if not flask_session:
            return
        marker = f"{station}:{duz}"
        if flask_session.get("_user_settings_marker") == marker:
            return
        flask_session["_user_settings_marker"] = marker
        flask_session.modified = True
    except RuntimeError:
        # Not running inside a request context; skip session memoization.
        return


def _ensure_parent(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


def _read_json(path: Path) -> _JSONType:
    if not path.exists():
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(data, Mapping):
        return dict(data)
    raise UserSettingsError(f"Expected mapping in {path}")


def _write_json(path: Path, data: Mapping[str, Any]) -> None:
    _ensure_parent(path)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def _delete_file(path: Path) -> None:
    try:
        path.unlink()
    except FileNotFoundError:
        pass


def _merge_scribe_prompts(base: Mapping[str, Any], overlay: Mapping[str, Any]) -> Dict[str, Any]:
    merged = {k: dict(v) for k, v in base.items() if isinstance(v, Mapping)}
    for key, value in overlay.items():
        if value is None:
            merged.pop(key, None)
            continue
        if not isinstance(value, Mapping):
            continue
        title = str(value.get("title") or "").strip()
        full_text = str(value.get("full_text") or "").strip()
        if not title or not full_text:
            # Skip empty payloads but allow deletions (handled above)
            continue
        merged[key] = {"title": title, "full_text": full_text}
    return merged


def _merge_prompts(defaults: Mapping[str, Any], overrides: Mapping[str, Any]) -> Dict[str, Any]:
    merged: Dict[str, Any] = dict(deepcopy(defaults))
    for key, value in overrides.items():
        if key == "scribe_prompts":
            base_prompts = merged.get("scribe_prompts")
            if not isinstance(base_prompts, Mapping):
                base_prompts = {}
            overlay_prompts = value if isinstance(value, Mapping) else {}
            merged["scribe_prompts"] = _merge_scribe_prompts(base_prompts, overlay_prompts)
            continue
        if value is None:
            merged.pop(key, None)
            continue
        merged[key] = value
    return merged


def _prune_empty(mapping: MutableMapping[str, Any]) -> None:
    empty_keys = [key for key, value in mapping.items() if value in (None, "", {}, [])]
    for key in empty_keys:
        mapping.pop(key, None)


def _apply_prompts_patch(overrides: _JSONType, patch: Mapping[str, Any]) -> bool:
    changed = False
    for key, value in patch.items():
        if key == "scribe_prompts":
            if value is None:
                if overrides.pop("scribe_prompts", None) is not None:
                    changed = True
                continue
            if not isinstance(value, Mapping):
                continue
            bucket = overrides.setdefault("scribe_prompts", {})
            if not isinstance(bucket, MutableMapping):
                bucket = overrides["scribe_prompts"] = {}
            for prompt_id, payload in value.items():
                if payload is None:
                    if prompt_id in bucket:
                        del bucket[prompt_id]
                        changed = True
                    continue
                if not isinstance(payload, Mapping):
                    continue
                title = str(payload.get("title") or "").strip()
                full_text = str(payload.get("full_text") or "").strip()
                if not title or not full_text:
                    continue
                incoming = {"title": title, "full_text": full_text}
                if bucket.get(prompt_id) != incoming:
                    bucket[prompt_id] = incoming
                    changed = True
            if not bucket:
                overrides.pop("scribe_prompts", None)
            continue
        if value is None:
            if overrides.pop(key, None) is not None:
                changed = True
            continue
        if overrides.get(key) != value:
            overrides[key] = value
            changed = True
    _prune_empty(overrides)
    return changed


def _subset(data: Mapping[str, Any], fields: Optional[Iterable[str]]) -> Dict[str, Any]:
    if not fields:
        return dict(data)
    chosen = set(fields)
    out: Dict[str, Any] = {}
    for key in chosen:
        if key in data:
            out[key] = deepcopy(data[key])
    return out


def load_prompts(
    *,
    station: Optional[str] = None,
    duz: Optional[str] = None,
    fields: Optional[Iterable[str]] = None,
    include_defaults: bool = True,
) -> Dict[str, Any]:
    resolved_station, resolved_duz = resolve_user_identity(station=station, duz=duz)
    ensure_user_directory(station=resolved_station, duz=resolved_duz)
    defaults = _read_json(_default_user_dir() / "prompts.json") if include_defaults else {}
    overrides = _read_json(_user_dir(resolved_station, resolved_duz) / "prompts.json")
    effective = _merge_prompts(defaults, overrides if overrides else {}) if include_defaults else overrides
    payload: Dict[str, Any] = {
        "station": resolved_station,
        "duz": resolved_duz,
        "prompts": _subset(effective, fields),
        "overrides": _subset(overrides, fields),
    }
    if include_defaults:
        payload["defaults"] = _subset(defaults, fields)
    return payload


def save_prompts(
    updates: Mapping[str, Any],
    *,
    station: Optional[str] = None,
    duz: Optional[str] = None,
) -> Dict[str, Any]:
    resolved_station, resolved_duz = resolve_user_identity(station=station, duz=duz)
    ensure_user_directory(station=resolved_station, duz=resolved_duz)
    user_path = _user_dir(resolved_station, resolved_duz) / "prompts.json"
    overrides = _read_json(user_path)
    if not _apply_prompts_patch(overrides, updates):
        return overrides
    if overrides:
        _write_json(user_path, overrides)
    else:
        _delete_file(user_path)
    return overrides


def load_layout(
    *,
    station: Optional[str] = None,
    duz: Optional[str] = None,
    include_defaults: bool = True,
) -> Dict[str, Any]:
    resolved_station, resolved_duz = resolve_user_identity(station=station, duz=duz)
    ensure_user_directory(station=resolved_station, duz=resolved_duz)
    defaults = _read_json(_default_user_dir() / "layout.json") if include_defaults else {}
    overrides = _read_json(_user_dir(resolved_station, resolved_duz) / "layout.json")
    effective = overrides or defaults
    payload: Dict[str, Any] = {
        "station": resolved_station,
        "duz": resolved_duz,
        "layout": deepcopy(effective),
        "overrides": deepcopy(overrides),
    }
    if include_defaults:
        payload["defaults"] = deepcopy(defaults)
    payload["source"] = "user" if overrides else "default"
    return payload


def save_layout(
    layout: Optional[Mapping[str, Any]],
    *,
    station: Optional[str] = None,
    duz: Optional[str] = None,
) -> None:
    resolved_station, resolved_duz = resolve_user_identity(station=station, duz=duz)
    ensure_user_directory(station=resolved_station, duz=resolved_duz)
    user_path = _user_dir(resolved_station, resolved_duz) / "layout.json"
    if layout is None:
        _delete_file(user_path)
        return
    _write_json(user_path, layout)
