import os
import sounddevice as sd
import numpy as np
import wave
import queue
import threading
import time
import json
from datetime import datetime
from dotenv import load_dotenv
 
# Load environment for configurable directories
load_dotenv()
 
# Allow overriding chunk directory via env; default to local 'chunks'
CHUNKS_DIR = os.getenv("CHUNKS_DIR", "chunks")
os.makedirs(CHUNKS_DIR, exist_ok=True)
 
recording = False
recording_thread = None
# Bounded queue to prevent unbounded backlog; drop-oldest in callback if full
q = queue.Queue(maxsize=30)

# Telemetry counters
_dropped_chunks = 0
_last_report = 0.0
 
def get_device_id():
    try:
        with open("config.json", "r") as f:
            config = json.load(f)
            return config.get("device_id", None)
    except:
        return None
 
# Lightweight callback: enqueue newest, drop oldest if full. Avoid heavy prints.
def audio_callback(indata, frames, time_info, status):
    global _dropped_chunks
    if status:
        # Only log when there is an actual overflow/underflow condition
        try:
            if getattr(status, 'input_overflow', False):
                print("[WARN] Input overflow")
        except Exception:
            pass
    try:
        # Copy to avoid referencing the temporary buffer
        q.put_nowait(indata.copy())
    except queue.Full:
        try:
            # Drop the oldest to make room for the newest
            _ = q.get_nowait()
            _dropped_chunks += 1
        except queue.Empty:
            pass
        try:
            q.put_nowait(indata.copy())
        except Exception:
            pass
 
# Write to a temp file and atomically rename to final to avoid partial reads
def save_wav(frames, filename, samplerate):
    tmp_name = filename + ".tmp"
    with wave.open(tmp_name, 'wb') as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(samplerate)
        wf.writeframes(b''.join(frames))
    os.replace(tmp_name, filename)
 
def start_recording():
    global recording, _last_report
    recording = True
    device_id = get_device_id()
    samplerate = 16000
    block_duration = 6  # seconds (reduced from 10s)
    base_overlap_seconds = 0.5  # overlap window to reduce error

    # Audio device config: provide buffer slack to reduce overflows
    blocksize = 1024  # frames per callback
    latency = 'high'  # could also be a float like 0.25

    print(f"[STARTING RECORDING] Using device: {device_id} -> CHUNKS_DIR={CHUNKS_DIR}")

    with sd.InputStream(samplerate=samplerate, channels=1, dtype='int16',
                        callback=audio_callback, device=device_id,
                        blocksize=blocksize, latency=latency):
        buffer = []
        start_time = time.time()

        try:
            while recording:
                # Light telemetry every ~5s
                now = time.time()
                if now - _last_report > 5:
                    try:
                        print(f"[AUDIO] qsize={q.qsize()}/{q.maxsize} dropped={_dropped_chunks}")
                    except Exception:
                        pass
                    _last_report = now

                try:
                    data = q.get(timeout=1)
                    buffer.append(data)

                    if time.time() - start_time >= block_duration:
                        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                        filename = os.path.join(CHUNKS_DIR, f"chunk_{timestamp}.wav")
                        # Convert numpy int16 frames to bytes
                        save_wav([d.tobytes() for d in buffer], filename, samplerate)
                        print(f"[SAVED] {filename}")

                        # Dynamic overlap: trim overlap when backlog is high
                        effective_overlap = base_overlap_seconds
                        try:
                            if q.qsize() > (q.maxsize // 2):
                                effective_overlap = 0.0
                        except Exception:
                            pass

                        # Keep last N seconds of audio for overlap
                        # Estimate seconds per block using last chunk's length
                        last_block = buffer[-1]
                        seconds_per_block = (len(last_block) / samplerate)
                        blocks_to_keep = int(effective_overlap / max(seconds_per_block, 1e-6))
                        if blocks_to_keep > 0:
                            buffer = buffer[-blocks_to_keep:]
                        else:
                            buffer = []
                        start_time = time.time()
                except queue.Empty:
                    continue
        finally:
            # Drain queue
            while not q.empty():
                try:
                    buffer.append(q.get_nowait())
                except queue.Empty:
                    break

            if buffer:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                filename = os.path.join(CHUNKS_DIR, f"chunk_{timestamp}_final.wav")
                save_wav([d.tobytes() for d in buffer], filename, samplerate)
                print(f"[SAVED FINAL] {filename}")
            else:
                print("[INFO] No leftover audio to save.")

def start_recording_thread():
    global recording_thread
    if recording_thread is None or not recording_thread.is_alive():
        recording_thread = threading.Thread(target=start_recording, daemon=True)
        recording_thread.start()


def stop_recording():
    global recording
    recording = False
    print("[STOPPED RECORDING]")
