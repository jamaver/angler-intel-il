/*
  Angler Intel IL v4.4.1 Dashboard Section Controls
  Shows/hides newer dashboard panels. Preferences are saved in this browser.
*/
(function () {
  "use strict";

  if (location.pathname !== "/") return;

  const SECTIONS = [
    { id: "ai-recommendations-panel-v44", label: "Smart Recommendations" },
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
      <p class="muted">Show or hide dashboard helper panels. Preferences are saved in this browser.</p>
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

  function visibleFor(id) {
    return localStorage.getItem(key(id)) !== "hidden";
  }

  function applyVisibility() {
    for (const section of SECTIONS) {
      const el = document.getElementById(section.id);
      if (!el) continue;
      el.style.display = visibleFor(section.id) ? "" : "none";
    }

    renderButtons();
  }

  function renderButtons() {
    const panel = ensurePanel();
    const box = panel.querySelector("#aiDashboardSectionButtons");

    box.innerHTML = SECTIONS.map(section => {
      const visible = visibleFor(section.id);
      return `
        <button type="button" data-section="${section.id}">
          ${visible ? "Hide" : "Show"} ${section.label}
        </button>
      `;
    }).join("");

    box.querySelectorAll("[data-section]").forEach(btn => {
      btn.addEventListener("click", () => {
        const id = btn.getAttribute("data-section");
        const visible = visibleFor(id);
        localStorage.setItem(key(id), visible ? "hidden" : "visible");
        applyVisibility();
      });
    });
  }

  function init() {
    ensurePanel();

    // Other dashboard panels load asynchronously, so apply a few times.
    window.setTimeout(applyVisibility, 300);
    window.setTimeout(applyVisibility, 1200);
    window.setTimeout(applyVisibility, 2500);
    window.setTimeout(applyVisibility, 4000);
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
