(function () {
  "use strict";

  if (location.pathname !== "/app-health") return;

  function esc(value) {
    return String(value ?? "")
      .replaceAll("&", "&amp;")
      .replaceAll("<", "&lt;")
      .replaceAll(">", "&gt;")
      .replaceAll('"', "&quot;")
      .replaceAll("'", "&#039;");
  }

  function ensurePanel() {
    let panel = document.getElementById("ai-health-backups-v443");
    if (panel) return panel;

    panel = document.createElement("section");
    panel.id = "ai-health-backups-v443";
    panel.className = "card ai-health-backups";
    panel.innerHTML = `
      <h2>Backups</h2>
      <p class="muted">Backup tools were moved here from Admin for the standalone version.</p>
      <button type="button" id="aiCreateHealthBackup">Create Backup</button>
      <button type="button" id="aiRefreshHealthBackups">Refresh</button>
      <div id="aiHealthBackupStatus" class="muted">Loading backups...</div>
      <div id="aiHealthBackupList"></div>
    `;

    const h1 = document.querySelector("h1");
    if (h1 && h1.parentNode) {
      h1.parentNode.insertBefore(panel, h1.nextSibling);
    } else {
      document.body.appendChild(panel);
    }

    panel.querySelector("#aiCreateHealthBackup").addEventListener("click", createBackup);
    panel.querySelector("#aiRefreshHealthBackups").addEventListener("click", loadBackups);

    return panel;
  }

  async function loadBackups() {
    const panel = ensurePanel();
    const status = panel.querySelector("#aiHealthBackupStatus");
    const list = panel.querySelector("#aiHealthBackupList");

    status.textContent = "Loading backups...";
    list.innerHTML = "";

    try {
      const res = await fetch("/api/app-health/backups");
      const data = await res.json();
      const backups = data.backups || [];

      status.textContent = `${backups.length} backup(s) found.`;

      if (!backups.length) {
        list.innerHTML = "<p class='muted'>No backups found yet.</p>";
        return;
      }

      list.innerHTML = backups.slice(0, 12).map(b => `
        <div class="ai-health-backup-row">
          <strong>${esc(b.filename)}</strong><br>
          <span class="muted">${esc(b.modified)} · ${esc(b.size_mb)} MB</span><br>
          <a href="${esc(b.download_url)}">Download</a>
        </div>
      `).join("");
    } catch (err) {
      status.textContent = "Unable to load backups: " + err;
    }
  }

  async function createBackup() {
    const panel = ensurePanel();
    const status = panel.querySelector("#aiHealthBackupStatus");

    status.textContent = "Creating backup...";

    try {
      const res = await fetch("/api/app-health/backups/create", { method: "POST" });
      const data = await res.json();

      if (!data.ok) {
        status.textContent = "Backup failed: " + (data.error || data.output || "unknown error");
        return;
      }

      status.textContent = "Backup created.";
      loadBackups();
    } catch (err) {
      status.textContent = "Backup failed: " + err;
    }
  }

  function init() {
    ensurePanel();
    loadBackups();
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
