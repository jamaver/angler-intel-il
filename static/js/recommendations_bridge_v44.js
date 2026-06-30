/*
  Angler Intel IL v4.4 Dashboard Smart Recommendations Bridge
*/
(function () {
  "use strict";

  if (location.pathname !== "/") return;

  const PANEL_ID = "ai-recommendations-panel-v44";

  function esc(value) {
    return String(value ?? "")
      .replaceAll("&", "&amp;")
      .replaceAll("<", "&lt;")
      .replaceAll(">", "&gt;")
      .replaceAll('"', "&quot;")
      .replaceAll("'", "&#039;");
  }

  function getZipValue() {
    const selectors = [
      "#zip",
      "#zipInput",
      "#zipcode",
      "#zip-code",
      "input[name='zip']",
      "input[name='zipcode']",
      "input[placeholder*='ZIP' i]",
      "input[placeholder*='zip' i]"
    ];

    for (const selector of selectors) {
      const el = document.querySelector(selector);
      if (el && el.value && /\d{5}/.test(el.value)) {
        return el.value.match(/\d{5}/)[0];
      }
    }

    return "60543";
  }

  function ensurePanel() {
    let panel = document.getElementById(PANEL_ID);
    if (panel) return panel;

    panel = document.createElement("section");
    panel.id = PANEL_ID;
    panel.className = "ai-smart-panel card";
    panel.innerHTML = `
      <div class="ai-smart-head">
        <div>
          <h2>Smart Recommendations</h2>
          <p class="muted">Combines local waters, active species, rig setups, season, and distance.</p>
        </div>
        <a class="ai-smart-link" href="/recommendations">Open Smart Picks</a>
      </div>

      <div class="ai-smart-controls">
        <label>
          Target
          <select id="aiSmartSpecies">
            <option value="">Active species mix</option>
          </select>
        </label>

        <label>
          Radius
          <select id="aiSmartRadius">
            <option value="15">15 mi</option>
            <option value="25">25 mi</option>
            <option value="35" selected>35 mi</option>
            <option value="50">50 mi</option>
            <option value="75">75 mi</option>
          </select>
        </label>

        <button type="button" id="aiSmartRefresh">Refresh Picks</button>
      </div>

      <div id="aiSmartStatus" class="muted">Loading smart recommendations...</div>
      <div id="aiSmartResults" class="ai-smart-grid"></div>
    `;

    const rigPanel = document.getElementById("ai-rig-panel-v43");
    const localPanel = document.getElementById("ai-local-waters-panel-v42");
    const sectionControls = document.getElementById("ai-dashboard-section-controls-v431");

    if (rigPanel && rigPanel.parentNode) {
      rigPanel.parentNode.insertBefore(panel, rigPanel.nextSibling);
    } else if (localPanel && localPanel.parentNode) {
      localPanel.parentNode.insertBefore(panel, localPanel.nextSibling);
    } else if (sectionControls && sectionControls.parentNode) {
      sectionControls.parentNode.insertBefore(panel, sectionControls.nextSibling);
    } else {
      document.body.insertBefore(panel, document.body.firstChild);
    }

    panel.querySelector("#aiSmartRefresh").addEventListener("click", loadRecommendations);
    panel.querySelector("#aiSmartSpecies").addEventListener("change", loadRecommendations);
    panel.querySelector("#aiSmartRadius").addEventListener("change", loadRecommendations);

    return panel;
  }

  async function loadSpecies() {
    const panel = ensurePanel();
    const select = panel.querySelector("#aiSmartSpecies");

    try {
      const res = await fetch("/api/species/active");
      const data = await res.json();

      const current = select.value;
      select.innerHTML = `<option value="">Active species mix</option>` + (data.species || []).map(s =>
        `<option value="${esc(s.id)}">${esc(s.name)}</option>`
      ).join("");
      select.value = current;
    } catch (err) {
      console.log("Unable to load species for smart recommendations", err);
    }
  }

  async function loadRecommendations() {
    const panel = ensurePanel();
    const status = panel.querySelector("#aiSmartStatus");
    const results = panel.querySelector("#aiSmartResults");
    const species = panel.querySelector("#aiSmartSpecies").value;
    const radius = panel.querySelector("#aiSmartRadius").value;
    const zip = getZipValue();

    status.textContent = `Loading smart picks for ZIP ${zip}...`;
    results.innerHTML = "";

    const params = new URLSearchParams({
      zip,
      radius,
      limit: "3"
    });

    if (species) params.set("species", species);

    try {
      const res = await fetch("/api/recommendations?" + params.toString());
      if (!res.ok) throw new Error("HTTP " + res.status);

      const data = await res.json();
      const water = data.best_bet && data.best_bet.water;
      const rig = data.best_bet && data.best_bet.rig;

      status.textContent = `${data.summary} Season: ${data.season}.`;

      results.innerHTML = `
        <article class="ai-smart-card">
          <h3>Best Water</h3>
          ${
            water
              ? `<p><strong>${esc(water.name)}</strong></p>
                 <p class="muted">${water.distance_miles !== null && water.distance_miles !== undefined ? esc(water.distance_miles) + " mi" : "distance unknown"} · Score ${esc(water.recommendation_score)}</p>
                 <p>${esc((water.recommendation_reasons || []).join("; "))}</p>
                 <a href="/water/${encodeURIComponent(water.id)}">View water intel</a>`
              : `<p>No water match yet. Try a larger radius.</p>`
          }
        </article>

        <article class="ai-smart-card">
          <h3>Best Rig</h3>
          ${
            rig
              ? `<p><strong>${esc(rig.name)}</strong></p>
                 <p class="muted">Score ${esc(rig.recommendation_score)}</p>
                 <p><strong>Line:</strong> ${esc(rig.line || "")}</p>
                 <p>${esc((rig.recommendation_reasons || []).join("; "))}</p>
                 <a href="/rigs?species=${encodeURIComponent(species || "")}">View rig guide</a>`
              : `<p>No rig match yet.</p>`
          }
        </article>
      `;
    } catch (err) {
      status.textContent = "Unable to load smart recommendations: " + err;
    }
  }

  function hookRefreshes() {
    document.addEventListener("submit", () => {
      window.setTimeout(loadRecommendations, 1200);
    }, true);

    document.addEventListener("click", event => {
      const target = event.target;
      if (!target || !target.matches?.("button,input[type='button'],input[type='submit'],a")) return;

      const text = (target.textContent || target.value || "").toLowerCase();
      if (/search|forecast|intel|refresh|go|update/.test(text)) {
        window.setTimeout(loadRecommendations, 1400);
      }
    }, true);
  }

  async function init() {
    ensurePanel();
    await loadSpecies();
    await loadRecommendations();
    hookRefreshes();
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
