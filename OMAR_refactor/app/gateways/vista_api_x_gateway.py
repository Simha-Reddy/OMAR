from __future__ import annotations
import os
import time
import requests
from typing import Any, Dict, Optional, Tuple
from .data_gateway import DataGateway, GatewayError

BASE_URL = os.getenv("VISTA_API_BASE_URL", "https://vista-api-x.vetext.app/api")
API_KEY = os.getenv("VISTA_API_KEY")
VERIFY_SSL = os.getenv("VISTA_API_VERIFY_SSL", "true").lower() in ("1","true","yes","on")
SUPPRESS_TLS_WARNINGS = os.getenv("VISTA_API_SUPPRESS_TLS_WARNINGS", "0").lower() in ("1","true","yes","on")
# RPC context: default to LHS RPC CONTEXT for now; configurable via .env
VPR_RPC_CONTEXT = os.getenv("VISTA_API_RPC_CONTEXT", "LHS RPC CONTEXT")

if not VERIFY_SSL and SUPPRESS_TLS_WARNINGS:
    try:
        import urllib3
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
    except Exception:
        pass

class VistaApiXGateway(DataGateway):
    """HTTP facade to vista-api-x with single refresh and simple backoff."""
    def __init__(self, station: str = "500", duz: str = "983"):
        self.station = str(station)
        self.duz = str(duz)
        self._token = None

    def _get_token(self) -> str:
        if not API_KEY:
            raise GatewayError("VISTA_API_KEY not configured")
        url = f"{BASE_URL}/auth/token"
        try:
            r = requests.post(url, json={"key": API_KEY}, timeout=20, verify=VERIFY_SSL)
            r.raise_for_status()
            j = r.json()
            tok = (j.get("data", {}) or {}).get("token") or j.get("token")
            if not tok:
                raise GatewayError("No token in response")
            return tok
        except Exception as e:
            raise GatewayError(f"Token fetch failed: {e}")

    def _ensure_token(self):
        if not self._token:
            self._token = self._get_token()

    def _post(self, path: str, body: dict, timeout: int = 60) -> Tuple[requests.Response, str]:
        self._ensure_token()
        headers = {"Authorization": f"Bearer {self._token}", "Accept":"application/json", "Content-Type":"application/json"}
        url = f"{BASE_URL}{path}"
        r = requests.post(url, json=body, headers=headers, timeout=timeout, verify=VERIFY_SSL)
        if r.status_code == 401:
            # single refresh then retry
            self._token = self._get_token()
            headers["Authorization"] = f"Bearer {self._token}"
            r = requests.post(url, json=body, headers=headers, timeout=timeout, verify=VERIFY_SSL)
        # mypy: _token is ensured by _ensure_token, but coerce to str for type stability
        return r, (self._token or "")

    def get_demographics(self, dfn: str) -> Dict[str, Any]:
        return self.get_vpr_domain(dfn, domain="patient")

    def get_vpr_domain(self, dfn: str, domain: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Generic VPR GET PATIENT DATA JSON call for any domain.
        Known domains include: patient, meds, labs, vitals, problems, visits, documents, radiology, allergies, etc.
        Extra key/values can be added via params for server-side filtering when supported.
        """
        body_params: Dict[str, Any] = {"patientId": str(dfn), "domain": str(domain)}
        if params and isinstance(params, dict):
            body_params.update({k: v for k, v in params.items() if v is not None})
        body = {
            "context": VPR_RPC_CONTEXT,
            "rpc": "VPR GET PATIENT DATA JSON",
            "jsonResult": True,
            "parameters": [ { "namedArray": body_params } ]
        }
        path = f"/vista-sites/{self.station}/users/{self.duz}/rpc/invoke"
        # minimal backoff for transient 5xx
        for attempt in range(3):
            try:
                r, _tok = self._post(path, body, timeout=60)
                if r.status_code >= 500:
                    time.sleep(0.8 * (attempt+1))
                    continue
                r.raise_for_status()
                try:
                    return r.json()
                except Exception:
                    return {"raw": r.text}
            except requests.RequestException as e:
                if attempt < 2:
                    time.sleep(0.8 * (attempt+1))
                    continue
                raise GatewayError(f"VPR domain '{domain}' request failed: {e}")
        raise GatewayError(f"VPR domain '{domain}' request failed after retries")

    def get_vpr_fullchart(self, dfn: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Call VPR GET PATIENT DATA JSON without a domain filter to retrieve the entire chart.
        Warning: This can be a very large payload. Consider using start/stop where supported.
        """
        body_params: Dict[str, Any] = {"patientId": str(dfn)}
        if params and isinstance(params, dict):
            body_params.update({k: v for k, v in params.items() if v is not None})
        body = {
            "context": VPR_RPC_CONTEXT,
            "rpc": "VPR GET PATIENT DATA JSON",
            "jsonResult": True,
            "parameters": [ { "namedArray": body_params } ]
        }
        path = f"/vista-sites/{self.station}/users/{self.duz}/rpc/invoke"
        for attempt in range(3):
            try:
                r, _tok = self._post(path, body, timeout=120)
                if r.status_code >= 500:
                    time.sleep(0.8 * (attempt+1))
                    continue
                r.raise_for_status()
                try:
                    return r.json()
                except Exception:
                    return {"raw": r.text}
            except requests.RequestException as e:
                if attempt < 2:
                    time.sleep(0.8 * (attempt+1))
                    continue
                raise GatewayError(f"VPR fullchart request failed: {e}")
        raise GatewayError("VPR fullchart request failed after retries")
