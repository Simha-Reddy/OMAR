from __future__ import annotations

import json
import os
import socket
import threading
import time
from collections import OrderedDict
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

try:
    import xmltodict  # type: ignore
except Exception:  # pragma: no cover
    xmltodict = None  # type: ignore

from .data_gateway import DataGateway, GatewayError
from .vpr_xml_parser import parse_vpr_results_xml
from ..services.labs_rpc import filter_panels, parse_orwcv_lab, parse_orwor_result
from ..services.transforms import vpr_to_quick_notes


# ---------------------------------------------------------------------------
# XML normalization helpers (ported from archived VPR socket implementation)
# ---------------------------------------------------------------------------


def _coerce_boolish(val: Any) -> Any:
    if isinstance(val, str):
        trimmed = val.strip().lower()
        if trimmed in {"true", "false"}:
            return trimmed == "true"
        if trimmed in {"1", "0"}:
            return trimmed == "1"
    return val


def _strip_xml_attrs(obj: Any) -> Any:
    if isinstance(obj, dict):
        result: Dict[str, Any] = {}
        text_value: Any = None
        for key, value in obj.items():
            if key == "#text":
                text_value = _strip_xml_attrs(value)
                continue
            cleaned = _strip_xml_attrs(value)
            if key.startswith("@"):
                result[key[1:]] = cleaned
            else:
                result[key] = cleaned
        if text_value is not None:
            if result:
                result.setdefault("value", text_value)
            else:
                return text_value
        if len(result) == 1 and "value" in result:
            single = result["value"]
            return _coerce_boolish(single)
        return {
            k: (_coerce_boolish(v) if not isinstance(v, (dict, list)) else v)
            for k, v in result.items()
        }
    if isinstance(obj, list):
        return [_strip_xml_attrs(v) for v in obj]
    return _coerce_boolish(obj)


_COLLECTION_CHILD_MAP: Dict[str, str] = {
    "addresses": "address",
    "comments": "comment",
    "drugClasses": "drugClass",
    "drugIngredients": "drugIngredient",
    "eligibilities": "eligibility",
    "ethnicities": "ethnicity",
    "exposures": "exposure",
    "facilities": "facility",
    "flags": "flag",
    "patients": "patient",
    "products": "product",
    "providers": "provider",
    "reactions": "reaction",
    "results": "result",
    "supports": "support",
    "telecomList": "telecom",
    "telecoms": "telecom",
    "orders": "order",
    "doses": "dose",
    "fills": "fill",
    "participants": "participant",
    "documents": "document",
    "notes": "note",
    "immunizations": "immunization",
}

_COLLECTION_RENAME: Dict[str, str] = {
    "telecomList": "telecoms",
}


def _normalize_collections(obj: Any) -> Any:
    if isinstance(obj, dict):
        for key in list(obj.keys()):
            obj[key] = _normalize_collections(obj[key])
        for key in list(obj.keys()):
            child_key = _COLLECTION_CHILD_MAP.get(key)
            if not child_key:
                continue
            rename_to = _COLLECTION_RENAME.get(key, key)
            value = obj[key]
            if isinstance(value, dict) and child_key in value:
                payload = value[child_key]
            else:
                payload = value
            if payload is None:
                seq: List[Any] = []
            elif isinstance(payload, list):
                seq = payload
            else:
                seq = [payload]
            obj[rename_to] = [_normalize_collections(item) for item in seq]
            if rename_to != key:
                del obj[key]
            else:
                obj[key] = obj[rename_to]
        return obj
    if isinstance(obj, list):
        return [_normalize_collections(v) for v in obj]
    return obj


def _normalize_telecom_entry(entry: Dict[str, Any]) -> Dict[str, Any]:
    out = dict(entry)
    if "value" in out and "telecom" not in out:
        out["telecom"] = out.pop("value")
    if "usageType" in out and "usageCode" not in out:
        usage = str(out.pop("usageType"))
        out["usageCode"] = usage
    if "usageCode" in out and "usageName" not in out:
        code = str(out["usageCode"]).upper()
        usage_names = {
            "MC": "mobile contact",
            "CP": "cell phone",
            "H": "home",
            "HP": "home phone",
            "WP": "work place",
            "EC": "emergency contact",
        }
        if code in usage_names:
            out["usageName"] = usage_names[code]
    return out


def _normalize_telecoms_recursive(obj: Any) -> Any:
    if isinstance(obj, dict):
        for key, value in list(obj.items()):
            if key == "telecoms" and isinstance(value, list):
                obj[key] = [
                    _normalize_telecom_entry(v) if isinstance(v, dict) else v
                    for v in value
                ]
            else:
                obj[key] = _normalize_telecoms_recursive(value)
        return obj
    if isinstance(obj, list):
        return [_normalize_telecoms_recursive(v) for v in obj]
    return obj


def _ensure_list(value: Any) -> List[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [value]


def _clean_text(value: Any) -> Optional[str]:
    if value is None:
        return None
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return str(value)
    if isinstance(value, str):
        stripped = value.strip()
        return stripped or None
    if isinstance(value, dict):
        for key in ("value", "text", "content", "displayName", "name", "line"):
            if key in value:
                resolved = _clean_text(value.get(key))
                if resolved:
                    return resolved
        return None
    if isinstance(value, list):
        for entry in value:
            resolved = _clean_text(entry)
            if resolved:
                return resolved
        return None
    try:
        text = str(value).strip()
        return text or None
    except Exception:
        return None


def _collect_strings(value: Any, keys: Tuple[str, ...]) -> List[str]:
    queue: List[Any] = list(_ensure_list(value))
    out: List[str] = []
    seen: set[str] = set()
    while queue:
        current = queue.pop(0)
        if current is None:
            continue
        if isinstance(current, dict):
            matched = False
            for key in keys:
                if key in current:
                    queue.append(current[key])
                    matched = True
            if matched:
                continue
            text = _clean_text(current)
            if text and text not in seen:
                out.append(text)
                seen.add(text)
            continue
        if isinstance(current, list):
            queue.extend(current)
            continue
        text = _clean_text(current)
        if text and text not in seen:
            out.append(text)
            seen.add(text)
    return out


def _to_iso_datetime(value: Any) -> Optional[str]:
    text = _clean_text(value)
    if not text:
        return None
    iso = _fileman_to_iso(text)
    if iso:
        return iso
    try:
        candidate = text.replace("Z", "+00:00")
        if "T" in candidate or "-" in candidate:
            stamp = datetime.fromisoformat(candidate)
            stamp_utc = stamp.astimezone(timezone.utc)
            return stamp_utc.replace(tzinfo=timezone.utc).isoformat().replace("+00:00", "Z")
    except Exception:
        pass
    digits = "".join(ch for ch in text if ch.isdigit())
    try:
        if len(digits) >= 14:
            year = int(digits[0:4])
            month = int(digits[4:6])
            day = int(digits[6:8])
            hour = int(digits[8:10])
            minute = int(digits[10:12])
            second = int(digits[12:14])
            stamp = datetime(year, month, day, hour, minute, second, tzinfo=timezone.utc)
            return stamp.isoformat().replace("+00:00", "Z")
        if len(digits) >= 12:
            year = int(digits[0:4])
            month = int(digits[4:6])
            day = int(digits[6:8])
            hour = int(digits[8:10])
            minute = int(digits[10:12])
            stamp = datetime(year, month, day, hour, minute, tzinfo=timezone.utc)
            return stamp.isoformat().replace("+00:00", "Z")
        if len(digits) >= 8:
            year = int(digits[0:4])
            month = int(digits[4:6])
            day = int(digits[6:8])
            stamp = datetime(year, month, day, tzinfo=timezone.utc)
            return stamp.isoformat().replace("+00:00", "Z")
    except Exception:
        return None
    return None


def _normalize_order_clinicians(value: Any) -> List[Dict[str, Any]]:
    entries: List[Dict[str, Any]] = []
    for raw in _ensure_list(value):
        if raw is None:
            continue
        source = raw if isinstance(raw, dict) else {"name": raw}
        record: Dict[str, Any] = {}
        name = None
        for key in ("name", "displayName", "providerName", "clinicianName", "value"):
            name = _clean_text(source.get(key))
            if name:
                break
        if name:
            record["name"] = name
        role = _clean_text(source.get("role") or source.get("roleName") or source.get("type"))
        if role:
            record["role"] = role
        uid = _clean_text(source.get("uid") or source.get("clinicianUid") or source.get("providerUid"))
        if uid:
            record["uid"] = uid
        signed = _clean_text(source.get("signedDateTime") or source.get("signed") or source.get("signatureDateTime"))
        if signed:
            record["signedDateTime"] = signed
            iso = _to_iso_datetime(signed)
            if iso:
                record["signedDateTimeIso"] = iso
        if record:
            entries.append(record)
    return entries


def _normalize_order_results(value: Any) -> List[Dict[str, Any]]:
    entries: List[Dict[str, Any]] = []
    for raw in _ensure_list(value):
        if raw is None:
            continue
        if isinstance(raw, dict):
            record: Dict[str, Any] = {}
            for target, keys in (
                ("uid", ("uid", "resultUid")),
                ("orderUid", ("orderUid",)),
                ("localId", ("localId", "id")),
                ("name", ("name", "displayName")),
                ("typeName", ("typeName", "type")),
                ("statusName", ("statusName", "status")),
                ("statusCode", ("statusCode",)),
            ):
                for key in keys:
                    text = _clean_text(raw.get(key))
                    if text:
                        record[target] = text
                        break
            value_text = _clean_text(raw.get("value") or raw.get("result"))
            if value_text:
                record.setdefault("value", value_text)
            dt_text = _clean_text(raw.get("dateTime") or raw.get("date") or raw.get("observed") or raw.get("resulted"))
            if dt_text:
                record["dateTime"] = dt_text
                iso = _to_iso_datetime(dt_text)
                if iso:
                    record["dateTimeIso"] = iso
            if record:
                entries.append(record)
        else:
            text = _clean_text(raw)
            if text:
                entries.append({"value": text})
    return entries


def _extract_order_id(order_uid: Optional[str], local_id: Optional[str]) -> Optional[str]:
    if local_id:
        return local_id
    if not order_uid:
        return None
    tail = order_uid.rsplit(":", 1)[-1]
    tail = tail.strip()
    if tail:
        return tail
    return None


def _normalize_order_item(item: Dict[str, Any]) -> Dict[str, Any]:
    data = dict(item)
    normalized: Dict[str, Any] = dict(data)
    normalized["domain"] = "order"

    uid = _clean_text(data.get("uid"))
    if uid:
        normalized["uid"] = uid
    order_uid = _clean_text(data.get("orderUid")) or uid
    if order_uid:
        normalized["orderUid"] = order_uid
    local_id = _clean_text(data.get("localId") or data.get("id"))
    if local_id:
        normalized["localId"] = local_id
    order_id = _extract_order_id(order_uid, local_id)
    if order_id:
        normalized["orderId"] = order_id

    name = None
    for key in ("name", "orderName", "displayName", "oiName"):
        name = _clean_text(data.get(key))
        if name:
            break
    if name:
        normalized["name"] = name
        normalized.setdefault("orderName", name)

    field_map: Tuple[Tuple[str, Tuple[str, ...]], ...] = (
        ("typeName", ("typeName", "type")),
        ("displayGroup", ("displayGroup", "group", "groupName")),
        ("service", ("service", "serviceName", "specialty")),
        ("category", ("category",)),
        ("statusName", ("statusName", "status")),
        ("statusCode", ("statusCode", "statusId")),
        ("statusVuid", ("statusVuid",)),
        ("providerName", ("providerName", "provider")),
        ("providerUid", ("providerUid", "providerId")),
        ("facilityName", ("facilityName", "facility")),
        ("facilityCode", ("facilityCode", "facilityId")),
        ("locationName", ("locationName", "location", "locationDisplayName")),
        ("locationUid", ("locationUid", "locationId")),
        ("scheduleName", ("scheduleName", "schedule")),
        ("urgency", ("urgency", "urgencyName")),
        ("oiName", ("oiName", "orderableItemName")),
        ("oiCode", ("oiCode", "orderableItemCode")),
        ("oiPackageRef", ("oiPackageRef", "orderableItemPackageRef")),
        ("predecessor", ("predecessor",)),
        ("successor", ("successor",)),
        ("enteredByName", ("enteredByName", "enteredBy")),
        ("enteredByUid", ("enteredByUid", "enteredById")),
        ("signerName", ("signerName", "signedByName")),
        ("signerUid", ("signerUid", "signedByUid")),
    )
    for target, keys in field_map:
        if target in normalized:
            continue
        for key in keys:
            text = _clean_text(data.get(key))
            if text:
                normalized[target] = text
                break

    if "orderName" not in normalized and normalized.get("oiName"):
        normalized["orderName"] = normalized["oiName"]
        if "name" not in normalized:
            normalized["name"] = normalized["oiName"]

    provider_block = data.get("provider")
    if "providerName" not in normalized:
        provider_name = _clean_text(provider_block)
        if provider_name:
            normalized["providerName"] = provider_name
    if "providerUid" not in normalized and isinstance(provider_block, dict):
        provider_uid = _clean_text(provider_block.get("uid") or provider_block.get("providerUid"))
        if provider_uid:
            normalized["providerUid"] = provider_uid

    facility_block = data.get("facility")
    if "facilityName" not in normalized:
        facility_name = _clean_text(facility_block)
        if facility_name:
            normalized["facilityName"] = facility_name
    if "facilityCode" not in normalized and isinstance(facility_block, dict):
        code = _clean_text(facility_block.get("code") or facility_block.get("facilityCode"))
        if code:
            normalized["facilityCode"] = code

    location_block = data.get("location")
    if "locationName" not in normalized:
        location_name = _clean_text(location_block)
        if location_name:
            normalized["locationName"] = location_name
    if "locationUid" not in normalized and isinstance(location_block, dict):
        location_uid = _clean_text(location_block.get("uid") or location_block.get("locationUid"))
        if location_uid:
            normalized["locationUid"] = location_uid

    date_fields: Tuple[Tuple[str, Tuple[str, ...]], ...] = (
        ("entered", ("entered", "dateTime", "ordered")),
        ("start", ("start", "startDate", "startDateTime")),
        ("stop", ("stop", "stopDate", "stopDateTime")),
        ("signedDateTime", ("signedDateTime", "signed", "signDateTime", "signatureDateTime")),
        ("released", ("released", "releaseDateTime")),
    )
    for target, keys in date_fields:
        if target in normalized:
            continue
        for key in keys:
            raw_val = data.get(key)
            text = _clean_text(raw_val)
            if text:
                normalized[target] = text
                iso = _to_iso_datetime(text)
                if iso:
                    normalized[f"{target}Iso"] = iso
                break

    admin_times = _clean_text(data.get("adminTimes") or data.get("adminTime"))
    if admin_times:
        normalized["adminTimes"] = admin_times

    instructions = _collect_strings(data.get("instructions") or data.get("instruction"), ("instructions", "instruction", "text", "line", "value"))
    if instructions:
        normalized["instructions"] = instructions
        normalized["instructionsText"] = "\n".join(instructions)

    content_lines = _collect_strings(data.get("content"), ("content", "text", "line", "value"))
    if content_lines:
        normalized["content"] = content_lines
        normalized["contentText"] = "\n".join(content_lines)
        normalized.setdefault("contentPreview", content_lines[0])

    results = _normalize_order_results(data.get("results"))
    if results:
        normalized["results"] = results

    clinicians_source = data.get("clinicians") or data.get("providers")
    clinicians = _normalize_order_clinicians(clinicians_source)
    if clinicians:
        normalized["clinicians"] = clinicians
        if "providerName" not in normalized:
            provider_pick = next((c for c in clinicians if (c.get("role") or "").upper() in {"A", "P", "PROVIDER"}), None)
            if not provider_pick and clinicians:
                provider_pick = clinicians[0]
            if provider_pick and provider_pick.get("name"):
                normalized["providerName"] = provider_pick["name"]

    status_name = normalized.get("statusName")
    if status_name and "status" not in normalized:
        normalized["status"] = status_name

    return normalized


def _normalize_patient_item(item: Dict[str, Any]) -> Dict[str, Any]:
    data = dict(item)
    if "bid" in data and "briefId" not in data:
        data["briefId"] = data.pop("bid")
    if "id" in data and "localId" not in data:
        data["localId"] = data.pop("id")
    if isinstance(data.get("localId"), str) and data["localId"].isdigit():
        try:
            data["localId"] = int(data["localId"])
        except Exception:
            pass
    dob_val = None
    if "dob" in data:
        dob_val = data.pop("dob")
    if "dateOfBirth" not in data and dob_val is not None:
        data["dateOfBirth"] = dob_val
    if "gender" in data and "genderName" not in data:
        gender_val = data.pop("gender")
        if isinstance(gender_val, dict):
            gender_code = gender_val.get("code") or gender_val.get("value")
            gender_text = gender_val.get("name") or gender_val.get("value")
        else:
            gender_code = str(gender_val)
            gender_text = str(gender_val)
        if gender_code:
            upper_code = str(gender_code).upper()
            code_map = {
                "M": ("urn:va:pat-gender:M", "Male"),
                "F": ("urn:va:pat-gender:F", "Female"),
                "U": ("urn:va:pat-gender:U", "Unknown"),
                "O": ("urn:va:pat-gender:O", "Other"),
            }
            match = code_map.get(upper_code)
            if match:
                data.setdefault("genderCode", match[0])
                data["genderName"] = match[1]
            elif gender_text:
                data["genderName"] = gender_text
        elif gender_text:
            data["genderName"] = gender_text
    if "telecomList" in data and "telecoms" not in data:
        holder = data.pop("telecomList")
        if isinstance(holder, dict) and "telecom" in holder:
            tele = holder["telecom"]
        else:
            tele = holder
        if tele is None:
            data["telecoms"] = []
        elif isinstance(tele, list):
            data["telecoms"] = tele
        else:
            data["telecoms"] = [tele]
    if "telecoms" in data:
        data["telecoms"] = [
            _normalize_telecom_entry(t) for t in data["telecoms"] if isinstance(t, dict)
        ]
    if "veteran" in data and not isinstance(data["veteran"], dict):
        data["veteran"] = {
            "isVet": 1 if _coerce_boolish(data.pop("veteran")) else 0
        }
    data = _normalize_telecoms_recursive(data)
    return data


def _normalize_domain_item(domain: Optional[str], item: Dict[str, Any]) -> Dict[str, Any]:
    base = _strip_xml_attrs(item)
    base = _normalize_collections(base)
    if domain == "patient" and isinstance(base, dict):
        return _normalize_patient_item(base)
    if domain == "order" and isinstance(base, dict):
        return _normalize_order_item(base)
    if isinstance(base, dict):
        if "telecomList" in base and "telecoms" not in base:
            holder = base.pop("telecomList")
            if isinstance(holder, dict) and "telecom" in holder:
                tele = holder["telecom"]
            else:
                tele = holder
            if tele is None:
                base["telecoms"] = []
            elif isinstance(tele, list):
                base["telecoms"] = tele
            else:
                base["telecoms"] = [tele]
        base = _normalize_telecoms_recursive(base)
    else:
        base = _normalize_telecoms_recursive(base)
    return base


def _extract_payload_items(payload: Any) -> List[Dict[str, Any]]:
    if isinstance(payload, dict):
        data_block = payload.get("data")
        if isinstance(data_block, dict) and isinstance(data_block.get("items"), list):
            return [entry for entry in data_block["items"] if isinstance(entry, dict)]
        items = payload.get("items")
        if isinstance(items, list):
            return [entry for entry in items if isinstance(entry, dict)]
    if isinstance(payload, list):
        return [entry for entry in payload if isinstance(entry, dict)]
    return []


def _ensure_xml_lib():
    if xmltodict is None:
        raise GatewayError("xmltodict is required for socket gateway XML parsing. Add 'xmltodict' to requirements.")


def _normalize_vpr_xml_to_items(xml_text: str, domain: Optional[str] = None) -> Dict[str, Any]:
    _ensure_xml_lib()
    text = (xml_text or "").strip()
    if not text:
        return {"items": []}
    lower = text.lower()
    if "<results" in lower:
        try:
            parsed = parse_vpr_results_xml(text, domain=domain)
            items = parsed.get("items") if isinstance(parsed, dict) else []
            normalized_items: List[Dict[str, Any]] = []
            if isinstance(items, list):
                for entry in items:
                    if isinstance(entry, dict):
                        normalized_items.append(_normalize_domain_item(domain, entry))
                    else:
                        normalized_items.append({"value": entry})
            result: Dict[str, Any] = {"items": normalized_items}
            if isinstance(parsed, dict) and parsed.get("meta"):
                result["meta"] = parsed["meta"]
            return result
        except Exception:
            pass
    try:
        parsed = xmltodict.parse(text)  # type: ignore[attr-defined]
    except Exception as exc:
        raise GatewayError(f"Failed to parse VPR XML: {exc}")
    data_section: Optional[Any] = None
    if isinstance(parsed, dict):
        data_section = parsed.get("data") or parsed.get("Data")
    if not isinstance(data_section, dict):
        if isinstance(parsed, list):
            items_raw = parsed
        else:
            items_raw = [parsed]
    else:
        wrapper = data_section.get("items") or data_section.get("Items")
        if isinstance(wrapper, dict):
            items_candidate = wrapper.get("item") or wrapper.get("Item")
        else:
            items_candidate = wrapper
        if items_candidate is None:
            items_raw = []
        elif isinstance(items_candidate, list):
            items_raw = items_candidate
        else:
            items_raw = [items_candidate]
    normalized_items: List[Dict[str, Any]] = []
    for entry in items_raw:
        if isinstance(entry, dict):
            normalized_items.append(_normalize_domain_item(domain, entry))
        else:
            normalized_items.append({"value": entry})
    return {"items": normalized_items}


# ---------------------------------------------------------------------------
# RPC client + socket utilities
# ---------------------------------------------------------------------------


class _VistaRPCLogger:
    def info(self, tag: str, message: str) -> None:
        try:
            print(f"[{tag}] {message}")
        except Exception:
            pass

    def error(self, tag: str, message: str) -> None:
        try:
            print(f"[{tag}] ERROR: {message}")
        except Exception:
            pass


def _parse_cipher_blob(blob: str) -> List[str]:
    text = (blob or "").strip()
    if not text:
        return []
    if text.startswith("["):
        try:
            loaded = json.loads(text)
            routes: List[str] = []
            for entry in loaded or []:
                value = str(entry).strip()
                if value:
                    routes.append(value)
            return routes
        except Exception:
            pass
    rows: List[str] = []
    for line in text.splitlines():
        stripped = line.strip()
        if stripped:
            rows.append(stripped)
    return rows


def _load_cipher_from_env() -> List[str]:
    path = os.getenv("VISTARPC_CIPHER_FILE")
    if path and os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as handle:
                rows = _parse_cipher_blob(handle.read())
            if rows:
                return rows
        except Exception as exc:
            raise GatewayError(f"failed to read cipher file: {exc}")
    blob = os.getenv("VISTARPC_CIPHER")
    rows = _parse_cipher_blob(blob or "")
    if rows:
        return rows
    raise GatewayError("VISTARPC_CIPHER not configured")


class _VistaRPCClient:
    CIPHER_TABLE: Optional[List[str]] = None

    def __init__(
        self,
        *,
        host: str,
        port: int,
        access: str,
        verify: str,
        context: str,
        logger: Optional[_VistaRPCLogger] = None,
    ) -> None:
        self.host = host
        self.port = int(port)
        self.access = access
        self.verify = verify
        self.context = context
        self.logger = logger or _VistaRPCLogger()
        self.sock: Optional[socket.socket] = None
        self._lock = threading.RLock()
        self._terminator = chr(4)
        self._last_used = time.monotonic()
        self._heartbeat_interval = 0
        self._heartbeat_stop = threading.Event()
        self._heartbeat_thread: Optional[threading.Thread] = None

    @classmethod
    def _get_cipher(cls) -> List[str]:
        if cls.CIPHER_TABLE is None:
            cls.CIPHER_TABLE = _load_cipher_from_env()
        return cls.CIPHER_TABLE

    def _encrypt(self, value: str) -> bytes:
        import random

        table = self._get_cipher()
        left = random.randint(0, len(table) - 1)
        right = random.randint(0, len(table) - 1)
        while right == left or right == 0:
            right = random.randint(0, len(table) - 1)
        table_left = table[left]
        table_right = table[right]
        encrypted = chr(left + 32)
        for char in value:
            idx = table_left.find(char)
            if idx == -1 or idx >= len(table_right):
                encrypted += char
            else:
                encrypted += table_right[idx]
        encrypted += chr(right + 32)
        return encrypted.encode("utf-8")

    @staticmethod
    def _encode_param(value: Any) -> str:
        if isinstance(value, dict):
            return json.dumps(value)
        return str(value)

    def _build_frame(self, name: str, params: List[Any], command: bool = False) -> str:
        proto = "[XWB]1130"
        command_flag = "4" if command else ("2" + chr(1) + "1")
        name_spec = chr(len(name)) + name
        if not params:
            param_spec = "54f"
        else:
            param_parts = ["5"]
            for value in params:
                encoded = self._encode_param(value)
                raw = encoded.encode("utf-8")
                param_parts.append("0" + str(len(raw)).zfill(3) + encoded)
            param_parts.append("f")
            param_spec = "".join(param_parts)
        return proto + command_flag + name_spec + param_spec + self._terminator

    def _read_frame(self) -> str:
        chunks: List[str] = []
        while True:
            if not self.sock:
                raise GatewayError("socket not connected")
            data = self.sock.recv(512)
            if not data:
                raise GatewayError("socket closed")
            chunk = data.decode("utf-8", errors="replace")
            if not chunks and chunk.startswith("\x00"):
                chunk = chunk.lstrip("\x00")
            if chunk.endswith(self._terminator):
                chunks.append(chunk[:-1])
                break
            chunks.append(chunk)
        message = "".join(chunks)
        self._last_used = time.monotonic()
        return message

    def connect(self) -> None:
        with self._lock:
            if self.sock:
                try:
                    self.sock.close()
                except Exception:
                    pass
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            try:
                self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)
            except Exception:
                pass
            self.sock.connect((self.host, self.port))
            time.sleep(0.25)
            self.logger.info("VistaRPC", f"connected to {self.host}:{self.port}")
            self._handshake()
            self._last_used = time.monotonic()

    def _handshake(self) -> None:
        if not self.sock:
            raise GatewayError("socket not connected")
        params = [socket.gethostbyname(socket.gethostname()), "0", "FMQL"]
        self.sock.sendall(self._build_frame("TCPConnect", params, True).encode("utf-8"))
        response = self._read_frame()
        if "accept" not in response.lower():
            raise GatewayError(f"TCPConnect failed: {response}")
        self.sock.sendall(self._build_frame("XUS SIGNON SETUP", [], False).encode("utf-8"))
        _ = self._read_frame()
        pair = f"{self.access};{self.verify}"
        secret = self._encrypt(pair).decode("utf-8")
        self.sock.sendall(self._build_frame("XUS AV CODE", [secret], False).encode("utf-8"))
        reply = self._read_frame()
        if "Not a valid" in reply:
            self.sock.sendall(self._build_frame("XUS AV CODE", [pair], False).encode("utf-8"))
            reply = self._read_frame()
            if "Not a valid" in reply:
                raise GatewayError("invalid ACCESS/VERIFY pair")
        if self.context:
            ok, message = self._create_context(self.context)
            if not ok:
                raise GatewayError(f"context failed for '{self.context}': {message}")
            self.logger.info("VistaRPC", f"context set to {self.context}")

    def _create_context(self, target: str) -> tuple[bool, str]:
        if not target:
            return False, "context name is empty"
        if not self.sock:
            raise GatewayError("socket not connected")
        self.sock.sendall(self._build_frame("XWB CREATE CONTEXT", [target], False).encode("utf-8"))
        reply_plain = self._read_frame()
        if self._is_context_success(reply_plain):
            self.context = target
            return True, reply_plain
        enc_target = self._encrypt(target).decode("utf-8")
        self.sock.sendall(self._build_frame("XWB CREATE CONTEXT", [enc_target], False).encode("utf-8"))
        reply_enc = self._read_frame()
        if self._is_context_success(reply_enc):
            self.context = target
            return True, reply_enc
        return False, reply_enc

    @staticmethod
    def _is_context_success(reply: str) -> bool:
        if not reply:
            return False
        response = reply.strip()
        if response.startswith("-1^"):
            return False
        lowered = response.lower()
        if "application context has not been created" in lowered:
            return False
        if "does not exist" in lowered:
            return False
        return response == "1"

    def close(self) -> None:
        self.stop_heartbeat()
        with self._lock:
            if not self.sock:
                return
            try:
                self.sock.sendall("#BYE#".encode("utf-8"))
            except Exception:
                pass
            try:
                self.sock.close()
            finally:
                self.sock = None

    def _set_context_locked(self, context: str) -> None:
        if not self.sock:
            raise GatewayError("socket not connected")
        if context == self.context:
            return
        ok, message = self._create_context(context)
        if not ok:
            raise GatewayError(f"context switch failed: {message}")
        self.logger.info("VistaRPC", f"context set to {context}")

    def call(self, rpc: str, params: List[Any]) -> str:
        with self._lock:
            return self._invoke_locked(rpc, params)

    def _invoke_locked(self, rpc: str, params: List[Any]) -> str:
        if not self.sock:
            raise GatewayError("socket not connected")
        frame = self._build_frame(rpc, params, False)
        self.sock.sendall(frame.encode("utf-8"))
        return self._read_frame()

    def call_in_context(self, context: str, rpc: str, params: List[Any]) -> str:
        with self._lock:
            if context != self.context:
                self._set_context_locked(context)
            result = self._invoke_locked(rpc, params)
            if _normalize_context_error(result):
                desired = context
                self.logger.info("VistaRPC", "context dropped; reconnecting")
                self.context = desired
                self.connect()
                self._set_context_locked(desired)
                result = self._invoke_locked(rpc, params)
                if _normalize_context_error(result):
                    raise GatewayError("context re-establish failed")
            return result

    def ensure_connected(self, max_idle_seconds: int = 300) -> None:
        if max_idle_seconds <= 0:
            return
        if not self.sock:
            self.connect()
            return
        elapsed = time.monotonic() - self._last_used
        if elapsed < max_idle_seconds:
            return
        try:
            self.call_in_context(self.context or "", "XUS GET USER INFO", [])
        except Exception:
            self.logger.info("VistaRPC", "ensure_connected ping failed; reconnecting")
            self.connect()

    def start_heartbeat(self, interval: int) -> None:
        if interval <= 0:
            self.stop_heartbeat()
            return
        self._heartbeat_interval = int(interval)
        if self._heartbeat_thread and self._heartbeat_thread.is_alive():
            return
        self._heartbeat_stop.clear()

        def _loop() -> None:
            while not self._heartbeat_stop.wait(self._heartbeat_interval):
                try:
                    if not self.sock:
                        self.connect()
                        continue
                    since_last = time.monotonic() - self._last_used
                    if since_last < (self._heartbeat_interval * 1.5):
                        continue
                    self.call_in_context(self.context or "", "XUS GET USER INFO", [])
                except Exception as exc:
                    try:
                        self.logger.info("VistaRPC", f"heartbeat detected issue: {exc}")
                    except Exception:
                        pass
                    try:
                        self.connect()
                    except Exception:
                        continue

        self._heartbeat_thread = threading.Thread(
            target=_loop,
            name="VistaRPCHeartbeat",
            daemon=True,
        )
        self._heartbeat_thread.start()

    def stop_heartbeat(self) -> None:
        self._heartbeat_stop.set()
        thread = self._heartbeat_thread
        self._heartbeat_thread = None
        if thread and thread.is_alive():
            try:
                thread.join(timeout=2.0)
            except Exception:
                pass


# ---------------------------------------------------------------------------
# Legacy OR RPC helpers reused for lab/detail/text flows
# ---------------------------------------------------------------------------


def _fileman_to_iso(value: Any) -> Optional[str]:
    try:
        text = str(value or "").strip()
        if not text:
            return None
        date_part, time_part = (text.split(".", 1) + [""])[:2]
        if len(date_part) != 7 or not date_part.isdigit():
            return None
        year = int(date_part[:3]) + 1700
        month = int(date_part[3:5])
        day = int(date_part[5:7])
        time_digits = "".join(ch for ch in time_part if ch.isdigit())
        hour = int(time_digits[0:2]) if len(time_digits) >= 2 else 0
        minute = int(time_digits[2:4]) if len(time_digits) >= 4 else 0
        second = int(time_digits[4:6]) if len(time_digits) >= 6 else 0
        stamp = datetime(year, month, day, hour, minute, second, tzinfo=timezone.utc)
        return stamp.isoformat().replace("+00:00", "Z")
    except Exception:
        return None


def _iso_to_fileman(value: Any) -> Optional[str]:
    try:
        text = str(value or "").strip()
        if not text:
            return None
        if text.isdigit() and len(text) == 7:
            return text
        if "T" in text or "-" in text:
            stamp = datetime.fromisoformat(text.replace("Z", "+00:00"))
            date_part = f"{stamp.year - 1700:03d}{stamp.month:02d}{stamp.day:02d}"
            if stamp.hour or stamp.minute or stamp.second:
                return f"{date_part}.{stamp.hour:02d}{stamp.minute:02d}{stamp.second:02d}"
            return date_part
        digits = "".join(ch for ch in text if ch.isdigit())
        if len(digits) >= 8:
            year = int(digits[0:4])
            month = int(digits[4:6])
            day = int(digits[6:8])
            date_part = f"{year - 1700:03d}{month:02d}{day:02d}"
            if len(digits) >= 12:
                hour = int(digits[8:10])
                minute = int(digits[10:12])
                if len(digits) >= 14:
                    second = int(digits[12:14])
                    return f"{date_part}.{hour:02d}{minute:02d}{second:02d}"
                return f"{date_part}.{hour:02d}{minute:02d}"
            return date_part
        return None
    except Exception:
        return None


def _normalize_context_error(text: str) -> bool:
    message = str(text or "").strip()
    if not message:
        return False
    message_stripped = message.lstrip("0123456789^~ ")
    lowered = message_stripped.lower()
    if not lowered:
        return False
    if "application context has not been created" in lowered:
        return True
    if "context has not been created" in lowered:
        return True
    if "the context" in lowered and "does not exist" in lowered:
        return True
    return False


def _normalize_doc_id(value: Any) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    lowered = text.lower()
    if lowered.startswith("urn:va:document:"):
        text = text.split(":", 2)[-1]
    text = text.strip()
    for sep in (":", ";"):
        if sep in text:
            tail = text.rsplit(sep, 1)[-1].strip()
            if tail:
                text = tail
    if "-" in text:
        tail = text.rsplit("-", 1)[-1].strip()
        if tail.isdigit():
            text = tail
    return text.strip()


# ---------------------------------------------------------------------------
# VistaDualSocketGateway implementation
# ---------------------------------------------------------------------------


_SOCKET_IDLE_MAX_SECONDS = max(30, int(os.getenv("VISTA_SOCKET_IDLE_SECONDS", "300") or 300))
_DOMAIN_CACHE_TTL = max(5, int(os.getenv("VISTA_VPR_CACHE_TTL", "120") or 120))
_DOMAIN_CACHE_SIZE = max(4, int(os.getenv("VISTA_VPR_CACHE_SIZE", "12") or 12))
_DEFAULT_VPR_CONTEXT = os.getenv("VISTA_VPR_CONTEXT", "JLV WEB SERVICES")
_HEARTBEAT_INTERVAL = int(os.getenv("VISTA_HEARTBEAT_INTERVAL", "60") or 60)


class VistaDualSocketGateway(DataGateway):
    """Dual-socket gateway using CPRS context for RPCs and JLV context for VPR XML."""

    def __init__(
        self,
        *,
        host: str,
        port: int,
        access: str,
        verify: str,
        default_context: Optional[str] = None,
        vpr_context: Optional[str] = None,
        session_id: Optional[str] = None,
        session_order: Optional[int] = None,
    ) -> None:
        self.host = host
        self.port = int(port)
        self.access = access
        self.verify = verify
        self.default_context = default_context or os.getenv("VISTA_DEFAULT_CONTEXT") or "OR CPRS GUI CHART"
        self.vpr_context = vpr_context or _DEFAULT_VPR_CONTEXT
        self.session_id = session_id or ""
        self.session_order = session_order
        self.logger = _VistaRPCLogger()
        self._or_client = self._build_client(self.default_context)
        self._vpr_client = self._build_client(self.vpr_context)
        self._connected = False
        self._workspace_lock = threading.RLock()
        self._site_key = f"{self.host}:{self.port}"
        self._domain_cache: "OrderedDict[Tuple[str, str, str, str], Tuple[float, Dict[str, Any]]]" = OrderedDict()
        self._cache_lock = threading.RLock()
        self._cacheable_domains = {
            "patient",
            "med",
            "lab",
            "vital",
            "document",
            "image",
            "procedure",
            "visit",
            "problem",
            "allergy",
        }

    def _build_client(self, context: str) -> _VistaRPCClient:
        client = _VistaRPCClient(
            host=self.host,
            port=self.port,
            access=self.access,
            verify=self.verify,
            context=context,
            logger=self.logger,
        )
        if _HEARTBEAT_INTERVAL > 0:
            client.start_heartbeat(_HEARTBEAT_INTERVAL)
        return client

    # ------------------------------------------------------------------
    # Lifecycle & caching helpers
    # ------------------------------------------------------------------

    def _clear_caches(self) -> None:
        with self._cache_lock:
            self._domain_cache.clear()

    def clear_patient_cache(self, dfn: Optional[str] = None) -> None:
        with self._cache_lock:
            if dfn is None:
                self._domain_cache.clear()
                return
            dfn_str = str(dfn)
            remove = [key for key in self._domain_cache if key[1] == dfn_str]
            for key in remove:
                self._domain_cache.pop(key, None)

    def _domain_cache_key(self, dfn: str, domain: str, params: Optional[Dict[str, Any]]) -> Tuple[str, str, str, str]:
        signature = ""
        if params:
            try:
                signature = json.dumps(params, sort_keys=True, separators=(",", ":"))
            except Exception:
                try:
                    signature = str(sorted(params.items()))
                except Exception:
                    signature = str(params)
        return (self._site_key, str(dfn), domain, signature)

    def _domain_cache_get(self, key: Tuple[str, str, str, str]) -> Optional[Dict[str, Any]]:
        now = time.monotonic()
        with self._cache_lock:
            entry = self._domain_cache.get(key)
            if not entry:
                return None
            ts, payload = entry
            if (now - ts) > _DOMAIN_CACHE_TTL:
                self._domain_cache.pop(key, None)
                return None
            self._domain_cache.move_to_end(key)
            return json.loads(json.dumps(payload))  # deep copy via json

    def _domain_cache_store(self, key: Tuple[str, str, str, str], payload: Dict[str, Any]) -> None:
        with self._cache_lock:
            self._domain_cache[key] = (time.monotonic(), payload)
            self._domain_cache.move_to_end(key)
            while len(self._domain_cache) > _DOMAIN_CACHE_SIZE:
                self._domain_cache.popitem(last=False)

    # ------------------------------------------------------------------
    # Connection management
    # ------------------------------------------------------------------

    def connect(self) -> None:
        if self._connected:
            return
        with self._workspace_lock:
            if self._connected:
                return
            self._or_client.connect()
            self._vpr_client.connect()
            self._connected = True
        self._or_client.ensure_connected(max_idle_seconds=_SOCKET_IDLE_MAX_SECONDS)
        self._vpr_client.ensure_connected(max_idle_seconds=_SOCKET_IDLE_MAX_SECONDS)

    def close(self) -> None:
        with self._workspace_lock:
            try:
                self._or_client.close()
            finally:
                try:
                    self._vpr_client.close()
                finally:
                    self._connected = False
        self._clear_caches()

    # ------------------------------------------------------------------
    # RPC helpers
    # ------------------------------------------------------------------

    def call_rpc(
        self,
        *,
        context: str,
        rpc: str,
        parameters: Optional[List[Dict[str, Any]]] = None,
        json_result: bool = False,
        timeout: int = 60,
    ) -> Any:  # type: ignore[override]
        self.connect()
        client = self._vpr_client if context == self.vpr_context else self._or_client
        params: List[Any] = []
        for entry in parameters or []:
            if "string" in entry:
                params.append(str(entry.get("string") or ""))
            elif "literal" in entry:
                params.append(str(entry.get("literal") or ""))
            elif "multiline" in entry:
                params.append(entry.get("multiline") or "")
            else:
                params.append(entry)
        raw = client.call_in_context(context, rpc, params)
        if json_result:
            try:
                return json.loads(raw)
            except Exception:
                return {"raw": raw}
        return raw

    # ------------------------------------------------------------------
    # VPR helpers
    # ------------------------------------------------------------------

    def _wrap_domain_response(
        self,
        domain: str,
        dfn: str,
        parsed: Dict[str, Any],
        *,
        raw_text: Optional[str] = None,
    ) -> Dict[str, Any]:
        try:
            items = []
            if isinstance(parsed, dict):
                items = parsed.get("items") or []
                if not isinstance(items, list):
                    items = []
                else:
                    normalized_items: List[Any] = []
                    for it in items:
                        if isinstance(it, dict):
                            normalized_items.append(_normalize_domain_item(domain, it))
                        else:
                            normalized_items.append(it)
                    items = normalized_items
            meta = parsed.get("meta") if isinstance(parsed, dict) else None
            if not isinstance(meta, dict):
                meta = {}
            total = meta.get("total")
            if not isinstance(total, int):
                try:
                    total = int(str(total))
                except Exception:
                    total = len(items)
            meta["total"] = total
            if meta.get("domain") is None and domain:
                meta["domain"] = domain
            if "dfn" not in meta:
                meta["dfn"] = str(dfn)
            data_block: Dict[str, Any] = {
                "totalItems": total,
                "items": items,
            }
            for key in ("version", "timeZone", "updated"):
                if meta.get(key) and key not in data_block:
                    data_block[key] = meta.get(key)
            response_body: Dict[str, Any] = {
                "items": items,
                "meta": meta,
                "data": data_block,
            }
            if raw_text:
                response_body["raw"] = raw_text
            return response_body
        except Exception:
            return parsed

    def _invoke_vpr(self, params: List[Any]) -> str:
        return self._vpr_client.call_in_context(self.vpr_context, "VPR GET PATIENT DATA", params)

    def _call_vpr(self, dfn: str, domain: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        positional_params: List[Any] = [str(dfn)]
        type_map = {
            "patient": "demographics",
            "med": "meds",
            "lab": "labs",
            "vital": "vitals",
            "document": "documents",
            "image": "images",
            "procedure": "procedures",
            "visit": "visits",
            "problem": "problems",
            "allergy": "reactions",
            "order": "orders",
            "consult": "consults",
            "immunization": "immunizations",
            "appointment": "appointments",
        }
        type_val = type_map.get(domain)
        if type_val:
            positional_params.append(type_val)
        forward_params: Dict[str, Any] = {}
        if params and isinstance(params, dict):
            for key, value in params.items():
                if value is None:
                    continue
                low = str(key).lower()
                if low in {"raw", "rawxml", "returnraw"}:
                    continue
                forward_params[str(key)] = value
        lower_params: Dict[str, Any] = {str(k).lower(): v for k, v in forward_params.items()}
        if forward_params:
            start = forward_params.get("start") or forward_params.get("START")
            stop = forward_params.get("stop") or forward_params.get("STOP")
            max_items = forward_params.get("max") or forward_params.get("MAX")
            item_id = forward_params.get("item") or forward_params.get("ITEM")
            if any(v is not None for v in (start, stop, max_items, item_id)):
                positional_params.append(str(start) if start else "")
                positional_params.append(str(stop) if stop else "")
                positional_params.append(str(max_items) if max_items else "")
                positional_params.append(str(item_id) if item_id else "")
        use_named_call = False
        if lower_params:
            # Keys other than the standard positional set require named parameters (e.g., text=1)
            allowed_positional = {"start", "stop", "max", "item"}
            if any(key not in allowed_positional for key in lower_params.keys()):
                use_named_call = True
            # Explicitly treat document text flag as named to guarantee payload inclusion
            if not use_named_call and domain == "document" and lower_params.get("text") not in (None, ""):
                use_named_call = True
        capture_raw = False
        if params and isinstance(params, dict):
            for key, value in params.items():
                try:
                    text = str(value).strip().lower()
                except Exception:
                    text = ""
                if text and key and str(key).strip().lower() in {"raw", "rawxml", "returnraw"}:
                    if text not in {"0", "false", "no", "off"}:
                        capture_raw = True
                        break

        if use_named_call:
            named = {"patientId": str(dfn)}
            if domain:
                named["domain"] = str(domain)
            for key, value in forward_params.items():
                if value is not None:
                    named[str(key)] = value
            raw = self._vpr_client.call_in_context(
                self.vpr_context,
                "VPR GET PATIENT DATA",
                [{"namedArray": named}],
            )
        else:
            raw = self._invoke_vpr(positional_params)
        try:
            parsed_results = parse_vpr_results_xml(raw, domain=domain)
            if parsed_results.get("items"):
                return self._wrap_domain_response(
                    domain,
                    dfn,
                    parsed_results,
                    raw_text=raw if capture_raw else None,
                )
        except Exception:
            pass
        named = {"patientId": str(dfn)}
        if domain:
            named["domain"] = str(domain)
        for k, v in forward_params.items():
            if v is not None:
                named[str(k)] = v
        fallback_raw = self._vpr_client.call_in_context(
            self.vpr_context,
            "VPR GET PATIENT DATA",
            [{"namedArray": named}],
        )
        try:
            parsed_results_2 = parse_vpr_results_xml(fallback_raw, domain=domain)
            if parsed_results_2.get("items"):
                return self._wrap_domain_response(
                    domain,
                    dfn,
                    parsed_results_2,
                    raw_text=fallback_raw if capture_raw else None,
                )
        except Exception:
            pass
        legacy = _normalize_vpr_xml_to_items(fallback_raw, domain)
        return self._wrap_domain_response(
            domain,
            dfn,
            legacy,
            raw_text=fallback_raw if capture_raw else None,
        )

    # ------------------------------------------------------------------
    # DataGateway interface
    # ------------------------------------------------------------------

    def get_demographics(self, dfn: str) -> Dict[str, Any]:
        return self.get_vpr_domain(dfn, domain="patient")

    def get_vpr_domain(
        self,
        dfn: str,
        domain: str,
        params: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:  # type: ignore[override]
        self.connect()
        domain = domain.lower()
        cache_key: Optional[Tuple[str, str, str, str]] = None
        if domain in self._cacheable_domains:
            cache_key = self._domain_cache_key(dfn, domain, params)
            cached = self._domain_cache_get(cache_key)
            if cached is not None:
                return cached
        payload = self._call_vpr(dfn, domain, params=params)
        if cache_key is not None:
            self._domain_cache_store(cache_key, payload)
        return payload

    def get_vpr_fullchart(
        self,
        dfn: str,
        params: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        domains = [
            "patient",
            "med",
            "lab",
            "vital",
            "document",
            "image",
            "procedure",
            "visit",
            "problem",
            "allergy",
        ]
        items: List[Dict[str, Any]] = []
        for dom in domains:
            try:
                part = self.get_vpr_domain(dfn, dom, params=params)
                arr = part.get("items") if isinstance(part, dict) else []
                if isinstance(arr, list):
                    items.extend(arr)
            except Exception:
                continue
        return {
            "items": items,
            "meta": {"domain": "fullchart", "dfn": str(dfn), "total": len(items)},
            "data": {"items": items, "totalItems": len(items)},
        }

    @staticmethod
    def _resolve_document_ids(
        index: int,
        quick: Dict[str, Any],
        raw: Optional[Dict[str, Any]],
    ) -> Tuple[str, Optional[str]]:
        doc_id: Optional[str] = None
        rpc_id: Optional[str] = None

        if isinstance(raw, dict):
            raw_rpc = raw.get("id") or raw.get("localId")
            if raw_rpc:
                rpc_id = str(raw_rpc)
                doc_id = str(raw_rpc)
            raw_uid = raw.get("uid") or raw.get("uidLong")
            if raw_uid:
                doc_id = str(raw_uid)

        if not doc_id:
            quick_uid = quick.get("uid") or quick.get("uidLong")
            if quick_uid:
                doc_id = str(quick_uid)

        if not doc_id and quick.get("id"):
            doc_id = str(quick.get("id"))

        if not doc_id:
            doc_id = str(index)

        if rpc_id is not None:
            rpc_id = str(rpc_id)

        return doc_id, rpc_id

    @staticmethod
    def _extract_text_from_raw(raw: Optional[Dict[str, Any]]) -> str:
        if not isinstance(raw, dict):
            return ""

        text_field = raw.get("text")
        blocks: List[str] = []

        def _maybe_add(val: Any) -> None:
            if isinstance(val, str):
                trimmed = val.strip()
                if trimmed:
                    blocks.append(trimmed)

        if isinstance(text_field, list):
            for block in text_field:
                if isinstance(block, dict):
                    for key in ("content", "text", "summary", "value"):
                        if block.get(key):
                            _maybe_add(str(block[key]))
                else:
                    _maybe_add(block)
        elif isinstance(text_field, dict):
            for key in ("content", "text", "summary", "value"):
                if text_field.get(key):
                    _maybe_add(str(text_field[key]))
        else:
            _maybe_add(text_field)

        if not blocks:
            for key in ("content", "body", "documentText", "noteText", "clinicalText", "report", "impression"):
                maybe = raw.get(key)
                if isinstance(maybe, dict):
                    for sub_key in ("content", "text"):
                        if maybe.get(sub_key):
                            _maybe_add(str(maybe[sub_key]))
                else:
                    _maybe_add(maybe)

        return "\n".join(blocks)

    def get_document_index_entries(
        self,
        dfn: str,
        params: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        clean_params: Dict[str, Any] = {}
        for key, value in (params or {}).items():
            if value is None:
                continue
            if str(key).lower() == "text":
                continue
            clean_params[str(key)] = value

        payload = self.get_vpr_domain(dfn, "document", params=clean_params or None)
        quick_items = vpr_to_quick_notes(payload)
        if not isinstance(quick_items, list):
            quick_items = []
        raw_items = _extract_payload_items(payload)

        entries: List[Dict[str, Any]] = []
        entries_by_doc: Dict[str, Dict[str, Any]] = {}
        missing_rpc_map: Dict[str, str] = {}

        for idx, quick_entry in enumerate(quick_items):
            quick_dict = dict(quick_entry) if isinstance(quick_entry, dict) else {}
            raw_entry = raw_items[idx] if idx < len(raw_items) else None
            doc_id, rpc_id = self._resolve_document_ids(idx, quick_dict, raw_entry)
            if doc_id in entries_by_doc:
                continue

            note_text = self._extract_text_from_raw(raw_entry)

            entry: Dict[str, Any] = {
                "doc_id": doc_id,
                "quick": quick_dict,
                "raw": raw_entry if isinstance(raw_entry, dict) else raw_entry,
                "text": note_text,
                "rpc_id": rpc_id,
            }

            entries.append(entry)
            entries_by_doc[doc_id] = entry

            if (not note_text) and rpc_id:
                missing_rpc_map[str(rpc_id)] = doc_id

        if missing_rpc_map:
            try:
                rpc_texts = self.get_document_texts(dfn, list(missing_rpc_map.keys()))
            except GatewayError:
                rpc_texts = {}
            for requested_id, lines in (rpc_texts or {}).items():
                doc_id = missing_rpc_map.get(str(requested_id))
                if not doc_id:
                    continue
                if doc_id not in entries_by_doc:
                    continue
                entry = entries_by_doc[doc_id]
                if isinstance(lines, list):
                    joined = "\n".join(str(segment) for segment in lines if str(segment).strip())
                else:
                    joined = str(lines or "")
                if joined.strip():
                    entry["text"] = joined

        def _entry_sort_key(entry: Dict[str, Any]) -> str:
            quick_block = entry.get("quick")
            if isinstance(quick_block, dict):
                date_val = quick_block.get("date") or quick_block.get("referenceDate")
                if date_val:
                    return str(date_val)
            raw_block = entry.get("raw")
            if isinstance(raw_block, dict):
                for key in ("date", "dateTime", "referenceDate", "entered", "referenceDateTime"):
                    candidate = raw_block.get(key)
                    if candidate:
                        return str(candidate)
            return ""

        entries.sort(key=_entry_sort_key, reverse=True)
        return entries

    def get_document_texts(self, dfn: str, doc_ids: List[str]) -> Dict[str, List[str]]:  # type: ignore[override]
        if not doc_ids:
            return {}
        requested = [str(doc_id).strip() for doc_id in doc_ids if str(doc_id).strip()]
        if not requested:
            return {}
        self.connect()
        results: Dict[str, List[str]] = {}
        cache: Dict[str, List[str]] = {}
        for doc_id in requested:
            normalized = _normalize_doc_id(doc_id)
            rpc_token = normalized or doc_id
            lines: Optional[List[str]] = None
            if rpc_token in cache:
                lines = cache[rpc_token]
            elif rpc_token:
                try:
                    raw = self._or_client.call_in_context(
                        self.default_context,
                        "TIU GET RECORD TEXT",
                        [rpc_token],
                    )
                    if isinstance(raw, (bytes, bytearray)):
                        raw = raw.decode("utf-8", errors="ignore")
                    if isinstance(raw, str):
                        trimmed = raw.strip()
                        if trimmed and not _normalize_context_error(trimmed):
                            lower = trimmed.lower()
                            markers = (
                                "not authorized",
                                "does not exist",
                                "rpc not registered",
                            )
                            if not any(marker in lower for marker in markers):
                                lines = trimmed.splitlines()
                except Exception:
                    lines = None
                if lines:
                    cache[rpc_token] = lines
            if lines:
                results[doc_id] = list(lines)
                if normalized and normalized != doc_id:
                    results.setdefault(normalized, list(lines))
        return results

    def get_lab_panels(
        self,
        dfn: str,
        *,
        start: Optional[str] = None,
        end: Optional[str] = None,
        max_panels: Optional[int] = None,
    ) -> List[Dict[str, Any]]:  # type: ignore[override]
        self.connect()
        raw = self._or_client.call_in_context(
            self.default_context,
            "ORWCV LAB",
            [str(dfn)],
        )
        panels = parse_orwcv_lab(raw)
        return filter_panels(panels, start=start, end=end, max_panels=max_panels)

    def get_lab_panel_detail(self, dfn: str, lab_id: str) -> Dict[str, Any]:  # type: ignore[override]
        self.connect()
        raw = self._or_client.call_in_context(
            self.default_context,
            "ORWOR RESULT",
            [str(dfn), "0", str(lab_id)],
        )
        return parse_orwor_result(raw)


# Re-export alias maintaining backwards compatibility with previous name
VistaSocketGateway = VistaDualSocketGateway
