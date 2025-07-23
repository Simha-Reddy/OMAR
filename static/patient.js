window.addEventListener("DOMContentLoaded", () => {
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

    // Main function to display patient info
    function displayPatientInfo(patientRecord) {
        if (!patientRecord) {
            console.error("No patient record provided.");
            return;
        }
        const name = getPatientName(patientRecord);
        const dob = getPatientDOB(patientRecord);
        // Update DOM elements
        const patientNameDisplay = document.getElementById("patientNameDisplay");
        if (patientNameDisplay) {
            patientNameDisplay.textContent = `Name: ${name}, DOB: ${dob}`;
        }
        const patientRecordJson = document.getElementById("patientRecordJson");
        if (patientRecordJson) {
            patientRecordJson.textContent = JSON.stringify(patientRecord, null, 2);
        }
        // Debug log
        console.log("Rendering patient record modules", patientRecord);
        renderPatientRecordModules(patientRecord);
    }

    // Expose functions globally
    window.displayPatientInfo = displayPatientInfo;
    window.getPatientName = getPatientName;
    window.getPatientDOB = getPatientDOB;
    window.getLabs = getLabs;
    window.getVitals = getVitals;

    // On DOMContentLoaded, fetch session and display info
    async function tryDisplayPatientInfo() {
        try {
            const res = await fetch("/session_data");
            const sessionData = await res.json();
            const patientRecord = sessionData.patient_record;
            if (patientRecord) {
                displayPatientInfo(patientRecord);
            } else {
                console.warn("No patient_record in session_data");
            }
        } catch (error) {
            console.error("Error fetching patient info:", error);
        }
    }
    // Run after DOM is fully loaded
    if (document.readyState === "complete" || document.readyState === "interactive") {
        setTimeout(tryDisplayPatientInfo, 0);
    } else {
        window.addEventListener("DOMContentLoaded", tryDisplayPatientInfo);
    }
});