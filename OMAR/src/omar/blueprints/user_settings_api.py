from __future__ import annotations

from typing import Iterable, Mapping, Optional

from flask import Blueprint, jsonify, request

from ..services.user_settings import (
    UserSettingsError,
    load_layout,
    load_prompts,
    save_layout,
    save_prompts,
)

bp = Blueprint("user_settings_api", __name__, url_prefix="/api/user-settings")


def _parse_fields(raw: Optional[str]) -> Optional[Iterable[str]]:
    if not raw:
        return None
    fields = [part.strip() for part in raw.split(",") if part.strip()]
    return fields or None


def _bool_param(name: str, default: bool = True) -> bool:
    raw = request.args.get(name)
    if raw is None:
        return default
    return str(raw).strip().lower() not in ("0", "false", "no", "off")


def _json_error(message: str, status: int = 400):
    return jsonify({"error": message}), status


@bp.route("/prompts", methods=["GET"])
def get_prompts():
    include_defaults = _bool_param("include_defaults", True)
    fields = _parse_fields(request.args.get("fields"))
    try:
        payload = load_prompts(include_defaults=include_defaults, fields=fields)
    except UserSettingsError as exc:
        return _json_error(str(exc), 500)
    return jsonify(payload)


@bp.route("/prompts", methods=["PUT", "PATCH"])
def update_prompts():
    payload = request.get_json(silent=True) or {}
    if not isinstance(payload, Mapping):
        return _json_error("Payload must be a JSON object", 400)
    try:
        save_prompts(payload)
        refreshed = load_prompts(include_defaults=True, fields=_parse_fields(request.args.get("fields")))
    except UserSettingsError as exc:
        return _json_error(str(exc), 500)
    return jsonify(refreshed)


@bp.route("/layout", methods=["GET"])
def get_layout():
    include_defaults = _bool_param("include_defaults", True)
    try:
        payload = load_layout(include_defaults=include_defaults)
    except UserSettingsError as exc:
        return _json_error(str(exc), 500)
    return jsonify(payload)


@bp.route("/layout", methods=["PUT", "PATCH"])
def update_layout():
    payload = request.get_json(silent=True) or {}
    if not isinstance(payload, Mapping):
        return _json_error("Payload must be a JSON object", 400)
    layout = payload.get("layout")
    if layout is not None and not isinstance(layout, Mapping):
        return _json_error("'layout' must be a JSON object or null", 400)
    try:
        save_layout(layout)
        refreshed = load_layout(include_defaults=True)
    except UserSettingsError as exc:
        return _json_error(str(exc), 500)
    return jsonify(refreshed)
