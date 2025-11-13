/*
  NoteRecorder: browser-side audio capture for the Note (scribe) tab.
  - HTML-first friendly: no framework required. Create an instance and wire to buttons.
  - Uses MediaRecorder when available; falls back to disabled state if not supported.
  - Chunk uploads via a pluggable uploader(patientId, generation, blob, seq).
  - Safe by default: requires explicit consent flag; auto-stops on patient switch.

  Usage example:
    const rec = new NoteRecorder({
      patientId: '123',
      getGeneration: () => window.sessionStorage.getItem('patient_generation'),
      onStatus: (state) => updateUI(state),
      uploader: noteUploadAdapter,
      chunkMs: 2000
    });
    startBtn.addEventListener('click', () => rec.start());
    stopBtn.addEventListener('click', () => rec.stop());
    // On patient switch: rec.onPatientSwitch()
*/
(function(){
  class NoteRecorder {
    constructor(opts={}){
      this.patientId = opts.patientId || null;
      this.getGeneration = typeof opts.getGeneration === 'function' ? opts.getGeneration : (() => null);
      this.onStatus = typeof opts.onStatus === 'function' ? opts.onStatus : (() => {});
      this.onError = typeof opts.onError === 'function' ? opts.onError : (e => console.error('[NoteRecorder]', e));
      this.uploader = typeof opts.uploader === 'function' ? opts.uploader : defaultUploader;
      this.chunkMs = typeof opts.chunkMs === 'number' ? Math.max(250, opts.chunkMs) : 2000;
      this.requireConsent = opts.requireConsent !== false; // default true
      this.hasConsent = !!opts.hasConsent;
      this.forceWav = !!opts.forceWav || !!window.FORCE_WAV_RECORDING;

      this.mediaStream = null;
      this.mediaRecorder = null;
      this.wavRecorder = null;
      this.seq = 0;
      this.active = false;
      this.mimeType = null;
      this.sessionId = null;

      this._notify({ ready: false, active: false, supported: this._isSupported() });
    }

    _isSupported(){
      return !!(navigator && navigator.mediaDevices);
    }

    async _ensureMic(){
      if (!this._isSupported()) throw new Error('Recording not supported in this browser');
      if (this.mediaStream) return this.mediaStream;
      try {
        this.mediaStream = await navigator.mediaDevices.getUserMedia({ audio: true, video: false });
        return this.mediaStream;
      } catch (err){
        throw new Error('Microphone access denied or unavailable');
      }
    }

    setConsent(val){
      this.hasConsent = !!val;
      this._notify({ consent: this.hasConsent });
    }

    setPatient(patientId){
      this.patientId = patientId || null;
      this._notify({ patientId: this.patientId });
    }

    async start(){
      if (this.active) return;
      if (!this.patientId) throw new Error('No patient selected');
      if (this.requireConsent && !this.hasConsent) throw new Error('Recording requires explicit consent');

      // Ensure a scribe session exists
      if (!this.sessionId){
        this.sessionId = await createScribeSession(this.patientId);
      }

      const stream = await this._ensureMic();

      const canMediaRecorder = !!window.MediaRecorder;
      const opusPreferred = ['audio/webm;codecs=opus', 'audio/webm', 'audio/ogg;codecs=opus'];
      let opusMime = '';
      if (canMediaRecorder){
        for (const mt of opusPreferred){
          try { if (window.MediaRecorder.isTypeSupported(mt)) { opusMime = mt; break; } } catch {}
        }
      }

      const useWav = this.forceWav || !canMediaRecorder || !opusMime;
      this.seq = 0;
      this.active = true;
      if (!useWav){
        this.mimeType = opusMime;
        try {
          this.mediaRecorder = new MediaRecorder(stream, this.mimeType ? { mimeType: this.mimeType } : undefined);
        } catch (err){
          // fallback to WAV path if MediaRecorder init fails
          this.mediaRecorder = null;
        }
      }

      if (this.mediaRecorder){
        this._wireRecorder();
        this.mediaRecorder.start(this.chunkMs);
        this._notify({ active: true, ready: true, mimeType: this.mimeType });
      } else {
        // WAV fallback: WebAudio + PCM16 encoder per chunk
        this.mimeType = 'audio/wav';
        this.wavRecorder = new WavRecorder(stream, {
          chunkMs: this.chunkMs,
          onChunk: async (blob) => {
            try {
              const seq = this.seq++;
              const gen = this.getGeneration ? this.getGeneration() : null;
              const mt = 'audio/wav';
              await this.uploader({ patientId: this.patientId, generation: gen, blob, seq, mimeType: mt });
              this._notify({ uploadedSeq: seq });
            } catch (e){ this.onError(e); }
          }
        });
        await this.wavRecorder.start();
        this._notify({ active: true, ready: true, mimeType: this.mimeType });
      }
    }

    _wireRecorder(){
      if (!this.mediaRecorder) return;
      this.mediaRecorder.ondataavailable = async (evt) => {
        try {
          if (!evt.data || !evt.data.size) return;
          const blob = evt.data;
          const seq = this.seq++;
          const gen = this.getGeneration ? this.getGeneration() : null;
          await this.uploader({
            patientId: this.patientId,
            generation: gen,
            blob,
            seq,
            mimeType: this.mimeType || blob.type || 'application/octet-stream'
          });
          this._notify({ uploadedSeq: seq });
        } catch (e){
          this.onError(e);
        }
      };
      this.mediaRecorder.onerror = (e) => {
        this.onError(e);
        this.stop();
      };
      this.mediaRecorder.onstop = () => {
        this._notify({ active: false });
      };
    }

    async stop(){
      if (!this.active) return;
      try {
        if (this.mediaRecorder && this.mediaRecorder.state !== 'inactive') this.mediaRecorder.stop();
        if (this.wavRecorder) await this.wavRecorder.stop();
      } finally {
        this.active = false;
        this.mediaRecorder = null;
        this.wavRecorder = null;
        // Do not stop the stream here to allow quick restarts; let onPatientSwitch fully tear down.
        this._notify({ active: false });
      }
      // Notify backend we are stopping (best-effort)
      try {
        if (this.sessionId){
          await stopScribeSession(this.patientId, this.sessionId);
        }
      } catch (e){ this.onError(e); }
    }

    async onPatientSwitch(){
      // Hard stop and release mic; reset state to avoid any cross-patient leakage
      try { await this.stop(); } catch {}
      if (this.mediaStream){
        for (const t of this.mediaStream.getTracks()) t.stop();
      }
      this.mediaStream = null;
      this.seq = 0;
      this.sessionId = null;
      this._notify({ active: false, ready: false });
    }

    _notify(state){
      try { this.onStatus({
        patientId: this.patientId,
        active: this.active,
        supported: this._isSupported(),
        ready: !!this.mediaStream,
        consent: this.hasConsent,
        mimeType: this.mimeType,
        ...state
      }); } catch {}
    }
  }

  // Simple WAV recorder using WebAudio. Encodes PCM16 LE on the fly, chunked per interval.
  class WavRecorder {
    constructor(stream, opts={}){
      this.stream = stream;
      this.chunkMs = typeof opts.chunkMs === 'number' ? Math.max(250, opts.chunkMs) : 2000;
      this.onChunk = typeof opts.onChunk === 'function' ? opts.onChunk : (()=>{});
      this.ctx = null;
      this.source = null;
      this.processor = null;
      this.buffers = [];
      this.sampleRate = 0;
      this.timer = null;
    }
    async start(){
      this.ctx = new (window.AudioContext || window.webkitAudioContext)();
      this.sampleRate = this.ctx.sampleRate;
      this.source = this.ctx.createMediaStreamSource(this.stream);
      // ScriptProcessorNode is deprecated but widely supported; bufferSize 4096 is reasonable.
      const bufferSize = 4096;
      this.processor = this.ctx.createScriptProcessor(bufferSize, 1, 1);
      this.source.connect(this.processor);
      this.processor.connect(this.ctx.destination);
      this.processor.onaudioprocess = (e) => {
        const input = e.inputBuffer.getChannelData(0);
        // Copy to avoid retaining the larger buffer
        this.buffers.push(new Float32Array(input));
      };
      // Flush timer
      this.timer = setInterval(() => this.flush(), this.chunkMs);
    }
    async stop(){
      try { if (this.timer) clearInterval(this.timer); } catch {}
      this.timer = null;
      try { if (this.processor) this.processor.disconnect(); } catch {}
      try { if (this.source) this.source.disconnect(); } catch {}
      try { if (this.ctx && this.ctx.state !== 'closed') await this.ctx.close(); } catch {}
      await this.flush();
      this.buffers = [];
      this.processor = null; this.source = null; this.ctx = null;
    }
    async flush(){
      if (!this.buffers.length) return;
      const floatData = concatFloat32(this.buffers);
      this.buffers = [];
      // Resample to 16000 Hz mono PCM16 for maximum Azure compatibility
      const targetRate = 16000;
      const resampled = (this.sampleRate && this.sampleRate !== targetRate)
        ? resampleFloat32(floatData, this.sampleRate, targetRate)
        : floatData;
      const wavBlob = encodeWav(resampled, targetRate);
      await this.onChunk(wavBlob);
    }
  }

  function concatFloat32(chunks){
    const total = chunks.reduce((n, a) => n + a.length, 0);
    const out = new Float32Array(total);
    let offset = 0;
    for (const a of chunks){ out.set(a, offset); offset += a.length; }
    return out;
  }

  function encodeWav(samplesFloat32, sampleRate){
    // Convert float [-1,1] to 16-bit PCM LE
    const bytesPerSample = 2;
    const numFrames = samplesFloat32.length;
    const blockAlign = bytesPerSample * 1; // mono
    const byteRate = sampleRate * blockAlign;
    const dataSize = numFrames * bytesPerSample;
    const buffer = new ArrayBuffer(44 + dataSize);
    const view = new DataView(buffer);
    // RIFF header
    writeString(view, 0, 'RIFF');
    view.setUint32(4, 36 + dataSize, true);
    writeString(view, 8, 'WAVE');
    // fmt chunk
    writeString(view, 12, 'fmt ');
    view.setUint32(16, 16, true); // PCM header size
    view.setUint16(20, 1, true);  // PCM format
    view.setUint16(22, 1, true);  // mono
    view.setUint32(24, sampleRate, true);
    view.setUint32(28, byteRate, true);
    view.setUint16(32, blockAlign, true);
    view.setUint16(34, 16, true); // bits per sample
    // data chunk
    writeString(view, 36, 'data');
    view.setUint32(40, dataSize, true);
    // PCM samples
    let offset = 44;
    for (let i=0; i<numFrames; i++){
      let s = Math.max(-1, Math.min(1, samplesFloat32[i]));
      view.setInt16(offset, s < 0 ? s * 0x8000 : s * 0x7FFF, true);
      offset += 2;
    }
    return new Blob([view], { type: 'audio/wav' });
  }

  function resampleFloat32(input, fromRate, toRate){
    if (!fromRate || fromRate === toRate) return input;
    const ratio = toRate / fromRate;
    const outLen = Math.max(1, Math.round(input.length * ratio));
    const output = new Float32Array(outLen);
    const step = 1 / ratio; // how many input samples per output sample
    let index = 0;
    for (let i = 0; i < outLen; i++){
      const pos = i * step;
      const i0 = Math.floor(pos);
      const i1 = Math.min(i0 + 1, input.length - 1);
      const frac = pos - i0;
      const s0 = input[i0] || 0;
      const s1 = input[i1] || 0;
      output[i] = s0 + (s1 - s0) * frac; // linear interpolation
    }
    return output;
  }

  function writeString(view, offset, str){
    for (let i=0; i<str.length; i++) view.setUint8(offset+i, str.charCodeAt(i));
  }

  function _getCsrfToken(){
    const m = document.cookie.match(/(?:^|; )csrf_token=([^;]+)/);
    return m ? decodeURIComponent(m[1]) : '';
  }

  async function defaultUploader({ patientId, generation, blob, seq, mimeType }){
    // Default uploader expects a backend at /api/scribe/stream
    const sid = window.currentScribeSessionId || null;
    if (!sid) throw new Error('No scribe session');
    const url = `/api/scribe/stream?session_id=${encodeURIComponent(sid)}&seq=${seq}`;
    const headers = {
      'x-patient-id': String(patientId || ''),
      'x-patient-generation': String(generation || ''),
      'content-type': mimeType || 'application/octet-stream',
      'X-CSRF-Token': _getCsrfToken()
    };
    // Avoid keepalive here; it can cause network errors in some browsers for active page uploads
    let res;
    try {
      res = await fetch(url, { method: 'POST', headers, body: blob, credentials: 'same-origin' });
    } catch (e) {
      // Surface clearer message than the generic 'Failed to fetch'
      throw new Error('Upload failed (network)');
    }
    if (!res.ok) {
      let detail = '';
      try { detail = await res.text(); } catch {}
      throw new Error(`Upload failed: ${res.status}${detail ? ' - ' + detail : ''}`);
    }
    // Optionally read JSON for transcript deltas
    return res.headers.get('content-type')?.includes('application/json') ? res.json() : null;
  }

  async function createScribeSession(patientId){
    const resp = await fetch('/api/scribe/session', {
      method: 'POST',
  headers: { 'content-type': 'application/json', 'X-CSRF-Token': _getCsrfToken() },
      credentials: 'same-origin',
      body: JSON.stringify({ patient_id: patientId })
    });
    if (!resp.ok) throw new Error('Failed to create scribe session');
    const data = await resp.json();
    const sid = data.session_id;
    if (!sid) throw new Error('Invalid session response');
    // expose for uploader
    window.currentScribeSessionId = sid;
    return sid;
  }

  async function stopScribeSession(patientId, sessionId){
    const resp = await fetch(`/api/scribe/stop?session_id=${encodeURIComponent(sessionId)}`, {
      method: 'POST',
  headers: { 'x-patient-id': String(patientId||''), 'X-CSRF-Token': _getCsrfToken() },
      credentials: 'same-origin'
    });
    return resp.ok;
  }

  // Optional mock adapter (no network); attach as NoteRecorder.mockUploader
  async function mockUploader({ patientId, generation, blob, seq, mimeType }){
    await new Promise(r => setTimeout(r, 50));
    return { ok: true, patientId, generation, seq, bytes: blob.size, mimeType };
  }

  // UMD-lite exposure
  window.NoteRecorder = NoteRecorder;
  window.NoteRecorderMockUploader = mockUploader;
})();
