const form = document.getElementById("searchForm");
const zipInput = document.getElementById("zipInput");
const favoriteName = document.getElementById("favoriteName");
const targetSpeciesNode = document.getElementById("targetSpecies");
const targetProfileSummary = document.getElementById("targetProfileSummary");
const focusWaterNode = document.getElementById("focusWater");
const focusWaterSummary = document.getElementById("focusWaterSummary");

const FOCUS_WATER_STORAGE_KEY = "angler-intel.focus-water";

let currentZip = "60543";
let currentFocusWaterIdValue = localStorage.getItem(FOCUS_WATER_STORAGE_KEY) || "";
let latestData = null;
let targetProfile = null;
let gearInventory = [];

function el(id) {
  return document.getElementById(id);
}

function setHTML(id, html) {
  const node = el(id);
  if (node) node.innerHTML = html;
}

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
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
  largemouth_bass: "largemouth_bass.png",
  smallmouth_bass: "smallmouth_bass.png",
  crappie: "crappie.png",
  bluegill: "bluegill.png",
  catfish: "channel_catfish.png",
  channel_catfish: "channel_catfish.png",
  flathead_catfish: "channel_catfish.png",
  trout: "rainbow_trout.png",
  rainbow_trout: "rainbow_trout.png",
  brown_trout: "rainbow_trout.png",
  walleye: "walleye.png",
  sauger: "sauger.png",
  white_bass: "white_bass.png",
  northern_pike: "northern_pike.png",
  pike: "northern_pike.png",
  muskie: "northern_pike.png",
  musky: "northern_pike.png",
  common_carp: "generic_fish.png",
  yellow_perch: "generic_fish.png",
  generic_fish: "generic_fish.png",
};

function fishIconPath(value) {
  const key = iconSlug(value).replace(/-/g, "_");
  return `/static/fish/${FISH_ICON_MAP[key] || "generic_fish.png"}`;
}

function speciesIconClass(size = "md") {
  return `species-icon species-icon-${size}`;
}

function gearLabel(item) {
  if (!item) return "";
  return item.display_name || [item.brand, item.model].filter(Boolean).join(" ") || item.category || "";
}

function populateGearSelect(selectId, items, placeholder) {
  const node = el(selectId);
  if (!node) return;
  const options = [`<option value="">${escapeHtml(placeholder || "Optional")}</option>`];
  (items || []).forEach(item => {
    const value = item && item.id ? item.id : "";
    if (!value) return;
    options.push(`<option value="${escapeHtml(value)}">${escapeHtml(gearLabel(item))}</option>`);
  });
  node.innerHTML = options.join("");
}

async function loadCatchGearOptions() {
  try {
    const res = await fetch("/api/gear/items");
    const data = await res.json();
    if (!res.ok || !data.ok) return;
    gearInventory = Array.isArray(data.items) ? data.items : [];
    const owned = gearInventory.filter(item => String(item.status || "").toLowerCase() === "owned");
    const lineItems = gearInventory.filter(item => String(item.category || "").toLowerCase() === "line" && String(item.status || "").toLowerCase() === "owned");
    const rodItems = gearInventory.filter(item => String(item.category || "").toLowerCase() === "rod" && String(item.status || "").toLowerCase() === "owned");
    const reelItems = gearInventory.filter(item => String(item.category || "").toLowerCase() === "reel" && String(item.status || "").toLowerCase() === "owned");
    const lureItems = gearInventory.filter(item => String(item.category || "").toLowerCase() === "lure" && String(item.status || "").toLowerCase() === "owned");
    const terminalItems = gearInventory.filter(item => String(item.category || "").toLowerCase() === "terminal" && String(item.status || "").toLowerCase() === "owned");

    populateGearSelect("catchRod", rodItems.length ? rodItems : owned, "Optional");
    populateGearSelect("catchReel", reelItems.length ? reelItems : owned, "Optional");
    populateGearSelect("catchLine", lineItems.length ? lineItems : owned, "Optional");
    populateGearSelect("catchGearLure", lureItems.length ? lureItems : owned, "Optional");
    populateGearSelect("catchTerminal", terminalItems.length ? terminalItems : owned, "Optional");
  } catch (err) {
    console.error("Could not load gear inventory for catches", err);
  }
}

function lureIconPath(value) {
  const text = String(value || "").toLowerCase();
  if (text.includes("spinnerbait")) {
    if (text.includes("black") && text.includes("night")) return "/static/lures/spinnerbait/black_night.png";
    if (text.includes("bluegill")) return "/static/lures/spinnerbait/bluegill.png";
    if (text.includes("gold")) return "/static/lures/spinnerbait/gold_shiner.png";
    if (text.includes("chartreuse")) return "/static/lures/spinnerbait/chartreuse_white.png";
    return "/static/lures/spinnerbait/white_silver.png";
  }
  if (text.includes("topwater") || text.includes("popper")) {
    if (text.includes("chrome") && text.includes("blue")) return "/static/lures/topwater_popper/chrome_blue.png";
    if (text.includes("frog") && text.includes("green")) return "/static/lures/topwater_popper/frog_green.png";
    if (text.includes("black")) return "/static/lures/topwater_popper/black.png";
    if (text.includes("shad")) return "/static/lures/topwater_popper/shad.png";
    return "/static/lures/topwater_popper/bone.png";
  }
  if (text.includes("jig")) {
    if (text.includes("black") && text.includes("blue")) return "/static/lures/jig/black_blue.png";
    if (text.includes("brown") && text.includes("craw")) return "/static/lures/jig/brown_orange_craw.png";
    if (text.includes("pbj")) return "/static/lures/jig/pbj.png";
    if (text.includes("white")) return "/static/lures/jig/white_shad.png";
    return "/static/lures/jig/green_pumpkin.png";
  }
  if (text.includes("crankbait") || text.includes("crank")) {
    if (text.includes("firetiger")) return "/static/lures/crankbait/firetiger.png";
    if (text.includes("chartreuse") && text.includes("black")) return "/static/lures/crankbait/chartreuse_black_back.png";
    if (text.includes("bluegill")) return "/static/lures/crankbait/bluegill.png";
    if (text.includes("craw")) return "/static/lures/crankbait/craw_red.png";
    if (text.includes("sexy shad")) return "/static/lures/crankbait/sexy_shad.png";
    return "/static/lures/crankbait/shad.png";
  }
  if (text.includes("swimbait") || text.includes("paddle tail") || text.includes("paddletail")) {
    if (text.includes("ayu")) return "/static/lures/swimbait/ayu.png";
    if (text.includes("green") && text.includes("pumpkin")) return "/static/lures/swimbait/green_pumpkin.png";
    if (text.includes("bluegill")) return "/static/lures/swimbait/bluegill.png";
    if (text.includes("pearl") || text.includes("white")) return "/static/lures/swimbait/pearl_white.png";
    return "/static/lures/swimbait/shad.png";
  }
  if (text.includes("frog")) {
    if (text.includes("leopard")) return "/static/lures/frog/leopard_frog.png";
    if (text.includes("brown")) return "/static/lures/frog/brown_frog.png";
    if (text.includes("black")) return "/static/lures/frog/black_frog.png";
    if (text.includes("white")) return "/static/lures/frog/white_frog.png";
    return "/static/lures/frog/green_frog.png";
  }
  if (text.includes("spoon")) {
    if (text.includes("blue") && text.includes("silver")) return "/static/lures/spoon/blue_silver.png";
    if (text.includes("firetiger")) return "/static/lures/spoon/firetiger.png";
    if (text.includes("chartreuse")) return "/static/lures/spoon/chartreuse.png";
    if (text.includes("gold")) return "/static/lures/spoon/gold.png";
    return "/static/lures/spoon/silver.png";
  }
  if (text.includes("inline spinner") || text.includes("rooster tail") || text.includes("spinner")) {
    if (text.includes("firetiger")) return "/static/lures/inline_spinner/firetiger.png";
    if (text.includes("chartreuse")) return "/static/lures/inline_spinner/chartreuse.png";
    if (text.includes("gold")) return "/static/lures/inline_spinner/gold.png";
    return "/static/lures/inline_spinner/silver.png";
  }
  if (text.includes("drop shot") || text.includes("dropshot") || text.includes("finesse rig")) {
    if (text.includes("morning dawn")) return "/static/lures/drop_shot/morning_dawn.png";
    if (text.includes("watermelon") && text.includes("red")) return "/static/lures/drop_shot/watermelon_red.png";
    if (text.includes("shad")) return "/static/lures/drop_shot/shad.png";
    return "/static/lures/drop_shot/green_pumpkin.png";
  }
  if (text.includes("minnow")) return "/static/lures/swimbait/shad.png";
  if (text.includes("worm")) return "/static/lures/soft_plastic_worm/green_pumpkin.png";
  if (text.includes("catfish")) return "/static/lures/generic_lure.png";
  return "/static/lures/generic_lure.png";
}

function waterIconForRecord(water = {}) {
  const manual = String(water.manual || "").toLowerCase() === "true" || String(water.source || "").toLowerCase() === "manual";
  if (manual) return "/static/icons/water/manual.svg";
  if (water.favorite) return "/static/icons/water/favorite.svg";
  if (water.stocked_trout) return "/static/icons/water/trout.svg";

  const text = [water.type, water.name, water.label]
    .map(value => String(value || "").toLowerCase())
    .join(" ");

  if (text.includes("spillway") || text.includes("tailwater") || text.includes("tail-water")) return "/static/icons/water/spillway.svg";
  if (text.includes("reservoir")) return "/static/icons/water/reservoir.svg";
  if (text.includes("pond")) return "/static/icons/water/pond.svg";
  if (text.includes("river") || text.includes("creek") || text.includes("stream")) return "/static/icons/water/river.svg";
  if (text.includes("lake") || text.includes("great lake")) return "/static/icons/water/lake.svg";
  return "/static/icons/water/other.svg";
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

function scoreText(value, suffix = "%") {
  const score = Number(value);
  return Number.isFinite(score) ? `${Math.round(score)}${suffix}` : "Not available";
}

function emptyDashboardPanel(message) {
  return `<div class="dashboard-panel-empty small">${escapeHtml(message)}</div>`;
}

function renderDashboardSummary(data) {
  const waters = data.waters || [];
  const weather = data.weather || {};
  const target = data.target_species || currentTargetSpecies() || "Auto";
  const focusWater = data.water || waters[0] || {};
  const focusWaterLabel = focusWater.name ? `${focusWater.name}${focusWater.distance ? ` · ${focusWater.distance} mi` : ""}` : "Auto from ZIP";
  const focusWaterDetail = focusWater.type || data.area_type || "ZIP search";
  const catchInsights = data.catch_insights || {};
  const learningLabel = catchInsights.total ? `${catchInsights.sample_quality || "active"} sample` : "no catches";
  const learningDetail = catchInsights.headline || catchInsights.summary || "Log catches to build your pattern.";
  const overall = data.overall || {};
  const focusFit = data.water_profile?.target_fit_score;
  const score = overall.score ?? focusFit;
  const scoreLabel = overall.rating || data.water_profile?.target_fit_label || "";

  return `
    <div class="dashboard-metric-grid">
      ${renderMetric("Target", target, data.target_species_source || "profile")}
      ${renderMetric("Score", Number.isFinite(Number(score)) ? `${Math.round(Number(score))}/100` : "Not available", scoreLabel)}
      ${renderMetric("Wind", `${weather.wind ?? "?"} mph`, weather.fallback ? "fallback weather" : "live weather")}
      ${renderMetric("Focus", focusWaterLabel, focusWaterDetail)}
      ${renderMetric("Learning", learningLabel, learningDetail)}
    </div>
  `;
}

function renderDashboardBrief(data) {
  const waters = data.waters || [];
  const topWater = data.water || waters[0];
  const secondWater = waters[1];
  const target = data.target_species || currentTargetSpecies() || "Auto";

  if (!topWater) {
    return `
      <div class="dashboard-brief-empty">
        <p>No focus water selected yet.</p>
        <a class="hero-action" href="/map">Open Map</a>
        <a class="hero-action secondary-link" href="/waters">Local Waters</a>
      </div>
    `;
  }

  const topWaterIcon = waterIconForRecord(topWater);
  const secondWaterLabel = secondWater ? `${secondWater.name}${secondWater.distance ? ` · ${secondWater.distance} mi` : ""}` : "";
  const catchInsights = data.catch_insights || {};
  const catchSignal = catchInsights.headline || catchInsights.summary || "";
  const waterScore = topWater.local_score ?? data.water_profile?.target_fit_score ?? data.overall?.score;
  const waterScoreLabel = Number.isFinite(Number(waterScore))
    ? `${Math.round(Number(waterScore))} score`
    : "Fit pending";
  const waterIntelAction = topWater.id
    ? `<a class="hero-action secondary-link" href="/water/${encodeURIComponent(topWater.id)}">Water Intel</a>`
    : "";

  return `
    <div class="dashboard-brief-top">
      <img class="dashboard-water-icon" src="${topWaterIcon}" alt="">
      <div>
        <div class="small">Best nearby water</div>
        <h3>${topWater.name || "Selected waterbody"}</h3>
        <div class="small">${topWater.type || "water"}${topWater.city ? ` · ${topWater.city}` : ""}${topWater.distance ? ` · ${topWater.distance} mi` : ""}</div>
      </div>
    </div>
    <div class="dashboard-brief-pills">
      <span class="mini">${target}</span>
      <span class="mini">${waterScoreLabel}</span>
      <span class="mini">${topWater.favorite ? "Favorite" : "Near you"}</span>
      ${secondWaterLabel ? `<span class="mini">Next: ${secondWaterLabel}</span>` : ""}
    </div>
    ${catchSignal ? `
      <div class="dashboard-brief-learning">
        <span class="mini">Catch signal</span>
        <div class="small">${escapeHtml(catchSignal)}</div>
      </div>
    ` : ""}
    <div class="dashboard-brief-actions">
      <a class="hero-action" href="/map">Open Map</a>
      <a class="hero-action secondary-link" href="/waters">Local Waters</a>
      ${waterIntelAction}
    </div>
  `;
}

function renderTripPlan(data) {
  const waters = data.waters || [];
  const focusWater = data.water || waters[0] || {};
  const target = data.target_species || currentTargetSpecies() || "Auto";
  const bestBet = data.best_bet || {};
  const intel = data.smart_intelligence || {};
  const planWhy = bestBet.why || data.smart_intelligence?.summary || "Load intel to see the plan.";
  const waterLabel = focusWater.name || data.location?.city || "Auto from ZIP";
  const waterType = focusWater.type || data.area_type || "water";
  const targetFit = bestBet.fit_label || data.overall?.rating || "Target fit";
  const bestTime = bestBet.time_label || data.best_time?.label || "Any time";
  const bestTimeRange = bestBet.time_range || data.best_time?.time || "";
  const lure = bestBet.lure_name || data.lure_cards?.[0]?.name || "Lure";
  const lurePath = bestBet.lure_image || bestBet.lure_asset?.path || lureIconPath(lure);
  const fishPath = bestBet.fish_image || fishIconPath(bestBet.species || target);
  const lureColors = asList(bestBet.colors).slice(0, 3);
  const reasons = asList(bestBet.reasons).slice(0, 4);
  const decisionFactors = asList(intel.decision_factors).slice(0, 4);
  const catchInsights = data.catch_insights || {};
  const signalReasons = decisionFactors.length ? decisionFactors : (reasons.length ? reasons : asList(intel.positive_signals).slice(0, 4));
  const reasonList = signalReasons.length ? signalReasons : [planWhy];
  const conditionBits = [];
  const weather = data.weather || {};
  if (weather.temp !== undefined && weather.temp !== null && weather.temp !== "") {
    conditionBits.push(`Temp ${weather.temp}°F`);
  }
  if (weather.wind !== undefined && weather.wind !== null && weather.wind !== "") {
    conditionBits.push(`Wind ${weather.wind} mph`);
  }
  if (weather.pressure !== undefined && weather.pressure !== null && weather.pressure !== "") {
    conditionBits.push(`Pressure ${weather.pressure} inHg`);
  }
  if (weather.cloud !== undefined && weather.cloud !== null && weather.cloud !== "") {
    conditionBits.push(`Cloud ${weather.cloud}%`);
  }
  if (bestBet.size) {
    conditionBits.push(`Size ${bestBet.size}`);
  }
  if (bestBet.speed) {
    conditionBits.push(`Retrieve ${bestBet.speed}`);
  }
  const waterAction = focusWater.id
    ? `<a class="hero-action secondary-link" href="/water/${encodeURIComponent(focusWater.id)}">Open Water Intel</a>`
    : `<a class="hero-action secondary-link" href="/map">Open Map</a>`;

  return `
    <div class="trip-plan-shell">
      <div class="trip-plan-hero">
        <div class="trip-plan-media">
          <img class="${speciesIconClass("lg")} trip-plan-fish-art" src="${escapeHtml(fishPath)}" alt="${escapeHtml(bestBet.species || target)}">
          <div class="trip-plan-media-copy">
            <div class="small">Target fit</div>
            <h3>${escapeHtml(target)}</h3>
            <div class="small">${escapeHtml(waterLabel)}${focusWater.city ? ` · ${escapeHtml(focusWater.city)}` : ""}${focusWater.distance ? ` · ${escapeHtml(focusWater.distance)} mi` : ""}</div>
            <div class="trip-plan-pills">
              <span class="mini">${escapeHtml(targetFit)}</span>
              ${focusWater.favorite ? `<span class="mini">Favorite</span>` : ""}
              ${focusWater.manual ? `<span class="mini">Manual</span>` : ""}
              <span class="mini">${escapeHtml(waterType)}</span>
            </div>
          </div>
        </div>

        <div class="trip-plan-lure">
          <img class="recommendation-lure-art lure-art lure-art-md" src="${escapeHtml(lurePath)}" alt="${escapeHtml(lure)}">
          <div class="trip-plan-lure-copy">
            <div class="small">Primary lure</div>
            <strong>${escapeHtml(lure)}</strong>
            <div class="small">${escapeHtml(bestBet.speed || "Presentation guide")}</div>
            ${bestBet.size ? `<div class="small">Size: ${escapeHtml(bestBet.size)}</div>` : ""}
            ${lureColors.length ? `<div class="trip-plan-pills">${lureColors.map(color => `<span class="mini">${escapeHtml(color)}</span>`).join("")}</div>` : ""}
          </div>
        </div>
      </div>

      <div class="trip-plan-grid">
        <div class="trip-plan-item">
          <span>Best time</span>
          <strong>${escapeHtml(bestTime)}</strong>
          <small>${escapeHtml(bestTimeRange)}</small>
        </div>
        <div class="trip-plan-item">
          <span>Retrieve</span>
          <strong>${escapeHtml(bestBet.speed || "Presentation guide")}</strong>
          <small>${escapeHtml(bestBet.size || "Lure size from the selected profile")}</small>
        </div>
        <div class="trip-plan-item trip-plan-wide">
          <span>Why it works</span>
          <strong>${escapeHtml(planWhy)}</strong>
        </div>
      </div>

      ${conditionBits.length ? `
        <div class="trip-plan-condition-row">
          ${conditionBits.slice(0, 5).map(bit => `<span class="mini">${escapeHtml(bit)}</span>`).join("")}
        </div>
      ` : ""}

      ${(catchInsights.headline || catchInsights.takeaway || catchInsights.summary) ? `
        <div class="trip-plan-learning">
          <span class="mini">Learning signal</span>
          <div class="small">${escapeHtml(catchInsights.headline || catchInsights.summary || "Catch history is active.")}</div>
          ${catchInsights.takeaway || catchInsights.weight ? `<div class="small">${escapeHtml(catchInsights.takeaway || catchInsights.weight)}</div>` : ""}
        </div>
      ` : ""}

      <ul class="trip-plan-reason-list">
        ${reasonList.map(reason => `<li>${escapeHtml(reason)}</li>`).join("")}
      </ul>

      <div class="trip-plan-actions">
        ${waterAction}
        <a class="hero-action" href="/reports">Saved Reports</a>
        <button class="secondary" type="button" onclick="openSnapshot()">Trip Snapshot</button>
      </div>
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

focusWaterNode?.addEventListener("change", () => {
  const value = focusWaterNode.value.trim();
  setFocusWaterSelection(value);
  renderFocusWaterSummary(latestData || {});
  loadIntel(currentZip, value).catch(err => {
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

function currentFocusWaterId() {
  return focusWaterNode ? focusWaterNode.value.trim() : currentFocusWaterIdValue;
}

function setFocusWaterSelection(waterId) {
  currentFocusWaterIdValue = String(waterId || "").trim();
  localStorage.setItem(FOCUS_WATER_STORAGE_KEY, currentFocusWaterIdValue);
  if (focusWaterNode && focusWaterNode.value !== currentFocusWaterIdValue) {
    focusWaterNode.value = currentFocusWaterIdValue;
  }
}

function renderFocusWaterSummary(data = {}) {
  if (!focusWaterSummary) return;
  const water = data.water || {};
  const focusName = water.name || data.location?.city || "Auto from ZIP";
  const focusType = water.type || data.area_type || "ZIP-based";
  const fit = water.id ? "Selected waterbody" : "ZIP search";
  focusWaterSummary.textContent = `${fit}: ${focusName} · ${focusType}`;
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

function focusWaterLabel(water) {
  const bits = [water?.name, water?.type, water?.city].filter(Boolean);
  return bits.join(" · ") || "Waterbody";
}

async function loadFocusWaters() {
  if (!focusWaterNode) return;

  try {
    const res = await fetch("/api/map-data");
    const data = await res.json();
    if (!res.ok || !data.ok) {
      throw new Error(data.error || "Could not load waters");
    }

    const rankedWaters = Array.isArray(data.top_waters) && data.top_waters.length ? data.top_waters.slice() : [];
    const records = rankedWaters.length
      ? rankedWaters
      : Array.isArray(data.waters)
        ? data.waters.slice().sort((a, b) => {
            const aRank = Number(Boolean(a.favorite)) * 3 + Number(Boolean(a.manual || String(a.source || "").toLowerCase() === "manual")) * 2 + Number(Boolean(a.stocked_trout));
            const bRank = Number(Boolean(b.favorite)) * 3 + Number(Boolean(b.manual || String(b.source || "").toLowerCase() === "manual")) * 2 + Number(Boolean(b.stocked_trout));
            if (aRank !== bRank) return bRank - aRank;
            const aScore = Number(a.score || a.local_score || 0);
            const bScore = Number(b.score || b.local_score || 0);
            if (aScore !== bScore) return bScore - aScore;
            return String(a.name || "").localeCompare(String(b.name || ""));
          })
        : [];

    const options = ['<option value="">Auto from ZIP</option>'];
    for (const record of records.slice(0, 50)) {
      const label = focusWaterLabel(record);
      options.push(`<option value="${escapeHtml(record.id)}">${escapeHtml(label)}</option>`);
    }
    focusWaterNode.innerHTML = options.join("");

    const saved = localStorage.getItem(FOCUS_WATER_STORAGE_KEY) || "";
    if (saved && Array.from(focusWaterNode.options).some(option => option.value === saved)) {
      focusWaterNode.value = saved;
      currentFocusWaterIdValue = saved;
    } else {
      focusWaterNode.value = "";
      currentFocusWaterIdValue = "";
      localStorage.removeItem(FOCUS_WATER_STORAGE_KEY);
    }
  } catch (err) {
    console.error(err);
    focusWaterNode.innerHTML = '<option value="">Auto from ZIP</option>';
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
        <b><img class="${speciesIconClass("sm")} icon-mini" src="${fishIconPath(c.species)}" alt=""> ${c.species}</b>
        <div class="small">${c.timestamp} · ZIP ${c.zip || "unknown"}${c.waterbody ? ` · ${c.waterbody}` : ""}</div>
        <div><img class="icon-mini lure-art lure-art-sm" src="${lureIconPath(c.lure || "worm")}" alt=""> ${c.lure || "No lure recorded"}</div>
        ${c.gear_labels ? `<div class="small">${Object.entries(c.gear_labels).map(([key, value]) => `${escapeHtml(key)}: ${escapeHtml(value)}`).join(" · ")}</div>` : ""}
        ${c.gear_summary ? `<div class="small">${escapeHtml(c.gear_summary)}</div>` : ""}
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
  const rodNode = el("catchRod");
  const reelNode = el("catchReel");
  const lineNode = el("catchLine");
  const lureGearNode = el("catchGearLure");
  const terminalNode = el("catchTerminal");

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
      notes,
      rod_id: rodNode ? rodNode.value : "",
      reel_id: reelNode ? reelNode.value : "",
      line_id: lineNode ? lineNode.value : "",
      lure_id: lureGearNode ? lureGearNode.value : "",
      terminal_id: terminalNode ? terminalNode.value : "",
    })
  });

  if (!res.ok) {
    alert("Could not save catch.");
    return;
  }

  if (lureNode) lureNode.value = "";
  if (waterbodyNode) waterbodyNode.value = "";
  if (notesNode) notesNode.value = "";
  if (rodNode) rodNode.value = "";
  if (reelNode) reelNode.value = "";
  if (lineNode) lineNode.value = "";
  if (lureGearNode) lureGearNode.value = "";
  if (terminalNode) terminalNode.value = "";

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

async function loadIntel(zip, waterId = currentFocusWaterId()) {
  currentZip = zip;
  if (zipInput) zipInput.value = zip;
  const target = currentTargetSpecies();
  const focusWaterId = String(waterId || "").trim();

  setHTML("status", "Loading fishing intelligence...");

  try {
    const params = new URLSearchParams({ zip });
    if (target) params.set("target_species", target);
    if (focusWaterId) params.set("water_id", focusWaterId);
    const res = await fetch(`/api/intel?${params.toString()}`);
    const data = await res.json();

    if (!res.ok) {
      if (focusWaterId) {
        setFocusWaterSelection("");
        renderFocusWaterSummary({});
        return loadIntel(zip, "");
      }
      setHTML("status", data.error || "Error loading data");
      return;
    }

    latestData = data;
    if (data.water?.id) {
      setFocusWaterSelection(data.water.id);
    } else if (focusWaterId) {
      setFocusWaterSelection(focusWaterId);
    }
    renderFocusWaterSummary(data);
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
  const headline = insights.headline || insights.summary || "Catch history is active.";
  const takeaway = insights.takeaway || insights.weight || "Use catch history as a tie-breaker, not the whole decision.";
  const dominantSpecies = insights.dominant_species || {};
  const dominantLure = insights.dominant_lure || {};
  const dominantWaterbody = insights.dominant_waterbody || {};

  return `
    <div class="insight-summary">
      <div class="insight-summary-head">
        <div>
          <b>What your catches suggest</b>
          <div class="small">${headline}</div>
        </div>
        <span class="mini">${sampleQuality}</span>
      </div>
      <div class="small">${takeaway}</div>
      <div class="insight-chip-row">
        ${dominantSpecies.name ? `<span class="mini"><img class="${speciesIconClass("sm")} icon-mini" src="${fishIconPath(dominantSpecies.name)}" alt=""> ${dominantSpecies.name}${dominantSpecies.count ? ` · ${dominantSpecies.count}` : ""}</span>` : ""}
        ${dominantLure.name ? `<span class="mini"><img class="icon-mini lure-art lure-art-sm" src="${lureIconPath(dominantLure.name)}" alt=""> ${dominantLure.name}${dominantLure.count ? ` · ${dominantLure.count}` : ""}</span>` : ""}
        ${dominantWaterbody.name ? `<span class="mini"><img class="icon-mini" src="${waterIconForRecord({ type: dominantWaterbody.type || dominantWaterbody.name, name: dominantWaterbody.name })}" alt=""> ${dominantWaterbody.name}${dominantWaterbody.count ? ` · ${dominantWaterbody.count}` : ""}</span>` : ""}
      </div>
    </div>

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
    ${topSpecies.map(s => `<div class="pill-line"><img class="${speciesIconClass("sm")} icon-mini" src="${fishIconPath(s.name)}" alt=""> ${s.name}: ${s.count}</div>`).join("")}

    <h3>Top Lures</h3>
    ${topLures.map(l => `<div class="pill-line"><img class="icon-mini lure-art lure-art-sm" src="${lureIconPath(l.name)}" alt=""> ${l.name}: ${l.count}</div>`).join("")}

    <h3>Top Waterbodies</h3>
    ${topWaterbodies.map(w => `<div class="pill-line"><img class="icon-mini" src="${waterIconForRecord({ type: w.type || w.name, name: w.name })}" alt=""> ${w.name}: ${w.count}</div>`).join("")}

    <h3>Local Waterbodies</h3>
    ${localTopWaterbodies.map(w => `<div class="pill-line"><img class="icon-mini" src="${waterIconForRecord({ type: w.type || w.name, name: w.name, manual: w.manual })}" alt=""> ${w.name}: ${w.count}</div>`).join("")}

    <div class="small">Sample quality: ${sampleQuality}</div>
  `;
}

function analyticsRows(rows, emptyText) {
  if (!Array.isArray(rows) || !rows.length) {
    return `<div class="small">${escapeHtml(emptyText)}</div>`;
  }
  return rows.slice(0, 3).map(row => `
    <div class="analytics-evidence-row">
      <span>${escapeHtml(row.label || "Recorded item")}</span>
      <strong>${Number(row.count || row.catch_count || row.usage_events || row.linked_catches || 0)}</strong>
    </div>
  `).join("");
}

function analyticsResult(result) {
  return result.status === "fulfilled" && result.value && result.value.ok ? result.value : null;
}

async function loadAnalyticsEvidence(data = {}) {
  const body = el("analyticsEvidenceBody");
  if (!body) return;
  const params = new URLSearchParams({ limit: "3" });
  const target = currentTargetSpecies();
  const waterbody = String(data.water?.name || "").trim();
  if (target) params.set("species", target);
  if (waterbody) params.set("waterbody", waterbody);
  const query = params.toString();
  try {
    const fetchJson = async path => {
      const response = await fetch(`${path}?${query}`);
      if (!response.ok) return null;
      return response.json();
    };
    const results = await Promise.allSettled([
      fetchJson("/api/analytics/personal"),
      fetchJson("/api/analytics/catch-water"),
      fetchJson("/api/analytics/lures"),
      fetchJson("/api/analytics/gear"),
      fetchJson("/api/analytics/outcomes"),
      fetchJson("/api/analytics/shadow-personal-intelligence"),
    ]);
    const personal = analyticsResult(results[0]);
    const waters = analyticsResult(results[1]);
    const lures = analyticsResult(results[2]);
    const gear = analyticsResult(results[3]);
    const outcomes = analyticsResult(results[4]);
    const shadow = analyticsResult(results[5]);
    if (!personal && !waters && !lures && !gear && !outcomes && !shadow) {
      body.innerHTML = `<div class="small">Recorded analytics are unavailable right now. Catch logging and trip planning remain available.</div>`;
      return;
    }
    const sample = personal?.sample || waters?.sample || lures?.sample || gear?.sample || {};
    const summary = Number(sample.catch_count || sample.catch_gear_links || 0);
    const quality = sample.quality || "limited";
    const topWater = waters?.waterbody_frequency?.rows || personal?.top_waterbodies || [];
    const topLures = lures?.lure_frequency?.rows || personal?.top_lures || [];
    const dayparts = waters?.time_of_day?.rows || [];
    const mostUsed = gear?.most_used || [];
    const firstDaypart = dayparts.find(row => Number(row.count) > 0);
    body.innerHTML = `
      <div class="analytics-evidence-summary">
        <span class="mini">${escapeHtml(quality)} sample</span>
        <span class="small">${summary} recorded ${summary === 1 ? "catch" : "catches"} in this view.</span>
      </div>
      <div class="analytics-evidence-grid">
        <div>
          <b>Water patterns</b>
          ${analyticsRows(topWater, "No named water patterns logged yet.")}
          ${firstDaypart ? `<div class="small">Most recorded: ${escapeHtml(firstDaypart.label)} (${Number(firstDaypart.count)})</div>` : ""}
        </div>
        <div>
          <b>Lure patterns</b>
          ${analyticsRows(topLures, "No lure patterns logged yet.")}
        </div>
        <div>
          <b>Gear history</b>
          ${analyticsRows(mostUsed, "No recorded gear-use events yet.")}
          ${gear?.underused?.length ? `<div class="small">${Number(gear.underused.length)} owned item(s) have no recorded use yet.</div>` : ""}
        </div>
      </div>
      ${outcomes ? `<div class="analytics-outcome-summary">
        <b>Trip outcomes</b>
        <div class="analytics-evidence-row"><span>Completed trips</span><strong>${Number(outcomes.sample?.completed_outcomes || 0)}</strong></div>
        <div class="analytics-evidence-row"><span>Fished / with catch</span><strong>${Number(outcomes.sample?.fished_trips || 0)} / ${Number(outcomes.sample?.trips_with_catches || 0)}</strong></div>
        <div class="small">${outcomes.sample?.catch_success_percent == null ? "Catch success needs completed fished trips." : `${Number(outcomes.sample.catch_success_percent)}% caught a fish; ${Number(outcomes.sample.no_catch_trips || 0)} no-catch trip(s).`}</div>
      </div>` : ""}
      ${shadow ? `<div class="analytics-shadow-summary">
        <b>Personal evidence</b>
        <span class="mini">${escapeHtml(shadow.sample_quality || "none")}</span>
        <div class="small">${escapeHtml(shadow.note || "Shadow evidence is unavailable.")}</div>
        <div class="small">Proposed adjustment: ${Number(shadow.proposed_adjustment || 0) >= 0 ? "+" : ""}${Number(shadow.proposed_adjustment || 0)} (not applied to live ranking).</div>
      </div>` : ""}
      <div class="small analytics-evidence-disclaimer">Patterns show recorded catches and gear use, not total effort or guaranteed effectiveness.</div>
    `;
  } catch (err) {
    console.warn("Personal analytics evidence unavailable", err);
    body.innerHTML = `<div class="small">Recorded analytics are temporarily unavailable.</div>`;
  }
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
  const explanationSections = asList(intel.explanation_sections);
  const positives = asList(intel.positive_signals);
  const cautions = asList(intel.caution_signals);
  const labels = asList(intel.condition_labels).map(c => `<span class="mini">${c}</span>`).join("");
  const rankingFactors = asList(intel.ranking_factors);
  const recommendations = (rankingFactors.length ? rankingFactors : asList(intel.recommendations)).map(r => `
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
  const lureRecommendation = intel.lure_recommendation || intel.lure_asset || {};
  if (sampleSize.local !== undefined || sampleSize.total !== undefined) {
    catchMeta.push(`Sample ${sampleSize.local || 0}/${sampleSize.total || 0}`);
  }
  if (catchHistory.strength) {
    catchMeta.push(`Strength: ${catchHistory.strength}`);
  }

  return `
    <div class="intel-shell">
      <div class="intel-shell-head">
        <div>
          <h3>${intel.headline || "Fishing pattern"}</h3>
          <p>${intel.summary || ""}</p>
        </div>
        <div class="intel-score-card">
          <div class="score">${confidenceScore ?? "?"}</div>
          <div class="small">${confidenceLabel}</div>
          <div class="small">${confidenceBasis}</div>
        </div>
      </div>

      ${intel.ok === false ? `<div class="status-warn">Fallback intelligence is active.</div>` : ""}

      ${lureRecommendation.path ? `
        <div class="intel-recommendation lure-recommendation">
          <img class="recommendation-lure-art lure-art lure-art-md" src="${lureRecommendation.path}" alt="${lureRecommendation.label || "Lure"}">
          <div>
            <b>Primary lure</b>
            <div>${lureRecommendation.label || intel.recommendations?.[1]?.value || "Lure"}</div>
            <div class="small">${intel.recommendations?.[1]?.why || "Chosen from the current lure plan."}</div>
          </div>
        </div>
      ` : ""}

      <div class="intel-chip-row">${labels}</div>

      <div class="intel-grid intel-quad-grid">
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

        <div class="intel-recommendation">
          <b>Confidence basis</b>
          <div class="small">${confidenceBasis || "No basis provided."}</div>
          <div class="small">${intel.fallback_used ? "Fallback logic was used." : "Primary logic stayed active."}</div>
        </div>
      </div>

      ${positives.length ? `<div class="intel-group">
        <h4>Positive signals</h4>
        <div class="intel-chip-row">${positives.map(item => `<span class="mini">${item}</span>`).join("")}</div>
      </div>` : ""}
      ${cautions.length ? `<div class="intel-group">
        <h4>Caution signals</h4>
        <div class="intel-chip-row">${cautions.map(item => `<span class="mini">${item}</span>`).join("")}</div>
      </div>` : ""}

      <div class="intel-grid intel-rationale-grid">${recommendations}</div>

      ${explanationSections.length ? `<div class="intel-group">
        <h4>Why this plan</h4>
        <div class="intel-rationale-list">
          ${explanationSections.map(section => `
            <div class="intel-rationale-card">
              <div class="intel-rationale-head">
                <b>${section.label || "Reason"}</b>
                ${section.value ? `<span class="mini">${section.value}</span>` : ""}
              </div>
              <div class="small">${section.why || ""}</div>
              ${(section.details || []).length ? `<ul class="intel-rationale-details">${section.details.map(item => `<li>${item}</li>`).join("")}</ul>` : ""}
            </div>
          `).join("")}
        </div>
      </div>` : ""}

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
    </div>
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

  if (focusWaterNode) {
    const waterId = data.water?.id || currentFocusWaterIdValue || "";
    if (waterId) {
      focusWaterNode.value = waterId;
      currentFocusWaterIdValue = waterId;
      localStorage.setItem(FOCUS_WATER_STORAGE_KEY, waterId);
    } else if (!focusWaterNode.value) {
      focusWaterNode.value = "";
    }
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
    </div>
  `);
  setHTML("dashboardSummary", renderDashboardSummary(data));
  setHTML("tripPlan", renderTripPlan(data));
  setHTML("dashboardBrief", renderDashboardBrief(data));

  const best = data.best_bet;

  if (best) {
    setHTML("bestBet", `
      <div class="best-bet-layout">
        <img class="${speciesIconClass("lg")} fish-img" src="${best.fish_image}" alt="${best.species}">
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
      <img class="lure-img" src="${l.image}" alt="${l.name}">
      <h3>${l.name}</h3>
      <div class="lure-sub">Good for ${l.species} · ${l.species_score}% species score</div>
      <div class="color-row">${colorPills(l.colors)}</div>
      <p class="small">${l.why}</p>
    </div>
  `).join(""));

  const timeBlocks = Array.isArray(data.time_blocks) ? data.time_blocks : [];
  setHTML("timeBlocks", timeBlocks.length ? timeBlocks.map(t => `
    <div class="time-card">
      <b>${t.label}</b>
      <div class="score">${scoreText(t.score)}</div>
      <div class="small">${t.time}</div>
    </div>
  `).join("") : emptyDashboardPanel("Hourly bite windows are unavailable for this weather update."));

  const hourly = Array.isArray(data.hourly) ? data.hourly : [];
  setHTML("hourly", hourly.length ? hourly.map(h => `
    <div class="hour-row">
      <span>${formatHour(h.hour)}</span>
      <div class="bar-wrap">
        <div class="bar" style="width:${Number.isFinite(Number(h.score)) ? Math.max(0, Math.min(100, Number(h.score))) : 0}%"></div>
      </div>
      <b>${scoreText(h.score)}</b>
    </div>
  `).join("") : emptyDashboardPanel("Hourly bite forecast is unavailable for this weather update."));

  setHTML("species", (data.species || []).slice(0, 8).map(s => `
    <div class="species-card species-with-image">
      <img class="${speciesIconClass("md")} fish-thumb" src="${s.fish_image}" alt="${s.name}">
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
        <img class="icon-mini" src="${waterIconForRecord(w)}" alt="">
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

  const forecast = Array.isArray(data.forecast) ? data.forecast : [];
  setHTML("forecast", forecast.length ? forecast.map(f => `
    <div class="forecast-day">
      <b>${escapeHtml(String(f.date || "Forecast").slice(5) || "Forecast")}</b>
      <div class="score">${scoreText(f.score)}</div>
      <div class="small">${escapeHtml(f.rating || "Rating unavailable")}</div>
      <div class="small">${f.low ?? "?"}° / ${f.high ?? "?"}°</div>
    </div>
  `).join("") : emptyDashboardPanel("7-day forecast is unavailable for this weather update."));

  setHTML("catchInsights", renderInsights(data.catch_insights));
  loadAnalyticsEvidence(data);
}

loadFavorites();
loadCatchGearOptions().finally(() => {
  loadCatchLog();
});
loadFocusWaters().finally(() => {
  loadTargetProfile().finally(() => {
    loadIntel("60543");
  });
});
