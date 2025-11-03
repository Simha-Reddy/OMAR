// --- State & globals ---
let chatHistory = [];
let isRecordingActive = false;
let lastServerTranscript = "";
let audioContext, analyser, microphone, animationId, micStream;
let autoSaveIntervalId = null;

// --- Theme bootstrap (Original vs VADesign) ---
// Applies on load based on localStorage and exposes a simple toggler for quick review.
try {
    const THEME_KEY = 'ui:theme';
    const root = document.documentElement;
    const saved = localStorage.getItem(THEME_KEY);
    // Default to VA theme unless explicitly set to 'original'
    if (saved === 'original') {
        root.removeAttribute('data-theme'); // Original palette
    } else {
        root.setAttribute('data-theme', 'va');
        if (saved === null) { try { localStorage.setItem(THEME_KEY, 'va'); } catch(_e){} }
    }
    window.toggleThemeVA = function(force){
        const target = (typeof force === 'string') ? force : (root.getAttribute('data-theme') === 'va' ? 'original' : 'va');
        if (target === 'va') {
            root.setAttribute('data-theme', 'va');
            try { localStorage.setItem(THEME_KEY, 'va'); } catch(_e){}
        } else {
            root.removeAttribute('data-theme');
            try { localStorage.setItem(THEME_KEY, 'original'); } catch(_e){}
        }
        return root.getAttribute('data-theme') || 'original';
    };
    // Optional hotkey: Alt+V toggles theme for quick visual QA
    window.addEventListener('keydown', function(e){
        try{
            if ((e.altKey || e.metaKey) && !e.shiftKey && !e.ctrlKey && (e.key === 'v' || e.key === 'V')) {
                const mode = window.toggleThemeVA();
                console.log('Theme:', mode);
            }
        }catch(_e){}
    });
} catch(_e){}

// Ensure an archive file name exists for the current patient; create one if missing
async function ensureArchiveNameInitialized() {
    try {
        const existing = localStorage.getItem('ssva:currentArchiveName');
        if (existing && existing.trim().length) return existing;
        let patientName = '';
        // Do not call legacy /get_patient; name will be set by header updates later
        let base = '';
        try {
            if (typeof buildArchiveBaseName === 'function') {
                base = buildArchiveBaseName(patientName || '');
            } else {
                const now = new Date();
                const mm = now.getMonth() + 1;
                const dd = now.getDate();
                const yy = String(now.getFullYear()).slice(-2);
                const hh = String(now.getHours()).padStart(2, '0');
                const min = String(now.getMinutes()).padStart(2, '0');
                const ss = String(now.getSeconds()).padStart(2, '0');
                base = `${mm}-${dd}-${yy} at ${hh}${min}${ss} with ${patientName || ''}`;
            }
        } catch(_e) { base = `session_${Date.now()}`; }
        try { localStorage.setItem('ssva:currentArchiveName', base); } catch(_e) {}
        return base;
    } catch(_e) { return null; }
}

// --- Extension Error Suppression ---
// Suppress browser extension errors that can interfere with application functionality
(function() {
    const originalError = window.onerror;
    const originalUnhandledRejection = window.onunhandledrejection;
    
    // Filter out extension-related errors
    window.onerror = function(message, source, lineno, colno, error) {
        // Suppress common extension errors
        if (typeof message === 'string') {
            if (message.includes('Extension context invalidated') ||
                message.includes('Could not establish connection') ||
                message.includes('Receiving end does not exist') ||
                message.includes('chrome-extension://') ||
                message.includes('moz-extension://')) {
                console.warn('🔇 Suppressed extension error:', message);
                return true; // Prevent default error handling
            }
        }
        
        // Call original handler for non-extension errors
        if (originalError) {
            return originalError.apply(this, arguments);
        }
        return false;
    };
    
    // Handle promise rejections from extensions
    window.onunhandledrejection = function(event) {
        if (event.reason && typeof event.reason === 'object') {
            const message = event.reason.message || event.reason.toString();
            if (message.includes('Extension context invalidated') ||
                message.includes('Could not establish connection') ||
                message.includes('Receiving end does not exist')) {
                console.warn('🔇 Suppressed extension promise rejection:', message);
                event.preventDefault();
                return;
            }
        }
        
        // Call original handler for non-extension rejections
        if (originalUnhandledRejection) {
            return originalUnhandledRejection.apply(this, arguments);
        }
    };
    
    // Suppress console errors from extensions in DevTools
    const originalConsoleError = console.error;
    console.error = function(...args) {
        const message = args.join(' ');
        if (message.includes('runtime.lastError') ||
            message.includes('Could not establish connection') ||
            message.includes('Receiving end does not exist') ||
            message.includes('Extension context invalidated')) {
            console.warn('🔇 Suppressed extension console error:', ...args);
            return;
        }
        originalConsoleError.apply(console, args);
    };
})();

// --- Wake Lock ---
// The Wake Lock API allows the web app to request that the device's screen stays on and prevents the system from sleeping.
// This is important for uninterrupted audio recording, as sleep/screen-off can suspend the recording process.
let wakeLock = null; // Holds the current Wake Lock object

// Requests a screen wake lock when recording starts.
// If successful, the device will not sleep or turn off the display while recording is active.
async function requestWakeLock() {
    try {
        // Request a screen wake lock
        wakeLock = await navigator.wakeLock.request('screen');
        // Listen for the 'release' event, which fires if the wake lock is released by the system or browser
        wakeLock.addEventListener('release', () => {
            console.log('Wake Lock was released');
        });
        console.log('Wake Lock is active');
    } catch (err) {
        // If the API is not supported or another error occurs, log it
        console.error(`${err.name}, ${err.message}`);
    }
}

// Releases the wake lock when recording stops.
// This allows the device to sleep or turn off the display again.
async function releaseWakeLock() {
    if (wakeLock) {
        await wakeLock.release();
        wakeLock = null;
        console.log('Wake Lock released by app');
    }
}

// If the page becomes visible again (e.g., after switching tabs or minimizing),
// re-acquire the wake lock if recording is still active. This is necessary because
// some browsers automatically release wake locks when the page is hidden.
document.addEventListener('visibilitychange', async () => {
    if (document.visibilityState === 'visible' && isRecordingActive) {
        await requestWakeLock();
    }
});

// --- Favicon swap for recording state ---
let __originalFaviconHref = null;
function __getFaviconLink(){
    try{ return document.querySelector('link[rel~="icon"], link[rel="shortcut icon"]'); }catch(_e){ return null; }
}
function __ensureOriginalFavicon(){
    try{
        if (__originalFaviconHref !== null) return;
        const link = __getFaviconLink();
        __originalFaviconHref = (link && link.getAttribute('href')) || '/static/icon.ico';
    }catch(_e){ __originalFaviconHref = '/static/icon.ico'; }
}
function updateFaviconForRecording(isRecording){
    // No longer swap to a custom red favicon; rely on the browser's own recording indicator.
    // We keep this function to preserve call sites; on stop, we ensure the original icon is restored.
    try{
        __ensureOriginalFavicon();
        if (!isRecording){
            let link = __getFaviconLink();
            if (!link){
                link = document.createElement('link');
                link.setAttribute('rel','icon');
                document.head.appendChild(link);
            }
            link.setAttribute('type','image/x-icon');
            link.setAttribute('href', __originalFaviconHref || '/static/icon.ico');
            // Remove any duplicate icon links to avoid browser picking an outdated one
            try{
                const all = Array.from(document.querySelectorAll('link[rel~="icon"], link[rel="shortcut icon"]'));
                for (const l of all){ if (l !== link) l.parentNode && l.parentNode.removeChild(l); }
            }catch(_e){}
        }
        // If recording is active, do nothing (keep original favicon)
    }catch(_e){}
}

// --- Spinner for thinking/loading state ---
function showThinkingSpinner(text = "Thinking...") {
    return `
        <span class="module-loading" style="font-size:1.2em; color:#888;">
            <svg width="24" height="24" viewBox="0 0 50 50" style="vertical-align:middle;">
                <circle cx="25" cy="25" r="20" fill="none" stroke="#888" stroke-width="5" stroke-linecap="round" stroke-dasharray="31.4 31.4" transform="rotate(-90 25 25)">
                    <animateTransform attributeName="transform" type="rotate" from="0 25 25" to="360 25 25" dur="1s" repeatCount="indefinite"/>
                </circle>
            </svg>
            ${text}
        </span>
    `;
}

// --- Mic visualization ---
function startMicFeedback() {
    const btn = document.getElementById("recordBtn");
    if (!btn || !navigator.mediaDevices?.getUserMedia) return;

    // Ensure overlay is visible and give a baseline glow immediately
    try {
        btn.classList.add('recording');
        btn.style.setProperty('--record-glow', '24px');
    } catch(_e) {}

    // If a previous stream was left over for any reason, stop it first
    try {
        if (micStream) {
            try { micStream.getTracks().forEach(t => { try { t.stop(); } catch(_e){} }); } catch(_e){}
            micStream = null;
        }
        if (microphone && typeof microphone.disconnect === 'function') { try { microphone.disconnect(); } catch(_e){} }
    } catch(_e){}

    navigator.mediaDevices.getUserMedia({ audio: true })
        .then(stream => {
            // Keep a reference so we can stop tracks on toggle off
            micStream = stream;
            audioContext = new (window.AudioContext || window.webkitAudioContext)();
            analyser = audioContext.createAnalyser();
            microphone = audioContext.createMediaStreamSource(stream);
            microphone.connect(analyser);

            const dataArray = new Uint8Array(analyser.frequencyBinCount);
            function animate() {
                analyser.getByteTimeDomainData(dataArray);
                const volume = Math.max(...dataArray) - 128;
                const intensity = Math.min(Math.abs(volume) / 128, 1);
                const glowPx = Math.floor(intensity * 80); // 0-80px range
                // Drive CSS variable used by the overlay pseudo-element
                try { btn.style.setProperty('--record-glow', glowPx + 'px'); } catch(_e) {}
                animationId = requestAnimationFrame(animate);
            }
            animate();
        })
        .catch(err => console.error("Mic access error:", err));
}

function stopMicFeedback() {
    if (animationId) { try { cancelAnimationFrame(animationId); } catch(_e){} animationId = null; }
    // Disconnect audio nodes
    try { if (microphone && typeof microphone.disconnect === 'function') microphone.disconnect(); } catch(_e){}
    try { if (analyser && typeof analyser.disconnect === 'function') analyser.disconnect(); } catch(_e){}
    // Stop the underlying mic stream tracks so the browser recording indicator clears
    try {
        if (micStream) { micStream.getTracks().forEach(t => { try { t.stop(); } catch(_e){} }); micStream = null; }
    } catch(_e){}
    // Close the audio context last
    try { if (audioContext) audioContext.close(); } catch(_e){}
    audioContext = null; analyser = null; microphone = null;
    const btn = document.getElementById("recordBtn");
    if (btn) {
        try {
            btn.classList.remove('recording');
            btn.style.removeProperty('--record-glow');
        } catch(_e) {}
        // Legacy cleanup (no longer used)
        btn.style.boxShadow = "none";
    }
}

// --- Utility ---
function escapeHtml(text) {
    return text.replace(/[&<>"']/g, function (m) {
        return ({
            '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'
        })[m];
    });
}
function escapeRegExp(string) {
    return string.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
}

// End Session: global function so links like onclick="endSession()" work
async function endSession() {
    console.log("End-Session invoked");
    if (!confirm("End session and archive transcript?")) return;

    const now = new Date();
    const month = now.getMonth() + 1;
    const day = now.getDate();
    const year = now.getFullYear().toString().slice(-2);
    const hour = now.getHours().toString().padStart(2, '0');
    const minute = now.getMinutes().toString().padStart(2, '0');
    const displayName = `${month}-${day}-${year} at ${hour}${minute} with `;
    // Prompt user with default displayName, always save as .json
    let sessionName = prompt("Enter a name for this session:", displayName);
    if (!sessionName) return;
    sessionName = sessionName.replace(/[@:]/g, '_');

    if (typeof SessionManager === "undefined") {
        alert("SessionManager is not available.");
        return;
    }
    try {
        stopAutoSaveLoop();
        // Clear any bound archive continuation
        try { localStorage.removeItem('ssva:currentArchiveName'); } catch(_e){}
        await SessionManager.endSession(sessionName);
        window.location.reload();
    } catch (err) {
        alert((err && err.message) || "Failed to save session.");
    }
}
// Expose globally
window.endSession = endSession;

// Wire up End Session Button if present
const endBtn = document.getElementById("endSessionBtn");
if (endBtn) {
    endBtn.addEventListener("click", endSession);
} else {
    console.warn("⚠️ endSessionBtn not found in DOM!");
}

// BroadcastChannel for syncing state across tabs
const recordingChannel = new BroadcastChannel('recording_channel');

async function getRecordingStatus() {
    // Prefer a centralized provider (SessionManager) or fall back to local UI state
    try {
        if (typeof SessionManager !== 'undefined' && typeof SessionManager.getRecordingStatus === 'function') {
            const v = await SessionManager.getRecordingStatus();
            return !!v;
        }
    } catch(_e) {}
    // Fallback: trust current UI state
    return !!currentRecordingState;
}

function _csrf(){ 
    try{ 
        // Prefer cookie value since it's set by server and matches session
        const cookieValue = document.cookie.split('; ')
            .find(row => row.startsWith('csrf_token='))
            ?.split('=')[1];
        if (cookieValue) return cookieValue;
        
        // Fallback to meta tag
        return document.querySelector('meta[name="csrf-token"]').getAttribute('content'); 
    }catch(_e){ return ''; } 
}

// Make CSRF function globally available for other scripts
window.getCsrfToken = _csrf;

// Support multiple/dynamic record buttons across the app
const RECORD_BTN_SELECTOR = '.image-record-btn, button#recordBtn:not(.image-record-btn)';
let currentRecordingState = false;

async function setRecordBtnState(isRecording) {
    currentRecordingState = !!isRecording;
    const buttons = Array.from(document.querySelectorAll(RECORD_BTN_SELECTOR));
    if (buttons.length === 0) return;

    for (const btn of buttons) {
        const isImageMode = btn.dataset && btn.dataset.visual === 'image';
        if (isImageMode) {
            // Swap image source instead of text
            const img = btn.querySelector('img');
            const startSrc = btn.dataset.startSrc || '/static/images/start_Recording_circle_button.png';
            const stopSrc = btn.dataset.stopSrc || '/static/images/stop_Recording_circle_button.png';
            if (img) {
                img.src = isRecording ? stopSrc : startSrc;
                img.alt = isRecording ? 'Stop Recording' : 'Start Recording';
            }
            // Ensure no text classes are applied in image mode
            btn.classList.remove('start-button', 'stop-button');
        } else {
            btn.textContent = isRecording ? 'Stop Recording' : 'Start Recording';
            btn.classList.toggle('stop-button', isRecording);
            btn.classList.toggle('start-button', !isRecording);
        }

        // Toggle overlay class and baseline glow so it's immediately visible
        try {
            btn.classList.toggle('recording', isRecording);
            if (isRecording) {
                btn.style.setProperty('--record-glow', '36px');
            } else {
                btn.style.removeProperty('--record-glow');
            }
        } catch(_e) {}
    }

    if (isRecording) {
        startMicFeedback(); // Start dynamic glow
        isRecordingActive = true;
        requestWakeLock();
        // Swap favicon to red recording indicator
        updateFaviconForRecording(true);
        // Publish status via runtime bus
        try { if (window.ScribeRuntime && typeof window.ScribeRuntime.setStatus === 'function') window.ScribeRuntime.setStatus(true); } catch(_e){}
        // NEW: ensure auto-archive is active when recording starts (Workspace requirement)
        try {
            await ensureArchiveNameInitialized();
            if (typeof startAutoArchiveForCurrentPatient === 'function') await startAutoArchiveForCurrentPatient();
        } catch(_e) {}
    } else {
        stopMicFeedback(); // Stop dynamic glow
        isRecordingActive = false;
        releaseWakeLock();
        // Restore original favicon
        updateFaviconForRecording(false);
        // Publish status via runtime bus
        try { if (window.ScribeRuntime && typeof window.ScribeRuntime.setStatus === 'function') window.ScribeRuntime.setStatus(false); } catch(_e){}
    }
}

async function toggleRecording() {
    const isRecording = await getRecordingStatus();
    try {
        if (isRecording) {
            if (window.ScribeRuntime && typeof window.ScribeRuntime.stop === 'function') {
                await window.ScribeRuntime.stop();
            }
            recordingChannel.postMessage({ isRecording: false });
            await setRecordBtnState(false);
        } else {
            if (window.ScribeRuntime && typeof window.ScribeRuntime.start === 'function') {
                await window.ScribeRuntime.start();
            }
            recordingChannel.postMessage({ isRecording: true });
            await setRecordBtnState(true);
        }
    } catch (e) {
        console.warn('Recording toggle failed:', e);
        try { alert(e && e.message ? e.message : 'Recording action failed'); } catch(_e){}
    }
}

// Listen for state changes from other tabs
recordingChannel.onmessage = (event) => {
    setRecordBtnState(event.data.isRecording);
};

// Ensure SessionManager is defined
if (typeof SessionManager === "undefined") {
    console.error("⚠️ SessionManager is not defined. Ensure SessionManager.js is loaded before app.js.");
}

document.addEventListener("DOMContentLoaded", function() {
    const hamburgerBtn = document.getElementById("hamburgerBtn");
    const mobileMenu = document.getElementById("mobileMenu");
    if (hamburgerBtn && mobileMenu) {
        hamburgerBtn.addEventListener("click", function() {
            mobileMenu.classList.toggle("open");
        });
        // Optional: close menu when clicking outside
        document.addEventListener("click", function(e) {
            if (!mobileMenu.contains(e.target) && !hamburgerBtn.contains(e.target)) {
                mobileMenu.classList.remove("open");
            }
        });
    }
});

document.addEventListener("DOMContentLoaded", async () => {
    console.log("Page loaded. Attempting to restore session...");

    // Initialize current state and reflect on any existing record buttons
    const isRecording = await getRecordingStatus();
    setRecordBtnState(isRecording);

    // Event delegation for dynamically added record buttons
    let lastTouchTime = 0;
    document.addEventListener('touchend', async (e) => {
        const btn = e.target && e.target.closest && e.target.closest(RECORD_BTN_SELECTOR);
        if (!btn) return;
        e.preventDefault();
        lastTouchTime = Date.now();
        await toggleRecording();
    }, { passive: false });

    document.addEventListener('click', async (e) => {
        const btn = e.target && e.target.closest && e.target.closest(RECORD_BTN_SELECTOR);
        if (!btn) return;
        // Ignore the synthetic click that follows touchend
        if (Date.now() - lastTouchTime < 500) return;
        await toggleRecording();
    });

    // Observe DOM for newly added record buttons and sync their initial state
    try {
        const obs = new MutationObserver((mutations) => {
            let found = false;
            for (const m of mutations) {
                if (m.type === 'childList') {
                    for (const node of m.addedNodes) {
                        if (!(node instanceof Element)) continue;
                        if (node.matches && node.matches(RECORD_BTN_SELECTOR)) { found = true; break; }
                        if (node.querySelector && node.querySelector(RECORD_BTN_SELECTOR)) { found = true; break; }
                    }
                }
                if (found) break;
            }
            if (found) {
                // Apply the cached currentRecordingState to all buttons
                setRecordBtnState(currentRecordingState);
            }
        });
        obs.observe(document.body, { childList: true, subtree: true });
    } catch(_e) {}

    // Remove any redundant session restoration logic
    if (typeof SessionManager !== "undefined") {
        // Delegate session restoration to SessionManager
        SessionManager.loadFromSession();
    } else {
        console.error("⚠️ SessionManager is not defined. Ensure SessionManager.js is loaded before app.js.");
    }
});

// Bootstrap CURRENT_PATIENT_DFN from server session on load
document.addEventListener('DOMContentLoaded', async () => {
    try {
        // Try sessionStorage first to avoid a flash of "No patient"
        const cached = sessionStorage.getItem('CURRENT_PATIENT_DFN');
        if (cached) { try { window.CURRENT_PATIENT_DFN = cached; } catch(_e) {} }
        let meta = null;
        try {
            if (window.PatientContext && typeof window.PatientContext.get === 'function') {
                meta = await window.PatientContext.get();
            }
        } catch(_e){}
        if (meta) {
            const dfn = meta && (meta.dfn || meta.patient_dfn || meta.patientDFN);
            if (dfn) {
                try { window.CURRENT_PATIENT_DFN = dfn; } catch(_e) {}
                try { sessionStorage.setItem('CURRENT_PATIENT_DFN', String(dfn)); } catch(_e) {}
            }
        }
    } catch(_e) {}
});

// Defensive transcript clearing during patient switch
try {
    window.addEventListener('PATIENT_SWITCH_START', async () => {
        try { lastServerTranscript = ""; } catch(_e){}
        const rt = document.getElementById('rawTranscript');
        if (rt) { rt.value = ''; try { rt.dispatchEvent(new Event('input', { bubbles: true })); } catch(_e){} }
        // Reflect recording state off in UI proactively; orchestrator will also stop server side
        try {
            const isRec = await getRecordingStatus();
            if (isRec) {
                await setRecordBtnState(false);
            }
        } catch(_e){}
    });
    window.addEventListener('workspace:patientSwitched', () => {
        const rt = document.getElementById('rawTranscript');
        if (rt && rt.value && rt.value.trim().length) {
            rt.value = ''; try { rt.dispatchEvent(new Event('input', { bubbles: true })); } catch(_e){}
        }
    });
} catch(_e){}

// --- Global Exit (clear patient data and return to home) ---
async function exitApp() {
    try {
        if (!confirm("Exit without saving? Archived transcripts remain. All unsaved session data will be cleared.")) {
            return;
        }

        // Stop auto-save if active and clear archive continuation
        try { 
            const maybePromise = stopAutoSaveLoop && stopAutoSaveLoop();
            if (maybePromise && typeof maybePromise.then === 'function') { await maybePromise; }
            localStorage.removeItem('ssva:currentArchiveName'); 
        } catch(_e){}

        // Give a brief moment for any inflight save to settle
        try { await new Promise(r => setTimeout(r, 120)); } catch(_e){}

        // Stop recording if active (server also attempts to stop)
        try {
            const isRec = await getRecordingStatus();
            if (isRec) {
                try { if (window.ScribeRuntime && typeof window.ScribeRuntime.stop === 'function') await window.ScribeRuntime.stop(); } catch(_e){}
                try { recordingChannel && recordingChannel.postMessage({ isRecording: false }); } catch(_e){}
                try { await setRecordBtnState(false); } catch(_e){}
            }
        } catch (e) { console.warn('Stop recording warning:', e); }

        // Clear server-side session and live transcript, close any sockets
        try {
            await fetch('/exit', { method: 'POST', headers: { 'X-CSRF-Token': _csrf() }, credentials: 'same-origin', cache: 'no-store', referrerPolicy: 'no-referrer' });
        } catch (e) { console.warn('Server exit warning:', e); }

        // Clear client-side app/session state
        // Removed redundant SessionManager.clearSession() call to avoid CSRF 403 after /exit clears the server session
        
        try { window.exploreQAHistory = []; } catch {}
        try { window.SessionState = {}; } catch {}
        try { if (recordingChannel && recordingChannel.close) recordingChannel.close(); } catch {}

        // Clear storages
        try { localStorage && localStorage.clear(); } catch {}
        try { sessionStorage && sessionStorage.clear(); } catch {}

        // Clear Cache Storage
        try {
            if (window.caches && caches.keys) {
                const names = await caches.keys();
                await Promise.all(names.map(n => caches.delete(n)));
            }
        } catch (e) { console.warn('Cache clear warning:', e); }

        // Clear IndexedDB databases (best-effort)
        try {
            if (window.indexedDB && indexedDB.databases) {
                const dbs = await indexedDB.databases();
                await Promise.all((dbs || []).map(db => db && db.name ? new Promise((res) => { const req = indexedDB.deleteDatabase(db.name); req.onsuccess = req.onerror = req.onblocked = () => res(); }) : Promise.resolve()));
            }
        } catch (e) { console.warn('IndexedDB clear warning:', e); }

        // Navigate to Exit page
        window.location.replace('/exit_page');
    } catch (err) {
        console.error('Exit error:', err);
        // Fallback: navigate to Exit page
        window.location.replace('/exit_page');
    }
}

// Expose exitApp globally for dropdown menus
try { window.exitApp = exitApp; } catch(_e){}

function getBoolSetting(key, def = false) {
    try { const v = localStorage.getItem(key); return v === null ? def : v === '1'; } catch { return def; }
}

async function autoSaveTick() {
    try {
        if (typeof SessionManager !== 'undefined' && SessionManager.saveToSession) {
            await SessionManager.saveToSession();
        }
        // Only persist to archive if we have meaningful content (transcript, scribe notes, or workspace draft note)
        const transcriptEl = document.getElementById('rawTranscript');
        const visitNotesEl = document.getElementById('visitNotes');
        const feedbackReplyEl = document.getElementById('feedbackReply');
        const avsEl = document.getElementById('patientInstructionsBox');
        let hasTranscript = !!(transcriptEl && transcriptEl.value && transcriptEl.value.trim().length);
        const hasVisitNotes = !!(visitNotesEl && visitNotesEl.value && visitNotesEl.value.trim().length);
        const hasWorkspaceDraft = !!(feedbackReplyEl && feedbackReplyEl.innerText && feedbackReplyEl.innerText.trim().length);
        const hasAvs = !!(avsEl && avsEl.value && avsEl.value.trim().length);

        // Fallback: check server live transcript via SessionManager if DOM field is absent/empty
        if (!hasTranscript && typeof SessionManager !== 'undefined' && SessionManager.getTranscript) {
            try {
                const t = await SessionManager.getTranscript(0);
                hasTranscript = !!(t && String(t).trim().length);
            } catch(_e) {}
        }

        const archiveName = localStorage.getItem('ssva:currentArchiveName');
        if (archiveName && (hasTranscript || hasVisitNotes || hasWorkspaceDraft || hasAvs) && typeof SessionManager !== 'undefined' && SessionManager.saveFullSession) {
            await SessionManager.saveFullSession(archiveName);
        }
    } catch (e) {
        console.warn('Auto-save tick failed', e);
    }
}

function startAutoSaveLoop() {
    // Guard by setting
    if (!getBoolSetting('ssva:autoSaveArchives', true)) {
        stopAutoSaveLoop();
        return;
    }
    if (autoSaveIntervalId) return; // already running
    // Save immediately once
    autoSaveTick();
    autoSaveIntervalId = setInterval(autoSaveTick, 5000);
}

function stopAutoSaveLoop() {
    if (autoSaveIntervalId) {
        clearInterval(autoSaveIntervalId);
        autoSaveIntervalId = null;
    }
}

// Back-compat name used by selection flows
async function startAutoArchiveForCurrentPatient() { startAutoSaveLoop(); }

try { window.startAutoArchiveForCurrentPatient = startAutoArchiveForCurrentPatient; } catch(_e){}
try { window.stopAutoSaveLoop = stopAutoSaveLoop; } catch(_e){}

// Start auto-save loop on load if enabled
document.addEventListener('DOMContentLoaded', () => {
    try { startAutoSaveLoop(); } catch(_e){}
});