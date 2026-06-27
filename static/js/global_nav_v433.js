/*
  Angler Intel IL v4.3.3
  Safe global navigation cleanup.

  This updates/creates the nav tabs in the browser instead of rewriting Python
  triple-quoted HTML strings.
*/
(function () {
  "use strict";

  const NAV_ITEMS = [
    ["/", "Dashboard"],
    ["/waters", "Local Waters"],
    ["/species", "Species"],
    ["/rigs", "Rig Setups"],
    ["/reports", "Saved Reports"],
    ["/data-tools", "Data Tools"],
    ["/app-health", "App Health"],
    ["/admin", "Admin"],
    ["/exports", "Export"]
  ];

  function activeForPath() {
    const path = window.location.pathname || "/";

    if (path === "/" || path === "") return "/";

    const matches = NAV_ITEMS
      .map(([href]) => href)
      .filter(href => href !== "/" && path === href || path.startsWith(href + "/"))
      .sort((a, b) => b.length - a.length);

    return matches[0] || "/";
  }

  function buildNav() {
    const active = activeForPath();
    const nav = document.createElement("nav");

    nav.className = "ai-main-tabs";
    nav.setAttribute("aria-label", "Angler Intel navigation");

    for (const [href, label] of NAV_ITEMS) {
      const a = document.createElement("a");
      a.href = href;
      a.textContent = label;
      a.className = href === active ? "ai-main-tab active" : "ai-main-tab";
      nav.appendChild(a);
    }

    return nav;
  }

  function installNav() {
    const fresh = buildNav();
    const existing = document.querySelector(".ai-main-tabs");

    if (existing && existing.parentNode) {
      existing.replaceWith(fresh);
      return;
    }

    const body = document.body;
    if (!body) return;

    const firstMeaningful = body.querySelector("h1, main, section, .card");
    if (firstMeaningful && firstMeaningful.parentNode) {
      firstMeaningful.parentNode.insertBefore(fresh, firstMeaningful);
    } else {
      body.insertBefore(fresh, body.firstChild);
    }
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", installNav);
  } else {
    installNav();
  }
})();
