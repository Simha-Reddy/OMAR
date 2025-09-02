document.addEventListener("DOMContentLoaded", async () => {
    console.log("Initializing Scribe page...");

    // Restore session data
    if (typeof SessionManager !== "undefined") {
        try {
            await SessionManager.loadFromSession();
            console.log("Session data restored from server.");
        } catch (err) {
            console.error("Failed to restore session data from server:", err);
        }
    }

    // --- AUTOSAVE on input changes ---
    const autosaveFields = [
        "visitNotes",
        "patientInstructionsBox",
        "promptPreview",
        "feedbackInput"
    ];
    autosaveFields.forEach(id => {
        const el = document.getElementById(id);
        if (el) {
            el.addEventListener("input", async () => {
                if (typeof SessionManager !== "undefined" && SessionManager.saveToSession) {
                    await SessionManager.saveToSession();
                }
            });
        }
    });

    // --- Patient Instructions ---
    const genBtn = document.getElementById("generatePatientInstructionsBtn");
    const printBtn = document.getElementById("printPatientInstructionsBtn");
    const instructionsBox = document.getElementById("patientInstructionsBox");
    const previewDiv = document.getElementById("patientInstructionsPreview");

    if (instructionsBox && previewDiv) {
        // Live preview of Markdown
        instructionsBox.addEventListener("input", function () {
            previewDiv.innerHTML = marked.parse(instructionsBox.value);
        });
    }

    if (genBtn && instructionsBox) {
        genBtn.onclick = generatePatientInstructions;
    }

    if (printBtn && instructionsBox) {
        printBtn.onclick = async function () {
            const html = previewDiv ? previewDiv.innerHTML : "";
            const win = window.open("", "_blank");
            win.document.write(`
                <html>
                <head>
                    <title>Patient Instructions</title>
                    <style>
                        body { font-family: 'Segoe UI', Arial, sans-serif; margin: 40px; }
                        h2 { color: #3498db; }
                        .markdown-body { font-size: 1.1em; }
                    </style>
                </head>
                <body>
                    <h2>Patient Instructions</h2>
                    <div class="markdown-body">${html}</div>
                </body>
                </html>
            `);
            win.document.close();
            win.focus();
            setTimeout(() => win.print(), 500);
        };
    }

    // --- Poll Scribe Status ---
    // Removed immediate call; delay first poll to avoid transient 404
    setTimeout(pollScribeStatus, 500);
    setInterval(pollScribeStatus, 3000);

    // --- Periodic AUTOSAVE every 10 seconds ---
    setInterval(async () => {
        if (typeof SessionManager !== "undefined" && SessionManager.saveToSession) {
            await SessionManager.saveToSession();
        }
    }, 10000);

    // --- Prompt Selector ---
    loadPrompts();

    // --- Auto-write flow triggered via /scribe?autowrite=1 ---
    (function(){
        function shouldAutoWrite(){
            try { return new URLSearchParams(window.location.search).has('autowrite'); } catch(_e){ return false; }
        }
        async function tryAutoWrite(attempt){
            attempt = attempt || 0;
            if (!shouldAutoWrite()) return;
            const preview = document.getElementById('promptPreview');
            // Wait for promptPreview to be populated (fetch in loadPrompts is async)
            if (preview && (!preview.value || !preview.value.trim())){
                if (attempt < 12){ // ~3.6s max wait
                    return setTimeout(()=>tryAutoWrite(attempt+1), 300);
                }
            }
            // 1) Generate patient instructions
            try { await generatePatientInstructions(); } catch(_e){}
            // 2) Then create clinic note (slight delay to avoid contention)
            setTimeout(()=>{ try { createNote(); } catch(_e){} }, 600);
        }
        // Kick off shortly after DOM ready so prompts can start loading
        setTimeout(()=>tryAutoWrite(0), 300);
    })();
});

// --- Helper: resolve [[...]] placeholders with data from our /fhir endpoints ---
async function _getPatientMetaOnce(){
  try{
    const r = await fetch('/get_patient', { cache:'no-store' });
    if(!r.ok) return null;
    const j = await r.json();
    if(j && j.dfn) return j;
  }catch(_e){}
  return null;
}

function _formatMedsList(meds){
  try{
    if(!Array.isArray(meds) || meds.length===0) return 'None';
    const lines = meds.map(m=>{
      const name = m && m.name ? String(m.name) : '';
      const parts = [];
      if(m && m.dose) parts.push(String(m.dose));
      if(m && m.route) parts.push(String(m.route));
      if(m && m.frequency) parts.push(String(m.frequency));
      const tail = parts.length ? ' — ' + parts.join(' ') : '';
      return `- ${name}${tail}`;
    });
    return lines.join('\n');
  }catch(_e){ return ''; }
}

function _formatProblemsList(problems){
  try{
    if(!Array.isArray(problems) || problems.length===0) return 'None';
    const lines = problems.map(p=>{
      const name = p && p.name ? String(p.name) : '';
      const act = (p && p.active) ? 'active' : 'inactive';
      return `- ${name} (${act})`;
    });
    return lines.join('\n');
  }catch(_e){ return ''; }
}

function _formatOrdersList(orders){
  try{
    if(!Array.isArray(orders) || orders.length===0) return 'None';
    const lines = orders.map(o=>{
      const d = o && o.date ? String(o.date).slice(0,10) : '';
      const typ = (o && o.type) ? String(o.type) : '';
      const nm = (o && o.name) ? String(o.name) : '';
      const st = (o && o.current_status) ? String(o.current_status) : '';
      const tail = st ? ` — ${st}` : '';
      return `- ${d}: [${typ}] ${nm}${tail}`;
    });
    return lines.join('\n');
  }catch(_e){ return ''; }
}

function _ordersTypeAlias(s){
  const v = String(s||'').trim().toLowerCase();
  if(['med','meds','medications','rx','pharmacy'].includes(v)) return 'meds';
  if(['lab','labs','laboratory'].includes(v)) return 'labs';
  return 'all';
}

function _ordersStatusAlias(s){
  const v = String(s||'').trim().toLowerCase();
  if(['active','a'].includes(v)) return 'active';
  if(['pending','p'].includes(v)) return 'pending';
  if(['current','actpend','active+pending','ap','c'].includes(v)) return 'current';
  if(['all','*'].includes(v)) return 'all';
  return 'current';
}

function _parseOrdersArgs(argStr){
  // Supports forms:
  //   "active", "active meds", "active meds 30"
  //   "status=active,type=meds,days=30"
  //   "since=YYYY-MM-DD" or "date=YYYY-MM-DD"
  // Returns { status, type, days }
  let status = 'current';
  let type = 'all';
  let days = 7;
  const s = String(argStr||'').trim();
  if(!s) return {status, type, days};
  // key=value style
  if(s.includes('=') || s.includes(',')){
    const parts = s.split(/[\s,]+/).filter(Boolean);
    for(const part of parts){
      const [kRaw,vRaw] = part.split('=');
      const k = (kRaw||'').toLowerCase();
      const v = (vRaw||'').trim();
      if(k==='status') status = _ordersStatusAlias(v);
      else if(k==='type' || k==='category') type = _ordersTypeAlias(v);
      else if(k==='days'){
        const n = parseInt(v,10); if(Number.isFinite(n) && n>0) days = n;
      } else if(k==='since' || k==='date'){
        const dt = new Date(v);
        if(!isNaN(dt.getTime())){
          const now = new Date();
          const diffMs = Math.max(0, now - dt);
          days = Math.max(1, Math.ceil(diffMs / (1000*60*60*24)));
        }
      }
    }
    return {status, type, days};
  }
  // space separated short form
  const parts = s.split(/[\s/]+/).filter(Boolean);
  if(parts[0]) status = _ordersStatusAlias(parts[0]);
  if(parts[1]) type   = _ordersTypeAlias(parts[1]);
  if(parts[2]){
    const d = parts[2].toLowerCase();
    if(d.endsWith('d')){
      const n = parseInt(d.slice(0,-1),10);
      if(Number.isFinite(n) && n>0) days = n;
    } else {
      const n = parseInt(d,10);
      if(Number.isFinite(n) && n>0) days = n;
      else {
        const dt = new Date(parts[2]);
        if(!isNaN(dt.getTime())){
          const now = new Date();
          const diffMs = Math.max(0, now - dt);
          days = Math.max(1, Math.ceil(diffMs / (1000*60*60*24)));
        }
      }
    }
  }
  return {status, type, days};
}

async function _resolveFhirToken(token){
  const t = String(token||'').trim().toLowerCase();
  // Map friendly tokens to concrete endpoints
  if(t === 'meds/active' || t === 'medications/active'){
    try{
      const r = await fetch('/fhir/medications?status=active', { cache:'no-store' });
      if(!r.ok) return null;
      const j = await r.json();
      const meds = (j && Array.isArray(j.medications)) ? j.medications : [];
      return _formatMedsList(meds);
    }catch(_e){ return null; }
  }
  if(t === 'meds' || t === 'medications'){
    try{
      const r = await fetch('/fhir/medications', { cache:'no-store' });
      if(!r.ok) return null;
      const j = await r.json();
      const meds = (j && Array.isArray(j.medications)) ? j.medications : [];
      return _formatMedsList(meds);
    }catch(_e){ return null; }
  }
  if(t === 'problems' || t === 'problems/active'){
    const url = t === 'problems/active' ? '/fhir/problems?status=active' : '/fhir/problems';
    try{
      const r = await fetch(url, { cache:'no-store' });
      if(!r.ok) return null;
      const j = await r.json();
      const arr = (j && Array.isArray(j.problems)) ? j.problems : [];
      return _formatProblemsList(arr);
    }catch(_e){ return null; }
  }
  if(t === 'age'){
    try{
      const r = await fetch('/session_data', { cache:'no-store' });
      if(!r.ok) return null;
      const j = await r.json();
      const pr = j && j.patient_record;
      if(!pr || !Array.isArray(pr.entry)) return null;
      const p = pr.entry.find(e=>e.resource && e.resource.resourceType==='Patient');
      const dob = p && p.resource && p.resource.birthDate;
      if(!dob) return null;
      // Compute age from DOB (YYYY, YYYY-MM, or YYYY-MM-DD)
      let y, m=1, d=1;
      if(/^\d{4}$/.test(dob)){ y = +dob; }
      else if(/^\d{4}-\d{2}$/.test(dob)){ const parts = dob.split('-').map(Number); y = parts[0]; m = parts[1]; }
      else if(/^\d{4}-\d{2}-\d{2}$/.test(dob)){ const parts = dob.split('-').map(Number); y = parts[0]; m = parts[1]; d = parts[2]; }
      else { const dt = new Date(dob); if(isNaN(dt.getTime())) return null; y = dt.getFullYear(); m = dt.getMonth()+1; d = dt.getDate(); }
      const today = new Date();
      let age = today.getFullYear() - y;
      const hadBD = ((today.getMonth()+1) > m) || (((today.getMonth()+1) === m) && (today.getDate() >= d));
      if(!hadBD) age -= 1;
      if(!isFinite(age) || age < 0 || age > 120) return null;
      return String(age);
    }catch(_e){ return null; }
  }
  // Orders token: [[orders]], [[orders:active meds 30]], [[orders:status=active,type=meds,days=30]], [[orders/active/labs/14]]
  if(t.startsWith('orders')){
    try{
      let status = 'current', type = 'all', days = 7;
      if(t.includes(':')){
        const argStr = t.split(':',2)[1] || '';
        const parsed = _parseOrdersArgs(argStr);
        status = parsed.status; type = parsed.type; days = parsed.days;
      } else if(t.includes('/')){
        const segs = t.split('/').filter(Boolean); // ['orders','active','meds','30']
        if(segs[1]) status = _ordersStatusAlias(segs[1]);
        if(segs[2]) type   = _ordersTypeAlias(segs[2]);
        if(segs[3]){
          const n = parseInt(segs[3],10); if(Number.isFinite(n) && n>0) days = n;
        }
      }
      const path = `/fhir/orders/${encodeURIComponent(status)}/${encodeURIComponent(type)}/${encodeURIComponent(String(days))}`;
      const r = await fetch(path, { cache:'no-store' });
      if(!r.ok) return null;
      const j = await r.json();
      const arr = (j && Array.isArray(j.orders)) ? j.orders : [];
      return _formatOrdersList(arr);
    }catch(_e){ return null; }
  }
  // Unknown: do not change
  return null;
}

async function replaceFhirPlaceholders(text){
  try{
    const s = String(text ?? '');
    if(!s.includes('[[')) return s;
    // Make sure a patient is loaded; if not, leave placeholders alone
    const meta = await _getPatientMetaOnce();
    if(!meta || !meta.dfn) return s;
    // Find unique tokens
    const re = /\[\[\s*([^\]\[]+?)\s*\]\]/g;
    const tokens = new Map();
    let m;
    while((m = re.exec(s))){ const raw = m[0]; const tok = m[1]; if(!tokens.has(raw)) tokens.set(raw, tok); }
    if(tokens.size === 0) return s;
    // Resolve all tokens
    const results = await Promise.all(Array.from(tokens.entries()).map(async ([raw, tok])=>{
      const val = await _resolveFhirToken(tok);
      return [raw, val];
    }));
    // Apply replacements
    let out = s;
    for(const [raw, val] of results){ if(typeof val === 'string' && val.length){ out = out.split(raw).join(val); } }
    return out;
  }catch(_e){ return String(text ?? ''); }
}

async function replaceFhirPlaceholdersSelective(text){
  try{
    const s = String(text ?? '');
    if(!s.includes('[[')) return s;
    // Ensure patient context exists
    const meta = await _getPatientMetaOnce();
    if(!meta || !meta.dfn) return s;
    const re = /\[\[\s*([^\]\[]+?)\s*\]\]/g;
    let out = '';
    let last = 0;
    let m;
    while((m = re.exec(s))){
      const start = m.index;
      const end = start + m[0].length;
      const isBraced = (start > 0 && s[start-1] === '{') && (end < s.length && s[end] === '}');
      out += s.slice(last, start);
      if(isBraced){
        // Leave token as-is
        out += m[0];
      } else {
        const tok = m[1];
        const val = await _resolveFhirToken(tok);
        out += (typeof val === 'string' && val.length) ? val : m[0];
      }
      last = end;
    }
    out += s.slice(last);
    return out;
  }catch(_e){ return String(text ?? ''); }
}

// --- Poll Scribe Status ---
function pollScribeStatus() {
    const transcriptEl = document.getElementById("rawTranscript");
    if (!transcriptEl) return;

    fetch('/scribe/live_transcript')
        .then(res => {
            if (!res.ok) throw new Error('live_transcript HTTP ' + res.status);
            return res.text();
        })
        .then(text => {
            transcriptEl.value = text;
            transcriptEl.scrollTop = transcriptEl.scrollHeight;
        })
        .catch(err => console.error('Error polling live transcript:', err));

    // (Optional) Keep status indicator logic if you want
    fetch('/scribe/status')
        .then(r => r.json())
        .then(data => {
            const statusEl = document.getElementById('statusIndicator');
            if (statusEl) {
                if (data.is_recording) {
                    statusEl.textContent = 'Recording...';
                } else if (data.pending_chunks > 0) {
                    statusEl.textContent = 'Transcribing...';
                } else {
                    statusEl.textContent = '';
                }
            }
        })
        .catch(err => console.error('Error polling status:', err));
}

// --- Create Note & chat feedback ---
async function createNote() {
    console.log("createNote fired");

    // Persist the currently selected prompt as last used
    try {
        const sel = document.getElementById("promptSelector");
        if (sel && sel.value) localStorage.setItem("lastPrompt", sel.value);
    } catch (_e) {}

    const transcript = document.getElementById("rawTranscript").value;
    const visitNotes  = document.getElementById("visitNotes").value;
    const promptRaw = document.getElementById("promptPreview").value;    // <-- full prompt (may contain [[...]] tokens)
    const promptText = await replaceFhirPlaceholdersSelective(promptRaw);
    const noteBox    = document.getElementById("feedbackReply");

    noteBox.innerText = "Loading…";

    const res = await fetch('/scribe/create_note', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
            transcript:   transcript,
            visit_notes:   visitNotes,
            prompt_text:  promptText
        })
    });

    const data = await res.json();
    // Replace [[...]] proxies with live FHIR data before displaying
    const finalNote = await replaceFhirPlaceholders(data.note || '');
    noteBox.innerText  = finalNote;

    // NEW: Auto-create a draft email if enabled in Settings (replaces Teams deep link)
    try {
        // Hydrate from server prefs if not present in localStorage
        try {
            const needEmail = !localStorage.getItem('ssva:emailAddress');
            const needAuto  = localStorage.getItem('ssva:autoDraftEmail') === null;
            const needForce = localStorage.getItem('ssva:emailForceOWA') === null;
            if (needEmail || needAuto || needForce) {
                const resp0 = await fetch('/user_prefs', { cache: 'no-store' });
                if (resp0.ok) {
                    const prefs = await resp0.json();
                    if (prefs && typeof prefs === 'object') {
                        if (typeof prefs.email_address === 'string') {
                            localStorage.setItem('ssva:emailAddress', prefs.email_address || '');
                        }
                        if ('auto_draft_email' in prefs) {
                            localStorage.setItem('ssva:autoDraftEmail', prefs.auto_draft_email ? '1' : '0');
                        }
                        if ('email_force_owa' in prefs) {
                            localStorage.setItem('ssva:emailForceOWA', prefs.email_force_owa ? '1' : '0');
                        }
                    }
                }
            }
        } catch(_e) {}

        const email = localStorage.getItem('ssva:emailAddress') || '';
        const autoDraft = localStorage.getItem('ssva:autoDraftEmail') === '1';
        const forceOWA  = localStorage.getItem('ssva:emailForceOWA') === '1';
        if (autoDraft && email.includes('@') && finalNote && finalNote.trim()) {
            const subject = buildNoteEmailSubject();
            const resp = await fetch('/email/create_draft', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ to: email, subject, body: finalNote, force_owa: forceOWA })
            });
            const rj = await resp.json().catch(()=>({}));
            if (rj && rj.status === 'ok') {
                try { showToast('Draft email created in Outlook Drafts.'); } catch(_e){ alert('Draft email created in Outlook Drafts.'); }
            } else if (rj && rj.status === 'fallback' && rj.url) {
                // Try to avoid truncation limits in Outlook Web by copying the full note
                let copied = false;
                try {
                    if (navigator.clipboard && finalNote) {
                        await navigator.clipboard.writeText(finalNote);
                        copied = true;
                    }
                } catch(_e) { copied = false; }

                if (copied) {
                    try { showToast('Full note copied. Opening Outlook Web – paste into the email body.'); } catch(_e){}
                    // Request a clean compose link with empty body to avoid long URL truncation
                    try {
                        const resp2 = await fetch('/email/create_draft', {
                            method: 'POST',
                            headers: { 'Content-Type': 'application/json' },
                            body: JSON.stringify({ to: email, subject, body: '', force_owa: true })
                        });
                        const rj2 = await resp2.json().catch(()=>({}));
                        const url = (rj2 && rj2.url) ? rj2.url : rj.url;
                        window.open(url, '_blank', 'noopener');
                    } catch(_e){
                        window.open(rj.url, '_blank', 'noopener');
                    }
                } else {
                    try { showToast('Opening Outlook Web to compose draft (content may be truncated).'); } catch(_e){}
                    window.open(rj.url, '_blank', 'noopener');
                }
            }
        }
    } catch(_e) { /* ignore */ }

    // Autosave after feedback reply is updated
    if (typeof SessionManager !== "undefined" && SessionManager.saveToSession) {
        await SessionManager.saveToSession();
    }
    chatHistory        = data.messages || [
        { role: "system",    content: "Note‐edit session" },
        { role: "assistant", content: finalNote }
    ];
}

// Helper: quick subject with patient name/time if available
function buildNoteEmailSubject(){
    try{
        const now = new Date();
        const hh = String(now.getHours()).padStart(2,'0');
        const mm = String(now.getMinutes()).padStart(2,'0');
        let patient = '';
        // Try to pull from session patient meta if present
        // This route returns { patient_record: {...} } among other fields
        // We'll sync call best-effort (non-blocking subject fallback)
        // Note: keeping it simple to avoid extra async fetch here
        if (window.SessionManager && SessionManager.state && SessionManager.state.patient_meta && SessionManager.state.patient_meta.name){
            patient = String(SessionManager.state.patient_meta.name);
        }
        const tail = patient ? ` for ${patient}` : '';
        return `Clinic note draft ${hh}:${mm}${tail}`;
    }catch(_e){ return 'Clinic note draft'; }
}

// Lightweight toast helper (no dependency). Optional.
function showToast(msg){
    try{
        const div = document.createElement('div');
        div.textContent = msg;
        div.style.cssText = 'position:fixed;bottom:20px;left:50%;transform:translateX(-50%);background:#323232;color:#fff;padding:10px 16px;border-radius:6px;z-index:9999;opacity:0.95;box-shadow:0 2px 8px rgba(0,0,0,0.3);';
        document.body.appendChild(div);
        setTimeout(()=>{ try{ document.body.removeChild(div); }catch(_e){} }, 2200);
    }catch(_e){ alert(msg); }
}

async function submitFeedback() {
  const input    = document.getElementById("feedbackInput");
  const replyDiv = document.getElementById("feedbackReply");
  const userMsg  = input.value.trim();
  if (!userMsg) return;

  // 1) Disable the input and show loading text
  input.disabled     = true;
  const oldPlaceholder = input.placeholder;
  input.placeholder  = "Loading AI response…";
  replyDiv.innerText = "Loading…";

  // 2) Send the request
  chatHistory.push({ role: 'user', content: userMsg });
  let data;
  try {
    const res = await fetch('/scribe/chat_feedback', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ messages: chatHistory })
    });
    data = await res.json();
  } catch (err) {
    replyDiv.innerText = "Error: " + err.message;
    data = { reply: "" };
  }

  // 3) Display the reply
  if (data.reply) {
    chatHistory.push({ role: 'assistant', content: data.reply });
    replyDiv.innerText = data.reply;
  }

  // 4) Re-enable the input and restore placeholder
  input.disabled    = false;
  input.placeholder = oldPlaceholder;
  input.value       = "";
  input.focus();
}


// --- Copy final note ---
function copyFinalNote() {
  const txt = document.getElementById("feedbackReply").innerText;
  navigator.clipboard.writeText(txt)
    .then(() => alert("Final note copied!"))
    .catch(() => alert("Copy failed"));
}

// --- Prompt & custom template loaders ---
let promptData = {};  // <-- store all name→text mappings

function loadPrompts() {
    fetch("/get_prompts")
        .then(r => r.json())
        .then(data => {
            const sel = document.getElementById("promptSelector");
            const preview = document.getElementById("promptPreview");
            if (!sel || !preview) {
                console.error("promptSelector or promptPreview not found!");
                return;
            }

            // Clear out any old options
            sel.innerHTML = "";

            // Populate options
            for (let name in data) {
                const opt = document.createElement("option");
                opt.value = name;
                opt.text = name;
                sel.appendChild(opt);
            }

            // Determine initial selection:
            // 1) previously used (localStorage)
            // 2) "Primary Care Progress Note" if available
            // 3) first available option
            const stored = localStorage.getItem("lastPrompt");
            let initialName = null;
            if (stored && data[stored]) {
                initialName = stored;
            } else if (data["Primary Care Progress Note"]) {
                initialName = "Primary Care Progress Note";
            } else {
                const keys = Object.keys(data);
                initialName = keys.length ? keys[0] : "";
            }

            // Apply initial selection and preview
            if (initialName) {
                sel.value = initialName;
                preview.value = data[initialName] || "";
                // Persist so next load uses this default
                localStorage.setItem("lastPrompt", initialName);
            }

            // Update preview on selection change
            sel.addEventListener("change", () => {
                const v = sel.value;
                preview.value = data[v] || "";
                localStorage.setItem("lastPrompt", v);
            });
        })
        .catch(err => console.error("Error loading prompts:", err));
}

function saveCustomTemplate() {
    const name = document.getElementById("customTemplateName").value;
    const text = document.getElementById("customTemplateText").value;
    fetch("/save_template", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name, text })
    })
    .then(response => {
        if (response.redirected) {
            window.location.href = response.url;
        } else {
            alert("Saved.");
        }
    });
}

let customTemplates = {};  // name → text

function loadCustomTemplateList() {
  const ul = document.getElementById("customTemplateList");
  ul.innerHTML = "";

  fetch("/list_custom_templates")
    .then(r => r.json())
    .then(names => {
      names.forEach(name => {
        // list item
        const li = document.createElement("li");
        li.style.marginBottom = "8px";

        // show button
        const showBtn = document.createElement("button");
        showBtn.textContent = "Show";
        showBtn.style.marginRight = "8px";

        // when clicked, fetch & display the template
        showBtn.addEventListener("click", () => {
          // if we already loaded it, just toggle visibility
          if (customTemplates[name]) {
            editor.style.display = editor.style.display === "none" ? "block" : "none";
            textarea.value   = customTemplates[name];
            return;
          }

          // else fetch it
          fetch(`/load_template/${encodeURIComponent(name)}`)
            .then(res => res.text())
            .then(text => {
              customTemplates[name] = text;
              textarea.value       = text;
              editor.style.display = "block";
            })
            .catch(err => console.error("Error loading template:", err));
        });

        // name label
        const nameSpan = document.createElement("span");
        nameSpan.textContent = name;
        nameSpan.style.marginRight = "12px";

        // hidden editor div
        const editor = document.createElement("div");
        editor.style.display = "none";
        editor.style.marginTop = "6px";

        // textarea for preview/edit
        const textarea = document.createElement("textarea");
        textarea.rows = 6;
        textarea.style.width = "100%";
        textarea.value = "";  // filled in on demand

        // save + delete buttons
        const saveBtn = document.createElement("button");
        saveBtn.textContent = "Save";
        saveBtn.style.marginRight = "6px";
        saveBtn.addEventListener("click", () => {
          fetch("/save_template", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ name, text: textarea.value })
          }).then(() => {
            customTemplates[name] = textarea.value;
            alert("Saved.");
          });
        });

        const deleteBtn = document.createElement("button");
        deleteBtn.textContent = "Delete";
        deleteBtn.addEventListener("click", () => {
          if (!confirm(`Delete "${name}"?`)) return;
          fetch(`/delete_template/${encodeURIComponent(name)}`, { method: "DELETE" })
            .then(() => loadCustomTemplateList());
        });

        editor.append(textarea, saveBtn, deleteBtn);
        li.append(showBtn, nameSpan, editor);
        ul.appendChild(li);
      });
    })
    .catch(err => console.error("Error loading custom templates:", err));
}

async function generatePatientInstructions() {
    const instructionsBox = document.getElementById("patientInstructionsBox");
    const previewDiv = document.getElementById("patientInstructionsPreview");
    instructionsBox.value = "Loading patient instructions...";
    const transcript = document.getElementById("rawTranscript").value;
    const visitNotes = document.getElementById("visitNotes").value;

    // Fetch the patient instructions prompt template
    const promptTemplate = await fetch('/load_patient_instructions_prompt')
        .then(res => res.ok ? res.text() : "");

    // Add instruction for Markdown output
    const mdInstruction = "Please format your output as Markdown (using -, *, **, etc. as appropriate) for clear printing.\n\n";
    let prompt = mdInstruction +
        promptTemplate
            .replace(/\{\{transcript\}\}/g, transcript)
            .replace(/\{\{visit_notes\}\}/g, visitNotes);

    // Expand [[...]] unless wrapped like {[[...]]}
    prompt = await replaceFhirPlaceholdersSelective(prompt);

    try {
        const res = await fetch('/scribe/create_note', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ transcript, visit_notes: visitNotes, prompt_text: prompt })
        });
        const data = await res.json();
        // Replace [[...]] proxies with live FHIR data before display
        const resolved = await replaceFhirPlaceholders(data.note || "");
        // Render as Markdown
        instructionsBox.value = resolved; // Fill textarea for further editing
        if (previewDiv) {
            try { previewDiv.innerHTML = marked.parse(instructionsBox.value); } catch(_e){ previewDiv.textContent = instructionsBox.value; }
        }
        if (typeof SessionManager !== "undefined" && SessionManager.saveToSession) {
            await SessionManager.saveToSession();
        }
    } catch (err) {
        console.error("Error generating patient instructions:", err);
        instructionsBox.value = "Error generating instructions.";
    }
}