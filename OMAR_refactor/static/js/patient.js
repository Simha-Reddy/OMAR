window.addEventListener("DOMContentLoaded", () => {
    const Api = (window.Api || null);
    // Helper function to extract patient name from FHIR bundle
    function getPatientName(patientRecord) {
        if (!patientRecord || !Array.isArray(patientRecord.entry)) return "Unknown";
        // Find the Patient resource
        const patientEntry = patientRecord.entry.find(e => e.resource && e.resource.resourceType === "Patient");
        if (!patientEntry || !patientEntry.resource.name || !patientEntry.resource.name.length) return "Unknown";
        const nameObj = patientEntry.resource.name[0];
        if (nameObj.text) return nameObj.text;
        // If no text, build from given/family
        const given = Array.isArray(nameObj.given) ? nameObj.given.join(" ") : "";
        const family = nameObj.family || "";
        return `${given} ${family}`.trim() || "Unknown";
    }

    // Helper function to extract patient DOB from FHIR bundle
    function getPatientDOB(patientRecord) {
        if (!patientRecord || !Array.isArray(patientRecord.entry)) return "Unknown";
        const patientEntry = patientRecord.entry.find(e => e.resource && e.resource.resourceType === "Patient");
        if (!patientEntry || !patientEntry.resource.birthDate) return "Unknown";
        // FHIR birthDate is YYYY-MM-DD
        const dob = patientEntry.resource.birthDate;
        if (/^\d{4}-\d{2}-\d{2}$/.test(dob)) {
            const [year, month, day] = dob.split("-");
            return `${month}/${day}/${year}`;
        }
        return dob;
    }

    // New: Helper to compute patient age from FHIR birthDate
    function getPatientAge(patientRecord) {
        try {
            if (!patientRecord || !Array.isArray(patientRecord.entry)) return "Unknown";
            const patientEntry = patientRecord.entry.find(e => e.resource && e.resource.resourceType === "Patient");
            const birthDateRaw = patientEntry && patientEntry.resource && patientEntry.resource.birthDate;
            if (!birthDateRaw || typeof birthDateRaw !== 'string') return "Unknown";
            // Handle FHIR partial dates: YYYY, YYYY-MM, YYYY-MM-DD
            let y, m = 1, d = 1;
            if (/^\d{4}$/.test(birthDateRaw)) {
                y = Number(birthDateRaw);
            } else if (/^\d{4}-\d{2}$/.test(birthDateRaw)) {
                const parts = birthDateRaw.split('-').map(Number);
                y = parts[0]; m = parts[1];
            } else if (/^\d{4}-\d{2}-\d{2}$/.test(birthDateRaw)) {
                const parts = birthDateRaw.split('-').map(Number);
                y = parts[0]; m = parts[1]; d = parts[2];
            } else {
                // Fallback: try Date.parse
                const dt = new Date(birthDateRaw);
                if (!isNaN(dt.getTime())) {
                    y = dt.getFullYear();
                    m = dt.getMonth() + 1;
                    d = dt.getDate();
                } else {
                    return "Unknown";
                }
            }
            const today = new Date();
            let age = today.getFullYear() - y;
            const hasHadBirthdayThisYear = ((today.getMonth() + 1) > m) || (((today.getMonth() + 1) === m) && (today.getDate() >= d));
            if (!hasHadBirthdayThisYear) age -= 1;
            if (!isFinite(age) || age < 0 || age > 120) return "Unknown";
            return String(age);
        } catch (_e) { return "Unknown"; }
    }

    // --- Helper: Extract Labs (category = laboratory) ---
    function getLabs(patientRecord) {
        if (!patientRecord || !Array.isArray(patientRecord.entry)) return [];
        return patientRecord.entry
            .filter(e => e.resource && e.resource.resourceType === "Observation" && e.resource.category && Array.isArray(e.resource.category) &&
                e.resource.category.some(cat => cat.coding && cat.coding.some(c => c.code === "laboratory"))
            )
            .map(e => e.resource);
    }

    // --- Helper: Extract Vitals (category = vital-signs) ---
    function getVitals(patientRecord) {
        if (!patientRecord || !Array.isArray(patientRecord.entry)) return [];
        return patientRecord.entry
            .filter(e => e.resource && e.resource.resourceType === "Observation" && e.resource.category && Array.isArray(e.resource.category) &&
                e.resource.category.some(cat => cat.coding && cat.coding.some(c => c.code === "vital-signs"))
            )
            .map(e => e.resource);
    }

    // --- Helper: Normalize Medications for Table Display ---
    function getNormalizedMedications(patientRecord) {
        if (!patientRecord || !Array.isArray(patientRecord.entry)) return [];
        // Accept both MedicationStatement and MedicationRequest
        return patientRecord.entry
            .filter(e => e.resource && (e.resource.resourceType === "MedicationStatement" || e.resource.resourceType === "MedicationRequest"))
            .map(e => {
                const med = e.resource;
                // Medication class: prefer note[].text (e.g., "ANTIPSYCHOTICS,OTHER"), then fall back to category text/coding
                let medClass = "";
                try {
                    if (Array.isArray(med.note) && med.note.length) {
                        const texts = med.note
                            .map(n => (n && typeof n.text === 'string') ? n.text.trim() : '')
                            .filter(Boolean);
                        if (texts.length) medClass = texts.join('; ');
                    }
                } catch(_) {}
                if (!medClass) {
                    // Fallback to category text or coding display
                    if (Array.isArray(med.category) && med.category.length) {
                        const catText = med.category.map(c => (c && c.text) ? c.text : '').find(Boolean);
                        if (catText) {
                            medClass = catText;
                        } else {
                            const codingDisp = med.category
                                .flatMap(c => (c && Array.isArray(c.coding)) ? c.coding : [])
                                .map(cd => (cd && (cd.display || cd.code)) ? (cd.display || cd.code) : '')
                                .find(Boolean);
                            if (codingDisp) medClass = codingDisp;
                        }
                    } else if (med.category && typeof med.category === 'object') {
                        medClass = med.category.text
                            || ((med.category.coding && med.category.coding[0]) ? (med.category.coding[0].display || med.category.coding[0].code) : '')
                            || '';
                    }
                }

                // Name
                let medName = med.medicationCodeableConcept && med.medicationCodeableConcept.text
                    ? med.medicationCodeableConcept.text
                    : (med.medicationCodeableConcept && med.medicationCodeableConcept.coding && med.medicationCodeableConcept.coding[0].display)
                        ? med.medicationCodeableConcept.coding[0].display
                        : "";
                // Dose
                let dose = "";
                if (med.dosageInstruction && med.dosageInstruction[0] && med.dosageInstruction[0].text) {
                    dose = med.dosageInstruction[0].text;
                } else if (med.dosage && med.dosage[0] && med.dosage[0].text) {
                    dose = med.dosage[0].text;
                }
                // Frequency (try to extract from sig/dosage text)
                let frequency = "";
                if (dose) {
                    const freqMatch = dose.match(/(\d+\s*x\s*\w+|\bBID\b|\bTID\b|\bQID\b|\bQ[0-9]+[HDW]?\b|\bPRN\b|\bQHS\b|\bQD\b|\bDAILY\b)/i);
                    if (freqMatch) frequency = freqMatch[0];
                }
                // Quantity
                let quantity = "";
                if (med.dispenseRequest && med.dispenseRequest.quantity && med.dispenseRequest.quantity.value !== undefined) {
                    quantity = med.dispenseRequest.quantity.value;
                } else if (med.quantity && med.quantity.value !== undefined) {
                    quantity = med.quantity.value;
                }
                // Last filled (use authoredOn, effectiveDateTime, or dateAsserted)
                let lastFilled = med.authoredOn || med.effectiveDateTime || med.dateAsserted || "";
                // Refills
                let refills = "";
                if (med.dispenseRequest && med.dispenseRequest.numberOfRepeatsAllowed !== undefined) {
                    refills = med.dispenseRequest.numberOfRepeatsAllowed;
                } else if (med.numberOfRepeatsAllowed !== undefined) {
                    refills = med.numberOfRepeatsAllowed;
                }
                // Status
                let status = med.status || "";
                // Return normalized object
                return {
                    medClass,
                    medName,
                    dose,
                    frequency,
                    quantity,
                    lastFilled,
                    refills,
                    status
                };
            });
    }

    async function renderMedicationsTable(patientRecord) {
        // Fetch normalized medications from server instead of re-normalizing on client
        const medTableDiv = document.getElementById("medicationsTable");
        if (!medTableDiv) {
            console.warn("[Medications] #medicationsTable not found; skipping table render.");
            return;
        }
        medTableDiv.style.height = "400px";
        medTableDiv.style.display = "block";
        let meds = [];
        try {
            const resp = await fetch('/fhir/medications');
            if (resp.ok) {
                const json = await resp.json();
                meds = Array.isArray(json.medications) ? json.medications : [];
            } else {
                console.warn('Failed to load /fhir/medications, status', resp.status);
            }
        } catch (e) {
            console.error('Error fetching /fhir/medications:', e);
        }
        // Adherence logic
        function getAdherenceStatus(row) {
            if (!row.lastFilled || !row.quantity || !row.frequency) return {icon:'?', color:'#ccc', text:'Unknown'};
            const last = new Date(row.lastFilled);
            if (isNaN(last.getTime())) return {icon:'?', color:'#ccc', text:'Unknown'};
            let daysSupply = 30;
            let freq = String(row.frequency || '').toUpperCase();
            if (freq.includes('QD') || freq.includes('DAILY')) daysSupply = row.quantity;
            else if (freq.includes('BID')) daysSupply = row.quantity / 2;
            else if (freq.includes('TID')) daysSupply = row.quantity / 3;
            else if (freq.includes('QID')) daysSupply = row.quantity / 4;
            else {
                const m = freq.match(/Q(\d+)D/);
                if (m) daysSupply = row.quantity * parseInt(m[1]);
            }
            const now = new Date();
            const daysSince = Math.floor((now - last) / (1000*60*60*24));
            if (daysSince < daysSupply + 7) return {icon:'✔', color:'#4caf50', text:'On time'};
            if (daysSince < daysSupply + 30) return {icon:'⚠', color:'#ffb300', text:'Late'};
            return {icon:'✖', color:'#e53935', text:'Likely non-adherent'};
        }
        meds.forEach(m => m.adherence = getAdherenceStatus(m).text);

        // Destroy previous table if exists
        if (window.medicationsTabulator) {
            window.medicationsTabulator.destroy();
        }
        const columns = [
            {title: "Class", field: "medClass", headerFilter: 'input', sorter:"string"},
            {title: "Name", field: "name", headerFilter: 'input', sorter:"string"},
            {title: "Dose", field: "dose", headerFilter: 'input', sorter:"string"},
            {title: "Frequency", field: "frequency", headerFilter: 'input', sorter:"string"},
            {title: "Quantity", field: "quantity", sorter:"number"},
            {title: "Last Filled", field: "lastFilled", sorter:"date"},
            {title: "Refills", field: "refills", sorter:"number"},
            {title: "Status", field: "status", headerFilter: 'input', sorter:"string"},
            {title: "Adherence", field: "adherence", hozAlign:"center", headerSort:false, formatter:function(cell){
                const row = cell.getData();
                const adh = getAdherenceStatus(row);
                return `<span title="${adh.text}" style="color:${adh.color};font-size:1.3em;">${adh.icon}</span>`;
            }}
        ];
        window.medicationsTabulator = new Tabulator("#medicationsTable", {
            data: meds,
            layout: "fitColumns",
            columns: columns,
            pagination: true,
            paginationSize: 10,
            movableColumns: true,
            // Keep total table width constant when resizing columns
            columnResizeMode: 'fit',
            columnMinWidth: 60,
            initialSort: [ {column: "status", dir: "asc"}, {column: "name", dir: "asc"} ],
            rowClick: function(e, row) {
                try { showMedicationDetailModal(row.getData()); } catch(_e){}
            },
        });
    }

    // --- NEW: Labs Table Renderer ---
    function flattenLabObservations(patientRecord){
        const labs = getLabs(patientRecord);
        const rows = [];
        labs.forEach(obs => {
            const common = {
                obsId: obs.id || '',
                date: obs.effectiveDateTime || obs.issued || '',
                category: 'Lab',
                test: (obs.code && (obs.code.text || (obs.code.coding && obs.code.coding[0] && (obs.code.coding[0].display || obs.code.coding[0].code)))) || '(Unnamed)',
                refRange: '',
                status: obs.status || '',
                interpretation: (obs.interpretation && obs.interpretation[0] && (obs.interpretation[0].text || (obs.interpretation[0].coding && obs.interpretation[0].coding[0] && (obs.interpretation[0].coding[0].display || obs.interpretation[0].coding[0].code)))) || ''
            };
            // Build reference range (simple)
            if (obs.referenceRange && obs.referenceRange.length){
                const rr = obs.referenceRange[0];
                const low = rr.low && rr.low.value !== undefined ? rr.low.value + (rr.low.unit? ' '+rr.low.unit:'') : '';
                const high = rr.high && rr.high.value !== undefined ? rr.high.value + (rr.high.unit? ' '+rr.high.unit:'') : '';
                if (low || high) common.refRange = `${low} - ${high}`.trim();
            }
            if (Array.isArray(obs.component) && obs.component.length){
                obs.component.forEach(c => {
                    const row = {...common};
                    row.subTest = (c.code && (c.code.text || (c.code.coding && c.code.coding[0] && (c.code.coding[0].display || c.code.coding[0].code)))) || '';
                    if (c.valueQuantity){
                        row.value = c.valueQuantity.value;
                        row.unit = c.valueQuantity.unit || c.valueQuantity.code || '';
                    } else if (c.valueString){
                        row.value = c.valueString;
                        row.unit = '';
                    } else if (c.valueCodeableConcept){
                        row.value = c.valueCodeableConcept.text || (c.valueCodeableConcept.coding && c.valueCodeableConcept.coding[0] && (c.valueCodeableConcept.coding[0].display || c.valueCodeableConcept.coding[0].code)) || '';
                        row.unit='';
                    } else {
                        row.value=''; row.unit='';
                    }
                    rows.push(row);
                });
            } else {
                const row = {...common};
                row.subTest = '';
                if (obs.valueQuantity){
                    row.value = obs.valueQuantity.value;
                    row.unit = obs.valueQuantity.unit || obs.valueQuantity.code || '';
                } else if (obs.valueString){
                    row.value = obs.valueString;
                    row.unit = '';
                } else if (obs.valueCodeableConcept){
                    row.value = obs.valueCodeableConcept.text || (obs.valueCodeableConcept.coding && obs.valueCodeableConcept.coding[0] && (obs.valueCodeableConcept.coding[0].display || obs.valueCodeableConcept.coding[0].code)) || '';
                    row.unit='';
                } else if (obs.valueInteger !== undefined){
                    row.value = obs.valueInteger;
                    row.unit='';
                } else {
                    row.value=''; row.unit='';
                }
                rows.push(row);
            }
        });
        return rows;
    }

    function extractQuickLabs(payload){
        if(Array.isArray(payload)) return payload;
        if(payload && Array.isArray(payload.result)) return payload.result;
        if(payload && payload.result && typeof payload.result === 'object' && Array.isArray(payload.result.items)) return payload.result.items;
        if(payload && Array.isArray(payload.labs)) return payload.labs;
        if(payload && Array.isArray(payload.items)) return payload.items;
        return [];
    }

    function specimenLabel(specimenRaw){
        if(specimenRaw == null) return '';
        if(typeof specimenRaw === 'string') return specimenRaw;
        if(typeof specimenRaw === 'object'){
            return specimenRaw.name || specimenRaw.display || specimenRaw.text || specimenRaw.description || specimenRaw.code || '';
        }
        return String(specimenRaw);
    }

    async function renderLabsTable(patientRecord){
        const container = document.getElementById('labsTable');
        if(!container) return; // Not on this page
        // Prefer quick endpoint for richer lab history; fallback to FHIR bundle if unavailable
        let data = [];
        let usedQuick = false;
        try{
            const resp = await fetch('/quick/patient/labs?days=365', { cache:'no-store', credentials:'same-origin', headers:{'Accept':'application/json','X-Caller':'PatientLabs'} });
            if(resp.ok){
                const js = await resp.json();
                const list = extractQuickLabs(js);
                if(list && list.length){
                    data = list.map(r=>{
                        const specimenRaw = r && (r.specimen ?? r.specimenType ?? r.sample ?? r.source ?? r.bodySite ?? null);
                        const specimen = specimenLabel(specimenRaw);
                        return {
                            obsId: r.uid || r.id || r.localId || '',
                            date: r.resulted || r.observedDate || r.collected || '',
                            category: 'Lab',
                            test: r.test || r.localName || r.name || '(Unnamed)',
                            subTest: specimen || '',
                            value: (r.result != null ? r.result : r.value) ?? '',
                            unit: r.unit || r.units || '',
                            refRange: r.referenceRange || r.refRange || '',
                            interpretation: r.flag || r.interpretation || (r.abnormal === true ? 'A' : ''),
                            status: r.status || r.panelStatus || ''
                        };
                    });
                    usedQuick = true;
                }
            }
        }catch(_e){}
        if(!usedQuick){
            data = flattenLabObservations(patientRecord);
        }
        if(window.labsTabulator){ window.labsTabulator.replaceData(data); return; }
        function abnormalFlag(row){
            const interp = (row.interpretation||'').toUpperCase();
            if(/\b(HH|H)\b/.test(interp)) return 'high';
            if(/\b(LL|L)\b/.test(interp)) return 'low';
            if(/ABN|ABNORMAL|A/.test(interp)) return 'abn';
            return '';
        }
        window.labsTabulator = new Tabulator('#labsTable', {
            data,
            layout:'fitColumns',
            pagination:true,
            paginationSize:15,
            movableColumns:true,
            reactiveData:false,
            // Keep total table width constant when resizing columns
            columnResizeMode: 'fit',
            columnMinWidth: 60,
            columns:[
                {title:'Date', field:'date', sorter:'datetime', headerFilter: 'input'},
                {title:'Test', field:'test', headerFilter: 'input'},
                {title:'Component', field:'subTest', headerFilter: 'input'},
                {title:'Value', field:'value', sorter:'number', formatter:(cell)=>{
                    const d = cell.getData();
                    const flag = abnormalFlag(d);
                    let color = '';
                    if(flag==='high') color='#d32f2f';
                    else if(flag==='low') color='#1976d2';
                    else if(flag==='abn') color='#e65100';
                    return `<span style="font-weight:${flag? '600':'400'};color:${color};">${cell.getValue()!==undefined?cell.getValue():''}</span>`;
                }},
                {title:'Unit', field:'unit', width:90},
                {title:'Ref Range', field:'refRange'},
                // If quick endpoint provided referenceRange string, prefer it in a visible column
                {title:'Reference Range', field:'referenceRange', visible:false},
                {title:'Interp', field:'interpretation', width:110, formatter:(cell)=>{
                    const v = cell.getValue()||''; const d=v.toUpperCase();
                    let color='';
                    if(/HH|H/.test(d)) color='#d32f2f';
                    else if(/LL|L/.test(d)) color='#1976d2';
                    else if(/ABN|ABNORMAL|A/.test(d)) color='#e65100';
                    return `<span style="color:${color};">${v}</span>`;
                }},
                {title:'Status', field:'status', width:90},
            ],
            rowClick:(e,row)=>{
                const detail = document.getElementById('labDetail');
                if(detail){
                    const d = row.getData();
                    detail.style.display='block';
                    detail.textContent = JSON.stringify(d, null, 2);
                }
            },
        });
    }

    // --- Patient Record Modules ---
    function renderPatientRecordModules(patientRecord) {
        const container = document.getElementById("patientRecordModules");
        if (!container) {
            console.warn("#patientRecordModules container not found");
            return;
        }
        container.innerHTML = "";

        // Helper to create a module panel
        function createPanel(title, contentHtml) {
            const panel = document.createElement("div");
            panel.className = "panel";
            panel.style.marginBottom = "18px";
            const h3 = document.createElement("h3");
            h3.textContent = title;
            panel.appendChild(h3);
            const content = document.createElement("div");
            content.className = "markdown-box";
            content.innerHTML = contentHtml;
            panel.appendChild(content);
            return panel;
        }

        // --- Problems (Active & Inactive) ---
        const allProblems = (patientRecord.entry || []).filter(e => e.resource && e.resource.resourceType === "Condition");
        if (allProblems.length) {
            let activeProblems = [], inactiveProblems = [];
            allProblems.forEach(p => {
                const status = (p.resource.clinicalStatus && p.resource.clinicalStatus.coding && p.resource.clinicalStatus.coding.length)
                    ? p.resource.clinicalStatus.coding[0].code
                    : (typeof p.resource.clinicalStatus === "string" ? p.resource.clinicalStatus : "active");
                if (status === "active") {
                    activeProblems.push(p);
                } else {
                    inactiveProblems.push(p);
                }
            });
            let html = "";
            html += `<strong>Active Problems</strong>:`;
            html += activeProblems.length ? `<ul>${activeProblems.map(p => `<li>${p.resource.code && p.resource.code.text ? p.resource.code.text : "(No description)"}</li>`).join("")}</ul>` : " <em>None</em>";
            html += `<strong>Inactive Problems</strong>:`;
            html += inactiveProblems.length ? `<ul>${inactiveProblems.map(p => `<li>${p.resource.code && p.resource.code.text ? p.resource.code.text : "(No description)"}</li>`).join("")}</ul>` : " <em>None</em>";
            container.appendChild(createPanel("Problems", html));
        } else {
            container.appendChild(createPanel("Problems", "<em>No problems found.</em>"));
        }

        // --- Medications ---
        // Show both MedicationStatement and MedicationRequest (FHIR output uses MedicationStatement)
        const meds = (patientRecord.entry || []).filter(e => e.resource && (e.resource.resourceType === "MedicationStatement" || e.resource.resourceType === "MedicationRequest"));
        let medsHtml = meds.length ? `<ul>${meds.map(m => {
            const med = m.resource;
            if (med.medicationCodeableConcept && med.medicationCodeableConcept.text) {
                return `<li>${med.medicationCodeableConcept.text}</li>`;
            } else if (med.medicationCodeableConcept && med.medicationCodeableConcept.coding && med.medicationCodeableConcept.coding.length) {
                return `<li>${med.medicationCodeableConcept.coding[0].display || med.medicationCodeableConcept.coding[0].code}</li>`;
            } else {
                return "<li>(No description)</li>";
            }
        }).join("")}</ul>` : "<em>No medications found.</em>";
        container.appendChild(createPanel("Medications", medsHtml));

        // --- Labs ---
        // Show all Observations with category 'laboratory' or 'vital-signs'
        const labs = (patientRecord.entry || []).filter(e => e.resource && e.resource.resourceType === "Observation" && e.resource.category && Array.isArray(e.resource.category) && e.resource.category.some(cat => cat.coding && cat.coding.some(c => c.code === "laboratory" || c.code === "vital-signs")));
        let labsHtml = labs.length ? `<ul>${labs.map(l => {
            const obs = l.resource;
            let label = obs.code && obs.code.text ? obs.code.text : "(No description)";
            if (obs.valueQuantity && obs.valueQuantity.value !== undefined) {
                label += `: ${obs.valueQuantity.value} ${obs.valueQuantity.unit || ""}`;
            }
            return `<li>${label}</li>`;
        }).join("")}</ul>` : "<em>No labs or vitals found.</em>";
        container.appendChild(createPanel("Labs & Vitals", labsHtml));
    }

    // Back-compat shim: ensure displayPatientInfo exists (delegates to API)
    // Main function to display patient info from refactor quick API
    async function displayPatientInfoFromApi() {
        try {
            const demo = await Api.quick('demographics');
            // Prefer refactor quick demographics fields (Name, DOB/DOB_ISO), fallback to legacy/fhir-style
            const nameFromQuick = (demo && (demo.Name || demo.name || demo.displayName || demo.fullName)) || '';
            const dobIso = (demo && (demo.DOB_ISO || demo.dob || '')) || '';
            const dobPretty = (demo && (demo.DOB || '')) || '';
            // Compute age consistently with workspace.js if DOB available
            let ageStr = '';
            try {
                const dobForAge = dobIso || dobPretty;
                if (dobForAge && typeof window.computeAgeFromDob === 'function') {
                    ageStr = window.computeAgeFromDob(String(dobForAge)) || '';
                }
            } catch(_e){}

            const patientNameDisplay = document.getElementById('patientNameDisplay');
            if (patientNameDisplay) {
                const dobText = dobPretty ? `, DOB: ${dobPretty}` : '';
                patientNameDisplay.textContent = `Name: ${nameFromQuick}${dobText}`;
            }
            const topBarStatus = document.getElementById('patientLookupResults');
            if (topBarStatus) {
                // Use unified display style: Name (Age) if age present
                const displayText = (nameFromQuick && ageStr)
                    ? `${nameFromQuick} (${ageStr})`
                    : nameFromQuick;
                topBarStatus.dataset.originalText = displayText;
                if (window.demoMasking && window.demoMasking.enabled) {
                    const maskedName = window.demoMasking.maskName(nameFromQuick);
                    topBarStatus.textContent = ageStr ? `${maskedName} (${ageStr})` : maskedName;
                } else {
                    topBarStatus.textContent = displayText;
                }
            }
        } catch (e) {
            console.warn('demographics load failed', e);
        }
    }
    // Back-compat: legacy callers may invoke window.displayPatientInfo(patientRecord)
    async function displayPatientInfo(_patientRecord){
        return displayPatientInfoFromApi();
    }
    // Function to update patient name display (for demo masking)
    function updatePatientNameDisplay() {
        const topBarStatus = document.getElementById("patientLookupResults");
        if (topBarStatus && topBarStatus.dataset.originalText) {
            const originalText = topBarStatus.dataset.originalText;
            // Detect either ", Age: NN" or " (NN)" at end
            const m = originalText.match(/(?:,\s*Age:\s*(\d+)\s*$|\s*\((\d+)\)\s*$)/);
            const age = m ? (m[1] || m[2] || '') : '';
            // Strip trailing age part in either pattern
            const nameOnly = originalText.replace(/(?:,\s*Age:\s*\d+\s*$|\s*\(\d+\)\s*$)/, '').trim();
            if (window.demoMasking && window.demoMasking.enabled) {
                const maskedName = window.demoMasking.maskName(nameOnly);
                if (age) {
                    // Preserve original delimiter style: if original had parentheses, keep it
                    const usedParens = /\(\d+\)\s*$/.test(originalText);
                    topBarStatus.textContent = usedParens ? `${maskedName} (${age})` : `${maskedName}, Age: ${age}`;
                } else {
                    topBarStatus.textContent = maskedName;
                }
            } else {
                topBarStatus.textContent = originalText;
            }
        }
    }

    // Expose functions globally
    window.displayPatientInfo = displayPatientInfo;
    window.updatePatientNameDisplay = updatePatientNameDisplay;
    window.getPatientName = getPatientName;
    window.getPatientDOB = getPatientDOB;
    window.getPatientAge = getPatientAge;
    window.getLabs = getLabs;
    window.getVitals = getVitals;
    window.getNormalizedMedications = getNormalizedMedications;
    // New: expose table renderers so they can be invoked after patient selection
    try {
        window.renderMedicationsTable = renderMedicationsTable;
    window.renderLabsTable = renderLabsTable;
    } catch(_e){}

    // When a patient switch starts, immediately clear the top header so old name doesn’t linger
    try {
        window.addEventListener('workspace:patientSwitched', () => {
            const el = document.getElementById('patientLookupResults');
            if (el) {
                el.textContent = 'Loading...';
                try { delete el.dataset.originalText; } catch(_){}
            }
        });
    } catch(_e){}

    // --- Primary Care Progress Note UI ---
    function getDocumentReferences(patientRecord) {
        if (!patientRecord || !Array.isArray(patientRecord.entry)) return [];
        return patientRecord.entry
            .filter(e => e.resource && e.resource.resourceType === 'DocumentReference')
            .map(e => e.resource);
    }

    function buildDocRefLabel(dr) {
        const title = (dr.description || (dr.type && dr.type.text) || 'Untitled').trim();
        const date = dr.date || '';
        return date ? `${title} (${date})` : title;
    }

    async function fetchPrimaryNote(docId) {
        const statusEl = document.getElementById('primaryNoteStatus');
        const pre = document.getElementById('primaryNoteText');
        if (statusEl) statusEl.textContent = 'Loading...';
        if (pre) pre.textContent = '';
        let url = '/last_primary_care_progress_note';
        if (docId) url += `?doc_id=${encodeURIComponent(docId)}`;
        try {
            const resp = await fetch(url);
            if (!resp.ok) {
                const txt = await resp.text();
                throw new Error(txt || resp.statusText);
            }
            const data = await resp.json();
            if (pre) pre.textContent = (data.text || []).join('\n');
            if (statusEl) statusEl.textContent = `Loaded doc ${data.doc_id || ''} (${data.line_count || 0} lines)`;
        } catch (err) {
            if (statusEl) statusEl.textContent = 'Error loading note';
            if (pre) pre.textContent = `Error: ${err}`;
        }
    }

    function initPrimaryNoteUI(patientRecord) {
        const panel = document.getElementById('primaryNotePanel');
        if (!panel) return;
        const docRefs = getDocumentReferences(patientRecord);
        if (!docRefs.length) {
            // keep hidden if none
            return;
        }
        panel.style.display = 'block';
        const select = document.getElementById('docRefSelect');
        if (select) {
            select.innerHTML = '';
            // Build array with id and label, filter those with masterIdentifier.value
            const enriched = docRefs.map(dr => ({
                id: (dr.masterIdentifier && dr.masterIdentifier.value) || '',
                label: buildDocRefLabel(dr),
                raw: dr
            })).filter(o => o.id);
            // Sort by date descending
            enriched.sort((a,b) => {
                const da = Date.parse(a.raw.date || '') || 0;
                const db = Date.parse(b.raw.date || '') || 0;
                return db - da;
            });
            const placeholder = document.createElement('option');
            placeholder.value = '';
            placeholder.textContent = '-- Select Document --';
            select.appendChild(placeholder);
            enriched.forEach(o => {
                const opt = document.createElement('option');
                opt.value = o.id;
                opt.textContent = o.label;
                if (/PRIMARY CARE PROGRESS/i.test(o.label) && !select.querySelector('option[data-primary]')) {
                    opt.setAttribute('data-primary','1');
                }
                select.appendChild(opt);
            });
        }
        const loadLastBtn = document.getElementById('loadPrimaryNoteBtn');
        if (loadLastBtn && !loadLastBtn._bound) {
            loadLastBtn._bound = true;
            loadLastBtn.addEventListener('click', () => fetchPrimaryNote());
        }
        const loadSelectedBtn = document.getElementById('loadSelectedDocBtn');
        if (loadSelectedBtn && !loadSelectedBtn._bound) {
            loadSelectedBtn._bound = true;
            // BUGFIX: use loadSelectedBtn instead of undefined loadSelectedDocBtn
            loadSelectedBtn.addEventListener('click', () => {
                const sel = document.getElementById('docRefSelect');
                if (sel && sel.value) fetchPrimaryNote(sel.value);
            });
        }
    }

    // Attach init to patient info load
    window.initPrimaryNoteUI = initPrimaryNoteUI;

    // --- Patient Demographics Modal ---
    function getPatientResource(patientRecord){
        if (!patientRecord || !Array.isArray(patientRecord.entry)) return null;
        const entry = patientRecord.entry.find(e => e.resource && e.resource.resourceType === 'Patient');
        return entry ? entry.resource : null;
    }
    function formatDOB(dob){
        if (!dob) return '-';
        // Expect YYYY or YYYY-MM or YYYY-MM-DD
        if (/^\d{4}-\d{2}-\d{2}$/.test(dob)){
            const [y,m,d] = dob.split('-');
            return `${m}/${d}/${y}`;
        }
        if (/^\d{4}-\d{2}$/.test(dob)){
            const [y,m] = dob.split('-');
            return `${m}/--/${y}`;
        }
        if (/^\d{4}$/.test(dob)) return `--/--/${dob}`;
        // fallback
        const dt = new Date(dob);
        return isNaN(dt.getTime()) ? String(dob) : dt.toLocaleDateString();
    }
    function extractSSNFromExtensions(ext){
        try {
            if (!Array.isArray(ext)) return null;
            const e = ext.find(x => x && x.url === 'http://hl7.org/fhir/StructureDefinition/patient-mothersMaidenName');
            return e && (e.valueString || e.value) ? (e.valueString || e.value) : null;
        } catch(_) { return null; }
    }
    function extractServiceConnection(ext){
        let scInd = null, scPct = null;
        try {
            if (Array.isArray(ext)){
                const eInd = ext.find(x => x && x.url === 'http://va.gov/fhir/StructureDefinition/service-connected-indicator');
                const ePct = ext.find(x => x && x.url === 'http://va.gov/fhir/StructureDefinition/service-connected-percentage');
                scInd = eInd && (typeof eInd.valueBoolean === 'boolean' ? eInd.valueBoolean : eInd.value === true);
                scPct = ePct && (Number.isFinite(ePct.valueInteger) ? ePct.valueInteger : (typeof ePct.value === 'number' ? ePct.value : null));
            }
        } catch(_){}
        return { scInd, scPct };
    }
    function renderDemographicsHTML(patient){
        if (!patient) return '<em>No demographics found.</em>';
        const name = (patient.name && patient.name[0] && (patient.name[0].text || [
            (Array.isArray(patient.name[0].given)? patient.name[0].given.join(' ') : ''),
            (patient.name[0].family || '')
        ].join(' ').trim())) || '';
        const dob = formatDOB(patient.birthDate);
        const ssn = extractSSNFromExtensions(patient.extension) || '-';
        const { scInd, scPct } = extractServiceConnection(patient.extension || []);
        const scText = (scInd === true ? `Yes${(Number.isFinite(scPct)? ` (${scPct}%)` : '')}` : (scInd === false ? 'No' : '-'));
        const telecom = Array.isArray(patient.telecom) ? patient.telecom : [];
        const phones = telecom.filter(t => (t.system||'').toLowerCase()==='phone').map(t => {
            const use = (t.use || '').toString();
            const useCap = use ? (use.charAt(0).toUpperCase()+use.slice(1)) : '';
            return `${useCap ? useCap+': ' : ''}${t.value || ''}`.trim();
        });
        const emails = telecom.filter(t => (t.system||'').toLowerCase()==='email').map(t => t.value).filter(Boolean);
        const addresses = Array.isArray(patient.address) ? patient.address : [];
        function fmtAddr(a){
            const lines = Array.isArray(a.line) ? a.line.join(', ') : '';
            const city = a.city || '';
            const state = a.state || a.stateProvince || '';
            const zip = a.postalCode || '';
            const use = a.use ? ` (${a.use})` : '';
            const parts = [lines, [city, state].filter(Boolean).join(', '), zip].filter(Boolean).join(' | ');
            return (parts || '-') + use;
        }
        const addrs = addresses.map(fmtAddr);
        return [
            `<div style="padding:4px 2px;"><strong>${escapeHtml(name)}</strong></div>`,
            `<div style="padding:4px 2px;display:grid;grid-template-columns:160px 1fr;gap:6px;align-items:start;">`
              + `<div>DOB</div><div>${escapeHtml(dob)}</div>`
              + `<div>SSN</div><div>${escapeHtml(ssn)}</div>`
              + `<div>Service Connection</div><div>${escapeHtml(scText)}</div>`
              + `<div>Phones</div><div>${phones.length? phones.map(p=>`<div>${escapeHtml(p)}</div>`).join('') : '-'}</div>`
              + `<div>Email</div><div>${emails.length? emails.map(e=>`<div>${escapeHtml(e)}</div>`).join('') : '-'}</div>`
              + `<div>Addresses</div><div>${addrs.length? addrs.map(a=>`<div>${escapeHtml(a)}</div>`).join('') : '-'}</div>`
            + `</div>`
        ].join('');
    }
    async function showPatientDemographicsModal(){
        try {
            let patientRecord = (window.LAST_PATIENT_RECORD) || null;
            if (!patientRecord){
                const res = await fetch('/session_data', { cache: 'no-store' });
                const js = await res.json();
                patientRecord = js.patient_record || null;
            }
            const patient = getPatientResource(patientRecord);
            const modal = document.getElementById('patientDemoModal');
            const content = document.getElementById('patientDemoContent');
            if (!modal || !content) return;
            content.innerHTML = renderDemographicsHTML(patient);
            modal.style.display = 'flex';
        } catch (e){ console.warn('Could not open demographics modal', e); }
    }
    function hidePatientDemographicsModal(){
        const modal = document.getElementById('patientDemoModal');
        if (modal) modal.style.display = 'none';
    }
    // Wire up triggers
    (function(){
        // Skip legacy demographics modal on Workspace; QuickDemographics handles it
        if (window.__IS_WORKSPACE) return;
        const top = document.getElementById('patientLookupResults');
        if (top && !top._demoBound){
            top._demoBound = true;
            top.addEventListener('click', () => { if (top.textContent && top.textContent.trim()) showPatientDemographicsModal(); });
            top.addEventListener('keydown', (e) => {
                if ((e.key === 'Enter' || e.key === ' ') && top.textContent && top.textContent.trim()) { e.preventDefault(); showPatientDemographicsModal(); }
            });
        }
        const closeBtn = document.getElementById('patientDemoCloseBtn');
        if (closeBtn && !closeBtn._demoBound){
            closeBtn._demoBound = true;
            closeBtn.addEventListener('click', hidePatientDemographicsModal);
        }
        const overlay = document.getElementById('patientDemoModal');
        if (overlay && !overlay._demoBound){
            overlay._demoBound = true;
            overlay.addEventListener('click', (e)=>{ if (e.target === overlay) hidePatientDemographicsModal(); });
        }
        document.addEventListener('keydown', (e)=>{
            if (e.key === 'Escape') hidePatientDemographicsModal();
        });
        // NEW: Delegate clicks/keys for when mobile creates #patientLookupResults after DOMContentLoaded
        if (!document._demoDelegationBound){
            if (window.__IS_WORKSPACE) return; // Workspace uses QuickDemographics overlay
            document._demoDelegationBound = true;
            document.addEventListener('click', (e)=>{
                try{
                    const tgt = e.target && (e.target.id === 'patientLookupResults' ? e.target : (e.target.closest ? e.target.closest('#patientLookupResults') : null));
                    if (tgt && tgt.textContent && tgt.textContent.trim()){
                        e.preventDefault();
                        showPatientDemographicsModal();
                    }
                }catch(_e){}
            }, true);
            document.addEventListener('keydown', (e)=>{
                try{
                    const active = document.activeElement;
                    if ((e.key === 'Enter' || e.key === ' ') && active && active.id === 'patientLookupResults' && active.textContent && active.textContent.trim()){
                        e.preventDefault();
                        showPatientDemographicsModal();
                    }
                }catch(_e){}
            }, true);
        }
    })();

    // On DOMContentLoaded, fetch patient info from refactor API and display
    async function tryDisplayPatientInfo() {
        const dfn = Api && Api.getDFN ? Api.getDFN() : '';
        if (!dfn) {
            const topBarStatus = document.getElementById('patientLookupResults');
            if (topBarStatus) topBarStatus.textContent = '';
            return;
        }
        await displayPatientInfoFromApi();
        // Render tables using new APIs
        try {
            // Meds
            if (typeof window.Tabulator !== 'undefined') {
                // Render meds via quick endpoint
                const meds = await Api.quick('meds');
                try {
                    const medTableDiv = document.getElementById('medicationsTable');
                    if (medTableDiv) {
                        const rows = Array.isArray(meds) ? meds.map(m => ({
                            medClass: m.class || m.category || '',
                            name: m.name || m.medication || m.drug || '',
                            dose: m.dose || '',
                            frequency: m.frequency || '',
                            quantity: m.quantity || '',
                            lastFilled: m.lastFilled || m.last || m.start || '',
                            refills: m.refills || '',
                            status: m.status || ''
                        })) : [];
                        if (window.medicationsTabulator) window.medicationsTabulator.destroy();
                        window.medicationsTabulator = new Tabulator('#medicationsTable', {
                            data: rows,
                            layout: 'fitColumns',
                            columns: [
                                { title: 'Class', field: 'medClass' },
                                { title: 'Name', field: 'name' },
                                { title: 'Dose', field: 'dose' },
                                { title: 'Frequency', field: 'frequency' },
                                { title: 'Quantity', field: 'quantity' },
                                { title: 'Last Filled', field: 'lastFilled' },
                                { title: 'Refills', field: 'refills' },
                                { title: 'Status', field: 'status' }
                            ]
                        });
                    }
                } catch {}
            }
        } catch (e) { console.warn('meds load failed', e); }
        try {
            // Labs list (recent 1y)
            const labsEnv = Api && Api.list ? await Api.list('labs', { last: '1y' }) : null;
            const items = extractQuickLabs(labsEnv);
            const data = items.map(r => ({
                date: r.resulted || r.collected || r.date || '',
                test: r.test || r.localName || r.name || '',
                subTest: specimenLabel(r && (r.specimen ?? r.specimenType ?? r.sample ?? r.source ?? r.bodySite ?? null)) || '',
                value: (r.result != null ? r.result : r.value) ?? '',
                unit: r.unit || r.units || '',
                refRange: r.referenceRange || r.range || r.refRange || '',
                interpretation: r.flag || r.interpretation || (r.abnormal === true ? 'A' : ''),
                status: r.status || ''
            }));
            if (typeof window.Tabulator !== 'undefined') {
                if (window.labsTabulator) { window.labsTabulator.replaceData(data); }
                else if (document.getElementById('labsTable')) {
                    window.labsTabulator = new Tabulator('#labsTable', {
                        data,
                        layout: 'fitColumns',
                        pagination: true,
                        paginationSize: 15,
                        columns: [
                            { title: 'Date', field: 'date' },
                            { title: 'Test', field: 'test' },
                            { title: 'Component', field: 'subTest' },
                            { title: 'Value', field: 'value' },
                            { title: 'Unit', field: 'unit' },
                            { title: 'Ref Range', field: 'refRange' },
                            { title: 'Interp', field: 'interpretation' },
                            { title: 'Status', field: 'status' }
                        ]
                    });
                }
            }
        } catch (e) { console.warn('labs load failed', e); }
    }
    // Run after DOM is fully loaded
    if (document.readyState === "complete" || document.readyState === "interactive") {
        setTimeout(tryDisplayPatientInfo, 0);
    } else {
        window.addEventListener("DOMContentLoaded", tryDisplayPatientInfo);
    }
    // Refresh patient info when DFN changes
    try { window.addEventListener('patient:changed', () => { tryDisplayPatientInfo(); }); } catch(_e){}
});