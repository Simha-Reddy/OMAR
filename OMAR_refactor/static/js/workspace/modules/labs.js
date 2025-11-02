// Labs Module for Workspace
// Integrates with existing labs functionality

window.WorkspaceModules = window.WorkspaceModules || {};

window.WorkspaceModules['Labs'] = {
    data: null,
    // Keep a persistent Tabulator instance to allow in-place updates without flicker
    table: null,
    // Root element for this module instance; scope all queries here
    rootEl: null,
    // Hint to workspace orchestrator to avoid hard re-render when DFN unchanged
    preserveOnRefresh: true,

    async render(container, options = {}) {
        try {
            const perfOn = (function(){ try{ return window.__WS_PERF || localStorage.getItem('ws_perf')==='1'; }catch(_e){ return false; } })();
            const tStart = (perfOn && performance && performance.now) ? performance.now() : 0;
            container.innerHTML = '<div class="module-loading">Loading labs...</div>';
            // Default to 365 days to show past year by default
            await this.loadData(365);
            container.innerHTML = `
                <div class="labs-module">
                    <div class="module-header">
                        <h3>Laboratory Results</h3>
                        <div class="labs-controls">
                            <select id="labs-days-filter">
                                <option value="30">Last 30 days</option>
                                <option value="90">Last 90 days</option>
                                <option value="365" selected>Last year</option>
                                <option value="all">All results</option>
                            </select>
                            <button class="refresh-btn" onclick="window.WorkspaceModules['Labs'].refresh()">Refresh</button>
                        </div>
                    </div>
                    <div class="labs-content">
                        <div class="labs-summary" id="labs-summary-workspace">
                            <!-- Recent key labs will go here -->
                        </div>
                        <div class="labs-table-container">
                            <div id="labs-table-workspace" style="height: 400px;"></div>
                        </div>
                    </div>
                </div>
            `;
            // Scope root to this instance
            this.rootEl = container.querySelector('.labs-module') || container;
            this.renderLabsSummary();
            await this.renderLabsTable();
            this.setupEventListeners();
            if (perfOn && performance && performance.now) {
                try { console.log(`LABS:render took ${(performance.now()-tStart).toFixed(0)}ms`); } catch(_e){}
            }
        } catch (error) {
            console.error('[Labs] Error in render:', error);
            const msg = (error && error.message) ? error.message : 'Unknown error';
            const friendly = /No patient selected/i.test(msg) ? 'Select a patient to view labs.' : `Error loading labs: ${msg}`;
            container.innerHTML = `
                <div class="module-error">
                    <h3>Labs Module</h3>
                    <p>${friendly}</p>
                    <button onclick="window.WorkspaceModules['Labs'].refresh()">Retry</button>
                </div>
            `;
        }
    },

    async loadData(days = 365) {
        try {
            let url = '/quick/patient/labs';
            if (typeof days === 'number' && isFinite(days) && days > 0) {
                // Request a bounded number of panels and include result payloads (server may ignore extra params safely)
                const params = new URLSearchParams();
                params.set('days', String(days));
                params.set('maxPanels', '60');
                params.set('results', '1');
                url += `?${params.toString()}`;
            }
            const response = await fetch(url, { cache: 'no-store', credentials: 'same-origin', headers: { 'Accept': 'application/json', 'X-Caller': 'LabsModule' } });
            if (!response.ok) {
                // Try to parse JSON error for clarity
                let emsg = response.statusText;
                try { const j = await response.json(); if (j && j.error) emsg = j.error; } catch(_e){}
                throw new Error(emsg || `HTTP ${response.status}`);
            }
            this.data = await response.json();
        } catch (error) {
            console.error('Error loading labs data:', error);
            throw error;
        }
    },

    renderLabsSummary() {
        const root = this.rootEl || document;
        const summaryContainer = root.querySelector('#labs-summary-workspace');
        if (!summaryContainer || !this.data || !this.data.labs) {
            if (summaryContainer) {
                summaryContainer.innerHTML = '<div class="labs-empty">No lab results available.</div>';
            }
            return;
        }

        const labs = this.data.labs;
        
        // Group labs by key types for summary
        const keyLabs = this.getKeyLabsSummary(labs);
        
        let html = '<div class="key-labs-grid">';
        
        Object.entries(keyLabs).forEach(([category, items]) => {
            if (items.length > 0) {
                html += `
                    <div class="key-lab-category">
                        <h4>${category}</h4>
                        <div class="lab-items">
                `;
                
                items.forEach(item => {
                    const abnormalClass = item.abnormal ? 'abnormal' : '';
                    html += `
                        <div class="lab-item ${abnormalClass}">
                            <span class="lab-name">${item.name}:</span>
                            <span class="lab-value">${item.value} ${item.unit || ''}</span>
                            <span class="lab-date">${this.formatDate(item.date)}</span>
                        </div>
                    `;
                });
                
                html += `
                        </div>
                    </div>
                `;
            }
        });
        
        html += '</div>';
        summaryContainer.innerHTML = html;
    },

    getKeyLabsSummary(labs) {
        const keyLabs = {
            'Chemistry': [],
            'Hematology': [],
            'Other': []
        };

        // Get most recent results for key lab types
        const labGroups = {};
        
        labs.forEach(lab => {
            const key = this.getLabKey(lab);
            if (!labGroups[key] || new Date(lab.resulted || lab.collected) > new Date(labGroups[key].resulted || labGroups[key].collected)) {
                labGroups[key] = lab;
            }
        });

        Object.values(labGroups).forEach(lab => {
            const category = this.getLabCategory(lab);
            if (this.isKeyLab(lab)) {
                keyLabs[category].push({
                    name: lab.test || lab.localName || 'Unknown',
                    value: lab.result,
                    unit: lab.unit,
                    date: lab.resulted || lab.collected,
                    abnormal: lab.abnormal
                });
            }
        });

        return keyLabs;
    },

    getLabKey(lab) {
        return `${lab.test || lab.localName || 'unknown'}_${lab.loinc || 'no-loinc'}`;
    },

    getLabCategory(lab) {
        const name = (lab.test || lab.localName || '').toLowerCase();
        const category = (lab.broadCategory || '').toLowerCase();
        
        if (category.includes('chemistry') || name.includes('glucose') || name.includes('sodium') || name.includes('potassium')) {
            return 'Chemistry';
        } else if (category.includes('hematology') || name.includes('wbc') || name.includes('rbc') || name.includes('hemoglobin')) {
            return 'Hematology';
        } else {
            return 'Other';
        }
    },

    isKeyLab(lab) {
        const name = (lab.test || lab.localName || '').toLowerCase();
        const keyTerms = [
            'glucose', 'sodium', 'potassium', 'chloride', 'co2', 'bun', 'creatinine',
            'wbc', 'rbc', 'hemoglobin', 'hematocrit', 'platelets',
            'cholesterol', 'triglycerides', 'hdl', 'ldl', 'a1c', 'psa'
        ];
        
        return keyTerms.some(term => name.includes(term));
    },

    async renderLabsTable() {
        const root = this.rootEl || document;
        const tableContainer = root.querySelector('#labs-table-workspace');
        if (!tableContainer) return;

        // Ensure Tabulator is available via static include
        if (!window.Tabulator) {
            console.error('[Labs] Tabulator missing. Ensure static includes in workspace.html/workspace_mobile.html.');
            tableContainer.innerHTML = '<p>Table functionality not available (Tabulator not loaded)</p>';
            return;
        }

        if (!this.data || !this.data.labs || this.data.labs.length === 0) {
            tableContainer.innerHTML = '<div class="labs-empty">No lab results to display.</div>';
            // If we have an existing table, clear its rows to reflect empty state without destroying the component
            try { if (this.table) { this.table.clearData(); } } catch(_e){}
            return;
        }

        try {
            // If a table already exists and is mounted, update data in place to avoid flicker
            if (this.table && this.table.element && document.body.contains(this.table.element)) {
                try { this.table.setData(this.data.labs); } catch(_e){ try { this.table.replaceData(this.data.labs); } catch(__e){} }
                return;
            }

            // Otherwise, create a new Tabulator instance
            tableContainer.innerHTML = '';
            const table = new Tabulator(tableContainer, {
                data: this.data.labs,
                pagination: "local",
                paginationSize: 50,
                layout: "fitColumns",
                columns: [
                    {
                        title: "Test",
                        field: "test",
                        formatter: function(cell) {
                            return cell.getValue() || cell.getRow().getData().localName || "Unknown";
                        },
                        width: 200
                    },
                    {
                        title: "Result",
                        field: "result",
                        formatter: function(cell) {
                            const data = cell.getRow().getData();
                            const result = cell.getValue();
                            const unit = data.unit || '';
                            const abnormal = data.abnormal;
                            
                            const className = abnormal ? 'abnormal-result' : '';
                            return `<span class="${className}">${result} ${unit}</span>`;
                        }
                    },
                    {
                        title: "Reference Range",
                        field: "referenceRange",
                        formatter: function(cell) {
                            const data = cell.getRow().getData();
                            // Prefer already-parsed string range from quick endpoint
                            if (data.referenceRange) {
                                return String(data.referenceRange);
                            }
                            // Fallbacks for FHIR-based rows
                            if (data.low != null && data.high != null) {
                                return `${data.low} - ${data.high}`;
                            } else if (data.low != null) {
                                return `> ${data.low}`;
                            } else if (data.high != null) {
                                return `< ${data.high}`;
                            }
                            return "";
                        }
                    },
                    {
                        title: "Date",
                        field: "resulted",
                        formatter: function(cell) {
                            const date = cell.getValue() || cell.getRow().getData().collected;
                            return date ? new Date(date).toLocaleDateString() : '';
                        },
                        sorter: "date",
                        sorterParams: { format: "iso" }
                    },
                    {
                        title: "Status",
                        field: "abnormal",
                        formatter: function(cell) {
                            const abnormal = cell.getValue();
                            if (abnormal === true) {
                                return '<span class="status-abnormal">Abnormal</span>';
                            } else if (abnormal === false) {
                                return '<span class="status-normal">Normal</span>';
                            }
                            return '';
                        },
                        width: 100
                    }
                ],
                initialSort: [
                    { column: "resulted", dir: "desc" }
                ]
            });
            // Persist instance for soft refresh
            this.table = table;
        } catch (error) {
            console.error('Error creating labs table:', error);
            tableContainer.innerHTML = '<div class="table-error">Error creating table</div>';
        }
    },

    setupEventListeners() {
        const root = this.rootEl || document;
        const daysFilter = root.querySelector('#labs-days-filter');
        if (daysFilter) {
            // Replace any prior listeners to prevent duplicate triggers
            try { daysFilter.onchange = null; } catch(_e){}
            daysFilter.addEventListener('change', async (e) => {
                const val = e.target.value;
                const days = (val === 'all') ? null : parseInt(val, 10);
                await this.loadData(days);
                this.renderLabsSummary();
                await this.renderLabsTable();
            }, { once: false });
        }
    },

    // Soft refresh used by orchestrator to avoid clearing DOM and flicker
    async refreshSoft() {
        try {
            const root = this.rootEl || document;
            const daysFilter = root.querySelector('#labs-days-filter');
            const days = daysFilter ? (daysFilter.value === 'all' ? null : parseInt(daysFilter.value, 10)) : 365;
            await this.loadData(days);
            this.renderLabsSummary();
            await this.renderLabsTable();
        } catch (e) {
            console.error('[Labs] refreshSoft error:', e);
        }
    },

    formatDate(dateString) {
        if (!dateString) return '';
        try {
            return new Date(dateString).toLocaleDateString();
        } catch {
            return dateString;
        }
    },

    async refresh() {
        try {
            // Delegate to soft refresh to avoid tearing down DOM
            await this.refreshSoft();
        } catch (e) {
            console.error('[Labs] refresh error:', e);
        }
    },

    // Allow workspace to clean up on patient switch/layout reset
    destroy() {
        try { if (this.table && typeof this.table.destroy === 'function') { this.table.destroy(); } } catch(_e){}
        this.table = null;
        this.data = null;
        try { const root = this.rootEl || document; const daysFilter = root.querySelector('#labs-days-filter'); if (daysFilter) daysFilter.onchange = null; } catch(_e){}
        this.rootEl = null;
    }
};

// No global event listeners; orchestrator will trigger refresh at correct stage
