(function () {
  "use strict";

  const DESCRIPTIONS = {
    "/": "Dashboard overview with forecasts, local waters, rig setups, and smart fishing picks.",
    "/recommendations": "Best water and rig recommendations based on active species, local waters, season, and distance.",
    "/waters": "Browse the local Illinois waters database and open waterbody-specific fishing intel.",
    "/species": "Manage common freshwater fish and optional species used by the recommendation engine.",
    "/rigs": "Practical rigging guides by fish, lure type, line, and conditions.",
    "/reports": "Create and view saved offline fishing reports on this Raspberry Pi.",
    "/data-tools": "Validate and inspect app data before upgrades or recommendation changes.",
    "/app-health": "Check files, routes, backups, reports, and general app health.",
    "/admin": "Local maintenance tools for service status, backups, reports, and logs.",
    "/exports": "Export user data, backups, catches, favorites, and app data."
  };

  function currentSection() {
    const path = window.location.pathname || "/";
    if (path === "/" || path === "") return "/";

    const keys = Object.keys(DESCRIPTIONS)
      .filter(k => k !== "/" && (path === k || path.startsWith(k + "/")))
      .sort((a, b) => b.length - a.length);

    return keys[0] || path;
  }

  function addDescription() {
    const section = currentSection();
    const description = DESCRIPTIONS[section];
    if (!description) return;

    const h1 = document.querySelector("h1");
    if (!h1) return;
    if (document.querySelector(".ai-page-description-v442")) return;

    const p = document.createElement("p");
    p.className = "ai-page-description-v442";
    p.textContent = description;
    h1.insertAdjacentElement("afterend", p);
  }

  function addVersionBadge() {
    const nav = document.querySelector(".ai-main-tabs");
    if (!nav || nav.querySelector(".ai-version-badge-v442")) return;

    const badge = document.createElement("span");
    badge.className = "ai-version-badge-v442";
    badge.textContent = "v4.4.2";

    const top = nav.querySelector(".ai-menu-top");
    if (top) top.appendChild(badge);
  }

  function init() {
    addDescription();
    addVersionBadge();
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
