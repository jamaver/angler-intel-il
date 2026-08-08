(function () {
  "use strict";
  if (location.pathname !== "/app-health") return;
  const card = document.createElement("section");
  card.className = "card ai-google-drive";
  card.innerHTML = `<h2>Google Drive Export</h2><p class="muted" aria-live="polite">Checking optional export status...</p><div class="ai-health-backup-row-actions"><button type="button" data-drive="test">Test connection</button><button type="button" data-drive="backup">Upload latest verified backup</button><button type="button" data-drive="pending">Upload pending</button></div>`;
  const anchor = document.getElementById("ai-health-backups-v443") || document.querySelector("h1");
  (anchor?.parentNode || document.body).insertBefore(card, anchor?.nextSibling || null);
  const message = card.querySelector("p");
  const show = (data) => {
    const state = data.google_drive || data.result || data;
    message.textContent = state.enabled ? `Enabled: ${state.pending || 0} pending, ${state.failed || 0} failed.` : "Disabled. Local data remains primary; configure rclone to enable exports.";
  };
  async function status() { try { show(await (await fetch("/api/app-health/google-drive/status")).json()); } catch (_) { message.textContent = "Google Drive status unavailable."; } }
  async function action(kind) {
    const urls = { test: "/api/app-health/google-drive/test", backup: "/api/app-health/google-drive/upload-latest-backup", pending: "/api/app-health/google-drive/upload-pending" };
    message.textContent = "Working...";
    try { const response = await fetch(urls[kind], { method: "POST" }); const data = await response.json(); show(data); if (!data.ok && data.error) message.textContent = data.error; } catch (_) { message.textContent = "Google Drive action unavailable."; }
  }
  card.querySelectorAll("[data-drive]").forEach((button) => button.addEventListener("click", () => action(button.dataset.drive)));
  status();
})();
