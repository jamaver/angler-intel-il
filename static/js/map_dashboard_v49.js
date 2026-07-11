(function () {
  "use strict";

  const BASEMAPS = {
    hybrid: {
      label: "Hybrid satellite",
      layers: [
        {
          url: "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
          options: {
            attribution: "Tiles &copy; Esri, Maxar, Earthstar Geographics, and the GIS User Community",
            maxZoom: 19
          }
        },
        {
          url: "https://server.arcgisonline.com/ArcGIS/rest/services/Reference/World_Boundaries_and_Places/MapServer/tile/{z}/{y}/{x}",
          options: {
            attribution: "Labels &copy; Esri",
            maxZoom: 19,
            opacity: 0.85
          }
        },
        {
          url: "https://server.arcgisonline.com/ArcGIS/rest/services/Reference/World_Transportation/MapServer/tile/{z}/{y}/{x}",
          options: {
            attribution: "Transportation &copy; Esri",
            maxZoom: 19,
            opacity: 0.85
          }
        }
      ]
    },
    satellite: {
      label: "Satellite",
      layers: [
        {
          url: "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
          options: {
            attribution: "Tiles &copy; Esri, Maxar, Earthstar Geographics, and the GIS User Community",
            maxZoom: 19
          }
        }
      ]
    },
    street: {
      label: "Street",
      layers: [
        {
          url: "https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png",
          options: {
            attribution: "&copy; OpenStreetMap contributors",
            maxZoom: 19
          }
        }
      ]
    },
    terrain: {
      label: "Terrain",
      layers: [
        {
          url: "https://{s}.tile.opentopomap.org/{z}/{x}/{y}.png",
          options: {
            attribution: "Map data: &copy; OpenStreetMap contributors, SRTM | Map style: &copy; OpenTopoMap",
            maxZoom: 17,
            subdomains: "abc"
          }
        }
      ]
    }
  };

  const TYPE_COLORS = {
    lake: "#2563eb",
    pond: "#16a34a",
    river: "#06b6d4",
    reservoir: "#f59e0b",
    "great-lake": "#0f766e",
    "lake-complex": "#7c3aed",
    creek: "#0ea5e9",
    other: "#8b5cf6",
    manual: "#ef4444"
  };

  const state = {
    map: null,
    currentBaseLayer: null,
    activeBasemap: "hybrid",
    markerLayer: null,
    waters: [],
    filtered: [],
    ranked: [],
    selectedId: null,
    targetProfile: null,
    filters: {
      favorite: false,
      manual: false,
      stocked: false,
      history: false,
      confidence: false
    },
    catalog: {
      base_count: 0,
      custom_count: 0,
      total_count: 0,
      warnings: []
    },
    waterIntel: null,
    initialFitDone: false
  };

  function byId(id) {
    return document.getElementById(id);
  }

  function esc(value) {
    return String(value ?? "").replace(/[&<>"']/g, ch => ({
      "&": "&amp;",
      "<": "&lt;",
      ">": "&gt;",
      "\"": "&quot;",
      "'": "&#039;"
    }[ch]));
  }

  function textBlock(value) {
    return esc(value).replace(/\n/g, "<br>");
  }

  function uniq(values) {
    return Array.from(new Set(values.filter(Boolean))).sort((a, b) => String(a).localeCompare(String(b)));
  }

  function speciesKey(value) {
    return String(value || "")
      .toLowerCase()
      .replace(/[^a-z0-9]+/g, "-")
      .replace(/^-+|-+$/g, "");
  }

  function splitList(value) {
    if (Array.isArray(value)) {
      return value.map(item => String(item).trim()).filter(Boolean);
    }
    if (!value) return [];
    return String(value)
      .split(/[,\n;/|]+/)
      .map(item => item.trim())
      .filter(Boolean);
  }

  function iconSlug(value) {
    return String(value || "")
      .toLowerCase()
      .replace(/&/g, " and ")
      .replace(/[^a-z0-9]+/g, "-")
      .replace(/^-+|-+$/g, "");
  }

  function waterIconPath(kind) {
    const slug = iconSlug(kind);
    if (!slug) return "/static/icons/map/missing_coordinates.svg";
    if (slug.includes("river") || slug.includes("creek") || slug.includes("stream")) return "/static/icons/map/river.svg";
    if (slug.includes("spillway") || slug.includes("tailwater") || slug.includes("tail-water")) return "/static/icons/map/spillway.svg";
    if (slug.includes("trout") || slug.includes("stocked")) return "/static/icons/map/high_confidence.svg";
    if (slug.includes("reservoir")) return "/static/icons/map/reservoir.svg";
    if (slug.includes("pond")) return "/static/icons/map/pond.svg";
    if (slug.includes("lake")) return "/static/icons/map/lake.svg";
    if (slug.includes("manual")) return "/static/icons/map/manual_water.svg";
    if (slug.includes("favorite")) return "/static/icons/map/favorite_water.svg";
    if (slug.includes("history")) return "/static/icons/map/catch_history.svg";
    if (slug.includes("target") || slug.includes("confidence")) return "/static/icons/map/high_confidence.svg";
    return "/static/icons/map/other.svg";
  }

  function currentTargetSpecies() {
    const selected = byId("mapTargetSpecies")?.value || "";
    if (selected) return selected;
    return state.targetProfile?.current_trip_target || state.targetProfile?.default_target_species || "";
  }

  function renderTargetSummary() {
    const label = byId("mapRankStatus");
    if (!label) return;
    const target = currentTargetSpecies();
    if (!target) {
      label.textContent = "Ranked for all waters until a target fish is selected.";
      return;
    }

    label.textContent = `Ranked for ${target}.`;
  }

  function toFloat(value) {
    const n = Number(value);
    return Number.isFinite(n) ? n : null;
  }

  function typeKey(rawType) {
    const type = String(rawType || "").toLowerCase();
    if (type.includes("river") || type.includes("creek") || type.includes("stream")) return "river";
    if (type.includes("reservoir")) return "reservoir";
    if (type.includes("pond")) return "pond";
    if (type.includes("lake complex")) return "lake-complex";
    if (type.includes("great lake")) return "great-lake";
    if (type.includes("lake")) return "lake";
    return "other";
  }

  function pinColor(water) {
    const key = water.manual || String(water.source || "").toLowerCase() === "manual"
      ? "manual"
      : typeKey(water.type);
    return TYPE_COLORS[key] || TYPE_COLORS.other;
  }

  function confidenceTier(water) {
    const confidence = String(water.confidence || "").toLowerCase();
    const catchHistory = Number(water.catch_history_count || 0) || 0;

    if (confidence.includes("high") || confidence.includes("strong") || confidence.includes("verified")) {
      return "high";
    }
    if (catchHistory >= 5 || confidence.includes("moderate") || confidence.includes("good")) {
      return "moderate";
    }
    return "low";
  }

  function targetFitScore(water, targetSpecies) {
    if (water && water.target_fit && Number.isFinite(Number(water.target_fit.score))) {
      return Math.max(0, Math.min(100, Number(water.target_fit.score)));
    }

    const target = String(targetSpecies || "").toLowerCase().trim();
    if (!target) return 0;

    const waterSpecies = splitList(water.species).map(item => item.toLowerCase());
    const waterType = String(water.type || "").toLowerCase();
    const isStockedTrout = !!water.stocked_trout;
    const catchHistory = Number(water.catch_history_count || 0) || 0;
    let score = 18;

    if (waterSpecies.includes(target)) {
      score += 50;
    } else if (target.includes("trout") && isStockedTrout) {
      score += 42;
    } else if (target.includes("bass") && ["lake", "pond", "reservoir"].some(item => waterType.includes(item))) {
      score += 24;
    } else if ((target.includes("walleye") || target.includes("sauger")) && ["river", "lake", "reservoir"].some(item => waterType.includes(item))) {
      score += 22;
    } else if ((target.includes("catfish") || target.includes("carp")) && ["river", "lake", "pond"].some(item => waterType.includes(item))) {
      score += 18;
    } else if ((target.includes("crappie") || target.includes("bluegill") || target.includes("perch")) && ["lake", "pond", "reservoir"].some(item => waterType.includes(item))) {
      score += 18;
    } else {
      score += 10;
    }

    if (catchHistory >= 5) score += 10;
    else if (catchHistory > 0) score += 5;

    if (water.favorite) score += 4;
    if (water.manual || String(water.source || "").toLowerCase() === "manual") score += 2;

    return Math.max(0, Math.min(100, score));
  }

  function targetFitLabel(score) {
    if (score >= 80) return "Excellent";
    if (score >= 60) return "Good";
    if (score >= 40) return "Fair";
    return "Low";
  }

  function pinGlyphPath(key) {
    if (key === "river") {
      return "M11 27c2.4-3.2 4.8-4.6 7.2-4.2 2 .3 3.8 1.5 5.4 3.5 1.8 2.2 3.8 3.4 6.1 3.4 2.4 0 4.4-1 6.1-3";
    }
    if (key === "reservoir") {
      return "M11 27c2.8-2.1 5.4-3.1 7.8-3.1 2.6 0 5.2 1 7.7 3s5.1 3 7.8 3";
    }
    return "M11 27c2.5-2.3 5-3.4 7.6-3.4 2.5 0 4.9 1 7.4 3s5 3 7.6 3";
  }

  function fishStarPath() {
    return "M22 12l2.6 5.4 6 .9-4.3 4.2 1 6-5.3-2.8-5.3 2.8 1-6-4.3-4.2 6-.9z";
  }

  function markerHtml(water) {
    const isManual = water.manual || String(water.source || "").toLowerCase() === "manual";
    const key = isManual ? "manual" : typeKey(water.type);
    const badges = [];

    if (isManual) {
      badges.push(`<span class="pin-badge manual" title="Manual waterbody">+</span>`);
    }
    if (water.favorite) {
      badges.push(`<span class="pin-badge favorite" title="Favorite">★</span>`);
    }
    if (water.stocked_trout) {
      badges.push(`<span class="pin-badge trout" title="Stocked trout">T</span>`);
    }
    if ((water.catch_history_count || 0) > 0) {
      badges.push(`<span class="pin-badge history" title="Catch history">${Math.min(9, Number(water.catch_history_count) || 0)}</span>`);
    }

    return `
      <div class="water-pin ${esc(key)}${water.id === state.selectedId ? " selected" : ""}" style="--pin-color:${pinColor(water)}">
        <svg viewBox="0 0 44 60" aria-hidden="true" focusable="false">
          <path class="pin-shell" d="M22 58C22 58 8 40 8 25C8 15.1 14.8 8 22 8C29.2 8 36 15.1 36 25C36 40 22 58 22 58Z"></path>
          <circle class="pin-window" cx="22" cy="24" r="10"></circle>
          <path class="pin-wave" d="${pinGlyphPath(key)}"></path>
          ${water.favorite ? `<path class="pin-star" d="${fishStarPath()}"></path>` : ""}
        </svg>
        <div class="pin-badges">${badges.join("")}</div>
      </div>
    `;
  }

  function markerIcon(water) {
    return L.divIcon({
      className: "",
      html: markerHtml(water),
      iconSize: [44, 60],
      iconAnchor: [22, 58],
      popupAnchor: [0, -48]
    });
  }

  function popupHtml(water) {
    const species = splitList(water.species);
    const chips = species.length
      ? species.map(item => `<span class="map-chip">${esc(item)}</span>`).join("")
      : `<span class="small">No species listed.</span>`;

    return `
      <strong>${esc(water.name || "Waterbody")}</strong><br>
      <span class="small">${esc(water.type || "water")}${water.city ? " · " + esc(water.city) : ""}${water.county ? " · " + esc(water.county) : ""}</span><br>
      <div style="margin-top:0.4rem">${chips}</div>
      <div style="margin-top:0.4rem"><a href="/water/${encodeURIComponent(water.id)}">Open water detail</a></div>
    `;
  }

  function setStatus(message) {
    const status = byId("mapStatus");
    if (status) {
      status.textContent = message;
    }
  }

  function setAddStatus(message, kind = "info") {
    const status = byId("mapAddStatus");
    if (!status) return;
    status.textContent = message;
    status.className = kind === "error" ? "small error-text" : "small";
  }

  function updateHeaderCounts() {
    const waterCount = byId("mapWaterCount");
    const customCount = byId("mapCustomCount");
    if (waterCount) waterCount.textContent = String(state.catalog.total_count || state.waters.length || 0);
    if (customCount) customCount.textContent = String(state.catalog.custom_count || 0);
  }

  function updateLayerLabel() {
    const label = byId("mapLayerLabel");
    if (label) {
      label.textContent = BASEMAPS[state.activeBasemap]?.label || "Basemap";
    }
  }

  function syncTargetSelector() {
    const targetSelect = byId("mapTargetSpecies");
    if (!targetSelect) return;
    targetSelect.value = currentTargetSpecies();
  }

  async function loadTargetProfile() {
    try {
      const data = await fetchJson("/api/target-profile");
      state.targetProfile = data.profile || null;
      syncTargetSelector();
      renderTargetSummary();
    } catch (error) {
      state.targetProfile = null;
      renderTargetSummary();
    }
  }

  async function saveTargetProfile(payload) {
    const data = await fetchJson("/api/target-profile", {
      method: "POST",
      headers: {
        "Content-Type": "application/json"
      },
      body: JSON.stringify(payload)
    });
    state.targetProfile = data.profile || null;
    syncTargetSelector();
    renderTargetSummary();
    return data;
  }

  function ensureMap() {
    if (state.map) return state.map;
    if (typeof L === "undefined") {
      setStatus("Leaflet is unavailable. Check the basemap script load.");
      return null;
    }

    const canvas = byId("mapCanvas");
    if (!canvas) return null;

    state.map = L.map(canvas, {
      zoomControl: true,
      preferCanvas: true
    });

    state.markerLayer = L.featureGroup().addTo(state.map);
    switchBaseMap(state.activeBasemap);

    state.map.setView([41.8, -88.1], 8);
    state.map.on("movestart", () => {
      if (state.initialFitDone) return;
    });

    return state.map;
  }

  function buildTileLayer(config) {
    const layer = L.tileLayer(config.url, config.options);
    return layer;
  }

  function switchBaseMap(name) {
    const map = ensureMap();
    if (!map) return;

    if (!BASEMAPS[name]) {
      name = "hybrid";
    }

    if (state.currentBaseLayer) {
      map.removeLayer(state.currentBaseLayer);
      state.currentBaseLayer = null;
    }

    const base = BASEMAPS[name];
    const layers = base.layers.map(buildTileLayer);
    const group = layers.length === 1 ? layers[0] : L.layerGroup(layers);
    group.addTo(map);
    state.currentBaseLayer = group;
    state.activeBasemap = name;
    updateLayerLabel();
  }

  function renderFilters() {
    const speciesSelect = byId("mapSpeciesFilter");
    const typeSelect = byId("mapTypeFilter");
    const targetSelect = byId("mapTargetSpecies");
    const speciesList = byId("mapSpeciesOptions");
    if (!speciesSelect || !typeSelect) return;

    const species = uniq(state.waters.flatMap(w => splitList(w.species)));
    const types = uniq(state.waters.map(w => w.type));

    speciesSelect.innerHTML = `<option value="">All species</option>` + species.map(item =>
      `<option value="${esc(item)}">${esc(item)}</option>`
    ).join("");
    typeSelect.innerHTML = `<option value="">All types</option>` + types.map(item =>
      `<option value="${esc(item)}">${esc(item)}</option>`
    ).join("");

    if (targetSelect) {
      const commonSpecies = [
        "largemouth bass",
        "smallmouth bass",
        "crappie",
        "bluegill",
        "channel catfish",
        "flathead catfish",
        "walleye",
        "sauger",
        "rainbow trout",
        "brown trout",
        "northern pike",
        "muskie"
      ];
      const targets = uniq([...species, ...commonSpecies]);
      targetSelect.innerHTML = `<option value="">Auto from water</option>` + targets.map(item =>
        `<option value="${esc(item)}">${esc(item)}</option>`
      ).join("");
    }

    if (speciesList) {
      speciesList.innerHTML = species.map(item => `<option value="${esc(item)}"></option>`).join("");
    }
  }

  function readFilterFlags() {
    state.filters = {
      favorite: !!byId("mapFilterFavorite")?.checked,
      manual: !!byId("mapFilterManual")?.checked,
      stocked: !!byId("mapFilterStocked")?.checked,
      history: !!byId("mapFilterHistory")?.checked,
      confidence: !!byId("mapFilterConfidence")?.checked
    };
  }

  function applyFilters() {
    const species = (byId("mapSpeciesFilter")?.value || "").toLowerCase();
    const type = (byId("mapTypeFilter")?.value || "").toLowerCase();
    const targetSpecies = currentTargetSpecies();
    readFilterFlags();

    state.filtered = state.waters.filter(water => {
      const speciesOk = !species || splitList(water.species).some(item => item.toLowerCase() === species);
      const typeOk = !type || String(water.type || "").toLowerCase() === type;
      const favoriteOk = !state.filters.favorite || !!water.favorite;
      const manualOk = !state.filters.manual || water.manual || String(water.source || "").toLowerCase() === "manual";
      const stockedOk = !state.filters.stocked || !!water.stocked_trout;
      const historyOk = !state.filters.history || Number(water.catch_history_count || 0) > 0;
      const confidenceOk = !state.filters.confidence || confidenceTier(water) === "high";
      return speciesOk && typeOk && favoriteOk && manualOk && stockedOk && historyOk && confidenceOk;
    });

    state.ranked = [...state.filtered].sort((a, b) => {
      const targetDelta = targetFitScore(b, targetSpecies) - targetFitScore(a, targetSpecies);
      if (targetDelta) return targetDelta;
      return (Number(b.catch_history_count || 0) - Number(a.catch_history_count || 0));
    });

    if (state.filtered.length) {
      if (!state.filtered.some(item => item.id === state.selectedId)) {
        state.selectedId = state.filtered[0].id;
      }
    } else {
      state.selectedId = null;
    }

    renderMap();
    renderDetails();
    if (state.selectedId) {
      loadWaterIntel(state.selectedId);
    }
    renderWaterList();
    renderRankedWaters();

    const statusParts = [`${state.filtered.length} of ${state.waters.length} waters shown`];
    if (state.catalog.warnings && state.catalog.warnings.length) {
      statusParts.push(`Warnings: ${state.catalog.warnings.slice(0, 2).join(" | ")}`);
    }
    setStatus(statusParts.join(" • "));
    const listStatus = byId("mapListStatus");
    if (listStatus) {
      const activeFilters = Object.entries(state.filters)
        .filter(([, value]) => value)
        .map(([key]) => key)
        .join(", ");
      listStatus.textContent = activeFilters ? `Active filters: ${activeFilters}` : "Filtered waters appear here.";
    }
  }

  function waterIntelUrl(waterId) {
    const targetSpecies = currentTargetSpecies();
    const params = new URLSearchParams({ water_id: waterId });
    if (targetSpecies) params.set("target_species", targetSpecies);
    return `/api/water-intel?${params.toString()}`;
  }

  function renderMapIntel(payload) {
    const container = byId("mapIntelResults");
    if (!container) return;

    if (!payload || !payload.smart_intelligence) {
      container.innerHTML = `<p class="small">No water intelligence available.</p>`;
      return;
    }

    const intel = payload.smart_intelligence;
    const bestBet = payload.best_bet || {};
    const confidence = intel.confidence || {};
    const targetFit = payload.target_fit || {};
    const positives = Array.isArray(intel.positive_signals) ? intel.positive_signals : [];
    const cautions = Array.isArray(intel.caution_signals) ? intel.caution_signals : [];
    const explanation = Array.isArray(intel.explanation) ? intel.explanation : [];
    const water = payload.water || {};

    container.innerHTML = `
      <div class="map-intel-head">
        <div>
          <h3>${esc(intel.headline || water.name || "Water intel")}</h3>
          <p class="small">${esc(intel.summary || "")}</p>
        </div>
        <div class="map-intel-score">
          <span>${esc(confidence.score ?? "?" )}</span>
          <label>${esc(confidence.label || confidence.level || "Unknown")}</label>
        </div>
      </div>

      <div class="chip-row">
        <span class="map-chip map-chip-strong">${esc(payload.selected_species || bestBet.species || "Target species")}</span>
        <span class="map-chip">${esc(payload.area_type || water.type || "water")}</span>
        <span class="map-chip">${esc(payload.weather?.temp ?? "?")}F</span>
        <span class="map-chip">${esc(payload.weather?.wind ?? "?")} mph wind</span>
        <span class="map-chip">${esc(payload.weather?.cloud ?? "?")}% cloud</span>
      </div>

      <div class="map-intel-grid">
        <div class="map-intel-panel">
          <strong>Primary lure</strong>
          <div>${esc(bestBet.lure_name || "General-purpose lure")}</div>
          <p class="small">${esc(bestBet.why || "")}</p>
        </div>
        <div class="map-intel-panel">
          <strong>Clarity</strong>
          <div>${esc(intel.clarity_signal?.label || "Unknown")}</div>
          <p class="small">${esc(intel.clarity_signal?.basis || "")}</p>
        </div>
        <div class="map-intel-panel">
          <strong>Catch history</strong>
          <div>${esc(intel.catch_history?.level || "none")}</div>
          <p class="small">${esc(intel.catch_history?.summary || "No catch history yet.")}</p>
        </div>
      <div class="map-intel-panel">
        <strong>Recommendation</strong>
        <div>${esc(bestBet.species || "Target species")}</div>
        <p class="small">${esc((bestBet.reasons && bestBet.reasons[0]) || "")}</p>
      </div>
      <div class="map-intel-panel">
        <strong>Target fit</strong>
        <div>${esc(targetFit.label || "Auto")}${targetFit.score !== undefined ? ` · ${esc(targetFit.score)}%` : ""}</div>
        <p class="small">${esc(targetFit.reason || "No target profile selected yet.")}</p>
      </div>
    </div>

      ${positives.length ? `
        <h4>Positive signals</h4>
        <div class="chip-row">${positives.map(item => `<span class="map-chip positive">${esc(item)}</span>`).join("")}</div>
      ` : ""}

      ${cautions.length ? `
        <h4>Caution signals</h4>
        <div class="chip-row">${cautions.map(item => `<span class="map-chip caution">${esc(item)}</span>`).join("")}</div>
      ` : ""}

      ${explanation.length ? `
        <details class="intel-details">
          <summary>Explanation</summary>
          <ul>${explanation.map(item => `<li>${esc(item)}</li>`).join("")}</ul>
        </details>
      ` : ""}

      <div class="map-intel-actions">
        <a class="button-link" href="/water/${encodeURIComponent(water.id)}">Open water detail</a>
        <a class="button-link secondary" href="/recommendations">Open Smart Picks</a>
      </div>
    `;
  }

  function waterRowMeta(water) {
    const parts = [];
    if (water.type) parts.push(esc(water.type));
    if (water.city) parts.push(esc(water.city));
    if (water.county) parts.push(esc(water.county));
    if (water.favorite) parts.push("Favorite");
    if (water.manual || String(water.source || "").toLowerCase() === "manual") parts.push("Manual");
    if (water.stocked_trout) parts.push("Stocked trout");
    if ((water.catch_history_count || 0) > 0) parts.push(`History ${water.catch_history_count}`);
    return parts.join(" · ");
  }

  function renderWaterList() {
    const list = byId("mapList");
    if (!list) return;

    const waters = (state.ranked.length ? state.ranked : state.filtered).slice(0, 24);
    if (!waters.length) {
      list.innerHTML = `<p class="small">No waters match the current filters.</p>`;
      return;
    }

    const target = currentTargetSpecies();
    list.innerHTML = waters.map(water => {
      const tier = confidenceTier(water);
      const fitScore = target ? targetFitScore(water, target) : 0;
      const icon = water.manual || String(water.source || "").toLowerCase() === "manual"
        ? waterIconPath("manual")
        : water.favorite
          ? waterIconPath("favorite")
          : water.stocked_trout
            ? waterIconPath("target")
            : waterIconPath(water.type);
      const active = water.id === state.selectedId ? " active" : "";
      return `
        <button type="button" class="map-water-row${active}" data-water-id="${esc(water.id)}">
          <div class="map-water-row-head">
            <strong><img class="icon-mini ai-icon map-marker-icon" src="${icon}" alt=""> ${esc(water.name || "Waterbody")}</strong>
            <span class="map-water-tier ${esc(tier)}">${target ? `${fitScore}%` : esc(tier)}</span>
          </div>
          <div class="small">${waterRowMeta(water)}${target ? ` · Fit ${fitScore}%` : ""}</div>
          <div class="map-water-row-chips">
            ${splitList(water.species).slice(0, 3).map(item => `<span class="map-chip">${esc(item)}</span>`).join("")}
          </div>
        </button>
      `;
    }).join("");

    list.querySelectorAll("[data-water-id]").forEach(button => {
      button.addEventListener("click", () => {
        const waterId = button.getAttribute("data-water-id");
        if (waterId) selectWater(waterId);
      });
    });
  }

  function renderRankedWaters() {
    const list = byId("mapRankedList");
    const target = currentTargetSpecies();
    if (!list) return;

    if (!state.ranked.length) {
      list.innerHTML = `<p class="small">No waters match the current filters.</p>`;
      return;
    }

    const waters = state.ranked.slice(0, 8);
    list.innerHTML = waters.map(water => {
      const score = targetFitScore(water, target);
      const label = targetFitLabel(score);
      const icon = water.manual || String(water.source || "").toLowerCase() === "manual"
        ? waterIconPath("manual")
        : water.favorite
          ? waterIconPath("favorite")
          : water.stocked_trout
            ? waterIconPath("target")
            : waterIconPath(water.type);
      return `
        <button type="button" class="map-water-row${water.id === state.selectedId ? " active" : ""}" data-ranked-water-id="${esc(water.id)}">
          <div class="map-water-row-head">
            <strong><img class="icon-mini ai-icon map-marker-icon" src="${icon}" alt=""> ${esc(water.name || "Waterbody")}</strong>
            <span class="map-water-tier ${esc(label.toLowerCase())}">${score}%</span>
          </div>
          <div class="small">${label} target fit · ${waterRowMeta(water)}</div>
          <div class="map-water-row-chips">
            ${splitList(water.species).slice(0, 3).map(item => `<span class="map-chip">${esc(item)}</span>`).join("")}
          </div>
        </button>
      `;
    }).join("");

    list.querySelectorAll("[data-ranked-water-id]").forEach(button => {
      button.addEventListener("click", () => {
        const waterId = button.getAttribute("data-ranked-water-id");
        if (waterId) selectWater(waterId);
      });
    });
  }

  async function loadWaterIntel(waterId) {
    const container = byId("mapIntelResults");
    if (container) {
      container.innerHTML = `<p class="small">Loading water intelligence...</p>`;
    }

    try {
      const data = await fetchJson(waterIntelUrl(waterId));
      state.waterIntel = data;
      renderMapIntel(data);
    } catch (error) {
      state.waterIntel = null;
      if (container) {
        container.innerHTML = `<p class="small error-text">Unable to load water intel: ${esc(error.message || error)}</p>`;
      }
    }
  }

  function renderMap() {
    const map = ensureMap();
    if (!map || !state.markerLayer) return;

    state.markerLayer.clearLayers();

    state.filtered.forEach(water => {
      if (water.lat === null || water.lat === undefined || water.lon === null || water.lon === undefined) {
        return;
      }

      const marker = L.marker([water.lat, water.lon], {
        icon: markerIcon(water),
        title: water.name || "Waterbody",
        alt: water.name || "Waterbody"
      });

      marker.on("click", () => {
        selectWater(water.id, { panTo: false });
      });

      marker.bindPopup(popupHtml(water), {
        closeButton: false,
        offset: [0, -10]
      });

      state.markerLayer.addLayer(marker);
    });

    const visibleIds = new Set(state.filtered.map(item => item.id));
    if (state.selectedId && !visibleIds.has(state.selectedId) && state.filtered.length) {
      state.selectedId = state.filtered[0].id;
    }

    if (!state.initialFitDone && state.filtered.length) {
      fitToWaters(state.filtered);
      state.initialFitDone = true;
    }
  }

  function fitToWaters(waters) {
    const map = ensureMap();
    if (!map || !waters.length) return;

    const latlngs = waters
      .filter(water => water.lat !== null && water.lon !== null && water.lat !== undefined && water.lon !== undefined)
      .map(water => [water.lat, water.lon]);

    if (!latlngs.length) return;

    const bounds = L.latLngBounds(latlngs);
    map.fitBounds(bounds.pad(0.18), { animate: false, maxZoom: 12 });
  }

  function renderDetails() {
    const details = byId("mapDetails");
    if (!details) return;

    const selected = state.waters.find(water => water.id === state.selectedId) || state.filtered[0] || null;
    if (!selected) {
      details.innerHTML = "No water selected.";
      const intel = byId("mapIntelResults");
      if (intel) intel.innerHTML = "";
      return;
    }

    state.selectedId = selected.id;

    const species = splitList(selected.species);
    const habitat = splitList(selected.habitat);
    const access = splitList(selected.access);
    const chips = [
      selected.manual || String(selected.source || "").toLowerCase() === "manual" ? "Manual waterbody" : null,
      selected.favorite ? "Favorite" : null,
      selected.stocked_trout ? "Stocked trout" : null,
      selected.confidence ? String(selected.confidence) : null,
      selected.source ? String(selected.source) : null,
      selected.catch_history_count ? `Catch history ${selected.catch_history_count}` : null
    ].filter(Boolean);

    details.innerHTML = `
      <div class="map-selection-head">
        <div>
          <h3>${esc(selected.name || "Waterbody")}</h3>
          <p class="small">${esc(selected.type || "water")}${selected.city ? " · " + esc(selected.city) : ""}${selected.county ? " · " + esc(selected.county) : ""}</p>
        </div>
        <span class="map-selected-badge">Selected</span>
      </div>
      <p>${chips.map(item => `<span class="map-chip">${esc(item)}</span>`).join("") || "<span class='small'>No extra flags.</span>"}</p>
      <p><strong>Species</strong><br>${species.length ? species.map(item => `<span class="map-chip">${esc(item)}</span>`).join("") : "No species listed."}</p>
      <p><strong>Access</strong><br>${access.length ? access.map(item => `<span class="map-chip habitat">${esc(item)}</span>`).join("") : "No access listed."}</p>
      <p><strong>Habitat</strong><br>${habitat.length ? habitat.map(item => `<span class="map-chip habitat">${esc(item)}</span>`).join("") : "No habitat listed."}</p>
      <p class="small">Lat ${esc(selected.lat)} · Lon ${esc(selected.lon)}</p>
      <p>${selected.notes ? textBlock(selected.notes) : "No notes yet."}</p>
      <div class="map-intel-actions">
        <a class="button-link" href="/water/${encodeURIComponent(selected.id)}">Open water detail</a>
        <button type="button" class="secondary-button" id="mapZoomToSelection">Zoom here</button>
      </div>
    `;

    const zoomButton = byId("mapZoomToSelection");
    if (zoomButton) {
      zoomButton.addEventListener("click", () => {
        if (selected.lat !== null && selected.lon !== null) {
          const map = ensureMap();
          if (map) map.setView([selected.lat, selected.lon], Math.max(map.getZoom() || 8, 12), { animate: true });
        }
      });
    }
  }

  function selectWater(id, options = {}) {
    state.selectedId = id;
    renderMap();
    renderDetails();

    const water = state.waters.find(item => item.id === id);
    if (!water) return;

    loadWaterIntel(id);

    if (options.panTo !== false) {
      const map = ensureMap();
      if (map) {
        const nextZoom = Math.max(map.getZoom() || 8, 12);
        map.setView([water.lat, water.lon], nextZoom, { animate: true });
      }
    }
  }

  async function fetchJson(url, options = {}) {
    const response = await fetch(url, {
      ...options,
      headers: {
        Accept: "application/json",
        ...(options.headers || {})
      }
    });

    const contentType = response.headers.get("content-type") || "";
    const text = await response.text();
    if (!contentType.includes("application/json")) {
      const snippet = text.trim().slice(0, 160) || "empty response";
      throw new Error(`Expected JSON from ${url} but received HTML or another format: ${snippet}`);
    }

    let data;
    try {
      data = JSON.parse(text);
    } catch (error) {
      throw new Error(`Invalid JSON from ${url}: ${error.message}`);
    }

    if (!response.ok) {
      throw new Error(data.error || `HTTP ${response.status}`);
    }

    return data;
  }

  async function loadMapData(options = {}) {
    try {
      const speciesFilter = byId("mapSpeciesFilter")?.value || "";
      const typeFilter = byId("mapTypeFilter")?.value || "";
      const targetSpecies = currentTargetSpecies();
      setStatus("Loading map data...");
      const params = new URLSearchParams();
      if (targetSpecies) params.set("target_species", targetSpecies);
      const data = await fetchJson(`/api/map-data${params.toString() ? `?${params.toString()}` : ""}`);
      state.catalog = {
        base_count: data.base_count || 0,
        custom_count: data.custom_count || 0,
        total_count: data.record_count || 0,
        warnings: data.warnings || []
      };
      state.waters = Array.isArray(data.waters) ? data.waters : [];
      const focused = options.focusId && state.waters.some(item => item.id === options.focusId)
        ? options.focusId
        : null;
      state.selectedId = focused || state.waters[0]?.id || null;

      ensureMap();
      renderFilters();
      if (byId("mapSpeciesFilter")) byId("mapSpeciesFilter").value = speciesFilter;
      if (byId("mapTypeFilter")) byId("mapTypeFilter").value = typeFilter;
      syncTargetSelector();
      renderTargetSummary();
      updateHeaderCounts();
      applyFilters();

      if (options.focusId) {
        const focus = state.waters.find(item => item.id === options.focusId);
        if (focus) {
          selectWater(focus.id, { panTo: true });
        }
      } else if (!state.initialFitDone && state.filtered.length) {
        fitToWaters(state.filtered);
        state.initialFitDone = true;
        if (state.selectedId) {
          loadWaterIntel(state.selectedId);
        }
      }
      if (data.target_profile) {
        state.targetProfile = data.target_profile;
        syncTargetSelector();
        renderTargetSummary();
      }
    } catch (error) {
      setStatus(`Unable to load map data: ${error.message || error}`);
    }
  }

  function fillCenterFields() {
    const map = ensureMap();
    if (!map) return;
    const center = map.getCenter();
    const lat = byId("mapWaterLat");
    const lon = byId("mapWaterLon");
    if (lat) lat.value = center.lat.toFixed(6);
    if (lon) lon.value = center.lng.toFixed(6);
    setAddStatus("Filled coordinates from the map center.");
  }

  function buildManualPayload() {
    return {
      name: byId("mapWaterName")?.value.trim(),
      type: byId("mapWaterType")?.value.trim() || "water",
      lat: byId("mapWaterLat")?.value.trim(),
      lon: byId("mapWaterLon")?.value.trim(),
      city: byId("mapWaterCity")?.value.trim(),
      county: byId("mapWaterCounty")?.value.trim(),
      state: byId("mapWaterState")?.value.trim() || "IL",
      species: splitList(byId("mapWaterSpecies")?.value).join(", "),
      access: splitList(byId("mapWaterAccess")?.value).join(", "),
      notes: byId("mapWaterNotes")?.value.trim(),
      favorite: !!byId("mapWaterFavorite")?.checked,
      stocked_trout: !!byId("mapWaterTrout")?.checked
    };
  }

  function validateManualPayload(payload) {
    if (!payload.name) return "Waterbody name is required.";
    if (!payload.type) return "Waterbody type is required.";
    if (payload.lat === "" || payload.lon === "") return "Latitude and longitude are required.";
    if (Number.isNaN(Number(payload.lat)) || Number.isNaN(Number(payload.lon))) return "Latitude and longitude must be numbers.";
    return null;
  }

  async function submitManualWater(event) {
    event.preventDefault();

    const payload = buildManualPayload();
    const validationError = validateManualPayload(payload);
    if (validationError) {
      setAddStatus(validationError, "error");
      return;
    }

    try {
      setAddStatus("Saving waterbody...");
      const result = await fetchJson("/api/waters/custom", {
        method: "POST",
        headers: {
          "Content-Type": "application/json"
        },
        body: JSON.stringify(payload)
      });

      setAddStatus(`Saved ${result.water?.name || "waterbody"}.`, "info");
      byId("mapAddForm")?.reset();
      const stateField = byId("mapWaterState");
      if (stateField) stateField.value = "IL";
      const speciesFilter = byId("mapSpeciesFilter");
      const typeFilter = byId("mapTypeFilter");
      if (speciesFilter) speciesFilter.value = "";
      if (typeFilter) typeFilter.value = "";
      await loadMapData({ focusId: result.water?.id });
    } catch (error) {
      setAddStatus(`Unable to save waterbody: ${error.message || error}`, "error");
    }
  }

  function bindUi() {
    byId("mapBaseLayer")?.addEventListener("change", event => {
      switchBaseMap(event.target.value);
    });

    byId("mapSpeciesFilter")?.addEventListener("change", applyFilters);
    byId("mapTypeFilter")?.addEventListener("change", applyFilters);
    ["mapFilterFavorite", "mapFilterManual", "mapFilterStocked", "mapFilterHistory", "mapFilterConfidence"].forEach(id => {
      byId(id)?.addEventListener("change", applyFilters);
    });
    byId("mapTargetSpecies")?.addEventListener("change", () => {
      saveTargetProfile({ current_trip_target: currentTargetSpecies() })
        .then(() => {
          if (state.selectedId) {
            loadWaterIntel(state.selectedId);
          }
          applyFilters();
        })
        .catch(() => {
          if (state.selectedId) {
            loadWaterIntel(state.selectedId);
          }
        });
    });
    byId("mapResetButton")?.addEventListener("click", () => {
      const species = byId("mapSpeciesFilter");
      const type = byId("mapTypeFilter");
      const target = byId("mapTargetSpecies");
      ["mapFilterFavorite", "mapFilterManual", "mapFilterStocked", "mapFilterHistory", "mapFilterConfidence"].forEach(id => {
        const input = byId(id);
        if (input) input.checked = false;
      });
      const base = byId("mapBaseLayer");
      if (species) species.value = "";
      if (type) type.value = "";
      if (target) target.value = "";
      if (base) base.value = "hybrid";
      state.selectedId = state.waters[0]?.id || null;
      state.activeBasemap = "hybrid";
      state.filters = {
        favorite: false,
        manual: false,
        stocked: false,
        history: false,
        confidence: false
      };
      switchBaseMap("hybrid");
      applyFilters();
      if (state.selectedId) {
        loadWaterIntel(state.selectedId);
      }
    });

    byId("mapUseCenterButton")?.addEventListener("click", fillCenterFields);
    byId("mapAddForm")?.addEventListener("submit", submitManualWater);
  }

  function init() {
    if (!byId("mapCanvas")) return;
    bindUi();
    ensureMap();
    updateLayerLabel();
    loadTargetProfile().finally(() => {
      loadMapData();
    });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
