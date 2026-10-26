
const $ = (id) => document.getElementById(id);

function showMessage(message, isError = false) {
  const el = $("msg");
  el.textContent = message;
  el.classList.remove("hidden");
  el.style.color = isError ? "#dc2626" : "#15803d";
}

function escapeHTML(value) {
  return String(value ?? "").replace(/[&<>"']/g, (char) => ({
    "&": "&amp;",
    "<": "&lt;",
    ">": "&gt;",
    '"': "&quot;",
    "'": "&#39;"
  })[char]);
}

async function requestJSON(url, options = {}) {
  const response = await fetch(url, options);
  if (!response.ok) {
    throw new Error(`Request failed: ${response.status}`);
  }
  return response.json();
}

function renderDashboard(data) {
  // Support common response formats from the Flask API.
  const rows = Array.isArray(data)
    ? data
    : (data.errors || data.records || data.recent || []);

  const summary = data.summary || data.stats || data;
  const counts = {};
  const severityCounts = {};

  rows.forEach((row) => {
    const type = row.type || row.category || "Other";
    const severity = String(row.severity || "Error").toLowerCase();
    counts[type] = (counts[type] || 0) + 1;
    severityCounts[severity] = (severityCounts[severity] || 0) + 1;
  });

  const total = summary.total ?? summary.total_errors ?? rows.length;
  const types = summary.types ?? summary.error_types ?? Object.keys(counts).length;
  const critical = summary.critical ?? severityCounts.critical ?? 0;
  const warning = summary.warning ?? summary.warnings ?? severityCounts.warning ?? 0;

  $("total").textContent = total;
  $("types").textContent = types;
  $("critical").textContent = critical;
  $("warning").textContent = warning;
  $("donutTotal").textContent = total;
  $("health").textContent = Number(critical) > 0 ? "ATTENTION" : "HEALTHY";

  const maxCount = Math.max(1, ...Object.values(counts));
  $("bars").innerHTML = Object.entries(counts).length
    ? Object.entries(counts).sort((a, b) => b[1] - a[1]).map(([name, count]) => `
        <div class="bar-row">
          <span>${escapeHTML(name)}</span>
          <div class="bar-track"><div class="bar-fill" style="width:${count / maxCount * 100}%"></div></div>
          <b>${count}</b>
        </div>`).join("")
    : "<p>No error categories available.</p>";

  const severityColors = {
    critical: "#ef4444",
    error: "#f97316",
    warning: "#f59e0b",
    info: "#3b82f6"
  };

  const entries = Object.entries(severityCounts);
  const sum = entries.reduce((n, [, count]) => n + count, 0);
  let offset = 0;
  const segments = entries.map(([severity, count]) => {
    const start = offset;
    offset += sum ? count / sum * 100 : 0;
    return `${severityColors[severity] || "#8b5cf6"} ${start}% ${offset}%`;
  });

  $("donut").style.background = sum
    ? `conic-gradient(${segments.join(",")})`
    : "#e5e7eb";

  $("legend").innerHTML = entries.map(([severity, count]) => `
    <div class="legend-item">
      <span class="legend-dot" style="background:${severityColors[severity] || "#8b5cf6"}"></span>
      ${escapeHTML(severity)} <b>${count}</b>
    </div>`).join("");

  const sortedTypes = Object.entries(counts).sort((a, b) => b[1] - a[1]);
  $("recurringList").innerHTML = sortedTypes.length
    ? sortedTypes.slice(0, 5).map(([type, count]) => `
        <article class="recurring-card">
          <b>${escapeHTML(type)}</b>
          <p>${count} occurrence${count === 1 ? "" : "s"}</p>
        </article>`).join("")
    : "<p>No recurring errors found.</p>";

  const recommendations = {
    network: "Check connectivity, service availability, and timeout settings.",
    database: "Check database connectivity, query performance, and connection pools.",
    authentication: "Review authentication rules, credentials, and access logs.",
    memory: "Inspect memory usage, object lifetimes, and resource limits.",
    filesystem: "Check file paths, permissions, and available disk space."
  };

  $("recommendationsList").innerHTML = sortedTypes.length
    ? sortedTypes.slice(0, 5).map(([type]) => {
        const key = type.toLowerCase();
        const advice = Object.entries(recommendations)
          .find(([keyword]) => key.includes(keyword))?.[1]
          || "Inspect the associated log details and trace the error to its source.";
        return `<article class="recommendation-item">
          <b>${escapeHTML(type)}</b><p>${escapeHTML(advice)}</p>
        </article>`;
      }).join("")
    : "<p>Load or upload logs to receive recommendations.</p>";

  $("recentBody").innerHTML = rows.length
    ? rows.slice().reverse().slice(0, 20).map((row) => `
        <tr>
          <td>${escapeHTML(row.timestamp || row.time || "—")}</td>
          <td>${escapeHTML(row.type || row.category || "Other")}</td>
          <td>${escapeHTML(row.message || row.error || "—")}</td>
          <td>${escapeHTML(row.severity || "Error")}</td>
        </tr>`).join("")
    : "<tr><td colspan='4'>No error records available.</td></tr>";
}

async function loadDemo() {
  try {
    $("demo").disabled = true;
    $("demo").textContent = "Loading...";
    const data = await requestJSON("/api/demo");
    renderDashboard(data);
    showMessage("Demo data loaded.");
  } catch (error) {
    showMessage(`Could not load demo data: ${error.message}`, true);
  } finally {
    $("demo").disabled = false;
    $("demo").textContent = "Load Demo";
  }
}

async function uploadErrors(file) {
  try {
    const parsed = JSON.parse(await file.text());

    const data = await requestJSON("/api/analyze", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(parsed)
    });

    renderDashboard(data);
    showMessage("File analyzed successfully.");
  } catch (error) {
    showMessage(`Could not analyze file: ${error.message}`, true);
  }
}

$("demo").addEventListener("click", loadDemo);
$("file").addEventListener("change", (event) => {
  const file = event.target.files[0];
  if (file) uploadErrors(file);
});

// Load sample data automatically when the dashboard opens.
loadDemo();
