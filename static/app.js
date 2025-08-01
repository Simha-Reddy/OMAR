// --- State & globals ---
let chatHistory = [];
let isRecordingActive = false;
let lastServerTranscript = "";
let audioContext, analyser, microphone, animationId;
// --- Wake Lock ---
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

// End Session Button
const endBtn = document.getElementById("endSessionBtn");
if (endBtn) {
    endBtn.addEventListener("click", async () => {
        console.log("End-Session button clicked");
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

        try {
            await SessionManager.endSession(sessionName);
            window.location.reload();
        } catch (err) {
            alert(err.message || "Failed to save session.");
        }
    });
} else {
    console.warn("⚠️ endSessionBtn not found in DOM!");
}

// BroadcastChannel for syncing state across tabs
const recordingChannel = new BroadcastChannel('recording_channel');

async function getRecordingStatus() {
    const res = await fetch('/recording_status');
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
        await fetch('/stop_recording', { method: 'POST' });
        recordingChannel.postMessage({ isRecording: false });
        await setRecordBtnState(false);
    } else {
        await fetch('/start_recording', { method: 'POST' });
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