/**
 * LogHealth – Log Analytics and System Health Intelligence
 * Frontend Dashboard Application Logic
 */

// State Management
const state = {
    activeTab: 'overview',
    apiKey: localStorage.getItem('loghealth_api_key') || localStorage.getItem('errorinsight_api_key') || 'dev-secret-key-12345',
    lastAnalytics: null,
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
    $('btn-view-all-components')?.addEventListener('click', () => switchTab('components'));
    $('btn-banner-view-anomalies')?.addEventListener('click', () => switchTab('anomalies'));
    $('btn-hero-view-report')?.addEventListener('click', () => switchTab('reports'));

    // Check URL hash on page load
    const hash = window.location.hash.replace('#', '');
    const validTabs = ['overview', 'dashboard', 'analytics', 'components', 'anomalies', 'risks', 'history', 'reports', 'upload', 'docs', 'settings'];
    if (validTabs.includes(hash)) {
        switchTab(hash === 'dashboard' ? 'overview' : hash);
    } else {
        switchTab('overview');
    }
}

function switchTab(tabName) {
    if (tabName === 'dashboard') tabName = 'overview';
    state.activeTab = tabName;
    window.location.hash = tabName;

    // Update active nav link
    document.querySelectorAll('.nav-link').forEach(link => {
        const linkTab = link.getAttribute('data-tab');
        if (linkTab === tabName || (tabName === 'overview' && linkTab === 'dashboard')) {
            link.classList.add('active');
        } else {
            link.classList.remove('active');
        }
    });

    // Update active content view
    document.querySelectorAll('.content-view').forEach(view => {
        if (view.id === `view-${tabName}` || (tabName === 'overview' && view.id === 'view-dashboard')) {
            view.classList.add('active');
        } else {
            view.classList.remove('active');
        }
    });

    // Update topbar breadcrumb title
    const titles = {
        overview: 'System Health Overview',
        dashboard: 'System Health Overview',
        analytics: 'Log Analytics & Trends',
        components: 'Component & Service Health',
        anomalies: 'Anomaly & Pattern Detection',
        risks: 'Evidence-Based Risk Prioritization',
        history: 'Stored Log History',
        reports: 'System Health Intelligence Report',
        upload: 'Log Ingestion & Upload',
        docs: 'API Integration Contract',
        settings: 'System & Database Settings'
    };
    if ($('current-view-title')) {
        $('current-view-title').textContent = titles[tabName] || 'Overview';
    }

    // Refresh view-specific content
    if (tabName === 'overview') {
        loadDashboardData();
    } else if (tabName === 'analytics') {
        loadAnalyticsView();
    } else if (tabName === 'components') {
        renderComponentHealthView();
    } else if (tabName === 'anomalies') {
        renderAnomaliesView();
    } else if (tabName === 'risks') {
        renderRisksView();
    } else if (tabName === 'history') {
        loadHistoryData();
    } else if (tabName === 'reports') {
        renderReportsView();
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
            if ($('db-indicator-dot')) $('db-indicator-dot').className = 'db-indicator-dot';
            if ($('db-status-text')) $('db-status-text').textContent = `SQLite: Connected (${count} records)`;
            if ($('sidebar-status-dot')) $('sidebar-status-dot').className = 'status-dot pulsing';
            if ($('sidebar-db-summary')) $('sidebar-db-summary').textContent = `SQLite: ${count} events stored`;

            if ($('settings-db-count')) {
                $('settings-db-count').textContent = `${count} records`;
            }
            if ($('settings-db-file') && data.database_file) {
                $('settings-db-file').textContent = data.database_file;
            }
        }
    } catch (err) {
        if ($('db-indicator-dot')) $('db-indicator-dot').className = 'db-indicator-dot error';
        if ($('db-status-text')) $('db-status-text').textContent = 'SQLite: Disconnected';
        if ($('sidebar-status-dot')) $('sidebar-status-dot').className = 'status-dot error';
        if ($('sidebar-db-summary')) $('sidebar-db-summary').textContent = 'Database Unavailable';
    }
}

// ==========================================================================
// CHARTS MANAGEMENT (CHART.JS)
// ==========================================================================
function renderCharts(chartData) {
    if (typeof Chart === 'undefined') return;

    // 1. Category / Component Bar Chart
    const catCanvas = $('categoryChart');
    if (catCanvas && chartData?.categories) {
        if (state.charts.category) {
            state.charts.category.destroy();
        }

        const ctx = catCanvas.getContext('2d');
        state.charts.category = new Chart(ctx, {
            type: 'bar',
            data: {
                labels: chartData.categories.labels.length ? chartData.categories.labels : ['No Component Data'],
                datasets: [{
                    label: 'Events Logged',
                    data: chartData.categories.data.length ? chartData.categories.data : [0],
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
        const hasData = chartData.severities.data.length > 0 && chartData.severities.data.some(v => v > 0);

        state.charts.severity = new Chart(ctx, {
            type: 'doughnut',
            data: {
                labels: hasData ? chartData.severities.labels : ['No Events'],
                datasets: [{
                    data: hasData ? chartData.severities.data : [1],
                    backgroundColor: hasData ? chartData.severities.colors : ['#334155'],
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
                labels: chartData.timeline.labels.length ? chartData.timeline.labels : ['No baseline'],
                datasets: [{
                    label: 'Event Velocity',
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
// DASHBOARD & OVERVIEW DATA LOADING
// ==========================================================================
async function loadDashboardData() {
    checkHealth();
    try {
        const response = await apiFetch('/api/analytics');
        const analytics = response.analytics || {};
        state.lastAnalytics = analytics;

        // 1. Update Metric Cards
        const total = analytics.total_events ?? analytics.total_errors ?? 0;
        const critical = analytics.critical_count ?? 0;
        const errors = analytics.error_count ?? 0;
        const warning = analytics.warning_count ?? 0;
        const info = analytics.info_count ?? 0;

        if ($('stat-total')) $('stat-total').textContent = total;
        if ($('stat-critical')) $('stat-critical').textContent = critical;
        if ($('stat-errors')) $('stat-errors').textContent = errors;
        if ($('stat-warning')) $('stat-warning').textContent = warning;
        if ($('stat-info')) $('stat-info').textContent = info;

        // 2. Update Explainable Health Score
        const hs = analytics.health_score || {};
        const scoreVal = hs.score;
        const healthBadge = $('system-health-badge');
        const scoreElem = $('health-score-val');

        if (scoreElem) {
            scoreElem.textContent = scoreVal !== null && scoreVal !== undefined ? scoreVal : '—';
        }

        if (healthBadge) {
            if (!hs.has_sufficient_data || total === 0) {
                healthBadge.textContent = 'NO DATA';
                healthBadge.className = 'badge-value';
            } else {
                healthBadge.textContent = hs.status.toUpperCase();
                healthBadge.className = `badge-value ${hs.status.toLowerCase()}`;
            }
        }

        if ($('hero-summary-text') && analytics.plain_english_summary) {
            $('hero-summary-text').textContent = analytics.plain_english_summary;
        }

        // 3. Render Charts
        if (analytics.chart_data) {
            renderCharts(analytics.chart_data);
        }

        // 4. Anomaly Banner
        const anomalyBanner = $('overview-anomaly-banner');
        const anomalies = analytics.anomalies || [];
        if (anomalyBanner) {
            if (anomalies.length > 0) {
                anomalyBanner.classList.remove('hidden');
                $('anomaly-banner-title').textContent = `${anomalies.length} Statistical Anomalies Detected`;
                $('anomaly-banner-text').textContent = anomalies[0].observed_fact;
            } else {
                anomalyBanner.classList.add('hidden');
            }
        }

        // 5. Component Quick Matrix
        renderOverviewComponentTable(analytics.component_health || []);

        // 6. Top Recurring Signatures
        renderRecurringErrors(analytics.recurring_errors || []);

        // 7. Operational Recommendations
        renderRecommendations(analytics.recommendations || []);

        // 8. Recent Log Records
        renderRecentErrorsTable(analytics.recent_errors || []);

    } catch (err) {
        showToast(`Failed to load analytics: ${err.message}`, 'error');
    }
}

function renderOverviewComponentTable(components) {
    const tbody = $('overview-component-body');
    if (!tbody) return;

    if (!components.length) {
        tbody.innerHTML = '<tr><td colspan="7" class="text-center py-4">No component telemetry available. Ingest logs to analyze.</td></tr>';
        return;
    }

    tbody.innerHTML = components.slice(0, 6).map(c => `
        <tr>
            <td><b>${escapeHTML(c.component)}</b></td>
            <td><code>${c.total_events}</code></td>
            <td><span class="severity-pill ${c.critical_count > 0 ? 'Critical' : 'Info'}">${c.critical_count}</span></td>
            <td><span class="text-orange">${c.error_count}</span></td>
            <td>${c.failure_rate}%</td>
            <td><span class="risk-badge ${c.risk_level.toLowerCase()}">${escapeHTML(c.risk_level)}</span></td>
            <td class="table-msg-cell">${escapeHTML(c.evidence[0] || 'Nominal')}</td>
        </tr>
    `).join('');
}

function renderRecurringErrors(recurringList) {
    const container = $('recurring-errors-list');
    if (!container) return;

    if (!recurringList.length) {
        container.innerHTML = '<div class="loading-state">No recurring failure patterns recorded in database.</div>';
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
        container.innerHTML = '<div class="loading-state">Ingest logs to generate operational recommendations.</div>';
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
        tbody.innerHTML = '<tr><td colspan="7" class="text-center py-4">No log records currently stored in SQLite.</td></tr>';
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
                <button class="btn btn-primary btn-sm" onclick="analyseFurtherRecord(${row.id})">Analyse further ↗</button>
            </td>
        </tr>
    `).join('');
}

// ==========================================================================
// COMPONENT HEALTH VIEW
// ==========================================================================
async function renderComponentHealthView() {
    if (!state.lastAnalytics) {
        await loadDashboardData();
    }
    const components = state.lastAnalytics?.component_health || [];
    const tbody = $('full-component-body');
    if (!tbody) return;

    if (!components.length) {
        tbody.innerHTML = '<tr><td colspan="10" class="text-center py-4">No component telemetry available. Ingest logs to analyze.</td></tr>';
        return;
    }

    tbody.innerHTML = components.map(c => `
        <tr>
            <td><b>${escapeHTML(c.component)}</b></td>
            <td><code>${c.total_events}</code></td>
            <td><span class="severity-pill ${c.critical_count > 0 ? 'Critical' : 'Info'}">${c.critical_count}</span></td>
            <td><span class="text-orange">${c.error_count}</span></td>
            <td><span class="text-warning">${c.warning_count}</span></td>
            <td>${c.failure_rate}%</td>
            <td><code>${c.risk_score}</code></td>
            <td><span class="risk-badge ${c.risk_level.toLowerCase()}">${escapeHTML(c.risk_level)}</span></td>
            <td class="table-msg-cell">${escapeHTML(c.evidence.join('; '))}</td>
            <td class="table-msg-cell">${escapeHTML(c.recommended_actions[0] || 'Monitor')}</td>
        </tr>
    `).join('');
}

// ==========================================================================
// ANOMALIES VIEW
// ==========================================================================
async function renderAnomaliesView() {
    if (!state.lastAnalytics) {
        await loadDashboardData();
    }
    const anomalies = state.lastAnalytics?.anomalies || [];
    const container = $('anomalies-list');
    if (!container) return;

    if (!anomalies.length) {
        container.innerHTML = '<div class="loading-state">No statistical volume spikes or critical bursts detected in active dataset.</div>';
    } else {
        container.innerHTML = anomalies.map(a => `
            <div class="anomaly-card">
                <div class="anomaly-card-header">
                    <div class="d-flex align-items-center gap-2">
                        <span class="anomaly-type-tag ${a.severity.toLowerCase()}">${escapeHTML(a.type)}</span>
                        <span style="font-size:12px;color:#94a3b8">Bucket: <code>${escapeHTML(a.time_bucket)}</code></span>
                    </div>
                    <span class="recurring-count-pill">${a.event_count} events</span>
                </div>
                <div class="anomaly-fact-box">
                    <strong>Observed Fact:</strong> ${escapeHTML(a.observed_fact)}
                </div>
                <div class="anomaly-suspected-box">
                    <strong>Suspected Cause:</strong> ${escapeHTML(a.suspected_cause)}
                </div>
                <div class="anomaly-rec-box">
                    <strong>Action:</strong> ${escapeHTML(a.recommendation)}
                </div>
            </div>
        `).join('');
    }

    // Also populate recurring error patterns table in anomalies view
    const recurBody = $('analytics-recurring-body');
    const recurList = state.lastAnalytics?.recurring_errors || [];
    if (recurBody) {
        if (!recurList.length) {
            recurBody.innerHTML = '<tr><td colspan="5" class="text-center py-4">No recurring patterns detected.</td></tr>';
        } else {
            recurBody.innerHTML = recurList.map(item => `
                <tr>
                    <td><span class="recurring-count-pill">${item.count}× occurrences</span></td>
                    <td><b>${escapeHTML(item.category)}</b></td>
                    <td><span class="severity-pill ${escapeHTML(item.severity)}">${escapeHTML(item.severity)}</span></td>
                    <td class="table-msg-cell" title="${escapeHTML(item.message)}">${escapeHTML(item.message)}</td>
                    <td>${escapeHTML(item.last_seen || 'Recently')}</td>
                </tr>
            `).join('');
        }
    }
}

// ==========================================================================
// RISK ASSESSMENT VIEW
// ==========================================================================
async function renderRisksView() {
    if (!state.lastAnalytics) {
        await loadDashboardData();
    }
    const risks = state.lastAnalytics?.prioritized_risks || [];
    const container = $('risks-list');
    if (!container) return;

    if (!risks.length) {
        container.innerHTML = '<div class="loading-state">No critical or high-priority operational risks identified.</div>';
        return;
    }

    container.innerHTML = risks.map(rk => `
        <div class="risk-card ${rk.risk_level.toLowerCase()}">
            <div class="risk-header">
                <span class="risk-title">${escapeHTML(rk.title)}</span>
                <span class="risk-badge ${rk.risk_level.toLowerCase()}">${escapeHTML(rk.risk_level)} RISK</span>
            </div>
            <div class="risk-body">
                <div class="risk-impact">
                    <strong>Operational Impact:</strong> ${escapeHTML(rk.why_it_matters)}
                </div>
                <div class="risk-evidence">
                    <strong>Evidence:</strong> ${escapeHTML(rk.evidence)}
                </div>
                ${rk.recommended_actions?.length ? `
                    <div style="font-size:12px;color:#38bdf8;margin-top:4px;">
                        <strong>Action:</strong> ${escapeHTML(rk.recommended_actions[0])}
                    </div>
                ` : ''}
            </div>
        </div>
    `).join('');
}

// ==========================================================================
// HEALTH REPORTS VIEW
// ==========================================================================
async function renderReportsView() {
    const reportBody = $('report-content-body');
    if (!reportBody) return;

    try {
        reportBody.innerHTML = '<div class="loading-state">Compiling system health report from active database telemetry...</div>';
        const res = await apiFetch('/api/report');
        const report = res.report || {};

        $('report-timestamp').textContent = report.generated_at || 'Just now';
        $('report-status-badge').textContent = (report.status || 'REPORT GENERATED').toUpperCase();
        $('report-status-badge').className = `report-status-badge ${(report.status || 'healthy').toLowerCase()}`;

        // Convert simple markdown lines to formatted HTML for preview
        const mdText = report.markdown || '';
        reportBody.innerHTML = formatMarkdownToHTML(mdText);

    } catch (err) {
        reportBody.innerHTML = `<div class="loading-state text-critical">Failed to compile report: ${escapeHTML(err.message)}</div>`;
    }
}

function formatMarkdownToHTML(md) {
    if (!md) return '<p>No report content available.</p>';
    const lines = md.split('\n');
    let html = '';
    let inTable = false;

    lines.forEach(line => {
        line = line.trim();
        if (line.startsWith('# ')) {
            html += `<h1>${escapeHTML(line.substring(2))}</h1>`;
        } else if (line.startsWith('## ')) {
            html += `<h2>${escapeHTML(line.substring(3))}</h2>`;
        } else if (line.startsWith('### ')) {
            html += `<h3>${escapeHTML(line.substring(4))}</h3>`;
        } else if (line.startsWith('|')) {
            const cells = line.split('|').filter((_, idx, arr) => idx > 0 && idx < arr.length - 1).map(c => c.trim());
            if (cells.every(c => c.startsWith('---') || c.startsWith(':---'))) {
                // separator line
                return;
            }
            if (!inTable) {
                html += '<table>';
                inTable = true;
            }
            html += `<tr>${cells.map(c => `<td>${escapeHTML(c)}</td>`).join('')}</tr>`;
        } else {
            if (inTable) {
                html += '</table>';
                inTable = false;
            }
            if (line.startsWith('- ')) {
                html += `<ul><li>${escapeHTML(line.substring(2))}</li></ul>`;
            } else if (line === '---') {
                html += '<hr>';
            } else if (line) {
                html += `<p>${escapeHTML(line)}</p>`;
            }
        }
    });

    if (inTable) html += '</table>';
    return html;
}

// ==========================================================================
// ANALYTICS VIEW
// ==========================================================================
async function loadAnalyticsView() {
    try {
        const response = await apiFetch('/api/analytics');
        const analytics = response.analytics || {};
        state.lastAnalytics = analytics;

        if ($('analytics-total-count')) {
            $('analytics-total-count').textContent = `${analytics.total_events ?? 0} Events Analyzed`;
        }

        if (analytics.chart_data) {
            renderCharts(analytics.chart_data);
        }

        // Historical comparison
        const comp = analytics.historical_comparison || {};
        if ($('comparison-description')) {
            $('comparison-description').textContent = comp.message || 'No historical comparison available.';
        }
        const tagsContainer = $('comparison-tags');
        if (tagsContainer) {
            let tags = [];
            if (comp.has_baseline) {
                tags.push(`<span class="comp-tag">Volume Δ: ${comp.delta_volume_percent > 0 ? '+' : ''}${comp.delta_volume_percent}%</span>`);
                if (comp.new_signatures_count) {
                    tags.push(`<span class="comp-tag text-warning">${comp.new_signatures_count} new error signatures</span>`);
                }
                if (comp.resolved_signatures_count) {
                    tags.push(`<span class="comp-tag text-healthy">${comp.resolved_signatures_count} resolved signatures</span>`);
                }
            } else {
                tags.push('<span class="comp-tag">Initial Session</span>');
            }
            tagsContainer.innerHTML = tags.join('');
        }

        // Subsystems Matrix
        const catCounts = analytics.category_counts || {};
        const categories = [
            'Database', 'Authentication', 'Network', 'File System', 'Memory', 'API & Backend', 'Background Jobs', 'Infrastructure', 'Application'
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
                        <div class="acc-count">${count} <small style="font-size:11px;color:#94a3b8">events</small></div>
                    </div>
                `;
            }).join('');
        }
    } catch (err) {
        showToast(`Analytics query error: ${err.message}`, 'error');
    }
}

// ==========================================================================
// LOG INGESTION & UPLOAD
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
            btnAnalyzeRaw.innerHTML = '<span>Processing Telemetry...</span>';

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
            showToast(`Ingested successfully: ${response.saved_to_database} records saved!`, 'success');
            loadDashboardData();
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
            loadDashboardData();
            switchTab('overview');
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
        loadDashboardData();
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
        feedback.innerHTML = `<strong>Ingestion Failure:</strong> ${escapeHTML(data.error || 'Unknown error occurred.')}`;
    } else {
        feedback.className = 'upload-feedback-box success';
        feedback.innerHTML = `
            <strong>Ingestion Complete:</strong> File <code>${escapeHTML(data.source_name)}</code> processed successfully.<br>
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
                <button class="btn btn-primary btn-sm" onclick="analyseFurtherRecord(${row.id})">Analyse further ↗</button>
                    </td>
                </tr>
            `).join('');
        }

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
// LOGSCOPE: FURTHER ANALYSIS
// ==========================================================================
function ensureLogScopeModal() {
    if ($('logscope-analysis-modal')) return;
    const modal = document.createElement('div');
    modal.id = 'logscope-analysis-modal';
    modal.className = 'modal-overlay hidden';
    modal.innerHTML = `
      <div class="modal-content logscope-analysis-content" role="dialog" aria-modal="true" aria-labelledby="logscope-analysis-title">
        <div class="modal-header"><div><h2 id="logscope-analysis-title">Analyse further with LogScope</h2><p class="modal-subtitle">Detailed diagnosis from LogScope's analysis engine</p></div><button type="button" class="modal-close" id="logscope-analysis-close" aria-label="Close">×</button></div>
        <div id="logscope-analysis-body" class="logscope-analysis-body"><p>Analysing error…</p></div>
        <div class="modal-footer"><button type="button" class="btn btn-secondary" id="logscope-analysis-dismiss">Close</button></div>
      </div>`;
    document.body.appendChild(modal);
    const close = () => modal.classList.add('hidden');
    $('logscope-analysis-close').addEventListener('click', close);
    $('logscope-analysis-dismiss').addEventListener('click', close);
    modal.addEventListener('click', event => { if (event.target === modal) close(); });
}

window.analyseFurtherRecord = async function(id) {
    ensureLogScopeModal();
    const modal = $('logscope-analysis-modal');
    const body = $('logscope-analysis-body');
    modal.classList.remove('hidden');
    body.innerHTML = '<p>Sending this error to LogScope…</p>';
    try {
        const detail = await apiFetch(`/api/errors/${encodeURIComponent(id)}`);
        const rec = detail.record || {};
        const logText = `${rec.timestamp || ''} [${rec.severity || 'Error'}] [${rec.category || 'Application'}] ${rec.message || ''}`.trim();
        const result = await apiFetch('/api/integrations/logscope/analyze', {
            method: 'POST', headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ log_text: logText, source_name: `LogHealth error #${rec.id || id}` })
        });
        const analysis = result.analysis || {};
        const items = analysis.errors || [];
        body.innerHTML = `
          <div class="logscope-source-pill">Analysis provided by LogScope · ${escapeHTML(analysis.primary_environment || 'Detected environment')}</div>
          <div class="logscope-summary-grid">
            <div><span>Errors detected</span><strong>${Number(analysis.stats?.total_errors ?? items.length)}</strong></div>
            <div><span>Critical</span><strong>${Number(analysis.stats?.critical ?? 0)}</strong></div>
            <div><span>Unique patterns</span><strong>${Number(analysis.stats?.unique_errors ?? items.length)}</strong></div>
          </div>
          ${items.length ? items.map(item => { const ex = item.explanation || {}; return `<article class="logscope-diagnosis-card"><div class="logscope-diagnosis-heading"><strong>${escapeHTML(item.type || 'Detected error')}</strong><span>${escapeHTML(item.severity || 'Error')}</span></div><p><b>What happened</b><br>${escapeHTML(ex.description || item.message || 'No description available.')}</p><p><b>Likely cause</b><br>${escapeHTML(ex.cause || 'The available evidence is insufficient to establish a root cause.')}</p><p><b>Suggested fix</b><br>${escapeHTML(ex.fix || 'Inspect the related stack trace and component logs.')}</p>${ex.code ? `<pre>${escapeHTML(ex.code)}</pre>` : ''}${(ex.source_links || []).length ? `<p><b>Related resources</b><br>${ex.source_links.map(link => `<a href="${escapeHTML(link.url || '#')}" target="_blank" rel="noopener noreferrer">${escapeHTML(link.title || link.source || 'Resource')}</a>`).join(' · ')}</p>` : ''}</article>`; }).join('') : '<p>LogScope could not detect a specific error from this record. Try inspecting the full original log in LogScope.</p>'}`;
    } catch (error) {
        body.innerHTML = `<div class="alert alert-danger">${escapeHTML(error.message || 'LogScope analysis failed.')}</div><p>Check that both deployments are available and the LOGSCOPE_API_URL setting is correct.</p>`;
    }
};

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
        $('modal-title').textContent = `${rec.category} Event Details`;
        $('modal-message').textContent = rec.message || '';

        const causesList = $('modal-causes-list');
        causesList.innerHTML = (recommendation.possible_causes || []).map(c => `<li>${escapeHTML(c)}</li>`).join('');

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

    // Formula Modal
    const formulaModal = $('formula-modal');
    const btnExplain = $('btn-explain-formula');
    const formulaClose = $('formula-modal-close');
    const formulaDismiss = $('formula-btn-dismiss');
    const formulaBackdrop = $('formula-backdrop');

    const openFormula = () => {
        if (!formulaModal) return;
        const hs = state.lastAnalytics?.health_score;
        const ded = hs?.deductions || {};

        if ($('fb-critical-deduction')) $('fb-critical-deduction').textContent = `-${ded.critical_deduction ?? 0.0}`;
        if ($('fb-error-deduction')) $('fb-error-deduction').textContent = `-${ded.error_deduction ?? 0.0}`;
        if ($('fb-warning-deduction')) $('fb-warning-deduction').textContent = `-${ded.warning_deduction ?? 0.0}`;
        if ($('fb-anomaly-deduction')) $('fb-anomaly-deduction').textContent = `-${ded.anomaly_deduction ?? 0.0}`;
        if ($('fb-concentration-deduction')) $('fb-concentration-deduction').textContent = `-${ded.concentration_deduction ?? 0.0}`;
        if ($('fb-final-score')) $('fb-final-score').textContent = `${ded.final_score ?? '—'} / 100`;

        formulaModal.classList.remove('hidden');
    };

    const closeFormula = () => formulaModal?.classList.add('hidden');

    btnExplain?.addEventListener('click', openFormula);
    formulaClose?.addEventListener('click', closeFormula);
    formulaDismiss?.addEventListener('click', closeFormula);
    formulaBackdrop?.addEventListener('click', closeFormula);
}

// ==========================================================================
// REPORT EXPORT ACTIONS
// ==========================================================================
function initReportActions() {
    $('btn-download-report-md')?.addEventListener('click', () => {
        window.location.href = '/api/report?format=markdown&download=1';
    });

    $('btn-copy-report-md')?.addEventListener('click', () => {
        const mdText = state.lastAnalytics?.report?.markdown;
        if (mdText) {
            navigator.clipboard.writeText(mdText).then(() => {
                showToast('Report Markdown copied to clipboard!', 'success');
            });
        } else {
            showToast('Report content not loaded yet.', 'warning');
        }
    });
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
        localStorage.setItem('loghealth_api_key', val);
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
            a.download = `loghealth_export_${new Date().toISOString().substring(0, 10)}.json`;
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
    const importParams = new URLSearchParams(window.location.search);
    if (importParams.get('imported') === '1') {
        const count = Number(importParams.get('count') || 0);
        showToast(`LogScope import received. ${count} new record(s) added to LogHealth.`, 'success', 6000);
        importParams.delete('imported'); importParams.delete('count');
        const cleanUrl = `${window.location.pathname}${importParams.toString() ? `?${importParams}` : ''}${window.location.hash}`;
        window.history.replaceState({}, '', cleanUrl);
    }
    initNavigation();
    initUploadHandlers();
    initHistoryControls();
    initModalHandlers();
    initReportActions();
    initApiExplorer();
    initSettingsHandlers();

    // Refresh Button Handler
    $('btn-refresh')?.addEventListener('click', () => {
        const btn = $('btn-refresh');
        btn.classList.add('refreshing');
        checkHealth();
        loadDashboardData();
        setTimeout(() => btn.classList.remove('refreshing'), 600);
        showToast('Dashboard telemetry refreshed from SQLite.', 'info');
    });

    // Initial Health and Dashboard Load
    checkHealth();
    loadDashboardData();
});
