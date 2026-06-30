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
    selectedId: null,
    catalog: {
      base_count: 0,
      custom_count: 0,
      total_count: 0,
      warnings: []
    },
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

    if (speciesList) {
      speciesList.innerHTML = species.map(item => `<option value="${esc(item)}"></option>`).join("");
    }
  }

  function applyFilters() {
    const species = (byId("mapSpeciesFilter")?.value || "").toLowerCase();
    const type = (byId("mapTypeFilter")?.value || "").toLowerCase();

    state.filtered = state.waters.filter(water => {
      const speciesOk = !species || splitList(water.species).some(item => item.toLowerCase() === species);
      const typeOk = !type || String(water.type || "").toLowerCase() === type;
      return speciesOk && typeOk;
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

    const statusParts = [`${state.filtered.length} of ${state.waters.length} waters shown`];
    if (state.catalog.warnings && state.catalog.warnings.length) {
      statusParts.push(`Warnings: ${state.catalog.warnings.slice(0, 2).join(" | ")}`);
    }
    setStatus(statusParts.join(" • "));
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
      <h3>${esc(selected.name || "Waterbody")}</h3>
      <p class="small">${esc(selected.type || "water")} ${selected.city ? "· " + esc(selected.city) : ""} ${selected.county ? "· " + esc(selected.county) : ""}</p>
      <p>${chips.map(item => `<span class="map-chip">${esc(item)}</span>`).join("") || "<span class='small'>No extra flags.</span>"}</p>
      <p><strong>Species</strong><br>${species.length ? species.map(item => `<span class="map-chip">${esc(item)}</span>`).join("") : "No species listed."}</p>
      <p><strong>Access</strong><br>${access.length ? access.map(item => `<span class="map-chip habitat">${esc(item)}</span>`).join("") : "No access listed."}</p>
      <p><strong>Habitat</strong><br>${habitat.length ? habitat.map(item => `<span class="map-chip habitat">${esc(item)}</span>`).join("") : "No habitat listed."}</p>
      <p class="small">Lat ${esc(selected.lat)} · Lon ${esc(selected.lon)}</p>
      <p>${selected.notes ? textBlock(selected.notes) : "No notes yet."}</p>
      <p><a href="/water/${encodeURIComponent(selected.id)}">Open water detail</a></p>
    `;
  }

  function selectWater(id, options = {}) {
    state.selectedId = id;
    renderMap();
    renderDetails();

    const water = state.waters.find(item => item.id === id);
    if (!water) return;

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
      setStatus("Loading map data...");
      const data = await fetchJson("/api/map-data");
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
    byId("mapResetButton")?.addEventListener("click", () => {
      const species = byId("mapSpeciesFilter");
      const type = byId("mapTypeFilter");
      const base = byId("mapBaseLayer");
      if (species) species.value = "";
      if (type) type.value = "";
      if (base) base.value = "hybrid";
      state.selectedId = state.waters[0]?.id || null;
      state.activeBasemap = "hybrid";
      switchBaseMap("hybrid");
      applyFilters();
    });

    byId("mapUseCenterButton")?.addEventListener("click", fillCenterFields);
    byId("mapAddForm")?.addEventListener("submit", submitManualWater);
  }

  function init() {
    if (!byId("mapCanvas")) return;
    bindUi();
    ensureMap();
    updateLayerLabel();
    loadMapData();
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
