(function () {
  "use strict";
  if (location.pathname !== "/app-health") return;

  const esc = (value) => String(value ?? "").replaceAll("&", "&amp;").replaceAll("<", "&lt;").replaceAll(">", "&gt;").replaceAll('"', "&quot;").replaceAll("'", "&#039;");

  function panel() {
    let node = document.getElementById("ai-health-backups-v443");
    if (node) return node;
    node = document.createElement("section");
    node.id = "ai-health-backups-v443";
    node.className = "card ai-health-backups";
    node.innerHTML = `<h2>Verified Runtime Backups</h2>
      <p class="muted">V7 archives are SQLite-safe and verified before listing. Restore rehearsal is temporary and never replaces live data.</p>
      <button type="button" id="aiCreateHealthBackup">Create verified backup</button>
      <button type="button" id="aiRefreshHealthBackups">Refresh</button>
      <div id="aiHealthBackupStatus" class="muted" aria-live="polite">Loading backups...</div>
      <div id="aiHealthBackupList"></div>`;
    const h1 = document.querySelector("h1");
    (h1?.parentNode || document.body).insertBefore(node, h1?.nextSibling || null);
    node.querySelector("#aiCreateHealthBackup").addEventListener("click", createBackup);
    node.querySelector("#aiRefreshHealthBackups").addEventListener("click", loadBackups);
    return node;
  }

  function row(backup, verified) {
    const manifest = verified ? `<a class="ai-health-backup-link" href="${esc(backup.manifest_download_url)}">Manifest</a>` : "";
    const rehearse = verified ? `<button type="button" data-rehearse-backup="${esc(backup.filename)}">Run restore rehearsal</button>` : "";
    return `<div class="ai-health-backup-row"><div class="ai-health-backup-row-head"><strong>${esc(backup.filename)}</strong><span class="muted">${esc(backup.modified)} · ${esc(backup.size_mb)} MB · ${verified ? "Verified V7" : "Legacy - not verified for SQLite authority"}</span></div>
      <div class="ai-health-backup-row-actions">${backup.download_url ? `<a class="ai-health-backup-link" href="${esc(backup.download_url)}">Download</a>` : ""}${manifest}${rehearse}<button type="button" class="danger" data-delete-backup="${esc(backup.filename)}">Delete</button></div></div>`;
  }

  async function loadBackups() {
    const node = panel(), status = node.querySelector("#aiHealthBackupStatus"), list = node.querySelector("#aiHealthBackupList");
    status.textContent = "Loading backups..."; list.innerHTML = "";
    try {
      const res = await fetch("/api/app-health/backups"), data = await res.json();
      const verified = data.verified_backups || [], legacy = data.legacy_backups || [];
      status.textContent = `${verified.length} verified V7 backup(s), ${legacy.length} legacy archive(s).`;
      list.innerHTML = `${verified.length ? `<h3>Verified V7 backups</h3>${verified.slice(0, 12).map((item) => row(item, true)).join("")}` : "<p class='muted'>No verified V7 backups found.</p>"}${legacy.length ? `<h3>Legacy archives</h3><p class='muted'>Legacy archives are retained for download/delete only and are not eligible for V7 live restore.</p>${legacy.slice(0, 12).map((item) => row(item, false)).join("")}` : ""}`;
      node.querySelectorAll("[data-delete-backup]").forEach((button) => button.addEventListener("click", () => deleteBackup(button.dataset.deleteBackup)));
      node.querySelectorAll("[data-rehearse-backup]").forEach((button) => button.addEventListener("click", () => rehearseBackup(button.dataset.rehearseBackup)));
    } catch (error) { status.textContent = `Unable to load backups: ${error}`; }
  }

  async function createBackup() {
    const status = panel().querySelector("#aiHealthBackupStatus"); status.textContent = "Creating verified SQLite-safe backup...";
    try {
      const res = await fetch("/api/app-health/backups/create", { method: "POST" }), data = await res.json();
      status.textContent = data.ok ? `Verified backup created: ${data.backup.filename}` : `Backup failed: ${data.error || "unknown error"}`;
      if (data.ok) loadBackups();
    } catch (error) { status.textContent = `Backup failed: ${error}`; }
  }

  async function rehearseBackup(filename) {
    const status = panel().querySelector("#aiHealthBackupStatus"); status.textContent = "Running restore rehearsal in temporary paths...";
    try {
      const res = await fetch("/api/app-health/backups/rehearse", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ filename }) }), data = await res.json();
      status.textContent = data.ok ? "Restore rehearsal passed. Live data was not changed." : `Restore rehearsal failed: ${data.error || "validation failed"}`;
    } catch (error) { status.textContent = `Restore rehearsal failed: ${error}`; }
  }

  async function deleteBackup(filename) {
    if (!filename || !confirm(`Delete local backup ${filename}? This permanently deletes the archive${filename.startsWith("angler_intel_v7_runtime_backup_") ? " and its manifest" : ""}.`)) return;
    const status = panel().querySelector("#aiHealthBackupStatus"); status.textContent = "Deleting backup...";
    try {
      const res = await fetch("/api/app-health/backups/delete", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ filename }) }), data = await res.json();
      status.textContent = data.ok ? `Deleted ${filename}.` : `Delete failed: ${data.error || "unknown error"}`;
      if (data.ok) loadBackups();
    } catch (error) { status.textContent = `Delete failed: ${error}`; }
  }

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", () => { panel(); loadBackups(); });
  else { panel(); loadBackups(); }
})();
