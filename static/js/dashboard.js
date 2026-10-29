/**
 * ErrorInsight – Intelligent Error Analyzer
 * Frontend Dashboard Application Logic
 */

// State Management
const state = {
    activeTab: 'dashboard',
    apiKey: localStorage.getItem('errorinsight_api_key') || 'dev-secret-key-12345',
    history: {
        page: 1,
        limit: 15,
        severity: '',
        category: '',
        search: '',
        sort: 'timestamp_desc',
        totalPages: 1,
        totalRecords: 0
    },
    charts: {
        category: null,
        severity: null,
        timeline: null
    }
};

// DOM Helper
const $ = (id) => document.getElementById(id);

// Safe HTML Escape
function escapeHTML(str) {
    return String(str ?? '').replace(/[&<>"']/g, (char) => ({
        '&': '&amp;',
        '<': '&lt;',
        '>': '&gt;',
        '"': '&quot;',
        "'": '&#39;'
    })[char]);
}

// Toast Notifications
function showToast(message, type = 'info', duration = 3500) {
    const container = $('toast-container');
    if (!container) return;

    const toast = document.createElement('div');
    toast.className = `toast ${type}`;
    toast.innerHTML = `<span>${escapeHTML(message)}</span>`;

    container.appendChild(toast);
    setTimeout(() => {
        toast.style.opacity = '0';
        toast.style.transform = 'translateX(100%)';
        setTimeout(() => toast.remove(), 300);
    }, duration);
}

// API Fetch Helper
async function apiFetch(endpoint, options = {}) {
    const defaultHeaders = {
        'Accept': 'application/json'
    };

    if (state.apiKey) {
        defaultHeaders['X-API-Key'] = state.apiKey;
    }

    options.headers = {
        ...defaultHeaders,
        ...(options.headers || {})
    };

    const response = await fetch(endpoint, options);
    const data = await response.json().catch(() => ({}));

    if (!response.ok) {
        const errorMsg = data.error || `HTTP ${response.status}: ${response.statusText}`;
        const err = new Error(errorMsg);
        err.status = response.status;
        err.data = data;
        throw err;
    }

    return data;
}

// ==========================================================================
// NAVIGATION & TABS
// ==========================================================================
function initNavigation() {
    const navLinks = document.querySelectorAll('.nav-link');
    navLinks.forEach(link => {
        link.addEventListener('click', (e) => {
            e.preventDefault();
            const tabName = link.getAttribute('data-tab');
            switchTab(tabName);
        });
    });

    $('btn-view-all-history')?.addEventListener('click', () => switchTab('history'));
    $('btn-quick-upload')?.addEventListener('click', () => switchTab('upload'));

    // Check URL hash on page load
    const hash = window.location.hash.replace('#', '');
    if (['dashboard', 'upload', 'history', 'analytics', 'docs', 'settings'].includes(hash)) {
        switchTab(hash);
    } else {
        switchTab('dashboard');
    }
}

function switchTab(tabName) {
    state.activeTab = tabName;
    window.location.hash = tabName;

    // Update active nav link
    document.querySelectorAll('.nav-link').forEach(link => {
        if (link.getAttribute('data-tab') === tabName) {
            link.classList.add('active');
        } else {
            link.classList.remove('active');
        }
    });

    // Update active content view
    document.querySelectorAll('.content-view').forEach(view => {
        if (view.id === `view-${tabName}`) {
            view.classList.add('active');
        } else {
            view.classList.remove('active');
        }
    });

    // Update topbar breadcrumb title
    const titles = {
        dashboard: 'System Dashboard',
        upload: 'Log Upload & Ingestion',
        history: 'Stored Error History',
        analytics: 'Subsystem Analytics',
        docs: 'API Integration Contract',
        settings: 'System & Database Settings'
    };
    if ($('current-view-title')) {
        $('current-view-title').textContent = titles[tabName] || 'Dashboard';
    }

    // Refresh view-specific content
    if (tabName === 'dashboard') {
        loadDashboardData();
    } else if (tabName === 'history') {
        loadHistoryData();
    } else if (tabName === 'analytics') {
        loadAnalyticsView();
    } else if (tabName === 'settings') {
        checkHealth();
    }
}

// ==========================================================================
// SYSTEM HEALTH & STATUS
// ==========================================================================
async function checkHealth() {
    try {
        const data = await apiFetch('/api/health');
        if (data.status === 'healthy') {
            const count = data.stored_record_count ?? 0;
            $('db-indicator-dot').className = 'db-indicator-dot';
            $('db-status-text').textContent = `SQLite: Connected (${count} records)`;
            $('sidebar-status-dot').className = 'status-dot pulsing';
            $('sidebar-db-summary').textContent = `SQLite: ${count} errors stored`;

            if ($('settings-db-count')) {
                $('settings-db-count').textContent = `${count} records`;
            }
            if ($('settings-db-file') && data.database_file) {
                $('settings-db-file').textContent = data.database_file;
            }
        }
    } catch (err) {
        $('db-indicator-dot').className = 'db-indicator-dot error';
        $('db-status-text').textContent = 'SQLite: Disconnected';
        $('sidebar-status-dot').className = 'status-dot error';
        $('sidebar-db-summary').textContent = 'Database Unavailable';
    }
}

// ==========================================================================
// CHARTS MANAGEMENT (CHART.JS)
// ==========================================================================
function renderCharts(chartData) {
    if (typeof Chart === 'undefined') return;

    // 1. Category Bar Chart
    const catCanvas = $('categoryChart');
    if (catCanvas && chartData?.categories) {
        if (state.charts.category) {
            state.charts.category.destroy();
        }

        const ctx = catCanvas.getContext('2d');
        state.charts.category = new Chart(ctx, {
            type: 'bar',
            data: {
                labels: chartData.categories.labels,
                datasets: [{
                    label: 'Errors Recorded',
                    data: chartData.categories.data,
                    backgroundColor: chartData.categories.colors.map(c => `${c}cc`),
                    borderColor: chartData.categories.colors,
                    borderWidth: 1.5,
                    borderRadius: 6
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: { display: false },
                    tooltip: {
                        backgroundColor: '#0f172a',
                        titleColor: '#ffffff',
                        bodyColor: '#cbd5e1',
                        borderColor: 'rgba(255,255,255,0.1)',
                        borderWidth: 1
                    }
                },
                scales: {
                    x: {
                        grid: { color: 'rgba(255,255,255,0.04)' },
                        ticks: { color: '#94a3b8', font: { family: 'Inter', size: 11 } }
                    },
                    y: {
                        beginAtZero: true,
                        grid: { color: 'rgba(255,255,255,0.06)' },
                        ticks: { color: '#94a3b8', font: { family: 'Inter', size: 11 }, precision: 0 }
                    }
                }
            }
        });
    }

    // 2. Severity Doughnut Chart
    const sevCanvas = $('severityChart');
    if (sevCanvas && chartData?.severities) {
        if (state.charts.severity) {
            state.charts.severity.destroy();
        }

        const ctx = sevCanvas.getContext('2d');
        state.charts.severity = new Chart(ctx, {
            type: 'doughnut',
            data: {
                labels: chartData.severities.labels,
                datasets: [{
                    data: chartData.severities.data,
                    backgroundColor: chartData.severities.colors,
                    borderColor: '#0f172a',
                    borderWidth: 3,
                    hoverOffset: 6
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                cutout: '72%',
                plugins: {
                    legend: {
                        position: 'right',
                        labels: { color: '#cbd5e1', font: { family: 'Inter', size: 11 }, padding: 12 }
                    },
                    tooltip: {
                        backgroundColor: '#0f172a',
                        borderColor: 'rgba(255,255,255,0.1)',
                        borderWidth: 1
                    }
                }
            }
        });
    }

    // 3. Error Activity Timeline Line Chart
    const timeCanvas = $('timelineChart');
    if (timeCanvas && chartData?.timeline) {
        if (state.charts.timeline) {
            state.charts.timeline.destroy();
        }

        const ctx = timeCanvas.getContext('2d');
        const gradient = ctx.createLinearGradient(0, 0, 0, 260);
        gradient.addColorStop(0, 'rgba(6, 182, 212, 0.35)');
        gradient.addColorStop(1, 'rgba(6, 182, 212, 0.0)');

        state.charts.timeline = new Chart(ctx, {
            type: 'line',
            data: {
                labels: chartData.timeline.labels.length ? chartData.timeline.labels : ['No data'],
                datasets: [{
                    label: 'Error Volume',
                    data: chartData.timeline.data.length ? chartData.timeline.data : [0],
                    borderColor: '#06b6d4',
                    backgroundColor: gradient,
                    borderWidth: 2,
                    fill: true,
                    tension: 0.35,
                    pointBackgroundColor: '#06b6d4',
                    pointBorderColor: '#ffffff',
                    pointRadius: 4,
                    pointHoverRadius: 6
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: { display: false },
                    tooltip: {
                        backgroundColor: '#0f172a',
                        borderColor: 'rgba(255,255,255,0.1)',
                        borderWidth: 1
                    }
                },
                scales: {
                    x: {
                        grid: { color: 'rgba(255,255,255,0.04)' },
                        ticks: { color: '#94a3b8', font: { family: 'Inter', size: 10 } }
                    },
                    y: {
                        beginAtZero: true,
                        grid: { color: 'rgba(255,255,255,0.06)' },
                        ticks: { color: '#94a3b8', font: { family: 'Inter', size: 11 }, precision: 0 }
                    }
                }
            }
        });
    }
}

// ==========================================================================
// DASHBOARD DATA LOADING
// ==========================================================================
async function loadDashboardData() {
    checkHealth();
    try {
        const response = await apiFetch('/api/analytics');
        const analytics = response.analytics || {};

        // 1. Update 5 Summary Stat Cards
        const total = analytics.total_errors ?? 0;
        const categories = analytics.unique_categories ?? 0;
        const critical = analytics.critical_count ?? 0;
        const warning = analytics.warning_count ?? 0;
        const info = analytics.info_count ?? 0;

        $('stat-total').textContent = total;
        $('stat-categories').textContent = categories;
        $('stat-critical').textContent = critical;
        $('stat-warning').textContent = warning;
        $('stat-info').textContent = info;

        // 2. Update System Health Hero Badge
        const healthBadge = $('system-health-badge');
        if (total === 0) {
            healthBadge.textContent = 'NO DATA';
            healthBadge.className = 'badge-value';
        } else if (critical > 0) {
            healthBadge.textContent = `${critical} CRITICAL`;
            healthBadge.className = 'badge-value critical';
        } else if (warning > 0) {
            healthBadge.textContent = `${warning} WARNINGS`;
            healthBadge.className = 'badge-value warning';
        } else {
            healthBadge.textContent = 'HEALTHY';
            healthBadge.className = 'badge-value';
        }

        // 3. Render Chart.js Visualizations
        if (analytics.chart_data) {
            renderCharts(analytics.chart_data);
        }

        // 4. Render Top Recurring Errors
        renderRecurringErrors(analytics.recurring_errors || []);

        // 5. Render Smart Recommendations
        renderRecommendations(analytics.recommendations || []);

        // 6. Render Recent Errors Table
        renderRecentErrorsTable(analytics.recent_errors || []);

    } catch (err) {
        showToast(`Failed to load analytics: ${err.message}`, 'error');
    }
}

function renderRecurringErrors(recurringList) {
    const container = $('recurring-errors-list');
    if (!container) return;

    if (!recurringList.length) {
        container.innerHTML = '<div class="loading-state">No recurring errors recorded in database.</div>';
        return;
    }

    container.innerHTML = recurringList.slice(0, 6).map(item => `
        <div class="recurring-card">
            <div class="recurring-card-top">
                <span class="category-pill">${escapeHTML(item.category)}</span>
                <div class="d-flex align-items-center gap-2">
                    <span class="severity-pill ${escapeHTML(item.severity)}">${escapeHTML(item.severity)}</span>
                    <span class="recurring-count-pill">${item.count}× detected</span>
                </div>
            </div>
            <div class="recurring-signature">${escapeHTML(item.message)}</div>
            <div class="recurring-meta">
                <span>Last seen: ${escapeHTML(item.last_seen || 'Recently')}</span>
            </div>
        </div>
    `).join('');
}

function renderRecommendations(recommendations) {
    const container = $('recommendations-list');
    if (!container) return;

    if (!recommendations.length) {
        container.innerHTML = '<div class="loading-state">Upload or stream logs to generate rule-based suggestions.</div>';
        return;
    }

    container.innerHTML = recommendations.slice(0, 4).map(rec => `
        <div class="recommendation-card">
            <div class="rec-title-wrap">
                <span class="rec-category-badge">${escapeHTML(rec.category)}</span>
                <span class="rec-card-title">${escapeHTML(rec.title)}</span>
            </div>
            <div class="rec-body-item">
                <strong>Likely Cause:</strong> ${escapeHTML(rec.possible_causes[0] || 'Unknown')}
            </div>
            <div class="rec-body-item">
                <strong>Recommended Fix:</strong> ${escapeHTML(rec.recommended_solutions[0] || 'Check logs.')}
            </div>
            <div class="rec-disclaimer">${escapeHTML(rec.disclaimer)}</div>
        </div>
    `).join('');
}

function renderRecentErrorsTable(recentList) {
    const tbody = $('recent-table-body');
    if (!tbody) return;

    if (!recentList.length) {
        tbody.innerHTML = '<tr><td colspan="7" class="text-center py-4">No error records currently stored.</td></tr>';
        return;
    }

    tbody.innerHTML = recentList.slice(0, 8).map(row => `
        <tr>
            <td><code>#${row.id}</code></td>
            <td>${escapeHTML(row.timestamp || '—')}</td>
            <td><span class="category-pill">${escapeHTML(row.source_name || 'upload')}</span></td>
            <td><b>${escapeHTML(row.category)}</b></td>
            <td class="table-msg-cell" title="${escapeHTML(row.message)}">${escapeHTML(row.message)}</td>
            <td><span class="severity-pill ${escapeHTML(row.severity)}">${escapeHTML(row.severity)}</span></td>
            <td>
                <button class="btn btn-secondary btn-sm" onclick="inspectErrorRecord(${row.id})">Inspect</button>
            </td>
        </tr>
    `).join('');
}

// ==========================================================================
// LOG UPLOAD & INGESTION
// ==========================================================================
function initUploadHandlers() {
    const dropzone = $('upload-dropzone');
    const fileInput = $('file-input');
    const rawInput = $('raw-log-input');
    const btnAnalyzeRaw = $('btn-analyze-raw');
    const btnClearRaw = $('btn-clear-raw');

    if (!dropzone || !fileInput) return;

    dropzone.addEventListener('dragover', (e) => {
        e.preventDefault();
        dropzone.classList.add('dragover');
    });

    dropzone.addEventListener('dragleave', () => {
        dropzone.classList.remove('dragover');
    });

    dropzone.addEventListener('drop', (e) => {
        e.preventDefault();
        dropzone.classList.remove('dragover');
        if (e.dataTransfer.files.length > 0) {
            handleFileUpload(e.dataTransfer.files[0]);
        }
    });

    fileInput.addEventListener('change', () => {
        if (fileInput.files.length > 0) {
            handleFileUpload(fileInput.files[0]);
        }
    });

    btnAnalyzeRaw?.addEventListener('click', async () => {
        const text = rawInput.value.trim();
        if (!text) {
            showToast('Please enter log text or JSON first.', 'error');
            return;
        }

        try {
            btnAnalyzeRaw.disabled = true;
            btnAnalyzeRaw.innerHTML = '<span>Processing...</span>';

            // Check if valid JSON
            let isJson = false;
            let jsonPayload = null;
            if (text.startsWith('{') || text.startsWith('[')) {
                try {
                    jsonPayload = JSON.parse(text);
                    isJson = true;
                } catch (e) {
                    isJson = false;
                }
            }

            let response;
            if (isJson) {
                response = await apiFetch('/api/analyze', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(jsonPayload)
                });
            } else {
                response = await apiFetch('/api/analyze', {
                    method: 'POST',
                    headers: { 'Content-Type': 'text/plain' },
                    body: text
                });
            }

            showUploadFeedback(response);
            checkHealth();
            showToast(`Analyzed successfully: ${response.saved_to_database} saved to SQLite!`, 'success');
        } catch (err) {
            showUploadFeedback({ error: err.message }, true);
            showToast(`Analysis failed: ${err.message}`, 'error');
        } finally {
            btnAnalyzeRaw.disabled = false;
            btnAnalyzeRaw.innerHTML = '<span>Analyze &amp; Persist to Database</span>';
        }
    });

    btnClearRaw?.addEventListener('click', () => {
        rawInput.value = '';
    });

    $('btn-load-demo-dataset')?.addEventListener('click', async () => {
        try {
            const data = await apiFetch('/api/seed', { method: 'POST' });
            showToast(data.message, 'success');
            checkHealth();
            switchTab('dashboard');
        } catch (err) {
            showToast(`Seed failed: ${err.message}`, 'error');
        }
    });

    // Copy sample format buttons
    document.querySelectorAll('.btn-copy-format').forEach(btn => {
        btn.addEventListener('click', () => {
            const fmt = btn.getAttribute('data-format');
            let content = '';
            if (fmt === 'a') {
                content = JSON.stringify({
                    errors: [{
                        id: 1,
                        timestamp: "2026-10-29 08:00:00",
                        type: "Database",
                        message: "Database connection failed",
                        severity: "Critical"
                    }]
                }, null, 2);
            } else if (fmt === 'b') {
                content = JSON.stringify([{
                    timestamp: "2026-10-29 08:00:00",
                    message: "Connection timeout",
                    severity: "Warning"
                }], null, 2);
            } else {
                content = "2026-10-29 08:00:00 [CRITICAL] Database connection failed\n2026-10-29 08:02:15 [ERROR] JWT token expired";
            }
            navigator.clipboard.writeText(content).then(() => {
                showToast(`Sample ${fmt.toUpperCase()} copied to clipboard!`, 'info');
            });
        });
    });
}

async function handleFileUpload(file) {
    const feedback = $('upload-feedback');
    feedback.className = 'upload-feedback-box hidden';

    const formData = new FormData();
    formData.append('file', file);

    try {
        showToast(`Uploading ${file.name}...`, 'info');
        const response = await apiFetch('/api/analyze', {
            method: 'POST',
            body: formData
        });

        showUploadFeedback(response);
        checkHealth();
        showToast(`${file.name}: ${response.saved_to_database} records saved!`, 'success');
    } catch (err) {
        showUploadFeedback({ error: err.message }, true);
        showToast(`Upload error: ${err.message}`, 'error');
    }
}

function showUploadFeedback(data, isError = false) {
    const feedback = $('upload-feedback');
    if (!feedback) return;

    feedback.classList.remove('hidden');
    if (isError) {
        feedback.className = 'upload-feedback-box error';
        feedback.innerHTML = `<strong>Upload Failure:</strong> ${escapeHTML(data.error || 'Unknown error occurred.')}`;
    } else {
        feedback.className = 'upload-feedback-box success';
        feedback.innerHTML = `
            <strong>Analysis Complete:</strong> File <code>${escapeHTML(data.source_name)}</code> processed successfully.<br>
            • <b>${data.saved_to_database}</b> new record(s) persisted to SQLite.<br>
            • <b>${data.duplicates}</b> duplicate record(s) safely ignored.<br>
            • <b>${data.rejected}</b> rejected invalid record(s).
        `;
    }
}

// ==========================================================================
// ERROR HISTORY VIEW & FILTERS
// ==========================================================================
function initHistoryControls() {
    const searchInput = $('history-search');
    const severitySelect = $('filter-severity');
    const categorySelect = $('filter-category');
    const sortSelect = $('filter-sort');
    const btnReset = $('btn-reset-filters');
    const btnPrev = $('btn-prev-page');
    const btnNext = $('btn-next-page');

    let debounceTimer;
    searchInput?.addEventListener('input', () => {
        clearTimeout(debounceTimer);
        debounceTimer = setTimeout(() => {
            state.history.search = searchInput.value.trim();
            state.history.page = 1;
            loadHistoryData();
        }, 300);
    });

    severitySelect?.addEventListener('change', () => {
        state.history.severity = severitySelect.value;
        state.history.page = 1;
        loadHistoryData();
    });

    categorySelect?.addEventListener('change', () => {
        state.history.category = categorySelect.value;
        state.history.page = 1;
        loadHistoryData();
    });

    sortSelect?.addEventListener('change', () => {
        state.history.sort = sortSelect.value;
        state.history.page = 1;
        loadHistoryData();
    });

    btnReset?.addEventListener('click', () => {
        if (searchInput) searchInput.value = '';
        if (severitySelect) severitySelect.value = '';
        if (categorySelect) categorySelect.value = '';
        if (sortSelect) sortSelect.value = 'timestamp_desc';

        state.history.search = '';
        state.history.severity = '';
        state.history.category = '';
        state.history.sort = 'timestamp_desc';
        state.history.page = 1;
        loadHistoryData();
    });

    btnPrev?.addEventListener('click', () => {
        if (state.history.page > 1) {
            state.history.page -= 1;
            loadHistoryData();
        }
    });

    btnNext?.addEventListener('click', () => {
        if (state.history.page < state.history.totalPages) {
            state.history.page += 1;
            loadHistoryData();
        }
    });
}

async function loadHistoryData() {
    const tbody = $('history-table-body');
    if (!tbody) return;

    tbody.innerHTML = '<tr><td colspan="7" class="text-center py-4">Querying SQLite database...</td></tr>';

    const [sortBy, sortDir] = state.history.sort.split('_');
    const params = new URLSearchParams({
        page: state.history.page,
        limit: state.history.limit,
        sort_by: sortBy,
        sort_dir: sortDir
    });

    if (state.history.severity) params.append('severity', state.history.severity);
    if (state.history.category) params.append('category', state.history.category);
    if (state.history.search) params.append('search', state.history.search);

    try {
        const response = await apiFetch(`/api/history?${params.toString()}`);
        const records = response.records || [];
        const pagination = response.pagination || {};

        state.history.totalPages = pagination.total_pages || 1;
        state.history.totalRecords = pagination.total_records || 0;

        if ($('history-total-count')) {
            $('history-total-count').textContent = `${pagination.total_records} Records Stored`;
        }

        if (!records.length) {
            tbody.innerHTML = '<tr><td colspan="7" class="text-center py-4">No records match the selected filter criteria.</td></tr>';
        } else {
            tbody.innerHTML = records.map(row => `
                <tr>
                    <td><code>#${row.id}</code></td>
                    <td>${escapeHTML(row.timestamp)}</td>
                    <td><span class="category-pill">${escapeHTML(row.source_name || 'upload')}</span></td>
                    <td><b>${escapeHTML(row.category)}</b></td>
                    <td class="table-msg-cell" title="${escapeHTML(row.message)}">${escapeHTML(row.message)}</td>
                    <td><span class="severity-pill ${escapeHTML(row.severity)}">${escapeHTML(row.severity)}</span></td>
                    <td>
                        <button class="btn btn-secondary btn-sm" onclick="inspectErrorRecord(${row.id})">Inspect</button>
                    </td>
                </tr>
            `).join('');
        }

        // Update pagination bar
        const startIdx = records.length ? (state.history.page - 1) * state.history.limit + 1 : 0;
        const endIdx = (state.history.page - 1) * state.history.limit + records.length;
        $('pagination-info').textContent = `Showing ${startIdx}-${endIdx} of ${pagination.total_records} records`;
        $('pagination-current-page').textContent = `Page ${state.history.page} of ${state.history.totalPages}`;

        $('btn-prev-page').disabled = !pagination.has_prev;
        $('btn-next-page').disabled = !pagination.has_next;

    } catch (err) {
        tbody.innerHTML = `<tr><td colspan="7" class="text-center py-4 text-critical">Error loading history: ${escapeHTML(err.message)}</td></tr>`;
    }
}

// ==========================================================================
// RECORD INSPECTION MODAL
// ==========================================================================
window.inspectErrorRecord = async function(id) {
    const modal = $('error-detail-modal');
    if (!modal) return;

    modal.classList.remove('hidden');

    try {
        const data = await apiFetch(`/api/errors/${id}`);
        const rec = data.record || {};
        const recommendation = data.recommendation || {};

        $('modal-id').textContent = `#${rec.id}`;
        $('modal-source-id').textContent = rec.source_id || 'N/A';
        $('modal-timestamp').textContent = rec.timestamp || '—';
        $('modal-severity').innerHTML = `<span class="severity-pill ${escapeHTML(rec.severity)}">${escapeHTML(rec.severity)}</span>`;
        $('modal-category').textContent = rec.category.toUpperCase();
        $('modal-title').textContent = `${rec.category} Error Inspection`;
        $('modal-message').textContent = rec.message || '';

        // Causes
        const causesList = $('modal-causes-list');
        causesList.innerHTML = (recommendation.possible_causes || []).map(c => `<li>${escapeHTML(c)}</li>`).join('');

        // Solutions
        const solutionsList = $('modal-solutions-list');
        solutionsList.innerHTML = (recommendation.recommended_solutions || []).map(s => `<li>${escapeHTML(s)}</li>`).join('');

    } catch (err) {
        showToast(`Failed to load error details: ${err.message}`, 'error');
        modal.classList.add('hidden');
    }
};

function initModalHandlers() {
    const modal = $('error-detail-modal');
    const closeBtn = $('modal-close');
    const dismissBtn = $('modal-btn-dismiss');
    const backdrop = $('modal-backdrop');

    const closeModal = () => modal?.classList.add('hidden');

    closeBtn?.addEventListener('click', closeModal);
    dismissBtn?.addEventListener('click', closeModal);
    backdrop?.addEventListener('click', closeModal);
}

// ==========================================================================
// ANALYTICS VIEW
// ==========================================================================
async function loadAnalyticsView() {
    try {
        const response = await apiFetch('/api/analytics');
        const analytics = response.analytics || {};
        const catCounts = analytics.category_counts || {};

        const categories = [
            'Database', 'Authentication', 'Network', 'File System', 'Memory', 'Application'
        ];

        const grid = $('analytics-category-grid');
        if (grid) {
            grid.innerHTML = categories.map(cat => {
                const count = catCounts[cat] || 0;
                return `
                    <div class="analytics-category-card">
                        <div class="acc-header">
                            <span class="acc-title">${cat}</span>
                            <span class="category-pill">${count > 0 ? 'ACTIVE' : 'IDLE'}</span>
                        </div>
                        <div class="acc-count">${count} <small style="font-size:11px;color:#94a3b8">occurrences</small></div>
                    </div>
                `;
            }).join('');
        }

        const recurBody = $('analytics-recurring-body');
        const recurList = analytics.recurring_errors || [];
        if (recurBody) {
            if (!recurList.length) {
                recurBody.innerHTML = '<tr><td colspan="5" class="text-center py-4">No recurring patterns recorded.</td></tr>';
            } else {
                recurBody.innerHTML = recurList.map(item => `
                    <tr>
                        <td><span class="recurring-count-pill">${item.count}× occurrences</span></td>
                        <td><b>${escapeHTML(item.category)}</b></td>
                        <td><span class="severity-pill ${escapeHTML(item.severity)}">${escapeHTML(item.severity)}</span></td>
                        <td class="table-msg-cell" title="${escapeHTML(item.message)}">${escapeHTML(item.message)}</td>
                        <td>${escapeHTML(item.last_seen || '—')}</td>
                    </tr>
                `).join('');
            }
        }
    } catch (err) {
        showToast(`Analytics query error: ${err.message}`, 'error');
    }
}

// ==========================================================================
// API DOCS & INTERACTIVE EXPLORER
// ==========================================================================
function initApiExplorer() {
    const consoleOutput = $('api-console-output');
    const consoleStatus = $('api-console-status');

    document.querySelectorAll('.test-api-btn').forEach(btn => {
        btn.addEventListener('click', async () => {
            const method = btn.getAttribute('data-method');
            const path = btn.getAttribute('data-path');
            const sample = btn.getAttribute('data-sample');

            if (consoleStatus) consoleStatus.textContent = `Sending ${method} ${path}...`;
            if (consoleOutput) consoleOutput.textContent = `// Request: ${method} ${path}\n// Connecting to backend...`;

            try {
                let options = { method };
                if (method === 'POST' && sample === 'logs') {
                    options.headers = { 'Content-Type': 'application/json' };
                    options.body = JSON.stringify({
                        errors: [{
                            id: "EXPLORER-TEST-1",
                            timestamp: new Date().toISOString().replace('T', ' ').substring(0, 19),
                            type: "Database",
                            message: "Test record sent via interactive API Explorer console",
                            severity: "Warning"
                        }]
                    });
                }

                const res = await fetch(path, {
                    ...options,
                    headers: {
                        ...(options.headers || {}),
                        'X-API-Key': state.apiKey,
                        'Accept': 'application/json'
                    }
                });

                const data = await res.json().catch(() => ({}));
                if (consoleStatus) consoleStatus.textContent = `HTTP ${res.status} ${res.statusText}`;
                if (consoleOutput) {
                    consoleOutput.textContent = JSON.stringify(data, null, 2);
                }

                checkHealth();
                showToast(`Request executed: HTTP ${res.status}`, res.ok ? 'success' : 'error');
            } catch (err) {
                if (consoleStatus) consoleStatus.textContent = 'Network Error';
                if (consoleOutput) consoleOutput.textContent = `Error: ${err.message}`;
                showToast(`Request failed: ${err.message}`, 'error');
            }
        });
    });

    $('btn-copy-base-url')?.addEventListener('click', () => {
        const url = window.location.origin;
        navigator.clipboard.writeText(url).then(() => {
            showToast('Base URL copied to clipboard!', 'info');
        });
    });

    $('btn-copy-python-code')?.addEventListener('click', () => {
        const code = $('python-snippet-content')?.textContent;
        if (code) {
            navigator.clipboard.writeText(code).then(() => {
                showToast('Python client code copied to clipboard!', 'info');
            });
        }
    });
}

// ==========================================================================
// SETTINGS & DATABASE MANAGEMENT
// ==========================================================================
function initSettingsHandlers() {
    const apiKeyInput = $('settings-api-key');
    const btnSaveKey = $('btn-save-client-key');
    const btnSeed = $('btn-seed-data');
    const btnClear = $('btn-clear-database');
    const btnExport = $('btn-export-json');

    if (apiKeyInput) {
        apiKeyInput.value = state.apiKey;
    }

    btnSaveKey?.addEventListener('click', () => {
        const val = apiKeyInput.value.trim();
        state.apiKey = val;
        localStorage.setItem('errorinsight_api_key', val);
        showToast('API Key saved for current session.', 'success');
    });

    btnSeed?.addEventListener('click', async () => {
        try {
            const data = await apiFetch('/api/seed', { method: 'POST' });
            showToast(data.message, 'success');
            checkHealth();
            loadDashboardData();
        } catch (err) {
            showToast(`Seed failed: ${err.message}`, 'error');
        }
    });

    btnClear?.addEventListener('click', async () => {
        if (!confirm('Are you sure you want to clear all error records from SQLite? This cannot be undone.')) {
            return;
        }

        try {
            const data = await apiFetch('/api/clear', { method: 'POST' });
            showToast(data.message, 'success');
            checkHealth();
            loadDashboardData();
        } catch (err) {
            showToast(`Clear failed: ${err.message}`, 'error');
        }
    });

    btnExport?.addEventListener('click', async () => {
        try {
            showToast('Exporting error logs...', 'info');
            const data = await apiFetch('/api/history?limit=500');
            const blob = new Blob([JSON.stringify(data.records || [], null, 2)], { type: 'application/json' });
            const url = URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = `error_insight_export_${new Date().toISOString().substring(0, 10)}.json`;
            a.click();
            URL.revokeObjectURL(url);
            showToast('Export downloaded successfully!', 'success');
        } catch (err) {
            showToast(`Export failed: ${err.message}`, 'error');
        }
    });
}

// ==========================================================================
// GLOBAL INITIALIZATION
// ==========================================================================
document.addEventListener('DOMContentLoaded', () => {
    initNavigation();
    initUploadHandlers();
    initHistoryControls();
    initModalHandlers();
    initApiExplorer();
    initSettingsHandlers();

    // Refresh Button Handler
    $('btn-refresh')?.addEventListener('click', () => {
        const btn = $('btn-refresh');
        btn.classList.add('refreshing');
        checkHealth();
        if (state.activeTab === 'dashboard') {
            loadDashboardData();
        } else if (state.activeTab === 'history') {
            loadHistoryData();
        } else if (state.activeTab === 'analytics') {
            loadAnalyticsView();
        }
        setTimeout(() => btn.classList.remove('refreshing'), 600);
        showToast('Dashboard refreshed from SQLite.', 'info');
    });

    // Initial Health and Dashboard Load
    checkHealth();
    loadDashboardData();
});
