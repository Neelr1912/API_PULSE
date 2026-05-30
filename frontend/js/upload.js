function getToken() {
  return localStorage.getItem("apipulse_token");
}

function uploadStatusLabel(item) {
  if (item.failed_rows > 0) return "Partial";
  return "Complete";
}

function formatDate(iso) {
  try {
    return new Date(iso).toLocaleString();
  } catch {
    return iso;
  }
}

/**
 * POST /upload/csv with upload progress via XMLHttpRequest.
 */
function uploadCSV(file, onProgress) {
  return new Promise((resolve, reject) => {
    const token = getToken();
    if (!token) {
      reject(new Error("Not authenticated. Please log in again."));
      return;
    }

    const formData = new FormData();
    formData.append("file", file);

    const xhr = new XMLHttpRequest();
    xhr.open("POST", `${API_BASE}/upload/csv`);
    xhr.setRequestHeader("Authorization", `Bearer ${token}`);

    xhr.upload.addEventListener("progress", (e) => {
      if (e.lengthComputable && typeof onProgress === "function") {
        onProgress(Math.round((e.loaded / e.total) * 100));
      }
    });

    xhr.onload = () => {
      let body = {};
      try {
        body = JSON.parse(xhr.responseText);
      } catch {
        body = { detail: xhr.responseText || "Upload failed" };
      }
      if (xhr.status >= 200 && xhr.status < 300) {
        resolve(body);
        return;
      }
      const detail =
        typeof body.detail === "string"
          ? body.detail
          : Array.isArray(body.detail)
            ? body.detail.map((d) => d.msg || JSON.stringify(d)).join(", ")
            : "Upload failed";
      reject(new Error(detail));
    };

    xhr.onerror = () => reject(new Error("Network error during upload"));
    xhr.send(formData);
  });
}

async function fetchUploadHistory() {
  const token = getToken();
  if (!token) throw new Error("Not authenticated");

  const res = await fetch(`${API_BASE}/upload/history`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    throw new Error(
      typeof data.detail === "string" ? data.detail : "Could not load upload history"
    );
  }
  return data;
}

function setUploadLoading(loading) {
  const btn = document.getElementById("upload-btn");
  const bar = document.getElementById("upload-progress");
  if (btn) {
    btn.disabled = loading;
    btn.classList.toggle("is-loading", loading);
    const spinner = btn.querySelector(".spinner");
    if (spinner) spinner.hidden = !loading;
  }
  if (bar) {
    bar.hidden = !loading;
    if (!loading) {
      bar.value = 0;
      bar.removeAttribute("value");
    }
  }
}

function showUploadSummary(data) {
  const card = document.getElementById("upload-summary");
  if (!card) return;

  const failedNote =
    data.failed_rows > 0
      ? `${data.failed_rows} rows skipped (see details)`
      : "All rows inserted";

  let detailsHtml = "";
  if (data.failed_details?.length) {
    const items = data.failed_details
      .slice(0, 8)
      .map((f) => `<li>Row ${f.row}: ${f.reason}</li>`)
      .join("");
    detailsHtml = `<ul class="failed-list">${items}</ul>`;
  }

  card.hidden = false;
  card.className = "upload-summary success";
  card.innerHTML = `
    <p class="summary-title">✅ ${data.message} — ${data.inserted_rows} rows inserted</p>
    <p>${failedNote}</p>
    <p>Routes detected: ${data.routes_detected?.length ?? 0}</p>
    ${detailsHtml}
  `;
}

function showUploadError(message) {
  const card = document.getElementById("upload-summary");
  if (!card) return;
  card.hidden = false;
  card.className = "upload-summary error";
  card.innerHTML = `<p class="summary-title">Upload failed</p><p>${message}</p>`;
}

function renderHistory(items) {
  const tbody = document.getElementById("history-tbody");
  if (!tbody) return;

  if (!items.length) {
    tbody.innerHTML = `<tr><td colspan="5" class="muted">No uploads yet</td></tr>`;
    return;
  }

  tbody.innerHTML = items
    .map(
      (h) => `
    <tr>
      <td>${h.filename}</td>
      <td>${h.inserted_rows} / ${h.total_rows}</td>
      <td>${formatDate(h.uploaded_at)}</td>
      <td><span class="status-badge ${uploadStatusLabel(h).toLowerCase()}">${uploadStatusLabel(h)}</span></td>
      <td class="muted">${h.failed_rows} failed</td>
    </tr>`
    )
    .join("");
}

document.addEventListener("DOMContentLoaded", () => {
  const fileInput = document.getElementById("csv-file");
  const uploadBtn = document.getElementById("upload-btn");
  const progress = document.getElementById("upload-progress");
  const historyToggle = document.getElementById("history-toggle");
  const historyPanel = document.getElementById("history-panel");

  historyToggle?.addEventListener("click", () => {
    const open = historyPanel.hidden;
    historyPanel.hidden = !open;
    historyToggle.setAttribute("aria-expanded", String(open));
    historyToggle.textContent = open ? "Recent Uploads ▲" : "Recent Uploads ▼";
  });

  uploadBtn?.addEventListener("click", async () => {
    const file = fileInput?.files?.[0];
    if (!file) {
      showUploadError("Please choose a CSV file first.");
      return;
    }

    setUploadLoading(true);
    if (progress) progress.hidden = false;

    try {
      const data = await uploadCSV(file, (pct) => {
        if (progress) {
          progress.value = pct;
          progress.textContent = `${pct}%`;
        }
      });
      showUploadSummary(data);
      try {
        if (typeof refreshDashboard === "function") {
          await refreshDashboard();
        }
      } catch {
        /* Analytics refresh is optional until Step 4 is fully wired */
      }
      const history = await fetchUploadHistory();
      renderHistory(history);
    } catch (err) {
      showUploadError(err.message);
    } finally {
      setUploadLoading(false);
    }
  });

  fetchUploadHistory()
    .then(renderHistory)
    .catch(() => renderHistory([]));
});
