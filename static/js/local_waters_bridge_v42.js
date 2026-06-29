/*
  Angler Intel v4.2
  Dashboard Local Waters Bridge

  Adds a reliable local waters panel to the main dashboard using /api/waters.
  Leaves the existing Nearby Waters/OpenStreetMap behavior untouched.
*/

(function () {
  "use strict";

  const PANEL_ID = "ai-local-waters-panel-v42";
  const DEFAULT_ZIP = "60543";
  const DEFAULT_RADIUS = 35;
  const DEFAULT_LIMIT = 8;

  function escapeHtml(value) {
    return String(value ?? "")
      .replaceAll("&", "&amp;")
      .replaceAll("<", "&lt;")
      .replaceAll(">", "&gt;")
      .replaceAll('"', "&quot;")
      .replaceAll("'", "&#039;");
  }

  function getZipValue() {
    const candidates = [
      "#zip",
      "#zipInput",
      "#zipcode",
      "#zip-code",
      "input[name='zip']",
      "input[name='zipcode']",
      "input[placeholder*='ZIP' i]",
      "input[placeholder*='zip' i]"
    ];

    for (const selector of candidates) {
      const el = document.querySelector(selector);
      if (el && el.value && /\d{5}/.test(el.value)) {
        return el.value.match(/\d{5}/)[0];
      }
    }

    const text = document.body ? document.body.innerText : "";
    const match = text.match(/\b\d{5}\b/);
    return match ? match[0] : DEFAULT_ZIP;
  }

  function findInsertPoint() {
    const headings = Array.from(document.querySelectorAll("h1,h2,h3,h4"));
    const nearbyHeading = headings.find(h => /nearby\s+waters/i.test(h.textContent || ""));

    if (nearbyHeading) {
      const card = nearbyHeading.closest(".card, section, article, div");
      if (card && card.parentNode) {
        return { parent: card.parentNode, before: card.nextSibling };
      }
      if (nearbyHeading.parentNode) {
        return { parent: nearbyHeading.parentNode, before: nearbyHeading.nextSibling };
      }
    }

    const nav = document.querySelector(".ai-main-tabs");
    if (nav && nav.parentNode) {
      return { parent: nav.parentNode, before: nav.nextSibling };
    }

    const main = document.querySelector("main") || document.body;
    return { parent: main, before: main.firstChild };
  }

  function ensurePanel() {
    let panel = document.getElementById(PANEL_ID);
    if (panel) return panel;

    panel = document.createElement("section");
    panel.id = PANEL_ID;
    panel.className = "ai-local-waters-panel card";
    panel.innerHTML = `
      <div class="ai-local-waters-head">
        <div>
          <h2>Reliable Local Waters</h2>
          <p class="muted">v4.2 uses the local starter waters database first. OpenStreetMap can still run separately for broader ZIP searches.</p>
        </div>
        <div class="ai-local-waters-controls">
          <label>
            Radius
            <select id="aiLocalWatersRadius">
              <option value="15">15 mi</option>
              <option value="25">25 mi</option>
              <option value="35" selected>35 mi</option>
              <option value="50">50 mi</option>
              <option value="75">75 mi</option>
            </select>
          </label>
          <button type="button" id="aiLocalWatersRefresh">Refresh</button>
          <a href="/waters" class="ai-local-waters-link">Open Waters</a>
        </div>
      </div>
      <div id="aiLocalWatersStatus" class="muted">Loading local waters...</div>
      <div id="aiLocalWatersResults" class="ai-local-waters-grid"></div>
    `;

    const spot = findInsertPoint();
    spot.parent.insertBefore(panel, spot.before);

    const refresh = panel.querySelector("#aiLocalWatersRefresh");
    if (refresh) {
      refresh.addEventListener("click", () => loadLocalWaters());
    }

    const radius = panel.querySelector("#aiLocalWatersRadius");
    if (radius) {
      radius.addEventListener("change", () => loadLocalWaters());
    }

    return panel;
  }

  function renderWaters(data) {
    const panel = ensurePanel();
    const status = panel.querySelector("#aiLocalWatersStatus");
    const results = panel.querySelector("#aiLocalWatersResults");
    const waters = Array.isArray(data.waters) ? data.waters : [];

    if (!waters.length) {
      status.textContent = `No local waters found for ZIP ${data.zip || getZipValue()} within ${data.radius_miles || DEFAULT_RADIUS} miles. Try a larger radius.`;
      results.innerHTML = "";
      return;
    }

    status.textContent = `${waters.length} local waters shown near ZIP ${data.zip || getZipValue()} · ${data.database?.total_waters ?? "?"} in database`;

    results.innerHTML = waters.map(w => {
      const species = Array.isArray(w.species) ? w.species.slice(0, 5) : [];
      const habitat = Array.isArray(w.habitat) ? w.habitat.slice(0, 4) : [];
      const distance = w.distance_miles !== null && w.distance_miles !== undefined
        ? `${escapeHtml(w.distance_miles)} mi`
        : "distance unknown";

      return `
        <article class="ai-local-water-card">
          <div class="ai-local-water-title">
            <strong>${escapeHtml(w.name)}</strong>
            <span>${escapeHtml(distance)}</span>
          </div>
          <div class="ai-local-water-meta">
            ${escapeHtml(w.type || "water")} · ${escapeHtml(w.city || "")} · ${escapeHtml(w.county || "")}
          </div>
          <div class="ai-local-water-tags">
            ${species.map(s => `<span>${escapeHtml(s)}</span>`).join("")}
          </div>
          <p class="ai-local-water-habitat">${habitat.length ? "Habitat: " + habitat.map(escapeHtml).join(", ") : ""}</p>
          <p>${escapeHtml(w.notes || "")}</p>
          <a href="/water/${encodeURIComponent(w.id)}">View local intel</a>
        </article>
      `;
    }).join("");
  }

  async function loadLocalWaters() {
    const panel = ensurePanel();
    const status = panel.querySelector("#aiLocalWatersStatus");
    const results = panel.querySelector("#aiLocalWatersResults");
    const zip = getZipValue();

    const radiusEl = panel.querySelector("#aiLocalWatersRadius");
    const radius = radiusEl ? radiusEl.value : DEFAULT_RADIUS;

    status.textContent = `Loading local waters for ZIP ${zip}...`;
    results.innerHTML = "";

    const params = new URLSearchParams({
      zip,
      radius,
      limit: String(DEFAULT_LIMIT)
    });

    try {
      const response = await fetch("/api/waters?" + params.toString(), {
        headers: { "Accept": "application/json" }
      });

      if (!response.ok) {
        throw new Error("HTTP " + response.status);
      }

      const data = await response.json();
      renderWaters(data);
    } catch (err) {
      status.textContent = "Unable to load local waters: " + err;
      results.innerHTML = `<p class="muted">The old Nearby Waters/OpenStreetMap section can still be used separately.</p>`;
    }
  }

  function hookSearchEvents() {
    document.addEventListener("submit", () => {
      window.setTimeout(loadLocalWaters, 900);
    }, true);

    document.addEventListener("click", (event) => {
      const target = event.target;
      if (!target) return;

      const text = (target.textContent || "").toLowerCase();
      const looksLikeSearch =
        target.matches?.("button,input[type='button'],input[type='submit'],a") &&
        /(search|forecast|intel|refresh|go|update)/i.test(text);

      if (looksLikeSearch) {
        window.setTimeout(loadLocalWaters, 1200);
      }
    }, true);

    document.addEventListener("keydown", (event) => {
      if (event.key === "Enter" && event.target && event.target.matches?.("input")) {
        window.setTimeout(loadLocalWaters, 1200);
      }
    }, true);
  }

  function init() {
    ensurePanel();
    hookSearchEvents();
    window.setTimeout(loadLocalWaters, 700);
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
