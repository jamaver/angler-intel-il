(function () {
  "use strict";

  const PAGE = window.__TACKLE_LOCKER__ || {};
  PAGE.searchSettings = PAGE.settings || PAGE.searchSettings || {};
  PAGE.importDraft = PAGE.importDraft || null;
  PAGE.searchResults = PAGE.searchResults || {};
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

  function getSettings() {
    return PAGE.searchSettings || {};
  }

  function providerIconFor(provider) {
    const key = String(provider || "").toLowerCase();
    const map = {
      amazon: "/static/gear/providers/amazon.svg",
      walmart: "/static/gear/providers/walmart.svg",
      structured: "/static/gear/providers/structured.svg",
      local: "/static/gear/providers/local.svg",
      manual: "/static/gear/providers/manual.svg",
      cache: "/static/gear/providers/cache.svg",
      generic: "/static/gear/providers/manual.svg",
    };
    return map[key] || "/static/gear/providers/manual.svg";
  }

  function fieldSourceLabel(value) {
    const key = String(value || "").toLowerCase();
    const labels = {
      page_metadata: "Page metadata",
      page_title: "Page title",
      page_text: "Page text",
      query_match: "Search hint match",
      imported: "Imported",
      manual: "Manual",
      local_upload: "Local upload",
      source_page: "Source page",
    };
    return labels[key] || value || "Imported";
  }

  function summarizeFieldSource(field, item) {
    const sources = item && typeof item.field_sources === "object" && item.field_sources ? item.field_sources : {};
    return fieldSourceLabel(sources[field] || "");
  }

  function renderImportReviewPanel(item) {
    const panel = byId("gearImportReview");
    if (!panel) return;
    const draft = item && typeof item === "object" ? item : null;
    if (!draft || (!draft.provider && !draft.source_url && !draft.query_match_applied && !draft.image_url)) {
      panel.innerHTML = `
        <div class="gear-import-review-empty">
          Imported products will appear here with source details and key field provenance before you save them.
        </div>
      `;
      return;
    }

    const fields = [
      ["Brand", draft.brand, summarizeFieldSource("brand", draft)],
      ["Model", draft.model, summarizeFieldSource("model", draft)],
      ["Display name", draft.display_name, summarizeFieldSource("display_name", draft)],
      ["Category", draft.category, summarizeFieldSource("category", draft)],
      ["Image", draft.image_url || draft.image || "", summarizeFieldSource("image_url", draft)],
      ["Length", draft.length_label || draft.length_ft || "", summarizeFieldSource("length_label", draft)],
      ["Power", draft.power || "", summarizeFieldSource("power", draft)],
      ["Action", draft.action || "", summarizeFieldSource("action", draft)],
      ["Lure weight", [draft.lure_weight_min_oz, draft.lure_weight_max_oz].filter(v => v !== null && v !== undefined && v !== "").join(" to "), summarizeFieldSource("lure_weight_min_oz", draft)],
      ["Line rating", [draft.line_rating_min_lb, draft.line_rating_max_lb].filter(v => v !== null && v !== undefined && v !== "").join(" to "), summarizeFieldSource("line_rating_min_lb", draft)],
      ["Lure type", draft.lure_type || "", summarizeFieldSource("lure_type", draft)],
      ["Reel type", draft.reel_type || "", summarizeFieldSource("reel_type", draft)],
      ["Line type", draft.line_type || "", summarizeFieldSource("line_type", draft)],
      ["Source URL", draft.source_url || draft.source_page_url || "", "Source page"],
      ["Source", draft.source_name || draft.provider || "", fieldSourceLabel(draft.query_match_applied ? "query_match" : draft.provider ? "page_metadata" : "manual")],
    ].filter(row => row[1]);

    const badges = [
      draft.provider ? `<span class="gear-badge">${escapeHtml(String(draft.provider).replaceAll("_", " "))}</span>` : "",
      draft.confidence ? `<span class="gear-badge">${escapeHtml(String(draft.confidence).replaceAll("_", " "))}</span>` : "",
      draft.query_match_applied ? `<span class="gear-badge gear-badge-favorite">Search hint match</span>` : "",
      draft.raw_provider_data_cached ? `<span class="gear-badge">Cached source</span>` : "",
      draft.image_source ? `<span class="gear-badge">${escapeHtml(String(draft.image_source).replaceAll("_", " "))}</span>` : "",
    ].filter(Boolean).join("");

    const summary = draft.product_summary || draft.import_summary || draft.description || "Imported gear is ready for review.";

    panel.innerHTML = `
      <section class="gear-import-review-card">
        <div class="gear-import-review-head">
          <div>
            <p class="eyebrow section-eyebrow">Import review</p>
            <h3>${escapeHtml(draft.display_name || [draft.brand, draft.model].filter(Boolean).join(" ") || "Imported product")}</h3>
            <p class="gear-muted">${escapeHtml(summary)}</p>
          </div>
          <div class="gear-badge-row">${badges}</div>
        </div>
        <div class="gear-import-review-grid">
          <div class="gear-import-review-media">
            <img class="gear-image-preview" src="${escapeHtml(draft.image || draft.image_url || "/static/gear/fallback/generic.svg")}" alt="${escapeHtml(draft.display_name || "Imported gear")}" onerror="this.src='/static/gear/fallback/generic.svg'">
            <div class="gear-import-review-meta">
              <p><strong>Source:</strong> ${escapeHtml(draft.source_name || draft.provider || "Imported product")}</p>
              ${draft.source_url ? `<p><strong>URL:</strong> <a href="${escapeHtml(draft.source_url)}" target="_blank" rel="noreferrer">${escapeHtml(draft.source_url)}</a></p>` : ""}
              ${draft.query_match_label ? `<p><strong>Best match:</strong> ${escapeHtml(draft.query_match_label)}</p>` : ""}
              ${draft.query_hint ? `<p><strong>Search hint:</strong> ${escapeHtml(draft.query_hint)}</p>` : ""}
            </div>
          </div>
          <div class="gear-import-review-fields">
            <div class="gear-import-review-note">
              Review the imported values below, then edit the form fields above before saving. Manual changes in the form always win.
            </div>
            <div class="gear-import-review-table">
              <div class="gear-import-review-row gear-import-review-row-head">
                <span>Field</span>
                <span>Value</span>
                <span>Source</span>
              </div>
              ${fields.map(([label, value, source]) => `
                <div class="gear-import-review-row">
                  <span>${escapeHtml(label)}</span>
                  <span>${escapeHtml(Array.isArray(value) ? value.join(", ") : value)}</span>
                  <span>${escapeHtml(source)}</span>
                </div>
              `).join("")}
            </div>
          </div>
        </div>
      </section>
    `;
  }

  function setSettings(settings) {
    PAGE.searchSettings = settings || {};
  }

  function applySettingsToControls() {
    const settings = getSettings();
    const scope = byId("gearSearchScope");
    const importCategory = byId("gearImportCategory");
    if (scope) scope.value = settings.search_scope_default || "both";
    if (byId("gearOnlineLookup")) byId("gearOnlineLookup").checked = Boolean(settings.online_lookup_enabled);
    if (byId("gearDefaultScope")) byId("gearDefaultScope").value = settings.search_scope_default || "both";
    if (byId("gearAllowRemoteImages")) byId("gearAllowRemoteImages").checked = Boolean(settings.allow_remote_images);
    if (byId("gearCacheLookupResults")) byId("gearCacheLookupResults").checked = settings.cache_lookup_results !== false;
    if (byId("gearPreferManufacturerSpecs")) byId("gearPreferManufacturerSpecs").checked = settings.prefer_manufacturer_specs !== false;
    if (importCategory && !importCategory.value) importCategory.value = "misc";
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
    PAGE.importDraft = null;
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
    setImagePreview("/static/gear/fallback/generic.svg");
    const imageUpload = byId("gearImageUpload");
    if (imageUpload) imageUpload.value = "";
    renderImportReviewPanel(null);
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

    const draft = PAGE.importDraft && typeof PAGE.importDraft === "object" ? PAGE.importDraft : null;
    if (draft) {
      payload.provider = draft.provider || "";
      payload.provider_product_id = draft.provider_product_id || "";
      payload.provider_icon = draft.provider_icon || "";
      payload.image_url = draft.image_url || "";
      payload.image_source = draft.image_source || "";
      payload.identifiers = draft.identifiers || {};
      payload.specifications = draft.specifications || {};
      payload.field_sources = draft.field_sources || {};
      payload.price = draft.price ?? null;
      payload.availability = draft.availability || "";
      payload.raw_provider_data_cached = Boolean(draft.raw_provider_data_cached);
      payload.query_match_applied = Boolean(draft.query_match_applied);
      payload.query_match_source = draft.query_match_source || "";
      payload.query_match_label = draft.query_match_label || "";
      payload.query_hint = draft.query_hint || "";
      if (!payload.notes && (draft.product_summary || draft.import_summary || draft.description)) {
        payload.notes = draft.product_summary || draft.import_summary || draft.description;
      }
      if (!payload.image && draft.image_url && !payload.image) {
        payload.image = draft.image_url;
      }
    }

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

  function resultDuplicateNote(item) {
    const duplicates = Array.isArray(item.duplicate_matches) ? item.duplicate_matches : [];
    if (!duplicates.length) return "";
    const first = duplicates[0];
    const name = first && first.display_name ? first.display_name : "an existing item";
    return `
      <div class="gear-duplicate-note">
        Possible match already in your locker.
        <button type="button" class="gear-inline-link" data-gear-open-existing="${escapeHtml(first && first.id ? first.id : "")}">${escapeHtml(name)}</button>
      </div>
    `;
  }

  function renderResultCard(item, options = {}) {
    if (!item) return "";
    const title = item.display_name || [item.brand, item.model].filter(Boolean).join(" ") || "Catalog result";
    const subtitle = [item.brand, item.model].filter(Boolean).join(" · ") || item.source_name || "Catalog source";
    const sourceLine = [
      item.source_name || "Catalog source",
      item.provider ? `Provider: ${item.provider}` : "",
      item.confidence ? `${item.confidence} confidence` : "",
      item.retrieved_at ? `Updated ${item.retrieved_at}` : "",
    ].filter(Boolean).join(" · ");
    const sourceUrl = item.source_url ? `<a href="${escapeHtml(item.source_url)}" target="_blank" rel="noreferrer">Source URL</a>` : "";
    const actionLabel = options.actionLabel || "Review";
    const actionAttr = options.actionAttr || "data-gear-review-result";
    const actionValue = options.actionValue || "";
    const duplicate = resultDuplicateNote(item);
    const duplicateMatches = Array.isArray(item.duplicate_matches) ? item.duplicate_matches : [];
    const summary = item.product_summary || item.import_summary || item.description || "";
    const importHint = item.query_match_applied ? `<p class="gear-import-summary">Suggested match from search hints${item.query_match_source ? ` - ${escapeHtml(item.query_match_source)}` : ""}</p>` : "";
    const specs = item.specifications && typeof item.specifications === "object"
      ? Object.entries(item.specifications).slice(0, 4).map(([key, value]) => `<span>${escapeHtml(String(key).replaceAll("_", " "))}: ${escapeHtml(value)}</span>`).join("")
      : "";
    const identifiers = item.identifiers && typeof item.identifiers === "object"
      ? Object.entries(item.identifiers).slice(0, 3).map(([key, value]) => `<span>${escapeHtml(String(key).toUpperCase())}: ${escapeHtml(value)}</span>`).join("")
      : "";
    const statusBadges = [
      item.match_group ? `<span class="gear-badge">${escapeHtml(item.match_group === "owned" ? "Owned" : item.match_group === "cached" ? "Cached" : item.match_group === "online" ? "Online" : item.match_group)}</span>` : "",
      item.raw_provider_data_cached ? `<span class="gear-badge">Cached</span>` : "",
      duplicateMatches.length ? `<span class="gear-badge gear-badge-favorite">Possible duplicate</span>` : "",
    ].filter(Boolean).join("");
    const providerIcon = providerIconFor(item.provider);

    return `
      <article class="gear-catalog-result" data-result-key="${escapeHtml(actionValue)}">
        <div class="gear-catalog-result-head">
          <div>
            <h3>${escapeHtml(title)}</h3>
            <p class="gear-muted">${escapeHtml(sourceLine || subtitle)}</p>
          </div>
          <img class="gear-provider-icon" src="${escapeHtml(item.provider_icon || providerIcon)}" alt="${escapeHtml(item.provider || "provider")}">
          <div class="gear-badge-row">${statusBadges}</div>
        </div>
        <div class="gear-catalog-result-body">
          <img class="gear-catalog-result-image" src="${escapeHtml(item.display_image || item.image || item.fallback_image || "")}" alt="${escapeHtml(title)}" onerror="this.src='${escapeHtml(item.fallback_image || "/static/gear/fallback/generic.svg")}'">
          <div class="gear-catalog-result-copy">
            <p class="gear-muted">${escapeHtml(subtitle)}</p>
            ${importHint}
            ${summary ? `<p class="gear-import-summary">${escapeHtml(summary)}</p>` : ""}
            ${specs ? `<div class="gear-item-specs">${specs}</div>` : ""}
            ${identifiers ? `<div class="gear-item-specs">${identifiers}</div>` : ""}
            ${item.price ? `<p class="gear-muted">Price: ${escapeHtml(item.price)}</p>` : ""}
            ${item.availability ? `<p class="gear-muted">Availability: ${escapeHtml(item.availability)}</p>` : ""}
            ${duplicate}
          </div>
        </div>
        <div class="gear-catalog-result-actions">
          ${sourceUrl}
          <button type="button" class="gear-toolbar-button" ${actionAttr}="${escapeHtml(actionValue)}">${escapeHtml(actionLabel)}</button>
        </div>
      </article>
    `;
  }

  function renderSearchResults(payload) {
    const box = byId("catalogResults");
    if (!box) return;

    const localOwned = Array.isArray(payload?.local?.owned) ? payload.local.owned : [];
    const localCached = Array.isArray(payload?.local?.cached) ? payload.local.cached : [];
    const online = Array.isArray(payload?.online?.matches) ? payload.online.matches : [];
    const messages = Array.isArray(payload?.messages) ? payload.messages : [];

    PAGE.searchResults = {
      localOwned,
      localCached,
      online,
      queryMatches: [],
    };

    const localCount = localOwned.length + localCached.length;
    const onlineCount = online.length;
    const localSections = [
      localOwned.length ? `<section class="gear-results-group"><h3>Owned gear</h3><div class="gear-catalog-results">${localOwned.map((item, idx) => renderResultCard(item, { actionLabel: "Edit", actionAttr: "data-gear-review-item", actionValue: `local-owned-${idx}` })).join("")}</div></section>` : "",
      localCached.length ? `<section class="gear-results-group"><h3>Cached catalog</h3><div class="gear-catalog-results">${localCached.map((item, idx) => renderResultCard(item, { actionLabel: "Review / add", actionAttr: "data-gear-review-item", actionValue: `local-cached-${idx}` })).join("")}</div></section>` : "",
    ].filter(Boolean).join("");

    const onlineSection = onlineCount
      ? `<section class="gear-results-group"><h3>Online results</h3><div class="gear-catalog-results">${online.map((item, idx) => renderResultCard(item, { actionLabel: "Review / import", actionAttr: "data-gear-review-item", actionValue: `online-${idx}` })).join("")}</div></section>`
      : `<section class="gear-results-group"><h3>Online results</h3><p class="gear-empty">${payload?.scope === "online" ? "No online products were returned. Try a different query, enable a provider, or paste a product URL." : "No online results yet. Enable online lookup or paste a product URL to import one."}</p></section>`;

    const messageMarkup = messages.length
      ? `<div class="gear-result-messages">${messages.map(message => `<p class="gear-empty">${escapeHtml(message)}</p>`).join("")}</div>`
      : "";

    const providerCards = Array.isArray(payload?.providers) && payload.providers.length
      ? `<section class="gear-results-group gear-provider-panel"><h3>Online providers</h3><div class="gear-provider-grid">${payload.providers.map(provider => `
          <article class="gear-provider-card">
            <img class="gear-provider-icon" src="${escapeHtml(provider.icon || providerIconFor(provider.provider_id))}" alt="${escapeHtml(provider.name || provider.provider_id || "provider")}">
            <div>
              <strong>${escapeHtml(provider.name || provider.provider_id || "Provider")}</strong>
              <p class="gear-muted">${escapeHtml(provider.status || (provider.enabled ? "enabled" : "disabled"))}${provider.requires_credentials ? " · credentials needed" : ""}</p>
            </div>
          </article>
        `).join("")}</div></section>`
      : "";

    if (!localCount && !onlineCount && !messages.length) {
      box.innerHTML = `
        <p class="gear-empty">No matching local or online products were found.</p>
        <div class="gear-empty-actions">
          <a class="gear-toolbar-button gear-toolbar-anchor" href="#gear-form">Add manually</a>
          <button type="button" class="gear-toolbar-button" id="gearFocusUrl">Paste product URL</button>
        </div>
      `;
      const focusUrl = byId("gearFocusUrl");
      if (focusUrl) focusUrl.addEventListener("click", () => byId("gearProductUrl")?.focus());
      return;
    }

    box.innerHTML = `
      ${messageMarkup}
      ${providerCards}
      ${localSections || `<p class="gear-empty">No local matches in the locker or cache.</p>`}
      ${onlineSection}
      <p class="gear-empty">Local results are shown first. Review imported products before saving them to your locker.</p>
    `;
  }

  async function searchCatalog() {
    const query = byId("catalogQuery").value.trim();
    const category = byId("catalogCategory").value;
    const scope = byId("gearSearchScope")?.value || getSettings().search_scope_default || "both";
    const box = byId("catalogResults");
    if (!box) return;
    if (!query) {
      box.innerHTML = "<p class='gear-empty'>Enter a search term to search local gear and optional online sources.</p>";
      return;
    }

    box.innerHTML = "<p class='gear-empty'>Searching local gear, cache, and enabled online providers...</p>";
    try {
      const params = new URLSearchParams({ q: query, scope });
      if (category) params.set("category", category);
      const res = await fetch(`/api/gear/search?${params.toString()}`);
      const data = await res.json();
      renderSearchResults(data);
    } catch (err) {
      box.innerHTML = `<p class='gear-empty'>Search failed: ${escapeHtml(err)}</p>`;
    }
  }

  async function importFromUrl() {
    const url = byId("gearProductUrl").value.trim();
    const query = byId("gearImportQuery").value.trim();
    const category = byId("gearImportCategory").value;
    const box = byId("catalogResults");
    if (!box) return;
    if (!url) {
      box.innerHTML = "<p class='gear-empty'>Paste a product URL first.</p>";
      return;
    }

    box.innerHTML = "<p class='gear-empty'>Importing product page...</p>";
    try {
      const res = await fetch("/api/gear/import/url", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ url, category, query }),
      });
      const data = await res.json();
      if (!res.ok || !data.ok) {
        throw new Error(data.error || `HTTP ${res.status}`);
      }
      const product = data.product || {};
      PAGE.importDraft = product;
      PAGE.searchResults = {
        ...(PAGE.searchResults || {}),
        queryMatches: Array.isArray(data.query_matches) ? data.query_matches : [],
      };
      populateForm(product);
      renderImportReviewPanel(product);
      box.innerHTML = `
        <section class="gear-results-group">
          <h3>Imported product</h3>
          <p class="gear-empty">The imported product has been loaded into the form for review. Confirm the details before saving.</p>
          ${renderResultCard(product, { actionLabel: "Review in form", actionAttr: "data-gear-review-import", actionValue: "imported" })}
        </section>
        ${Array.isArray(data.query_matches) && data.query_matches.length ? `<section class="gear-results-group"><h3>Suggested query matches</h3><div class="gear-catalog-results">${data.query_matches.map((item, idx) => renderResultCard(item, { actionLabel: idx === 0 ? "Use best match" : "Review match", actionAttr: "data-gear-review-result", actionValue: `query-${idx}` })).join("")}</div></section>` : ""}
        ${Array.isArray(data.duplicate_matches) && data.duplicate_matches.length ? `<section class="gear-results-group"><h3>Possible duplicates</h3><div class="gear-catalog-results">${data.duplicate_matches.map((item, idx) => renderResultCard(item, { actionLabel: "Open existing", actionAttr: "data-gear-open-existing", actionValue: item.id || `duplicate-${idx}` })).join("")}</div></section>` : ""}
      `;
    } catch (err) {
      box.innerHTML = `<p class='gear-empty'>URL import failed: ${escapeHtml(err)}</p>`;
    }
  }

  async function uploadGearImage(file) {
    if (!file) return null;
    const formData = new FormData();
    formData.append("image", file);
    const res = await fetch("/api/gear/upload-image", {
      method: "POST",
      body: formData,
    });
    const data = await res.json().catch(() => ({}));
    if (!res.ok || !data.ok) {
      throw new Error(data.error || `HTTP ${res.status}`);
    }
    return data;
  }

  function setImagePreview(url) {
    const preview = byId("gearImagePreview");
    if (preview) preview.src = url || "/static/gear/fallback/generic.svg";
  }

  function populateForm(item) {
    if (!item) return;
    PAGE.importDraft = item && (item.provider || item.provider_product_id || item.image_url || item.specifications || item.identifiers) ? item : null;
    const form = getForm();
    if (form) form.dataset.editingId = item.id || "";
    byId("gearFormTitle").textContent = `Edit ${item.display_name || "gear"}`;
    setField("Id", item.id);
    byId("gearCategory").value = item.category || "misc";
    byId("gearStatus").value = item.status || "owned";
    setField("Brand", item.brand);
    setField("Model", item.model);
    setField("DisplayName", item.display_name);
    setField("Image", item.image || item.image_url || item.display_image);
    setImagePreview(item.image || item.image_url || item.display_image || "/static/gear/fallback/generic.svg");
    setField("SourceName", item.source_name);
    setField("SourceUrl", item.source_url || item.source_page_url);
    setField("RetrievedAt", item.retrieved_at);
    byId("gearConfidence").value = item.confidence || "user-added";
    setField("Notes", item.notes || item.product_summary || item.import_summary || item.description || "");
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

    renderImportReviewPanel(item);
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
    else if (action === "archive" || action === "retire") url = `/api/gear/items/${encodeURIComponent(itemId)}/${action === "retire" ? "retire" : "archive"}`;
    else if (action === "delete") {
      const confirmed = window.confirm("Delete this gear item permanently? This cannot be undone.");
      if (!confirmed) return;
      url = `/api/gear/items/${encodeURIComponent(itemId)}/delete`;
    }
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

  function lookupSearchResult(key) {
    const search = PAGE.searchResults || {};
    const parts = String(key || "").split("-");
    if (parts.length === 2 && parts[0] === "online") {
      const idx = Number.parseInt(parts[1], 10);
      return Number.isFinite(idx) && Array.isArray(search.online) ? search.online[idx] : null;
    }
    if (parts.length === 2 && parts[0] === "query") {
      const idx = Number.parseInt(parts[1], 10);
      return Number.isFinite(idx) && Array.isArray(search.queryMatches) ? search.queryMatches[idx] : null;
    }
    if (parts.length < 3) return null;
    const group = parts[0];
    const bucket = parts[1];
    const idx = Number.parseInt(parts[2], 10);
    if (!Number.isFinite(idx)) return null;
    if (group === "local" && bucket === "owned") return Array.isArray(search.localOwned) ? search.localOwned[idx] : null;
    if (group === "local" && bucket === "cached") return Array.isArray(search.localCached) ? search.localCached[idx] : null;
    if (group === "online") return Array.isArray(search.online) ? search.online[idx] : null;
    if (group === "query") return Array.isArray(search.queryMatches) ? search.queryMatches[idx] : null;
    return null;
  }

  function openExistingItem(itemId) {
    const item = getItem(itemId) || lookupSearchResult(itemId);
    if (!item) return;
    const card = document.querySelector(`[data-item-id="${CSS.escape(String(item.id || ""))}"]`);
    if (card) {
      card.scrollIntoView({ behavior: "smooth", block: "center" });
      card.classList.add("gear-card-highlight");
      window.setTimeout(() => card.classList.remove("gear-card-highlight"), 1500);
    }
    populateForm(item);
  }

  function reviewSearchResult(key) {
    const item = lookupSearchResult(key);
    if (!item) return;
    populateForm(item);
    getForm()?.scrollIntoView({ behavior: "smooth", block: "start" });
  }

  function wireItemButtons() {
    document.addEventListener("click", event => {
      const button = event.target.closest("button, a");
      if (!button) return;

      const action = button.getAttribute("data-gear-action");
      if (action) {
        const itemId = button.getAttribute("data-gear-id");
        const item = getItem(itemId);
        if (action === "edit" && item) {
          populateForm(item);
        } else {
          mutateItem(itemId, action);
        }
        return;
      }

      const reviewKey = button.getAttribute("data-gear-review-item") || button.getAttribute("data-gear-review-result");
      if (reviewKey) {
        reviewSearchResult(reviewKey);
        return;
      }

      const importKey = button.getAttribute("data-gear-review-import");
      if (importKey) {
        populateForm(PAGE.importDraft || lookupSearchResult(importKey));
        return;
      }

      const openExisting = button.getAttribute("data-gear-open-existing");
      if (openExisting) {
        openExistingItem(openExisting);
      }
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

  async function saveSettings() {
    const payload = {
      search_scope_default: byId("gearDefaultScope")?.value || "both",
      online_lookup_enabled: Boolean(byId("gearOnlineLookup")?.checked),
      allow_remote_images: Boolean(byId("gearAllowRemoteImages")?.checked),
      cache_lookup_results: Boolean(byId("gearCacheLookupResults")?.checked),
      prefer_manufacturer_specs: Boolean(byId("gearPreferManufacturerSpecs")?.checked),
      enabled_providers: getSettings().enabled_providers || {},
    };

    try {
      const res = await fetch("/api/gear/settings", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      const data = await res.json();
      if (!res.ok || !data.ok) {
        throw new Error(data.error || `HTTP ${res.status}`);
      }
      setSettings(data.settings || payload);
      applySettingsToControls();
      alert("Search preferences saved.");
    } catch (err) {
      alert(`Unable to save gear preferences: ${err}`);
    }
  }

  function init() {
    applySettingsToControls();
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
    byId("gearImportUrlButton").addEventListener("click", importFromUrl);
    byId("gearSaveSettings").addEventListener("click", saveSettings);
    const imageUpload = byId("gearImageUpload");
    if (imageUpload) {
      imageUpload.addEventListener("change", async () => {
        const file = imageUpload.files && imageUpload.files[0] ? imageUpload.files[0] : null;
        if (!file) return;
        try {
          const upload = await uploadGearImage(file);
          if (upload && upload.image_url) {
            setField("Image", upload.image_url);
            setField("Notes", getField("Notes") || "Uploaded local image");
            setImagePreview(upload.image_url);
          }
        } catch (err) {
          alert(`Image upload failed: ${err.message || err}`);
        } finally {
          imageUpload.value = "";
        }
      });
    }
    byId("catalogQuery").addEventListener("keydown", event => {
      if (event.key === "Enter") {
        event.preventDefault();
        searchCatalog();
      }
    });
    byId("gearProductUrl").addEventListener("keydown", event => {
      if (event.key === "Enter") {
        event.preventDefault();
        importFromUrl();
      }
    });
    byId("gearDefaultScope").addEventListener("change", () => {
      const scope = byId("gearDefaultScope").value;
      setSettings({ ...getSettings(), search_scope_default: scope });
      if (byId("gearSearchScope")) byId("gearSearchScope").value = scope;
    });
    byId("gearSearchScope").addEventListener("change", () => {
      const scope = byId("gearSearchScope").value;
      setSettings({ ...getSettings(), search_scope_default: scope });
      byId("gearDefaultScope").value = scope;
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
