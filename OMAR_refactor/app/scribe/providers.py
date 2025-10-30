from __future__ import annotations
import os
import json
import time
from dataclasses import dataclass, asdict
from typing import Optional, Dict, Any

import requests


@dataclass
class TranscriptionResult:
    text: Optional[str]
    debug: Dict[str, Any]


class TranscriptionProvider:
    """Abstract provider interface for chunk transcription."""
    def transcribe_chunk(self, audio_bytes: bytes, content_type: str, *, language: str = "en-US") -> TranscriptionResult:
        raise NotImplementedError


class DevEchoTranscriptionProvider(TranscriptionProvider):
    def transcribe_chunk(self, audio_bytes: bytes, content_type: str, *, language: str = "en-US") -> TranscriptionResult:
        # Return a tiny marker proportional to size to simulate progress
        text = " " + ("…" if len(audio_bytes) > 12000 else "·")
        return TranscriptionResult(text=text, debug={
            "provider": "dev",
            "bytes": len(audio_bytes),
            "content_type_in": content_type,
        })


@dataclass
class AzureConfig:
    key: str
    region: Optional[str] = None
    endpoint: Optional[str] = None  # Full endpoint override
    language: str = "en-US"

    def url(self) -> str:
        if self.endpoint:
            base = self.endpoint.rstrip("/")
        else:
            if not self.region:
                raise ValueError("AZURE_SPEECH_REGION or AZURE_SPEECH_ENDPOINT required")
            base = f"https://{self.region}.stt.speech.microsoft.com"
        # Short audio REST endpoint (conversation)
        return f"{base}/speech/recognition/conversation/cognitiveservices/v1"


class AzureSpeechTranscriptionProvider(TranscriptionProvider):
    """Azure Speech Short Audio REST API provider.

    Notes:
      - Best used with WAV PCM (16-bit). Opus via REST is not consistently supported; prefer WAV for Safari and when FORCE_WAV is enabled.
      - This does one request per chunk and appends the recognized text. Not ideal for full accuracy but acceptable for incremental drafts.
    """
    def __init__(self, cfg: AzureConfig):
        self.cfg = cfg

    def _choose_auth_header(self) -> str:
        # APIM front doors often expect 'api-key'; regional endpoints accept 'Ocp-Apim-Subscription-Key'
        endpoint = (self.cfg.endpoint or "").lower()
        if ("azure-api" in endpoint) or ("apim" in endpoint):
            return "api-key"
        return "Ocp-Apim-Subscription-Key"

    def _post_with_retry(self, url: str, *, params: Dict[str, Any], headers: Dict[str, str], data: bytes,
                          retries: int = 3, backoff: float = 1.5, timeout: int = 15) -> requests.Response:
        last_exc = None
        for attempt in range(retries):
            try:
                t0 = time.time()
                resp = requests.post(url, params=params, headers=headers, data=data, timeout=timeout)
                elapsed_ms = int((time.time() - t0) * 1000)
                # Retry on 429 and 5xx
                if resp.status_code == 429 or 500 <= resp.status_code < 600:
                    time.sleep(backoff ** attempt)
                    continue
                # Attach timing for debug consumers
                resp.elapsed_ms_custom = elapsed_ms  # type: ignore[attr-defined]
                return resp
            except Exception as e:
                last_exc = e
                time.sleep(backoff ** attempt)
        if last_exc:
            raise last_exc
        return requests.post(url, params=params, headers=headers, data=data, timeout=timeout)

    def transcribe_chunk(self, audio_bytes: bytes, content_type: str, *, language: str = "en-US") -> TranscriptionResult:
        # Only attempt when WAV to maximize compatibility; otherwise return None to allow fallback
        ct = (content_type or '').lower()
        debug: Dict[str, Any] = {
            "provider": "azure",
            "content_type_in": content_type,
            "bytes": len(audio_bytes),
        }
        if "wav" not in ct:
            debug["skipped_reason"] = "non-wav-content"
            return TranscriptionResult(text=None, debug=debug)

        url = self.cfg.url()
        params = {
            "language": language or self.cfg.language or "en-US",
            "format": "detailed",
        }
        # Build headers with correct auth key header name
        auth_header_name = self._choose_auth_header()
        headers = {
            auth_header_name: self.cfg.key,
            "Content-Type": "audio/wav",  # send plain WAV for compatibility
            "Accept": "application/json",
        }

        debug.update({
            "url": url,
            "params": params,
            "auth_header": auth_header_name,
        })

        try:
            resp = self._post_with_retry(url, params=params, headers=headers, data=audio_bytes, retries=3, backoff=1.6, timeout=20)
            debug["status_code"] = resp.status_code
            debug["elapsed_ms"] = getattr(resp, 'elapsed_ms_custom', None)
            if resp.status_code != 200:
                # capture a small snippet to help diagnose
                body = resp.text[:400] if hasattr(resp, 'text') else ''
                debug["body_snippet"] = body
                return TranscriptionResult(text=None, debug=debug)

            # Try parse JSON
            try:
                data = resp.json()
                debug["parsed"] = True
                # Keep top-level keys to avoid leaking large payloads
                try:
                    debug["json_keys"] = list(data.keys()) if isinstance(data, dict) else []
                except Exception:
                    pass
            except Exception:
                debug["parsed"] = False
                return TranscriptionResult(text=None, debug=debug)

            # v1 may return { RecognitionStatus, DisplayText, Offset, Duration }
            # Prefer DisplayText when available; else try NBest list
            if isinstance(data, dict):
                if data.get("DisplayText"):
                    return TranscriptionResult(text=" " + data["DisplayText"].strip(), debug=debug)
                nbest = data.get("NBest")
                if isinstance(nbest, list) and nbest:
                    best = nbest[0]
                    txt = best.get("Display") or best.get("Lexical")
                    if txt:
                        return TranscriptionResult(text=" " + str(txt).strip(), debug=debug)
            return TranscriptionResult(text=None, debug=debug)
        except Exception as e:
            debug["exception"] = str(e)
            return TranscriptionResult(text=None, debug=debug)


_provider_singleton: Optional[TranscriptionProvider] = None


def get_transcription_provider() -> TranscriptionProvider:
    global _provider_singleton
    if _provider_singleton is not None:
        return _provider_singleton
    provider_name = os.getenv("SCRIBE_TRANSCRIBE_PROVIDER", "dev").strip().lower()
    if provider_name == "azure":
        key = os.getenv("AZURE_SPEECH_KEY") or os.getenv("AZURE_COG_SPEECH_KEY")
        region = os.getenv("AZURE_SPEECH_REGION")
        endpoint = os.getenv("AZURE_SPEECH_ENDPOINT")
        if key:
            cfg = AzureConfig(key=key, region=region, endpoint=endpoint, language=os.getenv("SCRIBE_LANG", "en-US"))
            _provider_singleton = AzureSpeechTranscriptionProvider(cfg)
            return _provider_singleton
        # If misconfigured, fall back to dev
    _provider_singleton = DevEchoTranscriptionProvider()
    return _provider_singleton
