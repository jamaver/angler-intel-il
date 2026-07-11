const form = document.getElementById("searchForm");
const zipInput = document.getElementById("zipInput");
const favoriteName = document.getElementById("favoriteName");
const targetSpeciesNode = document.getElementById("targetSpecies");
const targetProfileSummary = document.getElementById("targetProfileSummary");

let currentZip = "60543";
let latestData = null;
let targetProfile = null;

function el(id) {
  return document.getElementById(id);
}

function setHTML(id, html) {
  const node = el(id);
  if (node) node.innerHTML = html;
}

function asList(value) {
  if (Array.isArray(value)) return value.filter(item => item !== null && item !== undefined && item !== "");
  if (value === null || value === undefined || value === "") return [];
  return [value];
}

function iconSlug(value) {
  return String(value || "")
    .toLowerCase()
    .replace(/&/g, " and ")
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "");
}

const FISH_ICON_MAP = {
  largemouth_bass: "largemouth_bass",
  smallmouth_bass: "smallmouth_bass",
  crappie: "crappie",
  bluegill: "bluegill",
  catfish: "catfish",
  channel_catfish: "catfish",
  flathead_catfish: "catfish",
  trout: "trout",
  brown_trout: "trout",
  rainbow_trout: "trout",
  walleye: "walleye",
  pike: "pike",
  northern_pike: "pike",
  muskie: "pike",
  musky: "pike",
  sauger: "walleye",
  white_bass: "generic_fish",
  yellow_perch: "generic_fish",
  common_carp: "generic_fish",
  generic_fish: "generic_fish",
};

const LURE_ICON_MAP = {
  spinnerbait: "spinnerbait",
  topwater: "topwater_popper",
  topwater_popper: "topwater_popper",
  frog: "frog",
  jig: "jig",
  microjig: "jig",
  walleyejig: "drop_shot",
  crankbait: "crankbait",
  swimbait: "swimbait",
  minnow: "crankbait",
  inline_spinner: "inline_spinner",
  spoon: "spoon",
  drop_shot: "drop_shot",
  worm: "soft_plastic_worm",
  soft_plastic_worm: "soft_plastic_worm",
  catfishbait: "bobber_live_bait",
  bobber_live_bait: "bobber_live_bait",
  generic_lure: "generic_lure",
};

function normalizedIconKey(value) {
  return iconSlug(value).replace(/-/g, "_");
}

function fishIconPath(value) {
  const key = normalizedIconKey(value);
  return `/static/icons/fish/${FISH_ICON_MAP[key] || "generic_fish"}.svg`;
}

function lureIconPath(value) {
  const text = String(value || "").toLowerCase();
  if (text.includes("spinnerbait")) return "/static/icons/lures/spinnerbait.svg";
  if (text.includes("topwater") && text.includes("popper")) return "/static/icons/lures/topwater_popper.svg";
  if (text.includes("topwater")) return "/static/icons/lures/topwater_popper.svg";
  if (text.includes("frog")) return "/static/icons/lures/frog.svg";
  if ((text.includes("drop") && text.includes("shot")) || text.includes("dropshot")) return "/static/icons/lures/drop_shot.svg";
  if (text.includes("inline spinner") || text.includes("rooster tail")) return "/static/icons/lures/inline_spinner.svg";
  if (text.includes("swimbait")) return "/static/icons/lures/swimbait.svg";
  if (text.includes("crankbait") || text.includes("jerkbait") || text.includes("minnow") || text.includes("shad")) return "/static/icons/lures/crankbait.svg";
  if (text.includes("jig") && text.includes("micro")) return "/static/icons/lures/jig.svg";
  if (text.includes("jig") && text.includes("walleye")) return "/static/icons/lures/drop_shot.svg";
  if (text.includes("jig")) return "/static/icons/lures/jig.svg";
  if (text.includes("spoon")) return "/static/icons/lures/spoon.svg";
  if (text.includes("catfish") || text.includes("bait")) return "/static/icons/lures/bobber_live_bait.svg";
  if (text.includes("worm") || text.includes("plastic") || text.includes("ned") || text.includes("finesse")) return "/static/icons/lures/soft_plastic_worm.svg";
  const key = normalizedIconKey(value);
  return `/static/icons/lures/${LURE_ICON_MAP[key] || "generic_lure"}.svg`;
}

function waterIconForRecord(water = {}) {
  const manual = String(water.manual || "").toLowerCase() === "true" || String(water.source || "").toLowerCase() === "manual";
  if (manual) return "/static/icons/map/manual_water.svg";
  if (water.favorite) return "/static/icons/map/favorite_water.svg";
  if (water.stocked_trout) return "/static/icons/map/high_confidence.svg";

  const text = [water.type, water.name, water.label]
    .map(value => String(value || "").toLowerCase())
    .join(" ");

  if (text.includes("spillway") || text.includes("tailwater") || text.includes("tail-water")) return "/static/icons/map/spillway.svg";
  if (text.includes("reservoir")) return "/static/icons/map/reservoir.svg";
  if (text.includes("pond")) return "/static/icons/map/pond.svg";
  if (text.includes("river")) return "/static/icons/map/river.svg";
  if (text.includes("creek") || text.includes("stream")) return "/static/icons/map/creek.svg";
  if (text.includes("lake") || text.includes("great lake")) return "/static/icons/map/lake.svg";
  return "/static/icons/map/missing_coordinates.svg";
}

function renderMetric(label, value, small = "") {
  return `
    <div class="dashboard-metric">
      <span>${label}</span>
      <strong>${value}</strong>
      ${small ? `<small>${small}</small>` : ""}
    </div>
  `;
}

function renderDashboardSummary(data) {
  const waters = data.waters || [];
  const weather = data.weather || {};
  const target = data.target_species || currentTargetSpecies() || "Auto";
  const topWater = waters[0] || {};
  const topWaterLabel = topWater.name ? `${topWater.name}${topWater.distance ? ` · ${topWater.distance} mi` : ""}` : "No waters in range";

  return `
    <div class="dashboard-metric-grid">
      ${renderMetric("Target", target, data.target_species_source || "profile")}
      ${renderMetric("Score", `${data.overall?.score ?? "?"}/100`, data.overall?.rating || "")}
      ${renderMetric("Wind", `${weather.wind ?? "?"} mph`, weather.fallback ? "fallback weather" : "live weather")}
      ${renderMetric("Waters", `${waters.length}`, topWaterLabel)}
    </div>
  `;
}

function renderDashboardBrief(data) {
  const waters = data.waters || [];
  const topWater = waters[0];
  const secondWater = waters[1];
  const target = data.target_species || currentTargetSpecies() || "Auto";

  if (!topWater) {
    return `
      <div class="dashboard-brief-empty">
        <p>No waters matched this search radius.</p>
        <a class="hero-action" href="/map">Open Map</a>
      </div>
    `;
  }

  const topWaterIcon = waterIconForRecord(topWater);
  const secondWaterLabel = secondWater ? `${secondWater.name}${secondWater.distance ? ` · ${secondWater.distance} mi` : ""}` : "";

  return `
    <div class="dashboard-brief-top">
      <img class="dashboard-water-icon ai-icon map-marker-icon" src="${topWaterIcon}" alt="">
      <div>
        <div class="small">Best nearby water</div>
        <h3>${topWater.name || "Selected waterbody"}</h3>
        <div class="small">${topWater.type || "water"}${topWater.city ? ` · ${topWater.city}` : ""}${topWater.distance ? ` · ${topWater.distance} mi` : ""}</div>
      </div>
    </div>
    <div class="dashboard-brief-pills">
      <span class="mini">${target}</span>
      <span class="mini">${topWater.local_score ?? "?"} score</span>
      <span class="mini">${topWater.favorite ? "Favorite" : "Near you"}</span>
      ${secondWaterLabel ? `<span class="mini">Next: ${secondWaterLabel}</span>` : ""}
    </div>
    <div class="dashboard-brief-actions">
      <a class="hero-action" href="/map">Open Map</a>
      <a class="hero-action secondary-link" href="/waters">Local Waters</a>
      <a class="hero-action secondary-link" href="/water/${encodeURIComponent(topWater.id)}">Water Intel</a>
    </div>
  `;
}

if (form) {
  form.addEventListener("submit", e => {
    e.preventDefault();
    loadIntel(zipInput.value);
  });
}

targetSpeciesNode?.addEventListener("change", () => {
  syncTargetSpecies({ use_trip: true }).catch(err => {
    console.error(err);
  });
});

document.getElementById("setTripTarget")?.addEventListener("click", () => {
  syncTargetSpecies({ use_trip: true }).catch(err => {
    alert(err.message || "Could not save trip target.");
  });
});

document.getElementById("setDefaultTarget")?.addEventListener("click", () => {
  const value = targetSpeciesNode ? targetSpeciesNode.value.trim() : "";
  saveTargetProfile({ default_target_species: value, current_trip_target: value || "" })
    .then(() => loadIntel(currentZip))
    .catch(err => {
      alert(err.message || "Could not save default target.");
    });
});

document.getElementById("favoriteTarget")?.addEventListener("click", () => {
  const value = targetSpeciesNode ? targetSpeciesNode.value.trim() : "";
  if (!value) return;
  saveTargetProfile({ favorite_species_add: value })
    .then(() => loadIntel(currentZip))
    .catch(err => {
      alert(err.message || "Could not save favorite target.");
    });
});

function formatHour(hour) {
  const suffix = hour >= 12 ? "PM" : "AM";
  let h = hour % 12;
  if (h === 0) h = 12;
  return `${h} ${suffix}`;
}

function openSnapshot() {
  window.open(`/snapshot?zip=${encodeURIComponent(currentZip)}`, "_blank");
}

function currentTargetSpecies() {
  const selected = targetSpeciesNode ? targetSpeciesNode.value.trim() : "";
  if (selected) return selected;
  return targetProfile?.current_trip_target || targetProfile?.default_target_species || "";
}

function renderTargetProfile() {
  if (!targetProfileSummary) return;
  if (!targetProfile) {
    targetProfileSummary.textContent = "Target profile unavailable.";
    return;
  }

  const favorites = Array.isArray(targetProfile.favorite_species) ? targetProfile.favorite_species : [];
  const trip = targetProfile.current_trip_target || "Auto";
  const defaultTarget = targetProfile.default_target_species || "Auto";
  targetProfileSummary.textContent = `Trip target: ${trip} · Default: ${defaultTarget} · Favorites: ${favorites.slice(0, 3).join(", ") || "none"}`;
}

async function loadTargetProfile() {
  try {
    const res = await fetch("/api/target-profile");
    const data = await res.json();
    if (!res.ok || !data.ok) {
      throw new Error(data.error || "Could not load target profile");
    }

    targetProfile = data.profile || {};
    if (targetSpeciesNode) {
      targetSpeciesNode.value = targetProfile.current_trip_target || targetProfile.default_target_species || "";
    }
    renderTargetProfile();
  } catch (err) {
    console.error(err);
    targetProfile = null;
    renderTargetProfile();
  }
}

async function saveTargetProfile(payload) {
  const res = await fetch("/api/target-profile", {
    method: "POST",
    headers: {"Content-Type": "application/json"},
    body: JSON.stringify(payload)
  });

  const data = await res.json();
  if (!res.ok || !data.ok) {
    throw new Error(data.error || "Could not save target profile");
  }

  targetProfile = data.profile || {};
  if (targetSpeciesNode) {
    targetSpeciesNode.value = targetProfile.current_trip_target || targetProfile.default_target_species || "";
  }
  renderTargetProfile();
  return targetProfile;
}

async function loadFavorites() {
  try {
    const res = await fetch("/api/favorites");
    const favorites = await res.json();

    if (!favorites || favorites.length === 0) {
      setHTML("favorites", `<div class="small">No favorites saved yet.</div>`);
      return;
    }

    setHTML("favorites", favorites.map(f => `
      <div class="favorite-row">
        <button type="button" onclick="loadIntel('${f.zip}')">${f.name}<br><span>${f.zip}</span></button>
        <button type="button" class="danger" onclick="deleteFavorite('${f.zip}')">Remove</button>
      </div>
    `).join(""));
  } catch {
    setHTML("favorites", `<div class="small">Could not load favorites.</div>`);
  }
}

async function saveFavorite() {
  const name = favoriteName.value.trim() || `Favorite ${currentZip}`;

  const res = await fetch("/api/favorites", {
    method: "POST",
    headers: {"Content-Type": "application/json"},
    body: JSON.stringify({
      name: name,
      zip: currentZip
    })
  });

  if (!res.ok) {
    alert("Could not save favorite.");
    return;
  }

  favoriteName.value = "";
  await loadFavorites();
}

async function deleteFavorite(zip) {
  await fetch(`/api/favorites/${zip}`, {
    method: "DELETE"
  });
  await loadFavorites();
}

async function loadCatchLog() {
  try {
    const res = await fetch("/api/catches");
    const catches = await res.json();

    if (!catches || catches.length === 0) {
      setHTML("catchLog", `<div class="small">No catches logged yet.</div>`);
      return;
    }

    setHTML("catchLog", catches.slice(0, 20).map(c => `
      <div class="catch-row">
        <b><img class="icon-mini ai-icon fish-icon" src="${fishIconPath(c.species)}" alt=""> ${c.species}</b>
        <div class="small">${c.timestamp} · ZIP ${c.zip || "unknown"}${c.waterbody ? ` · ${c.waterbody}` : ""}</div>
        <div><img class="icon-mini ai-icon lure-icon" src="${lureIconPath(c.lure || "worm")}" alt=""> ${c.lure || "No lure recorded"}</div>
        <div class="small">${c.notes || ""}</div>
        <button class="danger small-btn" onclick="deleteCatch('${c.id}')">Delete</button>
      </div>
    `).join(""));
  } catch {
    setHTML("catchLog", `<div class="small">Could not load catch log.</div>`);
  }
}

async function saveCatch() {
  const speciesNode = el("catchSpecies");
  const lureNode = el("catchLure");
  const waterbodyNode = el("catchWaterbody");
  const notesNode = el("catchNotes");

  const species = speciesNode ? speciesNode.value : "";
  const lure = lureNode ? lureNode.value.trim() : "";
  const waterbody = waterbodyNode ? waterbodyNode.value.trim() : "";
  const notes = notesNode ? notesNode.value.trim() : "";

  if (!species) {
    alert("Choose a species first.");
    return;
  }

  const res = await fetch("/api/catches", {
    method: "POST",
    headers: {"Content-Type": "application/json"},
    body: JSON.stringify({
      zip: currentZip,
      species,
      lure,
      waterbody,
      notes
    })
  });

  if (!res.ok) {
    alert("Could not save catch.");
    return;
  }

  if (lureNode) lureNode.value = "";
  if (waterbodyNode) waterbodyNode.value = "";
  if (notesNode) notesNode.value = "";

  await loadCatchLog();
  await loadIntel(currentZip);
}

async function deleteCatch(id) {
  await fetch(`/api/catches/${id}`, {
    method: "DELETE"
  });
  await loadCatchLog();
  await loadIntel(currentZip);
}

async function loadIntel(zip) {
  currentZip = zip;
  if (zipInput) zipInput.value = zip;
  const target = currentTargetSpecies();

  setHTML("status", "Loading fishing intelligence...");

  try {
    const params = new URLSearchParams({ zip });
    if (target) params.set("target_species", target);
    const res = await fetch(`/api/intel?${params.toString()}`);
    const data = await res.json();

    if (!res.ok) {
      setHTML("status", data.error || "Error loading data");
      return;
    }

    latestData = data;
    render(data);
  } catch (err) {
    console.error(err);
    setHTML("status", `
      <b>Unable to load data.</b>
      <div class="small">The browser render failed. Run service logs if this continues.</div>
    `);
  }
}

function colorPills(colors) {
  return (colors || []).map(c => `<span class="color-pill">${c}</span>`).join("");
}

function renderInsights(insights) {
  if (!insights || insights.total === 0) {
    return `<div class="small">${insights ? insights.message : "No catch history yet."}</div>`;
  }

  const topSpecies = insights.top_species || [];
  const topLures = insights.top_lures || [];
  const topWaterbodies = insights.top_waterbodies || [];
  const localTopWaterbodies = insights.local_top_waterbodies || [];
  const sampleQuality = insights.sample_quality || "unknown";

  return `
    <div class="insight-grid">
      <div>
        <b>Total catches logged</b>
        <div class="score">${insights.total}</div>
      </div>
      <div>
        <b>This ZIP</b>
        <div class="score">${insights.local_total || 0}</div>
      </div>
    </div>

    <h3>Top Species</h3>
    ${topSpecies.map(s => `<div class="pill-line"><img class="icon-mini ai-icon fish-icon" src="${fishIconPath(s.name)}" alt=""> ${s.name}: ${s.count}</div>`).join("")}

    <h3>Top Lures</h3>
    ${topLures.map(l => `<div class="pill-line"><img class="icon-mini ai-icon lure-icon" src="${lureIconPath(l.name)}" alt=""> ${l.name}: ${l.count}</div>`).join("")}

    <h3>Top Waterbodies</h3>
    ${topWaterbodies.map(w => `<div class="pill-line"><img class="icon-mini ai-icon map-marker-icon" src="${waterIconForRecord({ type: w.type || w.name, name: w.name })}" alt=""> ${w.name}: ${w.count}</div>`).join("")}

    <h3>Local Waterbodies</h3>
    ${localTopWaterbodies.map(w => `<div class="pill-line"><img class="icon-mini ai-icon map-marker-icon" src="${waterIconForRecord({ type: w.type || w.name, name: w.name, manual: w.manual })}" alt=""> ${w.name}: ${w.count}</div>`).join("")}

    <div class="small">Sample quality: ${sampleQuality}</div>
  `;
}

async function syncTargetSpecies(payload = {}) {
  const value = targetSpeciesNode ? targetSpeciesNode.value.trim() : "";
  const nextPayload = { ...payload };
  if (value) {
    if (payload.use_trip !== false) {
      nextPayload.current_trip_target = value;
    }
  } else if (payload.use_trip !== false) {
    nextPayload.current_trip_target = "";
  }

  await saveTargetProfile(nextPayload);
  await loadIntel(currentZip);
}

function renderSmartIntelligence(intel) {
  if (!intel) {
    return `<div class="small">Smart intelligence is unavailable for this search.</div>`;
  }

  const confidence = intel.confidence || {};
  const confidenceLabel = confidence.label || confidence.level || (intel.ok ? "Moderate" : "Low");
  const confidenceScore = confidence.score ?? confidence.value;
  const confidenceBasis = confidence.basis || confidence.explanation || "";
  const explanation = asList(intel.explanation);
  const positives = asList(intel.positive_signals);
  const cautions = asList(intel.caution_signals);
  const labels = asList(intel.condition_labels).map(c => `<span class="mini">${c}</span>`).join("");
  const recommendations = asList(intel.recommendations).map(r => `
    <div class="intel-recommendation">
      <b>${r.label}: ${r.value}</b>
      <div class="small">${r.why || ""}</div>
    </div>
  `).join("");
  const strategy = asList(intel.strategy).map(item => `<li>${item}</li>`).join("");
  const nextActions = asList(intel.next_actions).map(item => `<li>${item}</li>`).join("");
  const warnings = asList(intel.warnings).map(item => `<li>${item}</li>`).join("");
  const errors = asList(intel.errors).map(item => `<li>${item}</li>`).join("");
  const inputQuality = intel.input_quality || {};
  const missingInputs = asList(confidence.missing_inputs || inputQuality.missing);
  const catchHistory = intel.catch_history || {};
  const sampleSize = catchHistory.sample_size || {};
  const catchMeta = [];
  if (sampleSize.local !== undefined || sampleSize.total !== undefined) {
    catchMeta.push(`Sample ${sampleSize.local || 0}/${sampleSize.total || 0}`);
  }
  if (catchHistory.strength) {
    catchMeta.push(`Strength: ${catchHistory.strength}`);
  }

  return `
    <h3>${intel.headline || "Fishing pattern"}</h3>
    <p>${intel.summary || ""}</p>
    ${intel.ok === false ? `<div class="status-warn">Fallback intelligence is active.</div>` : ""}
    <div class="intel-signal-row">${labels}</div>
    <div class="intel-grid">
      <div class="intel-recommendation">
        <b>Confidence</b>
        <div class="score">${confidenceScore ?? "?"}</div>
        <div class="small">${confidenceLabel}</div>
        <div class="small">${confidenceBasis}</div>
      </div>

      <div class="intel-recommendation">
        <b>Clarity</b>
        <div class="small">${intel.clarity_signal?.label || "unknown"}</div>
        <div class="small">${intel.clarity_signal?.basis || "No clarity basis available."}</div>
      </div>

      <div class="intel-recommendation">
        <b>Catch history</b>
        <div class="small">${catchHistory.summary || "No catch history yet."}</div>
        <div class="small">${catchMeta.join(" · ") || "Sample size is zero."}</div>
      </div>

      <div class="intel-recommendation">
        <b>Input quality</b>
        <div class="small">${inputQuality.ok ? "All key inputs present." : `Missing: ${missingInputs.join(", ") || "unknown"}`}</div>
        <div class="small">Source: ${inputQuality.source || "unknown"}${inputQuality.fallback ? " · fallback" : ""}</div>
      </div>
    </div>

    ${positives.length ? `<h4>Positive signals</h4><div class="intel-signal-row">${positives.map(item => `<span class="mini">${item}</span>`).join("")}</div>` : ""}
    ${cautions.length ? `<h4>Caution signals</h4><div class="intel-signal-row">${cautions.map(item => `<span class="mini">${item}</span>`).join("")}</div>` : ""}
    <div class="intel-grid">${recommendations}</div>
    ${explanation.length ? `<details class="intel-details">
      <summary>Explanation</summary>
      <ul>${explanation.map(item => `<li>${item}</li>`).join("")}</ul>
    </details>` : ""}
    <details class="intel-details">
      <summary>Strategy and next actions</summary>
      <h4>Strategy</h4>
      <ul>${strategy}</ul>
      <h4>Next actions</h4>
      <ul>${nextActions}</ul>
    </details>
    ${warnings ? `<details class="intel-details">
      <summary>Warnings</summary>
      <ul>${warnings}</ul>
    </details>` : ""}
    ${errors ? `<details class="intel-details">
      <summary>Errors</summary>
      <ul>${errors}</ul>
    </details>` : ""}
  `;
}

function render(data) {
  const loc = data.location || {};
  currentZip = loc.zip || currentZip;

  if (zipInput) zipInput.value = currentZip;
  if (targetSpeciesNode && data.target_species) {
    targetSpeciesNode.value = data.target_species;
  } else if (targetSpeciesNode && targetProfile) {
    targetSpeciesNode.value = targetProfile.current_trip_target || targetProfile.default_target_species || "";
  }

  setHTML("status", `
    <div class="status-layout">
      <div>
        <h2>${loc.city || "Unknown"}, ${loc.state || ""}</h2>
        <div class="small">ZIP ${loc.zip || currentZip} · ${data.area_type || "unknown"} water pattern</div>
        <div class="small">Target: ${data.target_species || currentTargetSpecies() || "auto"}</div>
        <div class="small">Generated: ${data.generated_at || ""}</div>
      </div>
      <div class="status-score">
        <div class="score">${data.overall?.score ?? "?"}/100</div>
        <div>${data.overall?.rating ?? ""}</div>
      </div>
      <div class="status-actions">
        <button class="secondary" onclick="openSnapshot()">Trip Snapshot</button>
      </div>
    </div>
  `);
  setHTML("dashboardSummary", renderDashboardSummary(data));
  setHTML("dashboardBrief", renderDashboardBrief(data));

  const best = data.best_bet;

  if (best) {
    setHTML("bestBet", `
      <div class="best-bet-layout">
      <img class="fish-img ai-icon fish-icon" src="${best.fish_image}" alt="${best.species}">
        <div>
          <h3>${best.species}</h3>
          <div class="score">${best.species_score}%</div>
          <p><b>Best window:</b> ${best.time_label} · ${best.time_range}</p>
          ${best.best_hour ? `<p><b>Best hour:</b> ${best.best_hour}</p>` : ""}
          <p><b>Throw:</b> ${best.lure_name}</p>
          <p><b>Retrieve:</b> ${best.speed} · <b>Size:</b> ${best.size}</p>
          <div class="color-row">${colorPills(best.colors)}</div>
        </div>
      </div>

      <div class="best-reasons">
        ${(best.reasons || []).map(r => `<div>✅ ${r}</div>`).join("")}
      </div>
    `);
  } else {
    setHTML("bestBet", `<div class="small">Best Bet unavailable.</div>`);
  }

  setHTML("smartIntelligence", renderSmartIntelligence(data.smart_intelligence));

  setHTML("conditions", `
    🌡 ${data.weather?.temp ?? "?"}°F<br>
    💨 ${data.weather?.wind ?? "?"} mph<br>
    📉 ${data.weather?.pressure ?? "?"} inHg<br>
    ☁️ ${data.weather?.cloud ?? "?"}% cloud cover<br>
    <span class="small">${data.weather?.fallback ? "Fallback weather estimate in use" : "Live weather feed"}</span>
  `);

  setHTML("bestTime", `
    <div class="score">${data.best_time?.score ?? "?"}%</div>
    <div>${data.best_time?.label ?? ""}</div>
    <div class="small">${data.best_time?.time ?? ""}</div>
    ${data.best_hour ? `<hr><b>Best Hour:</b><br>${formatHour(data.best_hour.hour)} - ${data.best_hour.score}%` : ""}
  `);

  setHTML("lureCards", (data.lure_cards || []).map(l => `
    <div class="lure-card">
      <div class="lure-top">
        ${l.top_pick ? `<span class="badge">Top pick</span>` : `<span></span>`}
        <span class="mini">${l.speed}</span>
        <span class="mini">${l.size}</span>
      </div>
      <img class="lure-img ai-icon lure-icon" src="${l.image}" alt="${l.name}">
      <h3>${l.name}</h3>
      <div class="lure-sub">Good for ${l.species} · ${l.species_score}% species score</div>
      <div class="color-row">${colorPills(l.colors)}</div>
      <p class="small">${l.why}</p>
    </div>
  `).join(""));

  setHTML("timeBlocks", (data.time_blocks || []).map(t => `
    <div class="time-card">
      <b>${t.label}</b>
      <div class="score">${t.score}%</div>
      <div class="small">${t.time}</div>
    </div>
  `).join(""));

  setHTML("hourly", (data.hourly || []).map(h => `
    <div class="hour-row">
      <span>${formatHour(h.hour)}</span>
      <div class="bar-wrap">
        <div class="bar" style="width:${h.score}%"></div>
      </div>
      <b>${h.score}%</b>
    </div>
  `).join(""));

  setHTML("species", (data.species || []).slice(0, 8).map(s => `
    <div class="species-card species-with-image">
      <img class="fish-thumb ai-icon fish-icon" src="${s.fish_image}" alt="${s.name}">
      <div>
        <h3>${s.name}</h3>
        <div class="score">${s.score}%</div>
        <div>${s.rating}</div>
        <div class="small">Habitat: ${s.habitat}</div>
        <div class="lures">
          🌅 Morning: ${s.lures?.morning || ""}<br>
          ☀️ Midday: ${s.lures?.midday || ""}<br>
          🌇 Evening: ${s.lures?.evening || ""}
        </div>
      </div>
    </div>
  `).join(""));

  const catchSpecies = el("catchSpecies");
  if (catchSpecies) {
    catchSpecies.innerHTML = (data.species || []).slice(0, 12).map(s => `
      <option value="${s.name}">${s.name}</option>
    `).join("");
  }

  if (!data.waters || data.waters.length === 0) {
    setHTML("waters", "No named waters found nearby from OpenStreetMap.");
  } else {
    setHTML("waters", data.waters.map(w => `
      <div class="water-row">
        <img class="icon-mini ai-icon map-marker-icon" src="${waterIconForRecord(w)}" alt="">
        <div class="water-row-meta">
          <b>${w.name}</b>
          <div class="small">${w.type}${w.distance ? ` - ${w.distance} mi` : ""}${w.city ? ` · ${w.city}` : ""}</div>
          <div class="water-row-chips">
            <span class="mini">${w.local_score ?? "?"} score</span>
            ${w.favorite ? `<span class="mini">Favorite</span>` : ""}
            ${w.stocked_trout ? `<span class="mini">Trout</span>` : ""}
            ${w.manual || String(w.source || "").toLowerCase() === "manual" ? `<span class="mini">Manual</span>` : ""}
          </div>
        </div>
        <a class="water-row-link" href="/water/${encodeURIComponent(w.id)}">Open Intel</a>
      </div>
    `).join(""));
  }

  setHTML("forecast", (data.forecast || []).map(f => `
    <div class="forecast-day">
      <b>${f.date.slice(5)}</b>
      <div class="score">${f.score}</div>
      <div class="small">${f.rating}</div>
      <div class="small">${f.low}° / ${f.high}°</div>
    </div>
  `).join(""));

  setHTML("catchInsights", renderInsights(data.catch_insights));
}

loadFavorites();
loadCatchLog();
loadTargetProfile().finally(() => {
  loadIntel("60543");
});
