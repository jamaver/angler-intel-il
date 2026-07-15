(function () {
  "use strict";

  const PAGE = window.__TACKLE_LOCKER__ || {};
  const FORM_ID = "gearForm";
  const CATEGORY_FIELDS = [
    "rod",
    "reel",
    "line",
    "lure",
    "terminal",
    "misc",
  ];

  function escapeHtml(value) {
    return String(value ?? "")
      .replaceAll("&", "&amp;")
      .replaceAll("<", "&lt;")
      .replaceAll(">", "&gt;")
      .replaceAll('"', "&quot;")
      .replaceAll("'", "&#039;");
  }

  function byId(id) {
    return document.getElementById(id);
  }

  function getForm() {
    return byId(FORM_ID);
  }

  function getItem(itemId) {
    const items = Array.isArray(PAGE.items) ? PAGE.items : [];
    return items.find(item => String(item && item.id ? item.id : "") === String(itemId || ""));
  }

  function setField(name, value) {
    const el = document.getElementById(`gear${name}`);
    if (!el) return;
    if (el.type === "checkbox") {
      el.checked = Boolean(value);
      return;
    }
    el.value = value == null ? "" : String(value);
  }

  function getField(name) {
    const el = document.getElementById(`gear${name}`);
    if (!el) return "";
    if (el.type === "checkbox") return el.checked;
    return el.value.trim();
  }

  function clearForm() {
    const form = getForm();
    if (form) form.dataset.editingId = "";
    byId("gearFormTitle").textContent = "Add gear";
    [
      "Id",
      "Brand",
      "Model",
      "DisplayName",
      "Image",
      "SourceName",
      "SourceUrl",
      "RetrievedAt",
      "Notes",
      "LengthFt",
      "LengthLabel",
      "Power",
      "Action",
      "Pieces",
      "LureWeightMin",
      "LureWeightMax",
      "LineMin",
      "LineMax",
      "TechniqueTags",
      "SpeciesTags",
      "ReelType",
      "GearRatio",
      "MaxDrag",
      "LineCapacity",
      "WeightOz",
      "Handedness",
      "LineType",
      "StrengthLb",
      "DiameterEquivalent",
      "LineColor",
      "LengthYd",
      "LureType",
      "LureColor",
      "LureWeight",
      "HookSize",
      "DepthMin",
      "DepthMax",
      "LureTechniqueTags",
      "LureSpeciesTags",
      "Quantity",
      "Subtype",
      "TerminalSize",
      "TerminalWeight",
      "TerminalHookSize",
      "TerminalQuantity",
      "MiscNotes",
    ].forEach(name => {
      const el = byId(`gear${name}`);
      if (el && el.type === "checkbox") el.checked = name === "AutoDisplayName";
      if (el && el.type !== "checkbox") el.value = "";
    });
    byId("gearStatus").value = "owned";
    byId("gearCategory").value = "rod";
    byId("gearConfidence").value = "user-added";
    byId("gearFavorite").checked = false;
    byId("gearAutoDisplayName").checked = true;
    syncCategoryFields();
  }

  function syncCategoryFields() {
    const category = byId("gearCategory").value;
    CATEGORY_FIELDS.forEach(name => {
      const block = document.querySelector(`[data-gear-category-block="${name}"]`);
      if (block) block.style.display = name === category ? "" : "none";
    });
    if (byId("gearAutoDisplayName")?.checked) {
      maybeFillDisplayName();
    }
  }

  function maybeFillDisplayName() {
    const category = byId("gearCategory").value;
    const brand = getField("Brand");
    const model = getField("Model");
    let displayName = "";
    if (category === "rod") {
      const lengthLabel = getField("LengthLabel");
      const power = getField("Power").replaceAll("_", " ");
      const action = getField("Action").replaceAll("_", " ");
      displayName = [brand, model, lengthLabel, power, action].filter(Boolean).join(" ");
    } else if (category === "reel") {
      const reelType = getField("ReelType").replaceAll("_", " ");
      const ratio = getField("GearRatio");
      displayName = [brand, model, reelType, ratio ? `${ratio}:1` : ""].filter(Boolean).join(" ");
    } else if (category === "line") {
      const lineType = getField("LineType").replaceAll("_", " ");
      const strength = getField("StrengthLb");
      displayName = [brand, model, strength ? `${strength} lb` : "", lineType].filter(Boolean).join(" ");
    } else if (category === "lure") {
      const lureType = getField("LureType").replaceAll("_", " ");
      const color = getField("LureColor").replaceAll("_", " ");
      displayName = [brand, model, lureType, color].filter(Boolean).join(" ");
    } else if (category === "terminal") {
      const subtype = getField("Subtype").replaceAll("_", " ");
      const size = getField("TerminalSize");
      displayName = [brand, model, subtype, size].filter(Boolean).join(" ");
    } else {
      displayName = [brand, model].filter(Boolean).join(" ");
    }
    if (displayName) {
      byId("gearDisplayName").value = displayName;
    }
  }

  function collectPayload() {
    const payload = {
      id: getField("Id"),
      category: byId("gearCategory").value,
      status: byId("gearStatus").value,
      brand: getField("Brand"),
      model: getField("Model"),
      display_name: getField("DisplayName"),
      image: getField("Image"),
      source_name: getField("SourceName"),
      source_url: getField("SourceUrl"),
      retrieved_at: getField("RetrievedAt"),
      confidence: byId("gearConfidence").value,
      notes: getField("Notes"),
      favorite: byId("gearFavorite").checked,
    };

    const category = payload.category;
    if (category === "rod") {
      payload.length_ft = getField("LengthFt");
      payload.length_label = getField("LengthLabel");
      payload.power = getField("Power");
      payload.action = getField("Action");
      payload.pieces = getField("Pieces");
      payload.lure_weight_min_oz = getField("LureWeightMin");
      payload.lure_weight_max_oz = getField("LureWeightMax");
      payload.line_rating_min_lb = getField("LineMin");
      payload.line_rating_max_lb = getField("LineMax");
      payload.technique_tags = getField("TechniqueTags");
      payload.species_tags = getField("SpeciesTags");
    } else if (category === "reel") {
      payload.reel_type = getField("ReelType");
      payload.gear_ratio = getField("GearRatio");
      payload.max_drag_lb = getField("MaxDrag");
      payload.line_capacity = getField("LineCapacity");
      payload.weight_oz = getField("WeightOz");
      payload.handedness = getField("Handedness");
    } else if (category === "line") {
      payload.line_type = getField("LineType");
      payload.strength_lb = getField("StrengthLb");
      payload.diameter_equivalent = getField("DiameterEquivalent");
      payload.color = getField("LineColor");
      payload.length_yd = getField("LengthYd");
    } else if (category === "lure") {
      payload.lure_type = getField("LureType");
      payload.color = getField("LureColor");
      payload.weight_oz = getField("LureWeight");
      payload.hook_size = getField("HookSize");
      payload.depth_min_ft = getField("DepthMin");
      payload.depth_max_ft = getField("DepthMax");
      payload.technique_tags = getField("LureTechniqueTags");
      payload.species_tags = getField("LureSpeciesTags");
      payload.quantity = getField("Quantity");
    } else if (category === "terminal") {
      payload.subtype = getField("Subtype");
      payload.size = getField("TerminalSize");
      payload.weight_oz = getField("TerminalWeight");
      payload.hook_size = getField("TerminalHookSize");
      payload.quantity = getField("TerminalQuantity");
    }

    return payload;
  }

  function renderCatalogResults(results) {
    const box = byId("catalogResults");
    if (!box) return;

    if (!Array.isArray(results) || !results.length) {
      box.innerHTML = "<p class='gear-empty'>No catalog matches. Manual entry is still available.</p>";
      return;
    }

    box.innerHTML = results.map(item => `
      <article class="gear-catalog-result">
        <div class="gear-catalog-result-head">
          <div>
            <h3>${escapeHtml(item.display_name || `${item.brand || ""} ${item.model || ""}`.trim() || "Catalog result")}</h3>
            <p class="gear-muted">${escapeHtml(item.source_name || "Catalog cache")} · ${escapeHtml(item.confidence || "low")} confidence</p>
          </div>
          <button type="button" data-catalog-use="${escapeHtml(item.display_name || "")}">Use</button>
        </div>
        <p class="gear-muted">${escapeHtml(item.brand || "")}${item.model ? ` · ${escapeHtml(item.model)}` : ""}</p>
        ${item.source_url ? `<a href="${escapeHtml(item.source_url)}" target="_blank" rel="noreferrer">Source URL</a>` : ""}
      </article>
    `).join("");

    box.querySelectorAll("[data-catalog-use]").forEach(button => {
      button.addEventListener("click", () => {
        const displayName = button.getAttribute("data-catalog-use") || "";
        const found = results.find(item => String(item.display_name || "") === displayName);
        if (found) {
          populateForm(found);
        }
      });
    });
  }

  async function searchCatalog() {
    const query = byId("catalogQuery").value.trim();
    const category = byId("catalogCategory").value;
    const box = byId("catalogResults");
    if (!box) return;
    if (!query) {
      box.innerHTML = "<p class='gear-empty'>Enter a search term to query the catalog cache.</p>";
      return;
    }

    box.innerHTML = "<p class='gear-empty'>Searching catalog cache...</p>";
    try {
      const params = new URLSearchParams({ q: query });
      if (category) params.set("category", category);
      const res = await fetch(`/api/gear/catalog/search?${params.toString()}`);
      const data = await res.json();
      renderCatalogResults(Array.isArray(data.products) ? data.products : []);
    } catch (err) {
      box.innerHTML = `<p class='gear-empty'>Catalog lookup failed: ${escapeHtml(err)}</p>`;
    }
  }

  function populateForm(item) {
    if (!item) return;
    const form = getForm();
    if (form) form.dataset.editingId = item.id || "";
    byId("gearFormTitle").textContent = `Edit ${item.display_name || "gear"}`;
    setField("Id", item.id);
    byId("gearCategory").value = item.category || "misc";
    byId("gearStatus").value = item.status || "owned";
    setField("Brand", item.brand);
    setField("Model", item.model);
    setField("DisplayName", item.display_name);
    setField("Image", item.image);
    setField("SourceName", item.source_name);
    setField("SourceUrl", item.source_url);
    setField("RetrievedAt", item.retrieved_at);
    byId("gearConfidence").value = item.confidence || "user-added";
    setField("Notes", item.notes);
    byId("gearFavorite").checked = Boolean(item.favorite);
    byId("gearAutoDisplayName").checked = false;

    setField("LengthFt", item.length_ft);
    setField("LengthLabel", item.length_label);
    setField("Power", item.power);
    setField("Action", item.action);
    setField("Pieces", item.pieces);
    setField("LureWeightMin", item.lure_weight_min_oz);
    setField("LureWeightMax", item.lure_weight_max_oz);
    setField("LineMin", item.line_rating_min_lb);
    setField("LineMax", item.line_rating_max_lb);
    setField("TechniqueTags", Array.isArray(item.technique_tags) ? item.technique_tags.join(", ") : item.technique_tags);
    setField("SpeciesTags", Array.isArray(item.species_tags) ? item.species_tags.join(", ") : item.species_tags);

    setField("ReelType", item.reel_type);
    setField("GearRatio", item.gear_ratio);
    setField("MaxDrag", item.max_drag_lb);
    setField("LineCapacity", item.line_capacity);
    setField("WeightOz", item.weight_oz);
    setField("Handedness", item.handedness);

    setField("LineType", item.line_type);
    setField("StrengthLb", item.strength_lb);
    setField("DiameterEquivalent", item.diameter_equivalent);
    setField("LineColor", item.color);
    setField("LengthYd", item.length_yd);

    setField("LureType", item.lure_type);
    setField("LureColor", item.color);
    setField("LureWeight", item.weight_oz);
    setField("HookSize", item.hook_size);
    setField("DepthMin", item.depth_min_ft);
    setField("DepthMax", item.depth_max_ft);
    setField("LureTechniqueTags", Array.isArray(item.technique_tags) ? item.technique_tags.join(", ") : item.technique_tags);
    setField("LureSpeciesTags", Array.isArray(item.species_tags) ? item.species_tags.join(", ") : item.species_tags);
    setField("Quantity", item.quantity);

    setField("Subtype", item.subtype);
    setField("TerminalSize", item.size);
    setField("TerminalWeight", item.weight_oz);
    setField("TerminalHookSize", item.hook_size);
    setField("TerminalQuantity", item.quantity);

    syncCategoryFields();
    getForm().scrollIntoView({ behavior: "smooth", block: "start" });
  }

  async function submitForm(event) {
    event.preventDefault();
    const form = getForm();
    const editingId = form.dataset.editingId || "";
    const payload = collectPayload();
    if (editingId) payload.id = editingId;

    try {
      const res = await fetch("/api/gear/items", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      const data = await res.json();
      if (!res.ok || !data.ok) {
        throw new Error(data.error || `HTTP ${res.status}`);
      }
      window.location.reload();
    } catch (err) {
      alert(`Unable to save gear: ${err}`);
    }
  }

  async function mutateItem(itemId, action) {
    if (!itemId) return;
    let url = "";
    if (action === "favorite") url = `/api/gear/items/${encodeURIComponent(itemId)}/favorite`;
    else if (action === "archive") url = `/api/gear/items/${encodeURIComponent(itemId)}/archive`;
    else return;

    try {
      const res = await fetch(url, { method: "POST", headers: { "Content-Type": "application/json" } });
      const data = await res.json();
      if (!res.ok || !data.ok) throw new Error(data.error || `HTTP ${res.status}`);
      window.location.reload();
    } catch (err) {
      alert(`Unable to update gear: ${err}`);
    }
  }

  function wireItemButtons() {
    document.querySelectorAll("[data-gear-action]").forEach(button => {
      button.addEventListener("click", () => {
        const action = button.getAttribute("data-gear-action");
        const itemId = button.getAttribute("data-gear-id");
        const item = getItem(itemId);
        if (action === "edit" && item) {
          populateForm(item);
        } else {
          mutateItem(itemId, action);
        }
      });
    });
  }

  function wireFilters() {
    const search = byId("gearSearchInput");
    const category = byId("gearCategoryFilter");
    const status = byId("gearStatusFilter");

    function applyFilters() {
      const q = search.value.trim().toLowerCase();
      const categoryValue = category.value;
      const statusValue = status.value;
      document.querySelectorAll("[data-gear-card]").forEach(card => {
        const text = card.innerText.toLowerCase();
        const matchesQuery = !q || text.includes(q);
        const matchesCategory = !categoryValue || card.getAttribute("data-category") === categoryValue;
        const matchesStatus = !statusValue || card.getAttribute("data-status") === statusValue;
        card.style.display = matchesQuery && matchesCategory && matchesStatus ? "" : "none";
      });
    }

    search.addEventListener("input", applyFilters);
    category.addEventListener("change", applyFilters);
    status.addEventListener("change", applyFilters);
    byId("gearClearFilters").addEventListener("click", () => {
      search.value = "";
      category.value = "";
      status.value = "";
      applyFilters();
    });
  }

  function init() {
    const form = getForm();
    if (form) form.addEventListener("submit", submitForm);

    byId("gearCategory").addEventListener("change", syncCategoryFields);
    ["gearBrand", "gearModel", "gearLengthLabel", "gearPower", "gearAction", "gearReelType", "gearGearRatio", "gearLineType", "gearStrengthLb", "gearLureType", "gearLureColor", "gearSubtype"].forEach(id => {
      const el = byId(id);
      if (el) el.addEventListener("input", maybeFillDisplayName);
    });
    byId("gearAutoDisplayName").addEventListener("change", () => {
      if (byId("gearAutoDisplayName").checked) maybeFillDisplayName();
    });
    byId("gearFormReset").addEventListener("click", clearForm);
    byId("catalogSearchButton").addEventListener("click", searchCatalog);
    byId("catalogQuery").addEventListener("keydown", event => {
      if (event.key === "Enter") {
        event.preventDefault();
        searchCatalog();
      }
    });

    wireItemButtons();
    wireFilters();
    syncCategoryFields();
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();

