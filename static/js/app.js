const form = document.getElementById("searchForm");
const zipInput = document.getElementById("zipInput");
const favoriteName = document.getElementById("favoriteName");

let currentZip = "60543";
let latestData = null;

function el(id) {
  return document.getElementById(id);
}

function setHTML(id, html) {
  const node = el(id);
  if (node) node.innerHTML = html;
}

if (form) {
  form.addEventListener("submit", e => {
    e.preventDefault();
    loadIntel(zipInput.value);
  });
}

function formatHour(hour) {
  const suffix = hour >= 12 ? "PM" : "AM";
  let h = hour % 12;
  if (h === 0) h = 12;
  return `${h} ${suffix}`;
}

function exportPDF() {
  window.print();
}

function openSnapshot() {
  window.open(`/snapshot?zip=${encodeURIComponent(currentZip)}`, "_blank");
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
        <b>${c.species}</b>
        <div class="small">${c.timestamp} · ZIP ${c.zip || "unknown"}</div>
        <div>🎣 ${c.lure || "No lure recorded"}</div>
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
  const notesNode = el("catchNotes");

  const species = speciesNode ? speciesNode.value : "";
  const lure = lureNode ? lureNode.value.trim() : "";
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
      notes
    })
  });

  if (!res.ok) {
    alert("Could not save catch.");
    return;
  }

  if (lureNode) lureNode.value = "";
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

  setHTML("status", "Loading fishing intelligence...");

  try {
    const res = await fetch(`/api/intel?zip=${encodeURIComponent(zip)}`);
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
    ${topSpecies.map(s => `<div class="pill-line">🐟 ${s.name}: ${s.count}</div>`).join("")}

    <h3>Top Lures</h3>
    ${topLures.map(l => `<div class="pill-line">🎣 ${l.name}: ${l.count}</div>`).join("")}
  `;
}

function render(data) {
  const loc = data.location || {};
  currentZip = loc.zip || currentZip;

  if (zipInput) zipInput.value = currentZip;

  setHTML("status", `
    <h2>${loc.city || "Unknown"}, ${loc.state || ""}</h2>
    <div class="score">${data.overall?.score ?? "?"}/100</div>
    <div>${data.overall?.rating ?? ""}</div>
    <div class="small">Detected water type: ${data.area_type || "unknown"}</div>
    <div class="small">Generated: ${data.generated_at || ""}</div>
    <button class="secondary" onclick="exportPDF()">Export Current Page</button>
    <button class="secondary" onclick="openSnapshot()">Trip Snapshot PDF</button>
  `);

  const best = data.best_bet;

  if (best) {
    setHTML("bestBet", `
      <div class="best-bet-layout">
        <img class="fish-img" src="${best.fish_image}" alt="${best.species}">
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

  setHTML("conditions", `
    🌡 ${data.weather?.temp ?? "?"}°F<br>
    💨 ${data.weather?.wind ?? "?"} mph<br>
    📉 ${data.weather?.pressure ?? "?"} inHg<br>
    ☁️ ${data.weather?.cloud ?? "?"}% cloud cover
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
      <img class="fish-thumb" src="${s.fish_image}" alt="${s.name}">
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
        📍 <b>${w.name}</b>
        <div class="small">${w.type}${w.distance ? ` - ${w.distance} mi` : ""}</div>
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
loadIntel("60543");
