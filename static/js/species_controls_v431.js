/*
  Angler Intel IL v4.3.1 Species Controls
  Adds active/common/optional species controls to the /species page.
*/
(function () {
  "use strict";

  if (!location.pathname.startsWith("/species")) return;

  function esc(value) {
    return String(value ?? "")
      .replaceAll("&", "&amp;")
      .replaceAll("<", "&lt;")
      .replaceAll(">", "&gt;")
      .replaceAll('"', "&quot;")
      .replaceAll("'", "&#039;");
  }

  function slug(value) {
    return String(value ?? "")
      .toLowerCase()
      .replace(/[^a-z0-9]+/g, "-")
      .replace(/^-|-$/g, "");
  }

  async function api(url, options = {}) {
    const res = await fetch(url, options);
    const text = await res.text();
    try {
      return JSON.parse(text);
    } catch {
      return { ok: res.ok, text };
    }
  }

  function ensurePanel() {
    let panel = document.getElementById("ai-species-controls-v431");
    if (panel) return panel;

    panel = document.createElement("section");
    panel.id = "ai-species-controls-v431";
    panel.className = "card ai-species-controls";
    panel.innerHTML = `
      <h2>Common Freshwater Fish</h2>
      <p class="muted">Common species are active by default. Add optional species only when you want them included in the local database workflow.</p>

      <div class="ai-species-control-row">
        <label>
          Add optional species
          <select id="aiOptionalSpeciesSelect"></select>
        </label>
        <button type="button" id="aiEnableSpeciesBtn">Add Species</button>
        <button type="button" id="aiResetSpeciesBtn">Reset Defaults</button>
        <a href="/data-tools">Open Data Tools</a>
      </div>

      <h3>Active Species</h3>
      <div id="aiActiveSpeciesList">Loading...</div>
    `;

    const h1 = Array.from(document.querySelectorAll("h1")).find(x => /species/i.test(x.textContent || ""));
    if (h1 && h1.parentNode) {
      h1.parentNode.insertBefore(panel, h1.nextSibling);
    } else {
      document.body.insertBefore(panel, document.body.firstChild);
    }

    panel.querySelector("#aiEnableSpeciesBtn").addEventListener("click", enableSelected);
    panel.querySelector("#aiResetSpeciesBtn").addEventListener("click", resetDefaults);

    return panel;
  }

  function getSpeciesCards() {
    return Array.from(document.querySelectorAll("#speciesCards article, article.card"))
      .filter(card => {
        const h = card.querySelector("h2");
        return h && card.closest("#ai-species-controls-v431") === null;
      });
  }

  async function refreshSpeciesControls() {
    const panel = ensurePanel();
    const activeData = await api("/api/species/active");
    const optionalData = await api("/api/species/optional");

    const activeIds = new Set(activeData.active_species || []);
    const byName = new Map();

    for (const s of activeData.species || []) byName.set(slug(s.name), s.id);
    for (const s of optionalData.species || []) byName.set(slug(s.name), s.id);

    const activeBox = panel.querySelector("#aiActiveSpeciesList");
    const select = panel.querySelector("#aiOptionalSpeciesSelect");

    activeBox.innerHTML = (activeData.species || []).map(s => `
      <span class="ai-species-pill">
        ${esc(s.name)}
        <button type="button" data-disable="${esc(s.id)}">×</button>
      </span>
    `).join("") || "<p>No active species.</p>";

    activeBox.querySelectorAll("[data-disable]").forEach(btn => {
      btn.addEventListener("click", () => disableSpecies(btn.getAttribute("data-disable")));
    });

    select.innerHTML = (optionalData.species || []).map(s => `
      <option value="${esc(s.id)}">${esc(s.name)}</option>
    `).join("");

    if (!select.innerHTML) {
      select.innerHTML = `<option value="">No optional species available</option>`;
    }

    // Hide inactive cards on /species so the default view stays clean.
    getSpeciesCards().forEach(card => {
      const title = card.querySelector("h2")?.textContent || "";
      const id = byName.get(slug(title)) || slug(title);
      card.style.display = activeIds.has(id) ? "" : "none";
    });
  }

  async function enableSelected() {
    const panel = ensurePanel();
    const select = panel.querySelector("#aiOptionalSpeciesSelect");
    const id = select.value;
    if (!id) return;

    await api("/api/species/enable", {
      method: "POST",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify({ id })
    });

    refreshSpeciesControls();
  }

  async function disableSpecies(id) {
    await api("/api/species/disable", {
      method: "POST",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify({ id })
    });

    refreshSpeciesControls();
  }

  async function resetDefaults() {
    if (!confirm("Reset active species to common freshwater defaults?")) return;

    await api("/api/species/reset", { method: "POST" });
    refreshSpeciesControls();
  }

  function init() {
    ensurePanel();
    refreshSpeciesControls();
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
