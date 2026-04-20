document.addEventListener('DOMContentLoaded', () => {
    
    // Global Constants
    const AQI_COLORS = {
        'Good': 'bg-good',
        'Satisfactory': 'bg-satisfactory',
        'Moderate': 'bg-moderate',
        'Poor': 'bg-poor',
        'Very Poor': 'bg-very-poor',
        'Severe': 'bg-severe'
    };

    let globalMetadata = {
        cities: [],
        stations: [],
        pollutants: []
    };

    // --- Page Init ---
    const path = window.location.pathname;
    
    if (path === '/') {
        initDashboard();
    } else if (path === '/add_data') {
        initAddData();
    } else if (path === '/reports') {
        initReports();
    } else if (path === '/queries') {
        initQueries();
    }

    // --- Shared Functions ---
    async function loadMetadata() {
        try {
            const res = await fetch('/api/metadata');
            const data = await res.json();
            globalMetadata = data; // Store globally
            
            // Populate City/Station/Pollutant selects on various pages if they exist
            document.querySelectorAll('#city-filter, #city_id, #param_city_id').forEach(select => {
                data.cities.forEach(c => {
                    const opt = document.createElement('option');
                    opt.value = c.city_id;
                    opt.textContent = c.city_name;
                    select.appendChild(opt);
                });
            });

            document.querySelectorAll('#param_station_id').forEach(select => {
                data.stations.forEach(s => {
                    const opt = document.createElement('option');
                    opt.value = s.station_id;
                    opt.textContent = s.station_name;
                    select.appendChild(opt);
                });
            });

        } catch (err) {
            console.error('Error loading metadata:', err);
        }
    }

    // --- Dashboard Functions ---
    async function initDashboard() {
        await loadMetadata();
        await loadDashboardStats();
        await loadTableData();
        document.getElementById('apply-filters').addEventListener('click', loadTableData);
        document.getElementById('export-csv').addEventListener('click', exportToCSV);
        setInterval(async () => {
            await loadDashboardStats();
            await loadTableData();
        }, 10000);
    }

    async function loadDashboardStats() {
        try {
            const res = await fetch('/api/dashboard_stats');
            const data = await res.json();
            document.getElementById('avg-aqi-val').textContent = data.average_aqi;
            document.getElementById('total-stations-val').textContent = data.total_stations;
            document.getElementById('most-polluted-val').textContent = data.most_polluted_city;
            checkAlerts(data.average_aqi);
        } catch (err) { console.error('Error loading stats:', err); }
    }

    async function loadTableData() {
        const cityId = document.getElementById('city-filter').value;
        const date = document.getElementById('date-filter').value;
        let url = '/api/aqi_results?';
        if (cityId) url += `city_id=${cityId}&`;
        if (date) url += `date=${date}`;
        try {
            const res = await fetch(url);
            const data = await res.json();
            const tbody = document.querySelector('#aqi-table tbody');
            tbody.innerHTML = '';
            data.forEach(row => {
                const tr = document.createElement('tr');
                const badgeClass = AQI_COLORS[row.category] || 'bg-good';
                tr.innerHTML = `<td>${row.measured_date}</td><td>${row.city_name}</td><td>${row.station_name}</td><td><strong>${row.final_aqi}</strong></td><td><span class="badge ${badgeClass}">${row.category}</span></td>`;
                tbody.appendChild(tr);
            });
        } catch (err) { console.error('Error loading table:', err); }
    }

    // --- Add Data Functions ---
    async function initAddData() {
        await loadMetadata();
        const citySelect = document.getElementById('city_id');
        const stationSelect = document.getElementById('station_id');

        citySelect.addEventListener('change', () => {
            const cityId = parseInt(citySelect.value);
            stationSelect.innerHTML = '<option value="">Select Station...</option>';
            if (!cityId) {
                stationSelect.disabled = true;
                stationSelect.innerHTML = '<option value="">Select City first...</option>';
                return;
            }
            const filteredStations = globalMetadata.stations.filter(s => s.city_id === cityId);
            filteredStations.forEach(s => {
                const opt = document.createElement('option');
                opt.value = s.station_id;
                opt.textContent = s.station_name;
                stationSelect.appendChild(opt);
            });
            stationSelect.disabled = false;
        });

        // Live Update Date/Time
        const dtInput = document.getElementById('measured_at');
        function updateTime() {
            const now = new Date();
            now.setMinutes(now.getMinutes() - now.getTimezoneOffset());
            dtInput.value = now.toISOString().slice(0, 16);
        }
        updateTime();
        setInterval(updateTime, 30000);

        document.getElementById('add-data-form').addEventListener('submit', async (e) => {
            e.preventDefault();
            const pollutants = {};
            for (let i = 1; i <= 6; i++) {
                const field = document.getElementById(`pollutant_${i}`);
                if (field && field.value.trim() !== "") pollutants[i] = parseFloat(field.value);
            }
            const payload = {
                station_id: document.getElementById('station_id').value,
                measured_at: document.getElementById('measured_at').value.replace('T', ' ') + ':00',
                pollutants: pollutants
            };
            try {
                const res = await fetch('/api/measurements', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(payload)
                });
                const data = await res.json();
                const msgBox = document.getElementById('form-msg');
                if (res.ok) {
                    msgBox.className = 'msg-success';
                    msgBox.textContent = data.message;
                    e.target.reset();
                    stationSelect.disabled = true;
                    updateTime();
                } else {
                    msgBox.className = 'msg-error';
                    msgBox.textContent = data.error || 'Failed to insert data';
                }
            } catch (err) { console.error('Submit error:', err); }
        });
    }

    // --- Queries Page Logic ---
    async function initQueries() {
        await loadMetadata();
        const typeSelect = document.getElementById('query_type');
        const filtersBox = document.getElementById('dynamic-filters');
        const runBtn = document.getElementById('run-query');
        const resultsBox = document.getElementById('query-results');

        const params = {
            city: document.getElementById('city-param'),
            station: document.getElementById('station-param'),
            date: document.getElementById('date-param')
        };

        const citySelect = document.getElementById('param_city_id');
        const stationSelect = document.getElementById('param_station_id');

        // Initial empty station list until city is picked
        stationSelect.innerHTML = '<option value="">Select city first...</option>';

        // Logic for cascading station list
        citySelect.addEventListener('change', () => {
            const cityId = parseInt(citySelect.value);
            stationSelect.innerHTML = '<option value="">Select Station...</option>';
            if (!cityId) return;
            const filtered = globalMetadata.stations.filter(s => s.city_id === cityId);
            filtered.forEach(s => {
                const opt = document.createElement('option');
                opt.value = s.station_id;
                opt.textContent = s.station_name;
                stationSelect.appendChild(opt);
            });
        });

        // Default Date to Today
        const dateInput = document.getElementById('param_date');
        if (dateInput) {
            const today = new Date().toISOString().split('T')[0];
            dateInput.value = today;
        }

        typeSelect.addEventListener('change', () => {
            const type = typeSelect.value;
            resultsBox.innerHTML = '';
            resultsBox.classList.add('hidden');
            
            if (!type) {
                filtersBox.classList.add('hidden');
                runBtn.disabled = true;
                return;
            }

            filtersBox.classList.remove('hidden');
            runBtn.disabled = false;

            // Show/Hide specific params based on query type
            Object.values(params).forEach(p => p.classList.add('hidden'));
            
            if (type === 'city_avg') {
                params.city.classList.remove('hidden');
            }
            if (type === 'daily_avg') {
                params.date.classList.remove('hidden');
            }
            if (type === 'detailed_logs') {
                params.city.classList.remove('hidden'); // City picker needed for cascading
                params.station.classList.remove('hidden');
                params.date.classList.remove('hidden');
            }
        });

        runBtn.addEventListener('click', async () => {
            const type = typeSelect.value;
            const cityId = document.getElementById('param_city_id').value;
            const stationId = document.getElementById('param_station_id').value;
            const date = document.getElementById('param_date').value;

            let url = `/api/custom_query?type=${type}`;
            if (!params.city.classList.contains('hidden')) url += `&city_id=${cityId}`;
            if (!params.station.classList.contains('hidden')) url += `&station_id=${stationId}`;
            if (!params.date.classList.contains('hidden')) url += `&date=${date}`;

            try {
                const res = await fetch(url);
                const result = await res.json();
                renderQueryResult(result);
            } catch (err) { console.error('Query Error:', err); }
        });
    }

    function renderQueryResult(result) {
        const box = document.getElementById('query-results');
        box.innerHTML = '';
        box.classList.remove('hidden');

        if (result.error) {
            box.innerHTML = `<div class="summary-result" style="border-left-color: #ef4444;"><p>Error</p><h2>${result.error}</h2></div>`;
            return;
        }

        if (result.type === 'summary') {
            const card = document.createElement('div');
            card.className = 'summary-result';
            const val = (result.value === null || result.value === undefined || result.value === 0) ? 'No record' : result.value;
            card.innerHTML = `
                <p>${result.label}</p>
                <h2>${val}</h2>
            `;
            box.appendChild(card);
        } else if (result.type === 'table') {
            if (!result.data || result.data.length === 0) {
                box.innerHTML = `<div class="summary-result"><p>Result</p><h2>No records found</h2></div>`;
                return;
            }
            const table = document.createElement('table');
            table.className = 'aqi-table';
            let headHTML = '<thead><tr>';
            result.headers.forEach(h => headHTML += `<th>${h}</th>`);
            headHTML += '</tr></thead>';
            
            let bodyHTML = '<tbody>';
            result.data.forEach(row => {
                bodyHTML += '<tr>';
                Object.values(row).forEach(val => bodyHTML += `<td>${val}</td>`);
                bodyHTML += '</tr>';
            });
            bodyHTML += '</tbody>';
            
            table.innerHTML = headHTML + bodyHTML;
            box.appendChild(table);
        }
    }

    // --- Reports ---
    async function initReports() {
        loadCityTrendsChart();
        loadHotspotsChart();
    }

    async function loadCityTrendsChart() {
        try {
            const res = await fetch('/api/reports/city_trends');
            const data = await res.json();
            const datasets = [];
            const colors = ['#3b82f6', '#f59e0b', '#10b981', '#ef4444', '#8b5cf6'];
            let i = 0;
            for (const [city, info] of Object.entries(data)) {
                datasets.push({
                    label: city,
                    data: info.dates.map((date, index) => ({x: date, y: info.aqi[index]})),
                    borderColor: colors[i % colors.length],
                    tension: 0.3
                });
                i++;
            }
            const ctx = document.getElementById('trendsChart').getContext('2d');
            new Chart(ctx, {
                type: 'line',
                data: { datasets },
                options: { responsive: true, maintainAspectRatio: false, scales: { x: { type: 'category' } } }
            });
        } catch (err) { console.error('Chart error', err); }
    }

    async function loadHotspotsChart() {
        try {
            const res = await fetch('/api/reports/hotspots');
            const data = await res.json();
            const ctx = document.getElementById('hotspotsChart').getContext('2d');
            new Chart(ctx, {
                type: 'bar',
                data: {
                    labels: data.map(d => `${d.station_name} (${d.city_name})`),
                    datasets: [{ label: 'Average AQI', data: data.map(d => d.avg_aqi), backgroundColor: '#ef4444' }]
                },
                options: { responsive: true, maintainAspectRatio: false }
            });
        } catch (err) { console.error('Chart error', err); }
    }

    function checkAlerts(aqi) {
        if (aqi > 400) showAlert('CRITICAL WARNING: Severe air quality levels detected!', 'critical');
        else if (aqi > 300) showAlert('WARNING: Poor air quality levels detected.', 'warning');
    }

    function showAlert(msg, level) {
        const container = document.getElementById('alert-container');
        if (container.innerHTML.includes(msg)) return;
        const alertDiv = document.createElement('div');
        alertDiv.className = `alert ${level}`;
        alertDiv.innerHTML = `<span>${msg}</span><span class="alert-close" onclick="this.parentElement.remove()">&times;</span>`;
        container.appendChild(alertDiv);
        if (level !== 'critical') setTimeout(() => alertDiv.remove(), 5000);
    }

    function exportToCSV() {
        const table = document.getElementById('aqi-table');
        let csv = [];
        for (let i = 0; i < table.rows.length; i++) {
            let row = [], cols = table.rows[i].querySelectorAll('td, th');
            for (let j = 0; j < cols.length; j++) row.push(cols[j].innerText.replace(/,/g, ''));
            csv.push(row.join(","));
        }
        const csvFile = new Blob([csv.join("\n")], {type: "text/csv"});
        const downloadLink = document.createElement("a");
        downloadLink.download = "aqi_report.csv";
        downloadLink.href = window.URL.createObjectURL(csvFile);
        downloadLink.style.display = "none";
        document.body.appendChild(downloadLink);
        downloadLink.click();
        document.body.removeChild(downloadLink);
    }
});
