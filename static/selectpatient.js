// Handles patient selection
window.selectPatientDFN = async function(dfn, name) {
    const res = await fetch("/select_patient", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ user_id: dfn, station: "500" })
    });
    const data = await res.json();
    document.getElementById("patientLookupResults").textContent = `Selected: ${name} (DFN: ${dfn})`;
    if (typeof updatePatientNameDisplay === "function") updatePatientNameDisplay();
};

// Attach event listeners
window.addEventListener("DOMContentLoaded", () => {
    const selectPatientBtn = document.getElementById("selectPatientBtn");

    if (selectPatientBtn) {
        selectPatientBtn.onclick = async function() {
            const patient_dfn = prompt("Enter patient DFN:");
            if (!patient_dfn) return;
            const res = await fetch("/select_patient", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ patient_dfn })
            });
            const data = await res.json();
            if (data && !data.error) {
                console.log(data); // Log the full medical record for debugging or further use
                if (window.displayPatientInfo) {
                    window.displayPatientInfo(data);
                }
            } else {
                alert("Failed to select patient: " + (data.error || "Unknown error"));
            }
        };
    }
});