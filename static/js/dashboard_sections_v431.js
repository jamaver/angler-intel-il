/*
  Angler Intel IL v4.3.1 Dashboard Section Controls
*/
(function () {
  "use strict";

  if (location.pathname !== "/") return;

  const SECTIONS = [
    { id: "ai-local-waters-panel-v42", label: "Local Waters" },
    { id: "ai-rig-panel-v43", label: "Rig Setup Guide" }
  ];

  function key(id) {
    return "anglerIntel.section." + id;
  }

  function ensurePanel() {
    let panel = document.getElementById("ai-dashboard-section-controls-v431");
    if (panel) return panel;

    panel = document.createElement("section");
    panel.id = "ai-dashboard-section-controls-v431";
    panel.className = "ai-dashboard-section-controls card";
    panel.innerHTML = `
      <h2>Dashboard Sections</h2>
      <p class="muted">Show or hide newer dashboard panels. Preferences are saved in this browser.</p>
      <div id="aiDashboardSectionButtons"></div>
    `;

    const nav = document.querySelector(".ai-main-tabs");
    if (nav && nav.parentNode) {
      nav.parentNode.insertBefore(panel, nav.nextSibling);
    } else {
      document.body.insertBefore(panel, document.body.firstChild);
    }

    return panel;
  }

  function applyVisibility() {
    for (const section of SECTIONS) {
      const el = document.getElementById(section.id);
      if (!el) continue;

      const stored = localStorage.getItem(key(section.id));
      const visible = stored !== "hidden";
      el.style.display = visible ? "" : "none";
    }

    renderButtons();
  }

  function renderButtons() {
    const panel = ensurePanel();
    const box = panel.querySelector("#aiDashboardSectionButtons");

    box.innerHTML = SECTIONS.map(section => {
      const visible = localStorage.getItem(key(section.id)) !== "hidden";
      return `
        <button type="button" data-section="${section.id}">
          ${visible ? "Hide" : "Show"} ${section.label}
        </button>
      `;
    }).join("");

    box.querySelectorAll("[data-section]").forEach(btn => {
      btn.addEventListener("click", () => {
        const id = btn.getAttribute("data-section");
        const visible = localStorage.getItem(key(id)) !== "hidden";
        localStorage.setItem(key(id), visible ? "hidden" : "visible");
        applyVisibility();
      });
    });
  }

  function init() {
    ensurePanel();
    window.setTimeout(applyVisibility, 300);
    window.setTimeout(applyVisibility, 1200);
    window.setTimeout(applyVisibility, 2500);
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
