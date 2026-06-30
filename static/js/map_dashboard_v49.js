(function () {
  "use strict";

  const state = {
    waters: [],
    filtered: [],
    bounds: null,
    selectedId: null
  };

  function esc(value) {
    return String(value ?? "").replace(/[&<>"']/g, ch => ({
      "&": "&amp;",
      "<": "&lt;",
      ">": "&gt;",
      "\"": "&quot;",
      "'": "&#039;"
    }[ch]));
  }

  function byId(id) {
    return document.getElementById(id);
  }

  function uniq(values) {
    return Array.from(new Set(values.filter(Boolean))).sort();
  }

  function project(water) {
    const b = state.bounds || {};
    const lonSpan = Math.max(0.0001, (b.max_lon || 0) - (b.min_lon || 0));
    const latSpan = Math.max(0.0001, (b.max_lat || 0) - (b.min_lat || 0));
    const x = ((water.lon - b.min_lon) / lonSpan) * 100;
    const y = (1 - ((water.lat - b.min_lat) / latSpan)) * 100;
    return {
      left: Math.max(3, Math.min(97, x)),
      top: Math.max(3, Math.min(97, y))
    };
  }

  function renderFilters() {
    const speciesSelect = byId("mapSpeciesFilter");
    const typeSelect = byId("mapTypeFilter");
    if (!speciesSelect || !typeSelect) return;

    const species = uniq(state.waters.flatMap(w => w.species || []));
    const types = uniq(state.waters.map(w => w.type));

    speciesSelect.innerHTML = `<option value="">All species</option>` + species.map(item =>
      `<option value="${esc(item)}">${esc(item)}</option>`
    ).join("");
    typeSelect.innerHTML = `<option value="">All types</option>` + types.map(item =>
      `<option value="${esc(item)}">${esc(item)}</option>`
    ).join("");
  }

  function applyFilters() {
    const species = (byId("mapSpeciesFilter")?.value || "").toLowerCase();
    const type = (byId("mapTypeFilter")?.value || "").toLowerCase();

    state.filtered = state.waters.filter(w => {
      const speciesOk = !species || (w.species || []).some(s => String(s).toLowerCase() === species);
      const typeOk = !type || String(w.type || "").toLowerCase() === type;
      return speciesOk && typeOk;
    });

    renderMap();
  }

  function markerClass(water) {
    const t = String(water.type || "").toLowerCase();
    if (t.includes("river") || t.includes("creek")) return "map-marker moving";
    if (t.includes("pond")) return "map-marker pond";
    if (t.includes("reservoir")) return "map-marker reservoir";
    return "map-marker lake";
  }

  function renderMap() {
    const canvas = byId("mapCanvas");
    const status = byId("mapStatus");
    if (!canvas || !status) return;

    status.textContent = `${state.filtered.length} of ${state.waters.length} waters shown`;

    canvas.innerHTML = `
      <div class="map-grid-line vertical one"></div>
      <div class="map-grid-line vertical two"></div>
      <div class="map-grid-line horizontal one"></div>
      <div class="map-grid-line horizontal two"></div>
      ${state.filtered.map(w => {
        const p = project(w);
        const selected = w.id === state.selectedId ? " selected" : "";
        return `<button class="${markerClass(w)}${selected}" style="left:${p.left}%;top:${p.top}%"
          data-water-id="${esc(w.id)}" type="button" title="${esc(w.name)}">
          <span>${esc((w.name || "?").slice(0, 1))}</span>
        </button>`;
      }).join("")}
    `;

    canvas.querySelectorAll(".map-marker").forEach(button => {
      button.addEventListener("click", () => {
        state.selectedId = button.getAttribute("data-water-id");
        renderMap();
        renderDetails();
      });
    });
  }

  function renderDetails() {
    const details = byId("mapDetails");
    if (!details) return;

    const water = state.waters.find(w => w.id === state.selectedId) || state.filtered[0];
    if (!water) {
      details.innerHTML = "No water selected.";
      return;
    }

    state.selectedId = water.id;
    details.innerHTML = `
      <h3>${esc(water.name)}</h3>
      <p><strong>${esc(water.type || "water")}</strong> · ${esc(water.city || "")} · ${esc(water.county || "")}</p>
      <p><strong>Species</strong><br>${(water.species || []).map(s => `<span class="map-chip">${esc(s)}</span>`).join("") || "No species listed."}</p>
      <p><strong>Habitat</strong><br>${(water.habitat || []).map(s => `<span class="map-chip habitat">${esc(s)}</span>`).join("") || "No habitat listed."}</p>
      <p class="small">Confidence: ${esc(water.confidence || "unknown")}</p>
      <p><a href="/water/${encodeURIComponent(water.id)}">Open water intel</a></p>
    `;
  }

  async function loadMap() {
    const status = byId("mapStatus");
    try {
      const res = await fetch("/api/map-data", {
        headers: { "Accept": "application/json" }
      });
      const contentType = res.headers.get("content-type") || "";
      const text = await res.text();

      if (!contentType.includes("application/json")) {
        const snippet = text.trim().slice(0, 80) || "empty response";
        throw new Error(`Expected JSON from /api/map-data but received HTML or another format: ${snippet}`);
      }

      const data = JSON.parse(text);
      if (!res.ok) {
        throw new Error(data.error || `HTTP ${res.status}`);
      }

      state.waters = Array.isArray(data.waters) ? data.waters : [];
      state.filtered = state.waters.slice();
      state.bounds = data.bounds;
      state.selectedId = state.waters[0]?.id || null;
      renderFilters();
      renderMap();
      renderDetails();
    } catch (err) {
      if (status) status.textContent = "Unable to load map data: " + err;
    }
  }

  document.addEventListener("DOMContentLoaded", () => {
    byId("mapSpeciesFilter")?.addEventListener("change", applyFilters);
    byId("mapTypeFilter")?.addEventListener("change", applyFilters);
    byId("mapResetButton")?.addEventListener("click", () => {
      const species = byId("mapSpeciesFilter");
      const type = byId("mapTypeFilter");
      if (species) species.value = "";
      if (type) type.value = "";
      applyFilters();
    });
    loadMap();
  });
})();
