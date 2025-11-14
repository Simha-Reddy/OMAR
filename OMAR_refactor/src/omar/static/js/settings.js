const PROMPTS_API_ENDPOINT = '/api/user-settings/prompts';
let summaryPromptState = { defaults: '', override: '', effective: '' };
let summaryPromptStatusTimer = null;

document.addEventListener("DOMContentLoaded", async () => {
    console.log("Initializing Settings page...");

    // Initialize Archive toggles (server-backed auto-archive ON/OFF, local auto-delete ON)
    try {
        const autoSaveKey = 'ssva:autoSaveArchives'; // legacy local fallback only
        const autoDeleteKey = 'ssva:autoDeleteArchives10d';
        if (localStorage.getItem(autoSaveKey) === null) localStorage.setItem(autoSaveKey, '1');
        if (localStorage.getItem(autoDeleteKey) === null) localStorage.setItem(autoDeleteKey, '1');
        const autoSaveBox = document.getElementById('toggleAutoSaveArchives');
        const autoDelBox = document.getElementById('toggleAutoDeleteArchives10d');
        // Fetch server auto-archive status; fallback to local if unavailable
        if (autoSaveBox) {
            try {
                const r = await fetch('/api/archive/auto-archive/status', { credentials: 'same-origin', cache: 'no-store' });
                if (r.ok) {
                    const j = await r.json();
                    autoSaveBox.checked = !!(j && j.enabled);
                    // Keep local mirror for legacy checks
                    localStorage.setItem(autoSaveKey, autoSaveBox.checked ? '1' : '0');
                } else {
                    autoSaveBox.checked = localStorage.getItem(autoSaveKey) === '1';
                }
            } catch(_e) {
                autoSaveBox.checked = localStorage.getItem(autoSaveKey) === '1';
            }
        }
        if (autoDelBox) autoDelBox.checked = localStorage.getItem(autoDeleteKey) === '1';
        if (autoSaveBox) autoSaveBox.addEventListener('change', async () => {
            const enabled = !!autoSaveBox.checked;
            // Persist to server; fallback to local mirror
            try {
                await fetch('/api/archive/auto-archive/toggle', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json', 'X-CSRF-Token': (window.getCsrfToken? window.getCsrfToken(): '') },
                    credentials: 'same-origin',
                    body: JSON.stringify({ enabled })
                });
            } catch(_e){}
            try { localStorage.setItem(autoSaveKey, enabled ? '1' : '0'); } catch(_e){}
        });
        if (autoDelBox) autoDelBox.addEventListener('change', async () => {
            localStorage.setItem(autoDeleteKey, autoDelBox.checked ? '1' : '0');
            if (autoDelBox.checked) {
                // Perform a one-time local cleanup of archives older than 10 days
                try {
                    const cutoff = Date.now() - (10 * 24 * 60 * 60 * 1000);
                    const toDelete = [];
                    for (let i = 0; i < localStorage.length; i++) {
                        const k = localStorage.key(i);
                        if (k && k.startsWith('session:archive:')) {
                            try {
                                const obj = JSON.parse(localStorage.getItem(k) || '{}');
                                if (obj && obj.ts && Number(obj.ts) < cutoff) toDelete.push(k);
                            } catch(_e){}
                        }
                    }
                    toDelete.forEach(k => { try { localStorage.removeItem(k); } catch(_e){} });
                } catch(_e){}
            }
        });
    } catch(e) { console.warn('Archive toggle init failed', e); }

    // NEW: CPRS sync toggle
    try {
        const cprsKey = 'ssva:autoCprsSync';
        if (localStorage.getItem(cprsKey) === null) localStorage.setItem(cprsKey, '1');
        const cprsBox = document.getElementById('toggleAutoCprsSync');
        if (cprsBox) {
            cprsBox.checked = localStorage.getItem(cprsKey) === '1';
            cprsBox.addEventListener('change', () => {
                const on = cprsBox.checked;
                localStorage.setItem(cprsKey, on ? '1' : '0');
                try {
                    if (on && window.startCprsPatientSync) window.startCprsPatientSync();
                    if (!on && window.stopCprsPatientSync) window.stopCprsPatientSync();
                } catch(_e){}
            });
        }
    } catch(e) { console.warn('CPRS toggle init failed', e); }

    // Dot-phrases reference: load automatically into the section
    const dotList = document.getElementById("dotphraseList");
    if (dotList) {
        try {
            const resp = await fetch('/dotphrase_commands');
            const data = await resp.json();
            const cmds = (data && data.commands) || [];
            dotList.innerHTML = '';
            cmds.forEach(c => {
                const li = document.createElement('li');
                const code = document.createElement('code');
                code.textContent = c.command;
                li.appendChild(code);
                const span = document.createElement('span');
                span.textContent = ' — ' + (c.explanation || '');
                li.appendChild(span);
                dotList.appendChild(li);
            });
        } catch (e) {
            dotList.innerHTML = '<li>Could not load commands.</li>';
        }
    }

    try {
        await initSummaryPromptSection();
    } catch (err) {
        console.warn('Summary prompt section init failed', err);
    }

    try {
        await loadDefaultPromptLibrary();
    } catch (err) {
        console.warn('Default prompt library init failed', err);
    }

    // Load the patient instructions prompt into the editor
    loadPatientInstructionsPrompt();
    document.getElementById("savePatientInstructionsPromptBtn").onclick = savePatientInstructionsPrompt;
    document.getElementById("clearPatientInstructionsPromptBtn").onclick = clearPatientInstructionsPrompt;
    document.getElementById("resetPatientInstructionsPromptBtn").onclick = resetPatientInstructionsPrompt;
    
    // Load the list of custom templates
    loadCustomTemplateList();

    // Automatically load the selected template into the editor
    const customTemplateDropdown = document.getElementById("customTemplateDropdown");
    if (customTemplateDropdown) {
        customTemplateDropdown.addEventListener("change", async () => {
            const selectedTemplate = customTemplateDropdown.value;
            if (selectedTemplate) {
                await loadCustomTemplateForEdit(selectedTemplate);
            } else {
                clearCustomTemplateEditor(); // Clear the editor if no template is selected
            }
        });
    }

    // Load the list of modules
    loadModuleList();

    // Automatically load the selected module into the edit area
    const moduleDropdown = document.getElementById("moduleDropdown");
    if (moduleDropdown) {
        moduleDropdown.addEventListener("change", async () => {
            const selectedModule = moduleDropdown.value;
            if (selectedModule) {
                await loadModuleForEdit(selectedModule);
            } else {
                clearModuleEditor(); // Clear the editor if no module is selected
            }
        });
    }

    // Appearance: Theme selector
    try {
        const THEME_KEY = 'ui:theme';
        const sel = document.getElementById('themeSelector');
        if (sel) {
            // Initialize from current DOM state or saved preference
            const current = (function(){
                try {
                    const saved = localStorage.getItem(THEME_KEY);
                    if (saved === 'original') return 'original';
                    // If DOM has data-theme="va" or no preference, treat as 'va'
                    const attr = document.documentElement.getAttribute('data-theme');
                    return (attr === 'va' || saved === 'va' || saved === null) ? 'va' : 'original';
                } catch(_e){ return 'va'; }
            })();
            sel.value = current;
            sel.addEventListener('change', () => {
                const v = sel.value === 'original' ? 'original' : 'va';
                if (typeof window.toggleThemeVA === 'function') {
                    window.toggleThemeVA(v);
                } else {
                    // Fallback if toggle not present
                    try {
                        if (v === 'va') {
                            document.documentElement.setAttribute('data-theme','va');
                            localStorage.setItem(THEME_KEY, 'va');
                        } else {
                            document.documentElement.removeAttribute('data-theme');
                            localStorage.setItem(THEME_KEY, 'original');
                        }
                    } catch(_e){}
                }
            });
        }
    } catch(e) { console.warn('Theme selector init failed', e); }
});

// --- Summary Prompt Functions ---

async function initSummaryPromptSection() {
    const editor = document.getElementById('summaryPromptText');
    if (!editor) return;

    await refreshSummaryPromptSection(true);

    const saveBtn = document.getElementById('saveSummaryPromptBtn');
    if (saveBtn) {
        saveBtn.addEventListener('click', async () => {
            await saveSummaryPromptOverride();
        });
    }

    const resetBtn = document.getElementById('resetSummaryPromptBtn');
    if (resetBtn) {
        resetBtn.addEventListener('click', async () => {
            await resetSummaryPromptOverride();
        });
    }

    const loadBtn = document.getElementById('loadSummaryDefaultBtn');
    if (loadBtn) {
        loadBtn.addEventListener('click', () => {
            const source = summaryPromptState.defaults || summaryPromptState.effective;
            if (source) {
                editor.value = source;
                try { editor.focus(); } catch(_e){}
                setSummaryPromptStatus('Loaded system default into editor. Save to activate.');
            } else {
                setSummaryPromptStatus('No default prompt available to load.', true);
            }
        });
    }
}

async function refreshSummaryPromptSection(forceRefresh = false) {
    const editor = document.getElementById('summaryPromptText');
    const preview = document.getElementById('summaryPromptEffectivePreview');
    const helper = document.getElementById('summaryPromptHelper');
    if (!editor) return;

    if (helper) helper.textContent = 'Loading prompt details…';

    try {
        const payload = await fetchPromptsData({ fields: ['summary_prompt'], forceRefresh, includeDefaults: true });
        const defaults = (payload && payload.defaults && typeof payload.defaults.summary_prompt === 'string')
            ? payload.defaults.summary_prompt.trim()
            : '';
        const override = (payload && payload.overrides && typeof payload.overrides.summary_prompt === 'string')
            ? payload.overrides.summary_prompt.trim()
            : '';
        let effective = '';
        if (payload && payload.prompts && typeof payload.prompts.summary_prompt === 'string') {
            effective = payload.prompts.summary_prompt.trim();
        } else if (override) {
            effective = override;
        } else {
            effective = defaults;
        }

        summaryPromptState = { defaults, override, effective };

        editor.value = override || '';
        if (preview) preview.value = effective || '';
        if (helper) {
            helper.textContent = override
                ? 'Custom summary prompt is active.'
                : 'Using the system default summary prompt.';
        }
    } catch (err) {
        console.warn('Summary prompt refresh failed', err);
        if (helper) helper.textContent = 'Unable to load summary prompt settings.';
    }
}

function setSummaryPromptStatus(message, isError = false) {
    const statusEl = document.getElementById('summaryPromptStatus');
    if (!statusEl) return;
    if (summaryPromptStatusTimer) {
        clearTimeout(summaryPromptStatusTimer);
        summaryPromptStatusTimer = null;
    }
    statusEl.style.color = isError ? '#b71c1c' : '#1b5e20';
    statusEl.textContent = message || '';
    if (message) {
        summaryPromptStatusTimer = setTimeout(() => {
            statusEl.textContent = '';
            summaryPromptStatusTimer = null;
        }, 3500);
    }
}

async function saveSummaryPromptOverride() {
    const editor = document.getElementById('summaryPromptText');
    if (!editor) return;
    const text = editor.value.trim();
    if (!text) {
        setSummaryPromptStatus('Enter prompt text or choose Use System Default.', true);
        return;
    }

    try {
        await patchPromptsPayload({ summary_prompt: text });
        setSummaryPromptStatus('Saved custom summary prompt.');
        await refreshSummaryPromptSection(true);
    } catch (err) {
        console.error('Summary prompt save failed', err);
        setSummaryPromptStatus('Could not save prompt.', true);
    }
}

async function resetSummaryPromptOverride() {
    try {
        await patchPromptsPayload({ summary_prompt: null });
        const editor = document.getElementById('summaryPromptText');
        if (editor) editor.value = '';
        await refreshSummaryPromptSection(true);
        setSummaryPromptStatus('Reverted to system default.');
    } catch (err) {
        console.error('Summary prompt reset failed', err);
        setSummaryPromptStatus('Could not revert to default.', true);
    }
}

async function patchPromptsPayload(payload) {
    if (window.UserSettingsClient && typeof window.UserSettingsClient.savePrompts === 'function') {
        await window.UserSettingsClient.savePrompts(payload || {});
        return;
    }
    const resp = await fetch(PROMPTS_API_ENDPOINT, {
        method: 'PATCH',
        headers: {
            'Content-Type': 'application/json',
            'Accept': 'application/json',
            'X-CSRF-Token': window.getCsrfToken ? window.getCsrfToken() : ''
        },
        credentials: 'same-origin',
        body: JSON.stringify(payload || {})
    });
    if (!resp.ok) {
        throw new Error(`HTTP ${resp.status}`);
    }
}

async function fetchPromptsData(options = {}) {
    if (window.UserSettingsClient && typeof window.UserSettingsClient.getPrompts === 'function') {
        return window.UserSettingsClient.getPrompts(options);
    }

    const params = new URLSearchParams();
    const fields = options.fields;
    if (Array.isArray(fields) && fields.length) {
        params.set('fields', fields.join(','));
    } else if (typeof fields === 'string' && fields.trim()) {
        params.set('fields', fields.trim());
    }
    if (options.includeDefaults === false) {
        params.set('include_defaults', '0');
    }
    const url = `${PROMPTS_API_ENDPOINT}${params.toString() ? `?${params.toString()}` : ''}`;
    const resp = await fetch(url, {
        method: 'GET',
        headers: { 'Accept': 'application/json' },
        credentials: 'same-origin',
        cache: 'no-store'
    });
    if (!resp.ok) {
        throw new Error(`HTTP ${resp.status}`);
    }
    return resp.json();
}

async function loadDefaultPromptLibrary(forceRefresh = false) {
    const container = document.getElementById('defaultPromptLibrary');
    if (!container) return;

    container.innerHTML = '<p style="margin:0;color:#48655d;">Loading default prompts…</p>';

    try {
        const payload = await fetchPromptsData({ forceRefresh, includeDefaults: true });
        const defaults = (payload && payload.defaults) || {};
        const fragment = document.createDocumentFragment();
        let added = 0;

        const summaryText = typeof defaults.summary_prompt === 'string' ? defaults.summary_prompt.trim() : '';
        if (summaryText) {
            fragment.appendChild(buildDefaultPromptCard('Clinical Summary Prompt (system)', summaryText, 'Key: summary_prompt'));
            added++;
        }

        const oneLinerText = typeof defaults.one_liner === 'string' ? defaults.one_liner.trim() : '';
        if (oneLinerText) {
            fragment.appendChild(buildDefaultPromptCard('One-liner Prompt', oneLinerText, 'Key: one_liner'));
            added++;
        }

        const patientText = typeof defaults.patient_instructions === 'string' ? defaults.patient_instructions.trim() : '';
        if (patientText) {
            fragment.appendChild(buildDefaultPromptCard('Patient Instructions Prompt', patientText, 'Key: patient_instructions'));
            added++;
        }

        const scribePrompts = defaults && typeof defaults.scribe_prompts === 'object' ? defaults.scribe_prompts : null;
        if (scribePrompts) {
            Object.entries(scribePrompts)
                .map(([id, info]) => {
                    if (!info || typeof info !== 'object') return null;
                    const title = String(info.title || id || '').trim();
                    const text = String(info.full_text || info.text || '').trim();
                    if (!title || !text) return null;
                    return { id, title, text };
                })
                .filter(Boolean)
                .sort((a, b) => a.title.localeCompare(b.title))
                .forEach(entry => {
                    fragment.appendChild(buildDefaultPromptCard(`Scribe Prompt • ${entry.title}`, entry.text, `Key: scribe_prompts → ${entry.id}`));
                    added++;
                });
        }

        Object.keys(defaults || {}).forEach(key => {
            if (['summary_prompt', 'one_liner', 'patient_instructions', 'scribe_prompts'].includes(key)) return;
            const value = defaults[key];
            if (typeof value === 'string' && value.trim()) {
                fragment.appendChild(buildDefaultPromptCard(`Default Prompt • ${key}`, value.trim(), `Key: ${key}`));
                added++;
            }
        });

        container.innerHTML = '';
        if (added) {
            container.appendChild(fragment);
        } else {
            container.innerHTML = '<p style="margin:0;color:#7b8d86;">No default prompts found.</p>';
        }
    } catch (err) {
        console.error('Default prompt library load failed', err);
        container.innerHTML = '<p style="margin:0;color:#b71c1c;">Unable to load default prompts.</p>';
    }
}

function buildDefaultPromptCard(title, text, metaText) {
    const details = document.createElement('details');
    details.className = 'default-prompt-block';

    const summary = document.createElement('summary');
    summary.textContent = title;
    details.appendChild(summary);

    if (metaText) {
        const meta = document.createElement('div');
        meta.className = 'default-prompt-meta';
        meta.textContent = metaText;
        details.appendChild(meta);
    }

    const toolbar = document.createElement('div');
    toolbar.className = 'default-prompt-toolbar';

    const copyBtn = document.createElement('button');
    copyBtn.type = 'button';
    copyBtn.textContent = 'Copy Prompt';

    const feedback = document.createElement('span');
    feedback.className = 'default-prompt-meta';
    feedback.style.marginLeft = 'auto';
    feedback.textContent = '';

    let resetTimer = null;
    copyBtn.addEventListener('click', async () => {
        if (resetTimer) {
            clearTimeout(resetTimer);
            resetTimer = null;
        }
        const ok = await copyPromptToClipboard(text);
        if (ok) {
            feedback.style.color = '#1b5e20';
            feedback.textContent = 'Copied!';
        } else {
            feedback.style.color = '#b71c1c';
            feedback.textContent = 'Copy failed';
        }
        resetTimer = setTimeout(() => {
            feedback.textContent = '';
            feedback.style.color = '#2f6f63';
            resetTimer = null;
        }, 2200);
    });

    toolbar.appendChild(copyBtn);
    toolbar.appendChild(feedback);
    details.appendChild(toolbar);

    const pre = document.createElement('pre');
    pre.className = 'default-prompt-text';
    pre.textContent = text;
    details.appendChild(pre);

    return details;
}

async function copyPromptToClipboard(text) {
    if (!text) return false;
    try {
        if (navigator.clipboard && navigator.clipboard.writeText) {
            await navigator.clipboard.writeText(text);
            return true;
        }
    } catch(_e){}

    try {
        const temp = document.createElement('textarea');
        temp.value = text;
        temp.setAttribute('readonly', '');
        temp.style.position = 'fixed';
        temp.style.opacity = '0';
        document.body.appendChild(temp);
        temp.focus();
        temp.select();
        const ok = document.execCommand('copy');
        document.body.removeChild(temp);
        return ok;
    } catch(err) {
        console.warn('Clipboard fallback failed', err);
        return false;
    }
}

// --- Custom Prompt Template Functions ---
async function loadCustomTemplateList() {
    const dropdown = document.getElementById("customTemplateDropdown");
    if (!dropdown) return;
    dropdown.innerHTML = '<option value="">-- Choose a template --</option>';
    const resp = await fetch("/list_custom_templates");
    const templates = await resp.json();
    templates.forEach(name => {
        const opt = document.createElement("option");
        opt.value = name;
        opt.textContent = name;
        dropdown.appendChild(opt);
    });
}

async function loadCustomTemplateForEdit(name) {
    const resp = await fetch(`/load_template/${encodeURIComponent(name)}`);
    const text = await resp.text();
    document.getElementById("customTemplateName").value = name;
    document.getElementById("customTemplateText").value = text;
}

function clearCustomTemplateEditor() {
    document.getElementById("customTemplateName").value = "";
    document.getElementById("customTemplateText").value = "";
}

async function saveCustomTemplate() {
    const name = document.getElementById("customTemplateName").value.trim();
    const text = document.getElementById("customTemplateText").value.trim();
    if (!name) {
        alert("Please enter a template name.");
        return;
    }    await fetch("/save_template", {
        method: "POST",
        headers: { 
            "Content-Type": "application/json",
            "X-CSRF-Token": window.getCsrfToken ? window.getCsrfToken() : ''
        },
        body: JSON.stringify({ name, text })
    });
    alert("Template saved.");
    loadCustomTemplateList();
}

async function deleteCustomTemplate() {
    const name = document.getElementById("customTemplateName").value.trim();
    if (!name) {
        alert("Please select a template to delete.");
        return;
    }
    if (confirm(`Delete template "${name}"?`)) {
        await fetch(`/delete_template/${encodeURIComponent(name)}`, { method: "DELETE" });
        loadCustomTemplateList();
        clearCustomTemplateEditor();
        alert("Template deleted.");
    }
}

// --- Patient Instructions Prompt Functions ---
async function loadPatientInstructionsPrompt() {
    const resp = await fetch("/load_patient_instructions_prompt");
    const text = await resp.ok ? await resp.text() : "";
    document.getElementById("patientInstructionsPromptText").value = text;
}

async function savePatientInstructionsPrompt() {
    const text = document.getElementById("patientInstructionsPromptText").value.trim();    await fetch("/save_patient_instructions_prompt", {
        method: "POST",
        headers: { 
            "Content-Type": "application/json",
            "X-CSRF-Token": window.getCsrfToken ? window.getCsrfToken() : ''
        },
        body: JSON.stringify({ text })
    });
    document.getElementById("patientInstructionsPromptStatus").textContent = "Saved!";
    setTimeout(() => {
        document.getElementById("patientInstructionsPromptStatus").textContent = "";
    }, 2000);
}

function clearPatientInstructionsPrompt() {
    document.getElementById("patientInstructionsPromptText").value = "";
    document.getElementById("patientInstructionsPromptStatus").textContent = "";
}

async function resetPatientInstructionsPrompt() {
    const resp = await fetch("/default_patient_instructions_prompt");
    if (resp.ok) {
        const text = await resp.text();
        document.getElementById("patientInstructionsPromptText").value = text;
        document.getElementById("patientInstructionsPromptStatus").textContent = "Reset to default!";
        setTimeout(() => {
            document.getElementById("patientInstructionsPromptStatus").textContent = "";
        }, 2000);
    } else {
        document.getElementById("patientInstructionsPromptStatus").textContent = "Could not load default.";
    }
}

// --- Smart Module Editor functions ---
async function loadModuleList() {
    const dropdown = document.getElementById("moduleDropdown");
    if (!dropdown) return;
    dropdown.innerHTML = '<option value="">-- Choose a module --</option>';
    const resp = await fetch("/list_modules");
    const files = await resp.json();
    files.forEach(name => {
        const opt = document.createElement("option");
        opt.value = name;
        opt.textContent = name;
        dropdown.appendChild(opt);
    });
}

async function loadModuleForEdit(name) {
    const resp = await fetch(`/load_module/${encodeURIComponent(name)}`);
    const text = await resp.text();
    document.getElementById("moduleFileName").value = name;
    // Parse fields from file
    document.getElementById("moduleTitle").value = (text.match(/^Title:\s*(.*)$/m)||[])[1]||"";
    document.getElementById("moduleOutput").value = (text.match(/^Output:\s*(.*)$/m)||[])[1]||"";
    document.getElementById("moduleChain").value = (text.match(/^Chain:\s*(.*)$/m)||[])[1]||"";
    // Inputs
    const inputChecks = document.querySelectorAll("#moduleInputs input[type=checkbox]");
    inputChecks.forEach(cb => cb.checked = false);
    (text.match(/^\[([ Xx])\]\s*(\w+)/gm)||[]).forEach(line => {
        const m = line.match(/^\[([ Xx])\]\s*(\w+)/);
        if (m && (m[1] === "X" || m[1] === "x")) {
            const cb = document.querySelector(`#moduleInputs input[value="${m[2]}"]`);
            if (cb) cb.checked = true;
        }
    });
    document.getElementById("moduleQuery").value = (text.match(/^Query:\s*(.*)$/m)||[])[1]||"";
    document.getElementById("moduleAIPrompt").value = (text.match(/^AI Prompt:\s*([\s\S]*)$/m)||[])[1]||"";
}

async function editSelectedModule() {
    const dropdown = document.getElementById("moduleDropdown");
    const name = dropdown.value;
    if (!name) {
        alert("Please select a module to edit.");
        return;
    }
    await loadModuleForEdit(name);
}

async function deleteSelectedModule() {
    const dropdown = document.getElementById("moduleDropdown");
    const name = dropdown.value;
    if (!name) {
        alert("Please select a module to delete.");
        return;
    }
    if (confirm(`Delete module "${name}"?`)) {
        await fetch(`/delete_module/${encodeURIComponent(name)}`, { method: "DELETE" });
        loadModuleList();
        clearModuleEditor();
        alert("Module deleted.");
    }
}

function clearModuleEditor() {
    document.getElementById("moduleFileName").value = "";
    document.getElementById("moduleTitle").value = "";
    document.getElementById("moduleOutput").value = "";
    document.getElementById("moduleChain").value = "";
    document.querySelectorAll("#moduleInputs input[type=checkbox]").forEach(cb => cb.checked = false);
    document.getElementById("moduleQuery").value = "";
    document.getElementById("moduleAIPrompt").value = "";
}

async function saveModule() {
    const name = document.getElementById("moduleFileName").value.trim();
    if (!name.endsWith(".txt")) {
        alert("Filename must end with .txt");
        return;
    }
    const title = document.getElementById("moduleTitle").value.trim();
    const output = document.getElementById("moduleOutput").value.trim();
    const chain = document.getElementById("moduleChain").value.trim();
    const inputs = Array.from(document.querySelectorAll("#moduleInputs input[type=checkbox]:checked")).map(cb => cb.value);
    const query = document.getElementById("moduleQuery").value.trim();
    const aiPrompt = document.getElementById("moduleAIPrompt").value.trim();

    // Enforce Output matches filename (without .txt)
    const expectedOutput = name.replace(/\.txt$/i, "");
    if (output !== expectedOutput) {
        alert(`Output must match the filename (without .txt): "${expectedOutput}"`);
        document.getElementById("moduleOutput").value = expectedOutput;
        return;
    }

    let content = `Title: ${title}\nOutput: ${output}\n`;
    if (chain) content += `Chain: ${chain}\n`;
    inputs.forEach(input => content += `[X] ${input}\n`);
    content += `\nQuery: ${query}\nAI Prompt: ${aiPrompt}\n`;    await fetch("/save_module", {
        method: "POST",
        headers: { 
            "Content-Type": "application/json",
            "X-CSRF-Token": window.getCsrfToken ? window.getCsrfToken() : ''
        },
        body: JSON.stringify({ name, content })
    });
    alert("Module saved.");
    loadModuleList();
}

// Auto-fill Output when typing filename
const moduleFileNameInput = document.getElementById("moduleFileName");
if (moduleFileNameInput) {
    moduleFileNameInput.addEventListener("input", function() {
        const fname = this.value.trim();
        if (fname.endsWith(".txt")) {
            document.getElementById("moduleOutput").value = fname.replace(/\.txt$/i, "");
        } else {
            document.getElementById("moduleOutput").value = fname;
        }
    });
}

function saveCustomTemplate() {
    const name = document.getElementById("customTemplateName").value;
    const text = document.getElementById("customTemplateText").value;    fetch("/save_template", {
        method: "POST",
        headers: { 
            "Content-Type": "application/json",
            "X-CSRF-Token": window.getCsrfToken ? window.getCsrfToken() : ''
        },
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