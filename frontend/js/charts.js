/** Chart.js helpers with instance tracking to avoid canvas reuse errors. */
const chartInstances = {};

function destroyChart(canvasId) {
  if (chartInstances[canvasId]) {
    chartInstances[canvasId].destroy();
    delete chartInstances[canvasId];
  }
}

const chartDefaults = {
  responsive: true,
  maintainAspectRatio: false,
  plugins: {
    legend: { labels: { color: "#e7ecf3" } },
  },
  scales: {
    x: { ticks: { color: "#94a3b8" }, grid: { color: "rgba(45,58,79,0.5)" } },
    y: { ticks: { color: "#94a3b8" }, grid: { color: "rgba(45,58,79,0.5)" } },
  },
};

function renderLatencyBarChart(canvasId, labels, data) {
  destroyChart(canvasId);
  const ctx = document.getElementById(canvasId);
  if (!ctx) return;
  chartInstances[canvasId] = new Chart(ctx, {
    type: "bar",
    data: {
      labels,
      datasets: [
        {
          label: "Avg latency (ms)",
          data,
          backgroundColor: "rgba(59, 130, 246, 0.7)",
          borderRadius: 4,
        },
      ],
    },
    options: {
      ...chartDefaults,
      plugins: { ...chartDefaults.plugins, legend: { display: false } },
    },
  });
}

function renderErrorDoughnut(canvasId, statusDistribution) {
  destroyChart(canvasId);
  const ctx = document.getElementById(canvasId);
  if (!ctx) return;
  const labels = Object.keys(statusDistribution);
  const data = Object.values(statusDistribution);
  const colors = labels.map((code) => {
    const c = parseInt(code, 10);
    if (c >= 500) return "#f87171";
    if (c >= 400) return "#fbbf24";
    if (c >= 300) return "#60a5fa";
    return "#4ade80";
  });

  chartInstances[canvasId] = new Chart(ctx, {
    type: "doughnut",
    data: {
      labels: labels.map((l) => `HTTP ${l}`),
      datasets: [{ data, backgroundColor: colors }],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: { legend: { position: "bottom", labels: { color: "#e7ecf3" } } },
    },
  });
}

function renderDailyTrendLine(canvasId, dailyBreakdown) {
  destroyChart(canvasId);
  const ctx = document.getElementById(canvasId);
  if (!ctx) return;
  const labels = Object.keys(dailyBreakdown).sort();
  const data = labels.map((k) => dailyBreakdown[k]);

  chartInstances[canvasId] = new Chart(ctx, {
    type: "line",
    data: {
      labels,
      datasets: [
        {
          label: "Avg latency (ms)",
          data,
          borderColor: "#3b82f6",
          backgroundColor: "rgba(59, 130, 246, 0.15)",
          fill: true,
          tension: 0.25,
        },
      ],
    },
    options: chartDefaults,
  });
}

function renderHourlyBarChart(canvasId, hourlyBreakdown) {
  destroyChart(canvasId);
  const ctx = document.getElementById(canvasId);
  if (!ctx) return;
  const labels = Array.from({ length: 24 }, (_, i) => String(i));
  const data = labels.map((h) => hourlyBreakdown[h] ?? 0);

  chartInstances[canvasId] = new Chart(ctx, {
    type: "bar",
    data: {
      labels,
      datasets: [
        {
          label: "Avg latency by hour",
          data,
          backgroundColor: labels.map((_, i) =>
            i >= 9 && i <= 17 ? "rgba(251, 191, 36, 0.75)" : "rgba(59, 130, 246, 0.55)"
          ),
        },
      ],
    },
    options: {
      ...chartDefaults,
      plugins: { ...chartDefaults.plugins, legend: { display: false } },
    },
  });
}

function destroyAllCharts() {
  Object.keys(chartInstances).forEach(destroyChart);
}
