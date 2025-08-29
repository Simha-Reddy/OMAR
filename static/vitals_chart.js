// ECharts integration for Vitals visualization on the Explore page.
// Defines a global function window.renderVitalsChart
// Assumes ECharts is loaded via CDN

window.renderVitalsChart = function(domId, patientRecord, options = {}) {
    if (!window.echarts) {
        console.error('ECharts library not loaded!');
        return;
    }
    const chartDom = document.getElementById(domId);
    if (!chartDom) {
        console.error('Vitals chart container not found:', domId);
        return;
    }
    // Dispose any existing chart instance on this dom
    const existing = echarts.getInstanceByDom(chartDom);
    if (existing) {
        echarts.dispose(chartDom);
    }
    const chart = echarts.init(chartDom);

    // Use patient.js to get vitals
    if (!window.getVitals) {
        chartDom.textContent = 'Vitals extraction not available.';
        return;
    }
    const vitals = window.getVitals(patientRecord);
    if (!vitals || !vitals.length) {
        chartDom.textContent = 'No vital signs found.';
        return;
    }

    // Normalize and group by time
    function parseTimeToISO(t) {
        if (typeof t === 'string') {
            if (/^\d{14}$/.test(t)) {
                // YYYYMMDDHHMMSS
                const y = t.slice(0,4), m = t.slice(4,6), d = t.slice(6,8),
                      H = t.slice(8,10), M = t.slice(10,12), S = t.slice(12,14);
                return `${y}-${m}-${d}T${H}:${M}:${S}Z`;
            } else if (/^\d{12}$/.test(t)) {
                // YYYYMMDDHHMM
                const y = t.slice(0,4), m = t.slice(4,6), d = t.slice(6,8),
                      H = t.slice(8,10), M = t.slice(10,12);
                return `${y}-${m}-${d}T${H}:${M}:00Z`;
            } else if (/^\d{8}$/.test(t)) {
                // YYYYMMDD
                const y = t.slice(0,4), m = t.slice(4,6), d = t.slice(6,8);
                return `${y}-${m}-${d}T00:00:00Z`;
            }
        }
        const d = new Date(t);
        if (!isNaN(d)) return d.toISOString();
        return t;
    }
    const normalizeVitalName = (name) => {
        if (!name) return 'Unknown';
        const n = name.toUpperCase();
        if (n === 'PULSE') return 'Pulse';
        if (n === 'PULSE OXIMETRY') return 'SpO2';
        if (n === 'TEMPERATURE') return 'Temp';
        if (n === 'RESPIRATION') return 'Resp';
        if (n === 'BLOOD PRESSURE') return 'BP';
        if (n === 'HEIGHT') return 'Height';
        if (n === 'WEIGHT') return 'Weight';
        return name.charAt(0).toUpperCase() + name.slice(1).toLowerCase();
    };
    const timeMap = {};
    vitals.forEach(obs => {
        // Debug log: print all code/text/coding for each vital
        console.log('VITAL OBS:', {
            code: obs.code,
            codeText: obs.code && obs.code.text,
            codeCoding: obs.code && obs.code.coding,
            valueQuantity: obs.valueQuantity,
            components: obs.component
        });
        const time = parseTimeToISO(obs.effectiveDateTime || obs.issued || obs.issuedDateTime || '');
        if (!time) return;
        if (!timeMap[time]) timeMap[time] = { time };
        let vitalType = obs.code && obs.code.text ? obs.code.text : (obs.code && obs.code.coding && obs.code.coding[0] && obs.code.coding[0].display) || 'Unknown';
        vitalType = normalizeVitalName(vitalType);
        // Handle BP as two values if present in components
        if (vitalType === 'BP' && Array.isArray(obs.component)) {
            obs.component.forEach(comp => {
                const compCode = comp.code && (comp.code.text || (comp.code.coding && comp.code.coding[0] && comp.code.coding[0].display));
                if (compCode) {
                    const codeNorm = compCode.toUpperCase();
                    if (codeNorm.includes('SYSTOLIC')) {
                        timeMap[time]['BP Systolic'] = comp.valueQuantity && typeof comp.valueQuantity.value === 'number' ? comp.valueQuantity.value : undefined;
                    } else if (codeNorm.includes('DIASTOLIC')) {
                        timeMap[time]['BP Diastolic'] = comp.valueQuantity && typeof comp.valueQuantity.value === 'number' ? comp.valueQuantity.value : undefined;
                    }
                }
            });
        } else if (vitalType === 'BP' && obs.valueQuantity && typeof obs.valueQuantity.value === 'string' && /^\d{2,3}\/\d{2,3}$/.test(obs.valueQuantity.value)) {
            // Handle BP as string like '135/100'
            const [sys, dia] = obs.valueQuantity.value.split('/').map(Number);
            if (!isNaN(sys)) timeMap[time]['BP Systolic'] = sys;
            if (!isNaN(dia)) timeMap[time]['BP Diastolic'] = dia;
        } else if (vitalType === 'BP' && obs.valueQuantity && typeof obs.valueQuantity.value === 'number') {
            // Fallback: single value BP
            timeMap[time]['BP'] = obs.valueQuantity.value;
        } else if (obs.valueQuantity && typeof obs.valueQuantity.value === 'number') {
            timeMap[time][vitalType] = obs.valueQuantity.value;
        }
    });
    const vitalsData = Object.values(timeMap).sort((a, b) => new Date(a.time) - new Date(b.time));
    // Sort vitalsData so most recent is first
    vitalsData.sort((a, b) => new Date(b.time) - new Date(a.time));
    // Build vitalTypes from all numeric types, then add BP if any BP Systolic or Diastolic present in vitalsData
    let vitalTypes = Array.from(new Set(
        vitals.flatMap(obs => {
            let name = obs.code && obs.code.text ? obs.code.text : (obs.code && obs.code.coding && obs.code.coding[0] && obs.code.coding[0].display) || 'Unknown';
            name = normalizeVitalName(name);
            if (name === 'BP') return [];
            if (obs.valueQuantity && typeof obs.valueQuantity.value === 'number') return [name];
            return [];
        })
    ));
    // If any BP Systolic or Diastolic present in vitalsData, add 'BP' to vitalTypes
    if (vitalsData.some(row => row['BP Systolic'] !== undefined || row['BP Diastolic'] !== undefined)) {
        if (!vitalTypes.includes('BP')) vitalTypes.push('BP');
    }
    if (!vitalTypes.length) {
        chartDom.textContent = 'No numeric vital signs found.';
        return;
    }

    // Add dropdown for vital type selection (only create once)
    let vitalTypeSelect = document.getElementById('vitalTypeSelect');
    if (!vitalTypeSelect) {
        vitalTypeSelect = document.createElement('select');
        vitalTypeSelect.id = 'vitalTypeSelect';
        chartDom.parentNode.insertBefore(vitalTypeSelect, chartDom.nextSibling);
    }
    // Always rebuild dropdown after vitalTypes is finalized
    vitalTypeSelect.innerHTML = '';
    vitalTypes.forEach(type => {
        const opt = document.createElement('option');
        opt.value = type;
        opt.textContent = type;
        vitalTypeSelect.appendChild(opt);
    });

    function render(type) {
        if (type === 'BP') {
            // BP: plot both Systolic and Diastolic if present
            let filtered = vitalsData
                .filter(row => (row['BP Systolic'] !== undefined && row['BP Systolic'] !== null) || (row['BP Diastolic'] !== undefined && row['BP Diastolic'] !== null))
                .map(row => ({
                    time: row.time,
                    systolic: row['BP Systolic'],
                    diastolic: row['BP Diastolic']
                }));
            filtered = filtered
                .map(row => ({...row, dateObj: new Date(row.time)}))
                .filter(row => !isNaN(row.dateObj))
                .sort((a, b) => b.dateObj - a.dateObj)
                .map(row => ({ time: row.dateObj.toISOString(), systolic: row.systolic, diastolic: row.diastolic }));

            // Debug: log the sorted times
            console.log('Sorted times for BP', filtered.map(row => row.time));

            const systolicData = filtered.filter(row => row.systolic !== undefined).map(row => [row.time, row.systolic]);
            const diastolicData = filtered.filter(row => row.diastolic !== undefined).map(row => [row.time, row.diastolic]);

            const series = [];
            if (systolicData.length) {
                series.push({
                    name: 'Systolic',
                    type: 'line',
                    showSymbol: true,
                    data: systolicData,
                    connectNulls: true
                });
            }
            if (diastolicData.length) {
                series.push({
                    name: 'Diastolic',
                    type: 'line',
                    showSymbol: true,
                    data: diastolicData,
                    connectNulls: true
                });
        }

        const option = {
                title: { text: 'Blood Pressure Over Time' },
            tooltip: {
                    trigger: 'item',
                    position: 'top',
                    formatter: function(params) {
                        // params is an object for trigger: 'item'
                        // Find all vitals at this time
                        const point = params.data;
                        const time = point[0];
                        const dateStr = new Date(time).toLocaleString();
                        // Find the most recent row in vitalsData with this time
                        const matchingRows = vitalsData.filter(r => (r.time === time) || (new Date(r.time).toISOString() === time));
                        const row = matchingRows.length ? matchingRows[0] : null;
                        if (!row) return dateStr;
                        let html = `<b>${dateStr}</b><br/>`;
                        if (row['BP Systolic'] !== undefined || row['BP Diastolic'] !== undefined) {
                            html += `BP: ${row['BP Systolic'] || ''}${row['BP Systolic'] && row['BP Diastolic'] ? '/' : ''}${row['BP Diastolic'] || ''}<br/>`;
                        }
                        for (const key of Object.keys(row)) {
                            if (key === 'time' || key.startsWith('BP')) continue;
                            if (row[key] !== undefined && row[key] !== null) {
                                html += `${key}: ${row[key]}<br/>`;
                            }
                        }
                        return html;
                    }
                },
                legend: { data: ['Systolic', 'Diastolic'] },
            dataZoom: [
                { type: 'slider', xAxisIndex: 0, start: 0, end: 100 },
                { type: 'inside', xAxisIndex: 0, start: 0, end: 100 }
            ],
            xAxis: {
                type: 'time',
                boundaryGap: false,
                    axisPointer: { type: 'line', snap: true },
                axisLabel: {
                    rotate: 30,
                    formatter: function(value) {
                            const d = new Date(value);
                            if (isNaN(d)) return value;
                            return d.toISOString().slice(0, 10);
                    }
                }
            },
            yAxis: { type: 'value', scale: true },
            series: series
        };
        chart.setOption(option, true);
        } else {
            // Only include rows with a value for the selected vital
            let filtered = vitalsData
                .filter(row => row[type] !== undefined && row[type] !== null)
                .map(row => ({
                    time: row.time,
                    value: row[type],
                    BP: row['BP']
                }));
            // Sort by Date object, not string
            filtered = filtered
                .map(row => ({...row, dateObj: new Date(row.time)}))
                .filter(row => !isNaN(row.dateObj))
                .sort((a, b) => a.dateObj - b.dateObj)
                .map(row => ({ time: row.dateObj.toISOString(), value: row.value, BP: row.BP }));

            // Debug: log the sorted times
            console.log('Sorted times for', type, filtered.map(row => row.time));

            const data = filtered.map(row => [row.time, row.value]);

            const series = [{
                name: type,
                type: 'line',
                showSymbol: true,
                data: data,
                connectNulls: true
            }];

            const option = {
                title: { text: type + ' Over Time' },
                tooltip: {
                    trigger: 'item',
                    position: 'top',
                    formatter: function(params) {
                        const point = params.data;
                        const time = point[0];
                        const dateStr = new Date(time).toLocaleString();
                        const row = vitalsData.find(r => {
                            return (r.time === time) || (new Date(r.time).toISOString() === time);
                        });
                        if (!row) return dateStr;
                        let html = `<b>${dateStr}</b><br/>`;
                        if (row['BP Systolic'] !== undefined || row['BP Diastolic'] !== undefined) {
                            html += `BP: ${row['BP Systolic'] || ''}${row['BP Systolic'] && row['BP Diastolic'] ? '/' : ''}${row['BP Diastolic'] || ''}<br/>`;
                        }
                        for (const key of Object.keys(row)) {
                            if (key === 'time' || key.startsWith('BP')) continue;
                            if (row[key] !== undefined && row[key] !== null) {
                                html += `${key}: ${row[key]}<br/>`;
                            }
                        }
                        return html;
                    }
                },
                legend: { data: [type] },
                dataZoom: [
                    { type: 'slider', xAxisIndex: 0, start: 0, end: 100 },
                    { type: 'inside', xAxisIndex: 0, start: 0, end: 100 }
                ],
                xAxis: {
                    type: 'time',
                    boundaryGap: false,
                    axisPointer: { type: 'line', snap: true },
                    axisLabel: {
                        rotate: 30,
                        formatter: function(value) {
                            const d = new Date(value);
                            if (isNaN(d)) return value;
                            return d.toISOString().slice(0, 10);
                        }
                    }
                },
                yAxis: { type: 'value', scale: true, axisPointer: { type: 'line', snap: true } },
                series: series
            };
            chart.setOption(option, true); // true for notMerge, to fully update
        }
    }

    // Initial render (always use first available type)
    // Default to the most recent vital type if available
    render(vitalTypeSelect.value || vitalTypes[0]);
    vitalTypeSelect.onchange = function() {
        render(this.value);
    };

    // --- NEW SUMMARY BAR: Show most recent value for each vital in requested order, with units and date/time ---
    // Define the order and display names/units for vitals
    const vitalDisplayOrder = [
        { key: 'Temp', label: 'Temp', units: '°F' },
        { key: 'BP', label: 'BP', units: 'mmHg' },
        { key: 'Pulse', label: 'HR', units: '/min' },
        { key: 'SpO2', label: 'SpO₂', units: '%' },
        { key: 'Resp', label: 'Resp', units: '/min' },
        { key: 'Weight', label: 'Weight', units: 'lb' },
        { key: 'Height', label: 'Height', units: 'in' },
        { key: 'Pain', label: 'Pain', units: '' }
    ];
    // Find the most recent value for each vital type
    function findMostRecentVital(vitalKey) {
        // Use vitalsData, which is already sorted descending by time
        for (let i = 0; i < vitalsData.length; i++) {
            const row = vitalsData[i];
            if (vitalKey === 'BP' && (row['BP Systolic'] !== undefined || row['BP Diastolic'] !== undefined)) {
                let value = '';
                if (row['BP Systolic'] !== undefined && row['BP Diastolic'] !== undefined) {
                    value = `${row['BP Systolic']}/${row['BP Diastolic']}`;
                } else if (row['BP Systolic'] !== undefined) {
                    value = `${row['BP Systolic']}`;
                } else if (row['BP Diastolic'] !== undefined) {
                    value = `${row['BP Diastolic']}`;
                }
                return { value, units: 'mmHg', time: row.time };
            } else if (row[vitalKey] !== undefined && row[vitalKey] !== null) {
                return { value: row[vitalKey], units: '', time: row.time };
            }
        }
        return null;
    }
    // Create a container for the summary bar if not present
    let summaryBar = document.getElementById('vitalsSummaryBar');
    if (!summaryBar) {
        summaryBar = document.createElement('div');
        summaryBar.id = 'vitalsSummaryBar';
        summaryBar.style.display = 'flex';
        summaryBar.style.justifyContent = 'space-between';
        summaryBar.style.flexWrap = 'wrap';
        summaryBar.style.marginBottom = '16px';
        summaryBar.style.padding = '12px 8px 8px 8px';
        summaryBar.style.border = '1px solid #ccc';
        summaryBar.style.background = '#f9f9f9';
        summaryBar.style.borderRadius = '8px';
        summaryBar.style.boxShadow = '0 2px 8px rgba(0,0,0,0.04)';
        chartDom.parentNode.insertBefore(summaryBar, chartDom);
    }
    // Update summary bar content
    let summaryHtml = '';
    const now = new Date('2025-07-22T12:00:00Z'); // Use current date for comparison
    vitalDisplayOrder.forEach(vital => {
        const mostRecent = findMostRecentVital(vital.key);
        if (mostRecent) {
            // Debug: log the raw date value
            console.log(`Raw date for ${vital.label}:`, mostRecent.time);
            let vitalTime = mostRecent.time;
            // If vitalTime is a number or a string of digits, treat as YYYYMMDDHHMMSS
            if (typeof vitalTime === 'number' || (typeof vitalTime === 'string' && /^\d{12,14}$/.test(vitalTime))) {
                vitalTime = parseTimeToISO(vitalTime);
            }
            vitalTime = new Date(vitalTime);
            const isValidDate = vitalTime instanceof Date && !isNaN(vitalTime);
            const isOld = isValidDate && (now - vitalTime) > 24 * 60 * 60 * 1000;
            summaryHtml += `<div style="flex: 1 1 120px; margin: 4px; text-align: center; min-width: 110px; max-width: 160px;">
                <div style="font-size: 20px; font-weight: bold; ${isOld ? 'color: #888; font-style: italic;' : 'color: #222;'}">
                    ${mostRecent.value} <span style="font-size:14px; color:#888;">${vital.units || mostRecent.units || ''}</span>
                </div>
                <div style="font-size: 15px; color: #0078d4; margin-bottom:2px; letter-spacing:0.5px;">${vital.label}</div>
                <div style="font-size: 12px; color: #aaa; margin-top:2px;">${isValidDate ? vitalTime.toLocaleString([], { year: 'numeric', month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' }) : 'No date'}</div>
            </div>`;
        } else {
            summaryHtml += `<div style="flex: 1 1 120px; margin: 4px; text-align: center; min-width: 110px; max-width: 160px;">
                <div style="font-size: 20px; color: #ccc;">--</div>
                <div style="font-size: 15px; color: #0078d4; margin-bottom:2px; letter-spacing:0.5px;">${vital.label}</div>
                <div style="font-size: 12px; color: #eee; margin-top:2px;">No data</div>
            </div>`;
        }
    });
    summaryBar.innerHTML = summaryHtml;
};
