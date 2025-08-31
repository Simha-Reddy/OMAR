// --- State & globals ---
let chatHistory = [];
let isRecordingActive = false;
let lastServerTranscript = "";
let audioContext, analyser, microphone, animationId;
let autoSaveIntervalId = null;

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
    if (!navigator.mediaDevices?.getUserMedia) return;

    navigator.mediaDevices.getUserMedia({ audio: true })
        .then(stream => {
            audioContext = new (window.AudioContext || window.webkitAudioContext)();
            analyser = audioContext.createAnalyser();
            microphone = audioContext.createMediaStreamSource(stream);
            microphone.connect(analyser);

            const dataArray = new Uint8Array(analyser.frequencyBinCount);
            function animate() {
                analyser.getByteTimeDomainData(dataArray);
                const volume = Math.max(...dataArray) - 128;
                const intensity = Math.min(Math.abs(volume) / 128, 1);
                const glow = Math.floor(intensity * 50);
                btn.style.boxShadow = `0 0 ${glow}px red`;
                animationId = requestAnimationFrame(animate);
            }
            animate();
        })
        .catch(err => console.error("Mic access error:", err));
}

function stopMicFeedback() {
    if (animationId) cancelAnimationFrame(animationId);
    if (audioContext) audioContext.close();
    document.getElementById("recordBtn").style.boxShadow = "none";
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
    const res = await fetch('/scribe/recording_status');
    const data = await res.json();
    return data.is_recording;
}

async function setRecordBtnState(isRecording) {
    const btn = document.getElementById('recordBtn');
    if (!btn) return;
    btn.textContent = isRecording ? 'Stop Recording' : 'Start Recording';
    btn.classList.toggle('stop-button', isRecording);
    btn.classList.toggle('start-button', !isRecording);

    if (isRecording) {
        startMicFeedback(); // Start glow effect
        isRecordingActive = true;
        requestWakeLock();
    } else {
        stopMicFeedback(); // Stop glow effect
        isRecordingActive = false;
        releaseWakeLock();
    }
}

async function toggleRecording() {
    const isRecording = await getRecordingStatus();
    if (isRecording) {
        await fetch('/scribe/stop_recording', { method: 'POST' });
        recordingChannel.postMessage({ isRecording: false });
        await setRecordBtnState(false);
    } else {
        await fetch('/scribe/start_recording', { method: 'POST' });
        recordingChannel.postMessage({ isRecording: true });
        await setRecordBtnState(true);
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

    // --- Recording Button (all pages with recordBtn) ---
    const btn = document.getElementById('recordBtn');
    if (btn) {
        const isRecording = await getRecordingStatus();
        setRecordBtnState(isRecording);
        btn.onclick = toggleRecording;
    }

    // Remove any redundant session restoration logic
    if (typeof SessionManager !== "undefined") {
        // Delegate session restoration to SessionManager
        SessionManager.loadFromSession();
    } else {
        console.error("⚠️ SessionManager is not defined. Ensure SessionManager.js is loaded before app.js.");
    }
});

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
                await fetch('/scribe/stop_recording', { method: 'POST' });
                recordingChannel && recordingChannel.postMessage({ isRecording: false });
                await setRecordBtnState(false);
            }
        } catch (e) { console.warn('Stop recording warning:', e); }

        // Clear server-side session and live transcript, close any sockets
        try {
            await fetch('/exit', { method: 'POST' });
        } catch (e) { console.warn('Server exit warning:', e); }

        // Clear client-side app/session state
        try { window.exploreQAHistory = []; } catch {}
        try { if (typeof SessionManager !== 'undefined') { await SessionManager.clearSession(); } } catch {}

        // Close BroadcastChannel
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
        // If continuing an existing archive restore, also update that file on disk
        const archiveName = localStorage.getItem('ssva:currentArchiveName');
        if (archiveName && typeof SessionManager !== 'undefined' && SessionManager.saveFullSession) {
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