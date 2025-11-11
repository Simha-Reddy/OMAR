from __future__ import annotations

import copy
import json
import os
import socket
import threading
import time
from collections import OrderedDict
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Set, Tuple

from .data_gateway import DataGateway, GatewayError
from ..services.labs_rpc import filter_panels, parse_orwor_result, parse_orwcv_lab


def _env_int(name: str, default: int) -> int:
	try:
		value = int(str(os.getenv(name, str(default))).strip() or default)
		return value
	except Exception:
		return default


_SOCKET_IDLE_MAX_SECONDS = max(30, _env_int("VISTA_SOCKET_IDLE_SECONDS", 300))
_DOMAIN_CACHE_TTL = max(5, _env_int("VISTA_VPR_CACHE_TTL", 120))
_DOMAIN_CACHE_SIZE = max(4, _env_int("VISTA_VPR_CACHE_SIZE", 12))
_PATIENT_LIST_TTL = max(5, _env_int("VISTA_PATIENT_LIST_TTL", 30))
_PATIENT_SEARCH_TTL = max(5, _env_int("VISTA_PATIENT_SEARCH_TTL", 20))
_PATIENT_SEARCH_CACHE_SIZE = max(4, _env_int("VISTA_PATIENT_SEARCH_CACHE_SIZE", 24))
_LAB_PANEL_CACHE_TTL = max(5, _env_int("VISTA_LAB_PANEL_CACHE_TTL", 180))
_LAB_PANEL_CACHE_SIZE = max(4, _env_int("VISTA_LAB_PANEL_CACHE_SIZE", 24))
_LAB_DETAIL_CACHE_TTL = max(10, _env_int("VISTA_LAB_DETAIL_CACHE_TTL", 600))
_LAB_DETAIL_CACHE_SIZE = max(8, _env_int("VISTA_LAB_DETAIL_CACHE_SIZE", 64))


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
		self._mark_used()
		return message

	def _mark_used(self) -> None:
		self._last_used = time.monotonic()

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
			self._mark_used()

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

	def _is_context_success(self, reply: str) -> bool:
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

		self._heartbeat_thread = threading.Thread(target=_loop, name="VistaRPCHeartbeat", daemon=True)
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


def _wrap_items(
    domain: str,
    dfn: str,
    items: List[Dict[str, Any]],
    meta: Optional[Dict[str, Any]] = None,
    raw_text: Optional[str] = None,
) -> Dict[str, Any]:
	payload = [item for item in items if isinstance(item, dict)]
	meta_block = meta.copy() if isinstance(meta, dict) else {}
	meta_block.setdefault("domain", domain)
	meta_block.setdefault("dfn", str(dfn))
	meta_block.setdefault("total", len(payload))
	data = {
		"totalItems": len(payload),
		"items": payload,
	}
	out = {
		"items": payload,
		"meta": meta_block,
		"data": data,
	}
	if raw_text is not None:
		out["raw"] = raw_text
	return out


def _parse_orwpt_ptinq(raw: str, dfn: str) -> Dict[str, Any]:
	lines = [line.strip() for line in str(raw or "").replace("\r", "").split("\n") if line.strip()]
	fields: Dict[str, Any] = {}
	for line in lines:
		if "^" in line:
			parts = line.split("^")
			key = parts[0].strip()
			values = [segment.strip() for segment in parts[1:] if segment]
			if key:
				if len(values) == 1:
					fields[key] = values[0]
				else:
					fields[key] = values
		elif ":" in line:
			key, value = [segment.strip() for segment in line.split(":", 1)]
			if key and value and key not in fields:
				fields[key] = value
		elif ";" in line and any(token.isdigit() for token in line):
			name_part = line.split(";", 1)[0].strip()
			fields.setdefault("NAME", name_part)
	full_name = fields.get("NAME") or fields.get("Patient") or ""
	ssn = fields.get("SSN") or ""
	dob_text = fields.get("DOB") or ""
	gender = fields.get("Sex") or fields.get("Gender") or ""
	dob_iso: Optional[str] = None
	if dob_text:
		try:
			parsed = datetime.strptime(dob_text.replace(",", ""), "%b %d %Y")
			dob_iso = parsed.date().isoformat()
		except Exception:
			try:
				parsed = datetime.strptime(dob_text.upper(), "%b %d,%Y")
				dob_iso = parsed.date().isoformat()
			except Exception:
				dob_iso = None
	item: Dict[str, Any] = {
		"localId": int(dfn) if str(dfn).isdigit() else str(dfn),
		"fullName": full_name,
		"ssn": ssn,
		"dateOfBirth": dob_iso or dob_text,
	}
	if gender:
		item["genderName"] = gender
	if dob_iso:
		item["birthDate"] = dob_iso
	telecoms: List[Dict[str, Any]] = []
	for key in ("Residence Number", "Temporary Phone", "Office Phone"):
		value = fields.get(key)
		if isinstance(value, str) and value.strip():
			usage = "WP" if "Office" in key else "HP"
			telecoms.append({"usageCode": usage, "telecom": value.strip()})
	if telecoms:
		item["telecoms"] = telecoms
	address_lines = []
	for key in ("Street Address", "City", "State", "Zip"):
		value = fields.get(key)
		if isinstance(value, str) and value.strip():
			address_lines.append((key, value.strip()))
	if address_lines:
		addr: Dict[str, Any] = {}
		for key, value in address_lines:
			if key == "Street Address":
				addr["streetLine1"] = value
			elif key == "City":
				addr["city"] = value
			elif key == "State":
				addr["stateProvince"] = value
			elif key == "Zip":
				addr["postalCode"] = value
		item["addresses"] = [addr]
	return item


def _parse_orwps_active(raw: str) -> List[Dict[str, Any]]:
	items: List[Dict[str, Any]] = []
	lines = str(raw or "").splitlines()
	current: Optional[Dict[str, Any]] = None
	for line in lines:
		stripped = line.strip()
		if not stripped:
			continue
		if stripped.startswith("~"):
			parts = stripped[1:].split("^")
			if len(parts) < 3:
				continue
			current = {
				"id": parts[0].strip(),
				"display": parts[2].strip(),
				"statusName": (parts[9].strip().lower() if len(parts) > 9 else "").title(),
				"overallStart": _fileman_to_iso(parts[16]) if len(parts) > 16 else None,
				"overallStop": _fileman_to_iso(parts[17]) if len(parts) > 17 else None,
			}
			current["name"] = current["display"]
			if current.get("statusName"):
				current["vaStatus"] = current["statusName"].upper()
				current["status"] = current["statusName"]
			if current["display"]:
				items.append(current)
		elif current and stripped.startswith("\\"):
			if stripped.lower().startswith("\\ sig:"):
				current["sig"] = stripped.split(":", 1)[-1].strip()
			elif stripped.lower().startswith("\\indication:"):
				current["indication"] = stripped.split(":", 1)[-1].strip()
	return items


_VITAL_TYPE_METADATA: Dict[str, Dict[str, Optional[str]]] = {
	"BP": {"display": "Blood Pressure", "default_unit": "mmHg"},
	"T": {"display": "Temperature", "default_unit": "F"},
	"TEMP": {"display": "Temperature", "default_unit": "F"},
	"P": {"display": "Pulse", "default_unit": "bpm"},
	"HR": {"display": "Pulse", "default_unit": "bpm"},
	"R": {"display": "Respiratory Rate", "default_unit": "breaths/min"},
	"RR": {"display": "Respiratory Rate", "default_unit": "breaths/min"},
	"WT": {"display": "Weight", "default_unit": "lbs"},
	"WTKG": {"display": "Weight", "default_unit": "kg"},
	"HT": {"display": "Height", "default_unit": "in"},
	"HTCM": {"display": "Height", "default_unit": "cm"},
	"PO2": {"display": "SpO2", "default_unit": "%"},
	"POX": {"display": "SpO2", "default_unit": "%"},
	"SP02": {"display": "SpO2", "default_unit": "%"},
	"O2": {"display": "SpO2", "default_unit": "%"},
	"PN": {"display": "Pain", "default_unit": None},
	"PAIN": {"display": "Pain", "default_unit": None},
	"BMI": {"display": "BMI", "default_unit": None},
	"CG": {"display": "Girth", "default_unit": "cm"},
}


def _extract_vital_unit(raw_fragment: str, result: str) -> Optional[str]:
	fragment = (raw_fragment or "").strip()
	if not fragment:
		return None
	value = (result or "").strip()
	if fragment == value:
		return None
	if value and fragment.startswith(value):
		fragment = fragment[len(value):].strip()
	if not fragment:
		return None
	tokens = [token.strip("() ") for token in fragment.split() if token.strip("() ")]
	if not tokens:
		return None
	unit = tokens[-1]
	if not unit or unit == value:
		return None
	if unit.lower() == "lb":
		return "lbs"
	return unit


def _parse_orqqvi_vitals(raw: str) -> List[Dict[str, Any]]:
	items: List[Dict[str, Any]] = []
	for line in str(raw or "").splitlines():
		parts = [segment.strip() for segment in line.split("^")]
		if len(parts) < 4:
			continue
		vital_code = parts[1]
		result = parts[2]
		observed = _fileman_to_iso(parts[3])
		metadata = _VITAL_TYPE_METADATA.get((vital_code or "").strip().upper(), {})
		display_name = metadata.get("display") or vital_code
		unit = None
		if len(parts) > 4 and parts[4]:
			unit = _extract_vital_unit(parts[4], result)
		if not unit:
			unit = metadata.get("default_unit")
		item = {
			"typeName": display_name,
			"result": result,
			"observed": observed,
			"typeCode": vital_code,
		}
		if unit:
			item["units"] = unit
		if len(parts) > 6 and parts[6]:
			item["location"] = parts[6]
		items.append(item)
	return items


def _parse_orqqpl_problem_list(raw: str) -> List[Dict[str, Any]]:
	results: List[Dict[str, Any]] = []
	for line in str(raw or "").splitlines():
		if "^" not in line:
			continue
		parts = [segment.strip() for segment in line.split("^")]
		if not parts or not parts[0]:
			continue
		status_code = parts[1].upper() if len(parts) > 1 else ""
		status = {
			"A": "ACTIVE",
			"I": "INACTIVE",
			"E": "ENTERED IN ERROR",
		}.get(status_code, status_code)
		summary = parts[2] if len(parts) > 2 else ""
		icd = parts[3] if len(parts) > 3 else ""
		updated = _fileman_to_iso(parts[5]) if len(parts) > 5 else None
		item = {
			"localId": parts[0],
			"problemText": summary,
			"statusName": status,
			"icdCode": icd,
		}
		if status:
			item["status"] = status
		if summary:
			item["summary"] = summary
		if updated:
			item["updated"] = updated
		results.append(item)
	return results


def _parse_orqqal_allergies(raw: str) -> List[Dict[str, Any]]:
	items: List[Dict[str, Any]] = []
	for line in str(raw or "").splitlines():
		parts = [segment.strip() for segment in line.split("^")]
		if len(parts) < 2 or not parts[0]:
			continue
		item = {
			"localId": parts[0],
			"summary": parts[1],
			"statusName": parts[2] if len(parts) > 2 else "ACTIVE",
		}
		if item["summary"]:
			item["name"] = item["summary"]
		if item.get("statusName"):
			item["status"] = item["statusName"]
		items.append(item)
	return items


def _parse_tiu_documents(raw: str) -> List[Dict[str, Any]]:
	items: List[Dict[str, Any]] = []
	for line in str(raw or "").splitlines():
		line = line.strip()
		if not line or line.startswith("~") or "^" not in line:
			continue
		parts = [segment.strip() for segment in line.split("^")]
		if not parts[0]:
			continue
		doc_id = parts[0]
		local_title = parts[1] if len(parts) > 1 else ""
		fileman_stamp = parts[2] if len(parts) > 2 else ""
		author_blob = parts[4] if len(parts) > 4 else ""
		location_name = parts[5] if len(parts) > 5 else ""
		status_text = parts[6] if len(parts) > 6 else ""
		encounter = parts[7] if len(parts) > 7 else ""
		ref_iso = _fileman_to_iso(fileman_stamp)
		author_display = author_blob
		if author_blob and ";" in author_blob:
			author_tokens = [token.strip() for token in author_blob.split(";") if token.strip()]
			if len(author_tokens) >= 2:
				author_display = author_tokens[1]
			elif author_tokens:
				author_display = author_tokens[-1]
		status_clean = status_text.title() if status_text else None
		item: Dict[str, Any] = {
			"id": doc_id,
			"localId": doc_id,
			"localTitle": local_title,
			"authorDisplayName": author_display,
			"authorRaw": author_blob or None,
			"locationName": location_name or None,
			"statusName": status_clean,
			"encounterName": encounter or None,
		}
		item["uid"] = f"urn:va:document:{doc_id}"
		if ref_iso:
			item["referenceDateTime"] = ref_iso
		if status_clean:
			item["status"] = status_clean.upper()
		items.append(item)
	return items


def _normalize_context_error(text: str) -> bool:
	message = str(text or "").strip()
	if not message:
		return False
	# Vista sometimes prefixes status codes (for example "9" or "-1^") ahead of the message.
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


class VistaSocketGateway(DataGateway):
	def __init__(
		self,
		*,
		host: str,
		port: int,
		access: str,
		verify: str,
		default_context: Optional[str] = None,
	) -> None:
		self.host = host
		self.port = int(port)
		self.access = access
		self.verify = verify
		self.default_context = default_context or os.getenv("VISTA_DEFAULT_CONTEXT") or "OR CPRS GUI CHART"
		self.logger = _VistaRPCLogger()
		self._client = self._build_client()
		self._connected = False
		self._site_key = f"{self.host}:{self.port}"
		self._cache_lock = threading.RLock()
		self._domain_cache: "OrderedDict[Tuple[str, str, str, str], Tuple[float, Dict[str, Any]]]" = OrderedDict()
		self._patient_list_cache: Optional[Tuple[float, Any]] = None
		self._patient_search_cache: "OrderedDict[str, Tuple[float, Any]]" = OrderedDict()
		self._lab_panel_cache: "OrderedDict[Tuple[str, str], Tuple[float, List[Dict[str, Any]]]]" = OrderedDict()
		self._lab_detail_cache: "OrderedDict[Tuple[str, str, str], Tuple[float, Dict[str, Any]]]" = OrderedDict()
		self._cacheable_domains = {"patient", "med", "lab", "vital", "problem", "allergy"}

	def _build_client(self) -> _VistaRPCClient:
		client = _VistaRPCClient(
			host=self.host,
			port=self.port,
			access=self.access,
			verify=self.verify,
			context=self.default_context,
			logger=self.logger,
		)
		interval_raw = os.getenv("VISTA_HEARTBEAT_INTERVAL", "60")
		try:
			interval = int(str(interval_raw).strip() or "60")
		except Exception:
			interval = 60
		if interval > 0:
			client.start_heartbeat(interval)
		return client

	def _clear_caches(self) -> None:
		with self._cache_lock:
			self._domain_cache.clear()
			self._patient_list_cache = None
			self._patient_search_cache.clear()
			self._lab_panel_cache.clear()
			self._lab_detail_cache.clear()

	def clear_patient_cache(self, dfn: Optional[str] = None) -> None:
		with self._cache_lock:
			if dfn is None:
				self._domain_cache.clear()
				return
			dfn_str = str(dfn)
			remove: List[Tuple[str, str, str, str]] = [key for key in self._domain_cache if key[1] == dfn_str]
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

	def _domain_cache_get(self, key: Optional[Tuple[str, str, str, str]]) -> Optional[Dict[str, Any]]:
		if key is None:
			return None
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
			return copy.deepcopy(payload)

	def _domain_cache_store(self, key: Optional[Tuple[str, str, str, str]], payload: Dict[str, Any]) -> None:
		if key is None:
			return
		with self._cache_lock:
			self._domain_cache[key] = (time.monotonic(), copy.deepcopy(payload))
			self._domain_cache.move_to_end(key)
			while len(self._domain_cache) > _DOMAIN_CACHE_SIZE:
				self._domain_cache.popitem(last=False)

	def _params_disable_cache(self, params: Optional[Dict[str, Any]]) -> bool:
		if not params:
			return False
		text_flag = str(params.get("text", "")).strip().lower()
		if text_flag in {"1", "true", "yes"}:
			return True
		return False

	@staticmethod
	def _raw_flag(params: Optional[Dict[str, Any]]) -> bool:
		try:
			if not params:
				return False
			val = str(params.get("raw", "")).strip().lower()
			return val in {"1", "true", "yes", "on"}
		except Exception:
			return False

	def _domain_cache_produce(
		self,
		key: Optional[Tuple[str, str, str, str]],
		producer,
	) -> Dict[str, Any]:
		cached = self._domain_cache_get(key)
		if cached is not None:
			return cached
		payload = producer()
		self._domain_cache_store(key, payload)
		return payload

	def _rpc_cache_key(self, rpc: str, parameters: Optional[List[Dict[str, Any]]]) -> str:
		if not parameters:
			return f"{rpc}|"
		try:
			return f"{rpc}|{json.dumps(parameters, sort_keys=True, separators=(",", ":"))}"
		except Exception:
			return f"{rpc}|{str(parameters)}"

	def _get_cached_rpc(
		self,
		context: str,
		rpc: str,
		parameters: Optional[List[Dict[str, Any]]],
		json_result: bool,
	) -> Optional[Any]:
		if json_result:
			return None
		if context != self.default_context:
			return None
		now = time.monotonic()
		if rpc == "ORQPT DEFAULT PATIENT LIST" and not parameters:
			with self._cache_lock:
				if self._patient_list_cache and (now - self._patient_list_cache[0]) <= _PATIENT_LIST_TTL:
					return self._patient_list_cache[1]
				return None
		if rpc in {"ORWPT LAST5", "ORWPT LIST ALL"}:
			key = self._rpc_cache_key(rpc, parameters)
			with self._cache_lock:
				entry = self._patient_search_cache.get(key)
				if not entry:
					return None
				ts, payload = entry
				if (now - ts) > _PATIENT_SEARCH_TTL:
					self._patient_search_cache.pop(key, None)
					return None
				self._patient_search_cache.move_to_end(key)
				return payload
		return None

	def _store_cached_rpc(
		self,
		context: str,
		rpc: str,
		parameters: Optional[List[Dict[str, Any]]],
		json_result: bool,
		payload: Any,
	) -> None:
		if json_result or context != self.default_context:
			return
		now = time.monotonic()
		if rpc == "ORQPT DEFAULT PATIENT LIST" and not parameters:
			with self._cache_lock:
				self._patient_list_cache = (now, payload)
			return
		if rpc in {"ORWPT LAST5", "ORWPT LIST ALL"}:
			key = self._rpc_cache_key(rpc, parameters)
			with self._cache_lock:
				self._patient_search_cache[key] = (now, payload)
				self._patient_search_cache.move_to_end(key)
				while len(self._patient_search_cache) > _PATIENT_SEARCH_CACHE_SIZE:
					self._patient_search_cache.popitem(last=False)

	def _reset_client(self) -> None:
		try:
			self._client.close()
		except Exception:
			pass
		self._client = self._build_client()
		self._connected = False
		self.logger.info("VistaRPC", "client reset after authentication failure")
		self._clear_caches()

	def connect(self) -> None:
		if self._connected:
			return
		try:
			self._client.connect()
			self._connected = True
		except GatewayError as err:
			text = str(err or "")
			if "invalid access/verify" in text.lower() or "tcpconnect failed" in text.lower():
				self._reset_client()
				self._client.connect()
				self._connected = True
			else:
				raise
		self._client.ensure_connected(max_idle_seconds=_SOCKET_IDLE_MAX_SECONDS)

	def close(self) -> None:
		try:
			self._client.close()
		finally:
			self._connected = False
		self._clear_caches()

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
		cached = self._get_cached_rpc(context, rpc, parameters, json_result)
		if cached is not None:
			return cached
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
		try:
			raw = self._client.call_in_context(context, rpc, params)
		except (GatewayError, OSError) as err:
			text = str(err or "")
			lowered = text.lower()
			if "invalid access/verify" in lowered:
				self._reset_client()
				self.connect()
				raw = self._client.call_in_context(context, rpc, params)
			elif "10053" in lowered or "connection was aborted" in lowered or "socket closed" in lowered:
				self.logger.info("VistaRPC", "socket connection aborted; resetting client")
				self._reset_client()
				self.connect()
				raw = self._client.call_in_context(context, rpc, params)
			else:
				raise
		self._store_cached_rpc(context, rpc, parameters, json_result, raw)
		if json_result:
			try:
				return json.loads(raw)
			except Exception:
				return {"raw": raw}
		return raw

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
		if domain in self._cacheable_domains and not self._params_disable_cache(params):
			cache_key = self._domain_cache_key(dfn, domain, params)
		if domain == "patient":
			include_raw = self._raw_flag(params)
			def _load_patient() -> Dict[str, Any]:
				raw = self._client.call_in_context(self.default_context, "ORWPT PTINQ", [str(dfn)])
				item = _parse_orwpt_ptinq(raw, dfn)
				return _wrap_items("patient", dfn, [item], raw_text=raw if include_raw else None)
			return self._domain_cache_produce(cache_key, _load_patient)
		if domain in ("med", "meds", "medication"):
			include_raw = self._raw_flag(params)
			def _load_med() -> Dict[str, Any]:
				raw = self._client.call_in_context(self.default_context, "ORWPS ACTIVE", [str(dfn)])
				items = _parse_orwps_active(raw)
				return _wrap_items("med", dfn, items, raw_text=raw if include_raw else None)
			return self._domain_cache_produce(cache_key, _load_med)
		if domain in ("lab", "labs"):
			include_raw = self._raw_flag(params)
			def _load_lab() -> Dict[str, Any]:
				raw = self._client.call_in_context(self.default_context, "ORWCV LAB", [str(dfn)])
				items = parse_orwcv_lab(raw)
				return _wrap_items("lab", dfn, items, raw_text=raw if include_raw else None)
			return self._domain_cache_produce(cache_key, _load_lab)
		if domain in ("vital", "vitals"):
			include_raw = self._raw_flag(params)
			def _load_vital() -> Dict[str, Any]:
				start = params.get("start") if params else None
				stop = params.get("stop") if params else None
				fm_start = _iso_to_fileman(start) or ""
				fm_stop = _iso_to_fileman(stop) or ""
				raw = self._client.call_in_context(self.default_context, "ORQQVI VITALS", [str(dfn), fm_start, fm_stop])
				items = _parse_orqqvi_vitals(raw)
				return _wrap_items("vital", dfn, items, raw_text=raw if include_raw else None)
			return self._domain_cache_produce(cache_key, _load_vital)
		if domain in ("document", "documents", "notes"):
			include_raw = self._raw_flag(params)
			return self._get_document_domain(dfn, params=params, include_raw=include_raw)
		if domain in ("problem", "problems"):
			include_raw = self._raw_flag(params)
			def _load_problem() -> Dict[str, Any]:
				raw = self._client.call_in_context(self.default_context, "ORQQPL PROBLEM LIST", [str(dfn)])
				items = _parse_orqqpl_problem_list(raw)
				return _wrap_items("problem", dfn, items, raw_text=raw if include_raw else None)
			return self._domain_cache_produce(cache_key, _load_problem)
		if domain in ("allergy", "allergies"):
			include_raw = self._raw_flag(params)
			def _load_allergy() -> Dict[str, Any]:
				raw = self._client.call_in_context(self.default_context, "ORQQAL LIST", [str(dfn)])
				items = _parse_orqqal_allergies(raw)
				return _wrap_items("allergy", dfn, items, raw_text=raw if include_raw else None)
			return self._domain_cache_produce(cache_key, _load_allergy)
		return _wrap_items(domain, dfn, [])

	def get_lab_panels(
		self,
		dfn: str,
		*,
		start: Optional[str] = None,
		end: Optional[str] = None,
		max_panels: Optional[int] = None,
	) -> List[Dict[str, Any]]:  # type: ignore[override]
		self.connect()
		key = (self._site_key, str(dfn))
		now = time.monotonic()
		with self._cache_lock:
			entry = self._lab_panel_cache.get(key)
			if entry and (now - entry[0]) <= _LAB_PANEL_CACHE_TTL:
				cached = copy.deepcopy(entry[1])
			else:
				cached = None
		if cached is None:
			raw = self._client.call_in_context(self.default_context, "ORWCV LAB", [str(dfn)])
			panels = parse_orwcv_lab(raw)
			with self._cache_lock:
				self._lab_panel_cache[key] = (now, copy.deepcopy(panels))
				self._lab_panel_cache.move_to_end(key)
				while len(self._lab_panel_cache) > _LAB_PANEL_CACHE_SIZE:
					self._lab_panel_cache.popitem(last=False)
			cached = panels
		return filter_panels(copy.deepcopy(cached), start=start, end=end, max_panels=max_panels)

	def get_lab_panel_detail(self, dfn: str, lab_id: str) -> Dict[str, Any]:  # type: ignore[override]
		self.connect()
		key = (self._site_key, str(dfn), str(lab_id))
		now = time.monotonic()
		with self._cache_lock:
			entry = self._lab_detail_cache.get(key)
			if entry and (now - entry[0]) <= _LAB_DETAIL_CACHE_TTL:
				return copy.deepcopy(entry[1])
		raw = self._client.call_in_context(self.default_context, "ORWOR RESULT", [str(dfn), "0", str(lab_id)])
		detail = parse_orwor_result(raw)
		with self._cache_lock:
			self._lab_detail_cache[key] = (now, copy.deepcopy(detail))
			self._lab_detail_cache.move_to_end(key)
			while len(self._lab_detail_cache) > _LAB_DETAIL_CACHE_SIZE:
				self._lab_detail_cache.popitem(last=False)
		return detail

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
			"problem",
			"allergy",
		]
		items: List[Dict[str, Any]] = []
		for domain in domains:
			try:
				payload = self.get_vpr_domain(dfn, domain=domain, params=params)
				domain_items = payload.get("items") if isinstance(payload, dict) else []
				if isinstance(domain_items, list):
					items.extend(domain_items)
			except Exception:
				continue
		return _wrap_items("fullchart", dfn, items)

	def get_document_texts(self, dfn: str, doc_ids: List[str]) -> Dict[str, List[str]]:  # type: ignore[override]
		self.connect()
		results: Dict[str, List[str]] = {}
		cache: Dict[str, List[str]] = {}
		for doc_id in doc_ids:
			original = str(doc_id or "").strip()
			if not original:
				continue
			normalized = _normalize_doc_id(original)
			rpc_token = normalized or original
			lines: Optional[List[str]] = None
			if rpc_token in cache:
				lines = cache[rpc_token]
			elif rpc_token:
				try:
					raw = self._client.call_in_context(self.default_context, "TIU GET RECORD TEXT", [rpc_token])
					text = str(raw or "").replace("\r", "")
					stripped = text.strip()
					if stripped and not _normalize_context_error(stripped):
						lower = stripped.lower()
						if not any(marker in lower for marker in ("not authorized", "does not exist", "rpc not registered")):
							lines = stripped.splitlines()
				except Exception:
					lines = None
				if lines:
					cache[rpc_token] = lines
			if lines:
				results[original] = list(lines)
				if normalized and normalized != original:
					results.setdefault(normalized, list(lines))
		return results

	@staticmethod
	def _candidate_ids(item: Dict[str, Any]) -> List[str]:
		ids: List[str] = []
		for key in ("id", "localId", "uid", "uidLong"):
			val = item.get(key)
			if not val:
				continue
			val_str = str(val).strip()
			if not val_str:
				continue
			ids.append(val_str)
			if ":" in val_str:
				ids.append(val_str.split(":")[-1])
			if "-" in val_str:
				ids.append(val_str.split("-")[-1])
		return ids

	def _get_document_domain(self, dfn: str, params: Optional[Dict[str, Any]] = None, include_raw: bool = False) -> Dict[str, Any]:
		settings = params or {}
		start = settings.get("start")
		stop = settings.get("stop")
		max_results = settings.get("max")
		context_id = settings.get("tiu_context_id") or settings.get("context_id") or settings.get("context") or "3"
		sort_order = settings.get("sort") or "D"
		status_filter = settings.get("status_filter")
		if status_filter is None:
			candidate_status = settings.get("status")
			if isinstance(candidate_status, str) and candidate_status.strip().isdigit():
				status_filter = candidate_status.strip()
			else:
				status_filter = "0"
		else:
			status_filter = str(status_filter)
		include_addenda = settings.get("include_addenda")
		if include_addenda is None:
			include_addenda = "0"
		else:
			include_addenda = "1" if str(include_addenda).lower() in {"1", "true", "yes"} else "0"
		target_tokens: Set[str] = set()
		for raw_token in (settings.get("id"), settings.get("uid")):
			if raw_token is None:
				continue
			value = str(raw_token).strip()
			if not value:
				continue
			for token in (value, value.lower()):
				target_tokens.add(token)
			if ":" in value:
				suffix = value.split(":")[-1]
				for token in (suffix, suffix.lower()):
					target_tokens.add(token)
			if "-" in value:
				suffix = value.split("-")[-1]
				for token in (suffix, suffix.lower()):
					target_tokens.add(token)
		text_requested = False
		text_flag = settings.get("text")
		if text_flag is not None:
			text_requested = str(text_flag).strip().lower() in {"1", "true", "yes"}
		elif settings.get("id"):
			# Clients typically request text when explicit IDs supplied
			text_requested = True
		try:
			max_count = int(str(max_results)) if max_results is not None else 200
		except Exception:
			max_count = 200
		if target_tokens:
			try:
				candidate_max = max(5, len(target_tokens) * 5)
				max_count = max(1, min(max_count, candidate_max))
			except Exception:
				max_count = max(1, min(max_count or 10, 10))
		start_fm = _iso_to_fileman(start) or "-1"
		stop_fm = _iso_to_fileman(stop) or "-1"
		rpc_params: List[Any] = [
			str(context_id),
			"1",
			str(dfn),
			start_fm,
			stop_fm,
			str(status_filter or "0"),
			str(max_count),
			str(sort_order or "D"),
			"1",
			include_addenda,
			"1",
			"",
		]
		raw = self._client.call_in_context(self.default_context, "TIU DOCUMENTS BY CONTEXT", rpc_params)
		items = _parse_tiu_documents(raw)
		if target_tokens:
			filtered: List[Dict[str, Any]] = []
			for item in items:
				if not isinstance(item, dict):
					continue
				candidates = self._candidate_ids(item)
				candidate_tokens = set(candidates)
				candidate_tokens.update(tok.lower() for tok in candidates)
				if candidate_tokens & target_tokens:
					filtered.append(item)
			if filtered:
				items = filtered
		if text_requested and items:
			doc_ids: List[str] = []
			seen_ids: Set[str] = set()
			for item in items:
				if not isinstance(item, dict):
					continue
				candidates = self._candidate_ids(item)
				candidate_tokens = set(candidates)
				candidate_tokens.update(tok.lower() for tok in candidates)
				if target_tokens and not (candidate_tokens & target_tokens):
					continue
				selected = None
				for cand in candidates:
					if cand.isdigit():
						selected = cand
						break
				if not selected and candidates:
					selected = candidates[0]
				if selected and selected not in seen_ids:
					seen_ids.add(selected)
					doc_ids.append(selected)
			if doc_ids:
				text_map = self.get_document_texts(dfn, doc_ids)
				for item in items:
					if not isinstance(item, dict):
						continue
					identifier = item.get("id") or item.get("localId") or item.get("uid")
					if not identifier:
						continue
					key = str(identifier)
					lines = text_map.get(key)
					if not lines and ":" in key:
						alt = key.split(":")[-1]
						lines = text_map.get(alt)
					if not lines:
						continue
					item["text"] = [{"content": ln} for ln in lines if isinstance(ln, str) and ln.strip()]
		meta = {
			"rpc": "TIU DOCUMENTS BY CONTEXT",
			"max": max_count,
			"start": start,
			"stop": stop,
			"status": settings.get("status"),
			"contextId": str(context_id),
		}
		return _wrap_items("document", dfn, items, meta, raw_text=raw if include_raw else None)

