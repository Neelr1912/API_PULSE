let routeData = [];
let sortKey = "avg_latency_ms";
let sortDir = "desc";

function getToken() {
  return localStorage.getItem("apipulse_token");
}

function authHeaders() {
  const token = getToken();
  if (!token) {
    window.location.replace("index.html");
    throw new Error("Not authenticated");
  }
  return { Authorization: `Bearer ${token}`, "Content-Type": "application/json" };
}

async function apiGet(path) {
  const res = await fetch(`${API_BASE}${path}`, { headers: authHeaders() });
  const data = await res.json().catch(() => ({}));
  if (res.status === 401) {
    localStorage.removeItem("apipulse_token");
    localStorage.removeItem("apipulse_user");
    window.location.replace("index.html");
    throw new Error("Session expired");
  }
  if (!res.ok) {
    throw new Error(typeof data.detail === "string" ? data.detail : "Request failed");
  }
  return data;
}

function scoreBadge(score) {
  if (score < 3) return { label: "Healthy", className: "healthy" };
  if (score < 6) return { label: "Unstable", className: "unstable" };
  return { label: "Critical", className: "critical" };
}

function trendIcon(trend) {
  if (trend === "improving") return '<span class="trend improving" title="Improving">↑</span>';
  if (trend === "degrading") return '<span class="trend degrading" title="Degrading">↓</span>';
  return '<span class="trend stable" title="Stable">→</span>';
}

function errorBadgeClass(rate) {
  if (rate < 5) return "badge-green";
  if (rate <= 15) return "badge-yellow";
  return "badge-red";
}

function latencyBadgeClass(ms) {
  if (ms < 500) return "badge-green";
  if (ms <= 1500) return "badge-yellow";
  return "badge-red";
}

function errorBadgeLabel(rate) {
  if (rate < 5) return "healthy";
  if (rate <= 15) return "elevated";
  return "high";
}

function latencyBadgeLabel(ms) {
  if (ms < 500) return "fast";
  if (ms <= 1500) return "moderate";
  return "slow";
}

function formatNum(n) {
  return Number(n).toLocaleString(undefined, { maximumFractionDigits: 2 });
}

async function fetchOverview() {
  const overview = await apiGet("/analytics/overview");
  document.getElementById("stat-total-reqs").textContent = formatNum(overview.total_requests_all);
  document.getElementById("stat-total-sub").textContent = `last 24h: ${formatNum(overview.requests_last_24h)}`;
  document.getElementById("stat-error-rate").textContent = `${formatNum(overview.overall_error_rate)}%`;
  const errBadge = document.getElementById("stat-error-badge");
  errBadge.textContent = `⚠ ${errorBadgeLabel(overview.overall_error_rate)}`;
  errBadge.className = `stat-badge ${errorBadgeClass(overview.overall_error_rate)}`;
  document.getElementById("stat-avg-latency").textContent = `${formatNum(overview.avg_latency_all)} ms`;
  const latBadge = document.getElementById("stat-latency-badge");
  latBadge.textContent = `🐢 ${latencyBadgeLabel(overview.avg_latency_all)}`;
  latBadge.className = `stat-badge ${latencyBadgeClass(overview.avg_latency_all)}`;
  document.getElementById("stat-routes").textContent = formatNum(overview.total_routes);
  document.getElementById("stat-routes-sub").textContent = "monitored";
}

function getFilteredRoutes() {
  const q = (document.getElementById("route-filter")?.value || "").trim().toLowerCase();
  let rows = [...routeData];
  if (q) rows = rows.filter((r) => r.route.toLowerCase().includes(q));
  rows.sort((a, b) => {
    const av = a[sortKey];
    const bv = b[sortKey];
    if (typeof av === "string") return sortDir === "asc" ? av.localeCompare(bv) : bv.localeCompare(av);
    return sortDir === "asc" ? av - bv : bv - av;
  });
  return rows;
}

function renderRouteTable() {
  const tbody = document.getElementById("routes-tbody");
  if (!tbody) return;
  const rows = getFilteredRoutes();
  if (!rows.length) {
    tbody.innerHTML = `<tr><td colspan="9" class="muted">No routes match. Upload logs or adjust filter.</td></tr>`;
    return;
  }

  tbody.innerHTML = rows
    .map((r) => {
      const badge = scoreBadge(r.instability_score);
      return `
      <tr class="route-row" data-route="${encodeURIComponent(r.route)}" tabindex="0">
        <td>${r.route}</td>
        <td>${r.method || "—"}</td>
        <td>${formatNum(r.total_requests)}</td>
        <td>${formatNum(r.avg_latency_ms)}</td>
        <td>${formatNum(r.p95_latency_ms)}</td>
        <td>${formatNum(r.error_rate_percent)}%</td>
        <td><span class="score-badge ${badge.className}">${badge.label} (${r.instability_score})</span></td>
        <td>${trendIcon(r.trend)}</td>
        <td>
          <span class="suggestion-tip" title="${r.suggestion.replace(/"/g, "&quot;")}">ℹ</span>
        </td>
      </tr>`;
    })
    .join("");

  tbody.querySelectorAll(".route-row").forEach((tr) => {
    tr.addEventListener("click", () => {
      const route = decodeURIComponent(tr.dataset.route);
      openRouteModal(route);
    });
  });
}

async function fetchRouteSummary() {
  routeData = await apiGet("/analytics/summary");
  renderRouteTable();
}

async function fetchRouteDetail(route) {
  const encoded = encodeURIComponent(route);
  return apiGet(`/analytics/route/${encoded}`);
}

function openModal() {
  const modal = document.getElementById("route-modal");
  if (modal) {
    modal.hidden = false;
    modal.setAttribute("aria-hidden", "false");
  }
}

function closeModal() {
  const modal = document.getElementById("route-modal");
  if (modal) {
    modal.hidden = true;
    modal.setAttribute("aria-hidden", "true");
  }
  if (typeof destroyAllCharts === "function") destroyAllCharts();
}

async function openRouteModal(route) {
  const loading = document.getElementById("modal-loading");
  openModal();
  if (loading) loading.hidden = false;

  try {
    const detail = await fetchRouteDetail(route);
    document.getElementById("modal-route-title").textContent = detail.route;
    const badge = scoreBadge(detail.instability_score);
    const badgeEl = document.getElementById("modal-score-badge");
    badgeEl.textContent = `${badge.label} (${detail.instability_score})`;
    badgeEl.className = `score-badge ${badge.className}`;

    document.getElementById("modal-avg").textContent = `${formatNum(detail.avg_latency_ms)} ms`;
    document.getElementById("modal-p95").textContent = `${formatNum(detail.p95_latency_ms)} ms`;
    document.getElementById("modal-p99").textContent = `${formatNum(detail.p99_latency_ms)} ms`;
    document.getElementById("modal-min").textContent = `${formatNum(detail.min_latency_ms)} ms`;
    document.getElementById("modal-max").textContent = `${formatNum(detail.max_latency_ms)} ms`;
    document.getElementById("modal-error").textContent = `${formatNum(detail.error_rate_percent)}%`;
    document.getElementById("modal-suggestion").textContent = detail.suggestion;

    renderDailyTrendLine("chart-daily", detail.daily_breakdown || {});
    renderHourlyBarChart("chart-hourly", detail.hourly_breakdown || {});
    renderErrorDoughnut("chart-status", detail.status_distribution || {});
  } catch (err) {
    document.getElementById("modal-suggestion").textContent = err.message;
  } finally {
    if (loading) loading.hidden = true;
  }
}

function setupTableSort() {
  document.querySelectorAll("#routes-table th[data-sort]").forEach((th) => {
    th.addEventListener("click", () => {
      const key = th.dataset.sort;
      if (sortKey === key) {
        sortDir = sortDir === "asc" ? "desc" : "asc";
      } else {
        sortKey = key;
        sortDir = "desc";
      }
      document.querySelectorAll("#routes-table th[data-sort]").forEach((h) => {
        h.classList.remove("sort-asc", "sort-desc");
      });
      th.classList.add(sortDir === "asc" ? "sort-asc" : "sort-desc");
      renderRouteTable();
    });
  });
}

async function refreshDashboard() {
  const analyticsSection = document.getElementById("analytics-section");
  try {
    if (analyticsSection) analyticsSection.classList.add("loading");
    await Promise.all([fetchOverview(), fetchRouteSummary()]);
  } finally {
    if (analyticsSection) analyticsSection.classList.remove("loading");
  }
}

document.addEventListener("DOMContentLoaded", () => {
  if (!getToken()) {
    window.location.replace("index.html");
    return;
  }

  document.getElementById("route-filter")?.addEventListener("input", renderRouteTable);
  setupTableSort();

  document.getElementById("modal-close")?.addEventListener("click", closeModal);
  document.getElementById("route-modal")?.addEventListener("click", (e) => {
    if (e.target.id === "route-modal") closeModal();
  });

  refreshDashboard();
});
