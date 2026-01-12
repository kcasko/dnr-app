const q = document.getElementById("q");
const btn = document.getElementById("btn");
const statusDiv = document.getElementById("status");
const resultsDiv = document.getElementById("results");

function escapeHtml(s) {
  return String(s)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function badge(row) {
  if (row.ban_type === "permanent") {
    return `<span class="badge-permanent">PERMANENT BAN</span>`;
  }
  if (row.ban_type === "temporary") {
    return `<span class="badge-temporary">TEMPORARY BAN (unresolved)</span>`;
  }
  return "";
}

async function doSearch() {
  const term = q.value.trim();
  resultsDiv.innerHTML = "";
  statusDiv.textContent = "";

  if (!term) {
    statusDiv.textContent = "Type a name to search.";
    return;
  }

  statusDiv.textContent = "Searching...";

  const res = await fetch(`/search?q=${encodeURIComponent(term)}`);
  const rows = await res.json();

  if (!Array.isArray(rows) || rows.length === 0) {
    statusDiv.textContent = "No active bans found.";
    return;
  }

  statusDiv.textContent = `Found ${rows.length} active ban(s).`;

  resultsDiv.innerHTML = rows.map(r => {
    const name = `${escapeHtml(r.first_name)} ${escapeHtml(r.last_name)}`;

    let resolveButton = "";
    if (r.ban_type === "temporary") {
      resolveButton = `
        <form method="post" action="/resolve/${r.id}" class="resolve-form">
            <button type="submit">Mark Paid</button>
        </form>
      `;
    }

    return `
      <div class="incident-card">
        <div class="incident-header">
            <div class="name">${name}</div>
            ${badge(r)}
        </div>
        <div class="meta">
            Reason: ${escapeHtml(r.reason)} |
            Room: ${escapeHtml(r.room_number || "")} |
            Date: ${escapeHtml(r.incident_date)} |
            Staff: ${escapeHtml(r.staff_initials)}
        </div>
        <div>${escapeHtml(r.description)}</div>
        ${resolveButton}
      </div>
    `;
  }).join("");
}

btn.addEventListener("click", doSearch);
q.addEventListener("keydown", e => {
  if (e.key === "Enter") doSearch();
});
