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
    }

    // Expose functions globally
    window.displayPatientInfo = displayPatientInfo;
    window.getPatientName = getPatientName;
    window.getPatientDOB = getPatientDOB;

    // On DOMContentLoaded, fetch session and display info
    window.addEventListener("DOMContentLoaded", async () => {
        try {
            const res = await fetch("/session_data");
            const sessionData = await res.json();
            const patientRecord = sessionData.patient_record;
            if (patientRecord) {
                displayPatientInfo(patientRecord);
            }
        } catch (error) {
            console.error("Error fetching patient info:", error);
        }
    });
});