document.addEventListener("DOMContentLoaded", async () => {
    console.log("Initializing Settings page...");

    // Initialize Archive toggles from localStorage (defaults: auto-save ON, auto-delete ON)
    try {
        const autoSaveKey = 'ssva:autoSaveArchives';
        const autoDeleteKey = 'ssva:autoDeleteArchives10d';
        if (localStorage.getItem(autoSaveKey) === null) localStorage.setItem(autoSaveKey, '1');
        if (localStorage.getItem(autoDeleteKey) === null) localStorage.setItem(autoDeleteKey, '1');
        const autoSaveBox = document.getElementById('toggleAutoSaveArchives');
        const autoDelBox = document.getElementById('toggleAutoDeleteArchives10d');
        if (autoSaveBox) autoSaveBox.checked = localStorage.getItem(autoSaveKey) === '1';
        if (autoDelBox) autoDelBox.checked = localStorage.getItem(autoDeleteKey) === '1';
        if (autoSaveBox) autoSaveBox.addEventListener('change', () => {
            localStorage.setItem(autoSaveKey, autoSaveBox.checked ? '1' : '0');
        });
        if (autoDelBox) autoDelBox.addEventListener('change', async () => {
            localStorage.setItem(autoDeleteKey, autoDelBox.checked ? '1' : '0');
            if (autoDelBox.checked) {
                try { await fetch('/delete_old_sessions?days=10', { method: 'GET' }); } catch(_e){}
            }
        });
    } catch(e) { console.warn('Archive toggle init failed', e); }

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

    // NEW: Initialize Email Draft settings (replaces Teams)
    try {
        const emailKey = 'ssva:emailAddress';
        const autoKey  = 'ssva:autoDraftEmail';
        const forceKey = 'ssva:emailForceOWA';
        const emailInput = document.getElementById('emailDraftAddressInput');
        const saveBtn    = document.getElementById('saveEmailAddressBtn');
        const statusLbl  = document.getElementById('emailAddressStatus');
        const autoChk    = document.getElementById('toggleEmailAutoDraft');
        const forceChk   = document.getElementById('toggleEmailForceOWA');

        // First, try to hydrate from server-side preferences
        try {
            const resp0 = await fetch('/user_prefs', { cache: 'no-store' });
            if (resp0.ok) {
                const prefs = await resp0.json();
                if (prefs && typeof prefs === 'object') {
                    if (typeof prefs.email_address === 'string') {
                        localStorage.setItem(emailKey, prefs.email_address || '');
                    }
                    if ('auto_draft_email' in prefs) {
                        localStorage.setItem(autoKey, prefs.auto_draft_email ? '1' : '0');
                    }
                    if ('email_force_owa' in prefs) {
                        localStorage.setItem(forceKey, prefs.email_force_owa ? '1' : '0');
                    }
                }
            }
        } catch(_e) { /* ignore */ }

        if (emailInput && saveBtn && autoChk) {
            const savedEmail = localStorage.getItem(emailKey) || '';
            if (savedEmail) {
                emailInput.value = savedEmail;
                autoChk.disabled = false;
                if (forceChk) forceChk.disabled = false;
            }
            const autoVal = localStorage.getItem(autoKey);
            autoChk.checked = autoVal === '1';

            if (forceChk) {
                const forceVal = localStorage.getItem(forceKey);
                forceChk.checked = forceVal === '1';
            }

            saveBtn.addEventListener('click', async () => {
                const val = (emailInput.value || '').trim();
                if (!val || !val.includes('@')) {
                    alert('Enter a valid email address.');
                    return;
                }
                localStorage.setItem(emailKey, val);
                // Persist to server as well
                try {
                    await fetch('/user_prefs', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({
                            email_address: val,
                            auto_draft_email: autoChk.checked,
                            email_force_owa: forceChk ? !!forceChk.checked : false
                        })
                    });
                } catch(_e) {}
                statusLbl.textContent = 'Saved!';
                autoChk.disabled = false;
                if (forceChk) forceChk.disabled = false;
                setTimeout(()=> statusLbl.textContent = '', 1500);
            });

            autoChk.addEventListener('change', async () => {
                if (autoChk.checked && !(emailInput.value||'').includes('@')) {
                    alert('Please save a valid email first.');
                    autoChk.checked = false;
                    return;
                }
                localStorage.setItem(autoKey, autoChk.checked ? '1' : '0');
                // Persist to server
                try {
                    await fetch('/user_prefs', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({
                            email_address: (emailInput.value||'').trim(),
                            auto_draft_email: autoChk.checked,
                            email_force_owa: forceChk ? !!forceChk.checked : false
                        })
                    });
                } catch(_e) {}
            });

            if (forceChk) {
                forceChk.addEventListener('change', async () => {
                    if (forceChk.checked && !(emailInput.value||'').includes('@')) {
                        alert('Please save a valid email first.');
                        forceChk.checked = false;
                        return;
                    }
                    localStorage.setItem(forceKey, forceChk.checked ? '1' : '0');
                    // Persist to server
                    try {
                        await fetch('/user_prefs', {
                            method: 'POST',
                            headers: { 'Content-Type': 'application/json' },
                            body: JSON.stringify({
                                email_address: (emailInput.value||'').trim(),
                                auto_draft_email: autoChk.checked,
                                email_force_owa: forceChk.checked
                            })
                        });
                    } catch(_e) {}
                });
            }
        }
    } catch(e) { console.warn('Email draft settings init failed', e); }
});

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
    }
    await fetch("/save_template", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
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
    const text = document.getElementById("patientInstructionsPromptText").value.trim();
    await fetch("/save_patient_instructions_prompt", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
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
    content += `\nQuery: ${query}\nAI Prompt: ${aiPrompt}\n`;

    await fetch("/save_module", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
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