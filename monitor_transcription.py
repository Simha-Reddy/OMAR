import os
import time
import requests
import json
from dotenv import load_dotenv
from concurrent.futures import ThreadPoolExecutor, as_completed
from threading import Lock

# Environment configuration
load_dotenv()
CHUNK_DIR = os.getenv("CHUNKS_DIR", "chunks")
TRANSCRIPT_DIR = os.getenv("TRANSCRIPT_DIR", "transcripts")
LIVE_TRANSCRIPT = os.getenv("LIVE_TRANSCRIPT", "live_transcript.txt")
MAX_WORKERS = int(os.getenv("TRANSCRIBE_WORKERS", "2"))
SCAN_INTERVAL = float(os.getenv("TRANSCRIBE_SCAN_INTERVAL", "1.0"))

os.makedirs(TRANSCRIPT_DIR, exist_ok=True)
os.makedirs(CHUNK_DIR, exist_ok=True)

_append_lock = Lock()
_session = requests.Session()

# Simple retry for 429/5xx
def _post_with_retry(url, headers, data, retries=3, backoff=1.5, timeout=(5, 60)):
    for attempt in range(retries):
        try:
            resp = _session.post(url, headers=headers, data=data, timeout=timeout)
            if resp.status_code == 429 or 500 <= resp.status_code < 600:
                time.sleep((backoff ** attempt))
                continue
            return resp
        except requests.RequestException:
            time.sleep((backoff ** attempt))
    # Final try without swallow to capture last error
    return _session.post(url, headers=headers, data=data, timeout=timeout)


def append_to_transcripts(text):
    with _append_lock:
        with open(LIVE_TRANSCRIPT, "a", encoding="utf-8") as f:
            f.write(text.strip() + "\n")


def azure_speech(wav_path, api_key):
    endpoint = os.getenv("AZURE_SPEECH_ENDPOINT", "https://spd-prod-openai-va-apim.azure-api.us")
    request_url = f"{endpoint}/speech/recognition/conversation/cognitiveservices/v1?language=en-US&format=detailed"
    headers = {
        "api-key": api_key,
        "Content-Type": "audio/wav"
    }
    try:
        with open(wav_path, "rb") as f:
            audio_data = f.read()
        response = _post_with_retry(request_url, headers=headers, data=audio_data)
        if response.status_code == 200:
            try:
                result = response.json()
            except Exception:
                return ""
            # Azure detailed format often returns NBest; keep DisplayText for now
            return result.get("DisplayText", "").strip()
        else:
            print(f"[ERROR] Azure Speech API {response.status_code} - {response.text[:200]}")
    except Exception as e:
        print(f"[ERROR] Exception during transcription: {e}")
    return ""


def _process_one(path, api_key):
    # Rename to lock for processing
    base, ext = os.path.splitext(path)
    processing_path = base + ".processing" + ext
    try:
        os.replace(path, processing_path)
    except FileNotFoundError:
        return 0.0  # already taken
    except PermissionError:
        return 0.0  # in use by another process

    t0 = time.time()
    result = azure_speech(processing_path, api_key)
    latency = time.time() - t0

    try:
        if result:
            append_to_transcripts(result)
        # remove processed file regardless of success to prevent pileup
        os.remove(processing_path)
    except Exception:
        # Best-effort cleanup
        try:
            os.remove(processing_path)
        except Exception:
            pass

    return latency


def monitor_chunks():
    with open(LIVE_TRANSCRIPT, "w", encoding="utf-8") as f:
        f.write("")

    api_key = os.getenv("AZURE_SPEECH_KEY")
    if not api_key:
        print("[ERROR] Missing Azure Speech key in environment.")
        return

    print(f"[TRANSCRIBE] Watching {CHUNK_DIR} with {MAX_WORKERS} workers")

    pending = set()
    last_report = 0.0

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as pool:
        futures = set()
        while True:
            # Telemetry every ~5s
            now = time.time()
            if now - last_report > 5:
                try:
                    print(f"[TRANSCRIBE] pending_files={len(pending)} in_flight={len(futures)}")
                except Exception:
                    pass
                last_report = now

            try:
                names = sorted([n for n in os.listdir(CHUNK_DIR) if n.endswith('.wav') and not n.endswith('.processing.wav')])
            except FileNotFoundError:
                time.sleep(SCAN_INTERVAL)
                continue

            for fname in names:
                if fname in pending:
                    continue
                wav_path = os.path.join(CHUNK_DIR, fname)
                pending.add(fname)
                fut = pool.submit(_process_one, wav_path, api_key)
                futures.add(fut)

            # Clean up finished futures
            done = [f for f in futures if f.done()]
            for f in done:
                try:
                    _ = f.result()
                except Exception as e:
                    print(f"[ERROR] worker: {e}")
                futures.remove(f)

            # Drop any names that no longer exist (processed)
            finished = {n for n in list(pending) if not os.path.exists(os.path.join(CHUNK_DIR, n))}
            pending.difference_update(finished)

            time.sleep(SCAN_INTERVAL)


if __name__ == "__main__":
    monitor_chunks()
