// Patient Chart RAG Query logic for Explore page
window.submitPatientRagQuery = async function() {
    const input = document.getElementById('patientRagQueryInput');
    const answerBox = document.getElementById('patientRagQueryAnswer');
    const query = input.value.trim();
    if (!query) {
        answerBox.innerHTML = '<span style="color:red">Please enter a question.</span>';
        return;
    }
    answerBox.innerHTML = '<em>Querying patient chart...</em>';
    try {
        const resp = await fetch('/patient/query_chart', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ query })
        });
        const data = await resp.json();
        if (data.error) {
            answerBox.innerHTML = `<span style='color:red'>${data.error}</span>`;
            return;
        }
        if (data.matches && data.matches.length > 0) {
            let html = '<b>Top Matches:</b><ul>';
            for (const m of data.matches) {
                html += `<li><pre style='white-space:pre-wrap'>${m.text}</pre><div style='font-size:0.9em;color:#888'>Score: ${m.score.toFixed(3)}</div></li>`;
            }
            html += '</ul>';
            answerBox.innerHTML = html;
        } else {
            answerBox.innerHTML = '<em>No relevant information found in patient chart.</em>';
        }
    } catch (e) {
        answerBox.innerHTML = `<span style='color:red'>Error: ${e}</span>`;
    }
};

// Poll ingestion coverage and update UI
function pollIngestionCoverage() {
    const statusDiv = document.getElementById('ingestionCoverageStatus');
    if (!statusDiv) return;
    async function update() {
        try {
            const resp = await fetch('/patient/ingestion_coverage');
            if (!resp.ok) throw new Error('Failed to fetch coverage');
            const data = await resp.json();
            let html = '';
            if (data.coverage) {
                html += `<b>Indexed notes:</b> ${data.ingested_count}`;
                if (data.coverage.earliest && data.coverage.latest) {
                    html += ` | <b>Date range:</b> ${data.coverage.earliest} to ${data.coverage.latest}`;
                }
            } else {
                html += 'No chart ingestion in progress.';
            }
            if (data.done) {
                html += ' <span style="color:green;font-weight:bold;">(Indexing complete)</span>';
            } else if (data.ingested_count > 0) {
                html += ' <span style="color:#b8860b;">(Indexing in progress...)</span>';
            }
            statusDiv.innerHTML = html;
            statusDiv.style.display = (data.coverage || data.ingested_count > 0) ? '' : 'none';
        } catch (e) {
            statusDiv.innerHTML = '<span style="color:red">Error loading ingestion status.</span>';
            statusDiv.style.display = '';
        }
    }
    update();
    // Poll every 4 seconds
    setInterval(update, 4000);
}

// Start polling on load
if (typeof window !== 'undefined') {
    window.addEventListener('DOMContentLoaded', pollIngestionCoverage);
}
