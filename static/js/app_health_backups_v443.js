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
          <div class="ai-health-backup-row-head">
            <strong>${esc(b.filename)}</strong>
            <span class="muted">${esc(b.modified)} · ${esc(b.size_mb)} MB</span>
          </div>
          <div class="ai-health-backup-row-actions">
            <a class="ai-health-backup-link" href="${esc(b.download_url)}">Download</a>
            <button type="button" data-restore-backup="${esc(b.filename)}">Restore</button>
          </div>
        </div>
      `).join("");

      panel.querySelectorAll("[data-restore-backup]").forEach(button => {
        button.addEventListener("click", () => restoreBackup(button.getAttribute("data-restore-backup") || ""));
      });
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

  async function restoreBackup(filename) {
    const panel = ensurePanel();
    const status = panel.querySelector("#aiHealthBackupStatus");

    if (!filename) {
      status.textContent = "Restore failed: missing backup filename.";
      return;
    }

    if (!confirm(`Restore backup ${filename}? This will copy current data aside first.`)) {
      return;
    }

    status.textContent = "Restoring backup...";

    try {
      const res = await fetch("/api/app-health/backups/restore", {
        method: "POST",
        headers: {
          "Content-Type": "application/json"
        },
        body: JSON.stringify({ filename })
      });
      const data = await res.json();

      if (!res.ok || !data.ok) {
        status.textContent = "Restore failed: " + (data.error || "unknown error");
        return;
      }

      status.textContent = `Restored ${filename}. Current data was copied aside first.`;
      loadBackups();
    } catch (err) {
      status.textContent = "Restore failed: " + err;
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
