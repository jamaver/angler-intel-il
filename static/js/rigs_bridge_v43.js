/*
  Angler Intel IL v4.3 dashboard rig bridge
*/
(function () {
  "use strict";

  const PANEL_ID = "ai-rig-panel-v43";

  function escapeHtml(value) {
    return String(value ?? "")
      .replaceAll("&", "&amp;")
      .replaceAll("<", "&lt;")
      .replaceAll(">", "&gt;")
      .replaceAll('"', "&quot;")
      .replaceAll("'", "&#039;");
  }

  function ensurePanel() {
    let panel = document.getElementById(PANEL_ID);
    if (panel) return panel;

    panel = document.createElement("section");
    panel.id = PANEL_ID;
    panel.className = "ai-rig-panel card";
    panel.innerHTML = `
      <div class="ai-rig-head">
        <div>
          <h2>Rig Setup Guide</h2>
          <p class="muted">v4.3 quick rigging help for trout, pike, bass, walleye, panfish, and catfish.</p>
        </div>
        <a href="/rigs" class="ai-rig-link">Open Full Rig Guide</a>
      </div>

      <div class="ai-rig-controls">
        <label>
          Target
          <select id="aiRigSpecies">
            <option value="bass">Bass</option>
            <option value="trout">Trout</option>
            <option value="pike">Pike/Muskie</option>
            <option value="walleye">Walleye/Sauger</option>
            <option value="crappie">Crappie/Panfish</option>
            <option value="catfish">Catfish</option>
          </select>
        </label>
        <button type="button" id="aiRigRefresh">Show Rig</button>
      </div>

      <div id="aiRigStatus" class="muted">Choose a target species.</div>
      <div id="aiRigResults" class="ai-rig-grid"></div>
    `;

    const localWaters = document.getElementById("ai-local-waters-panel-v42");
    if (localWaters && localWaters.parentNode) {
      localWaters.parentNode.insertBefore(panel, localWaters.nextSibling);
    } else {
      const nav = document.querySelector(".ai-main-tabs");
      if (nav && nav.parentNode) {
        nav.parentNode.insertBefore(panel, nav.nextSibling);
      } else {
        document.body.insertBefore(panel, document.body.firstChild);
      }
    }

    panel.querySelector("#aiRigRefresh").addEventListener("click", loadRig);
    panel.querySelector("#aiRigSpecies").addEventListener("change", loadRig);

    return panel;
  }

  async function loadRig() {
    const panel = ensurePanel();
    const species = panel.querySelector("#aiRigSpecies").value;
    const status = panel.querySelector("#aiRigStatus");
    const results = panel.querySelector("#aiRigResults");

    status.textContent = "Loading rig setups...";
    results.innerHTML = "";

    try {
      const res = await fetch("/api/rigs?species=" + encodeURIComponent(species));
      if (!res.ok) throw new Error("HTTP " + res.status);

      const data = await res.json();
      const rigs = Array.isArray(data.rigs) ? data.rigs.slice(0, 3) : [];

      if (!rigs.length) {
        status.textContent = "No rig setups matched.";
        return;
      }

      status.textContent = `${rigs.length} rig setup option(s) for ${species}`;

      results.innerHTML = rigs.map(r => `
        <article class="ai-rig-card">
          <h3>${escapeHtml(r.name)}</h3>
          <p><strong>Rod:</strong> ${escapeHtml(r.rod)}</p>
          <p><strong>Line:</strong> ${escapeHtml(r.line)}</p>
          <p><strong>Terminal:</strong> ${escapeHtml(r.terminal)}</p>
          <p><strong>Setup:</strong> ${escapeHtml(r.setup)}</p>
          <a href="/rigs?species=${encodeURIComponent(species)}">More rig details</a>
        </article>
      `).join("");
    } catch (err) {
      status.textContent = "Unable to load rig setups: " + err;
    }
  }

  function init() {
    ensurePanel();
    window.setTimeout(loadRig, 900);
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
