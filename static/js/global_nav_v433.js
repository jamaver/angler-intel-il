(function () {
  "use strict";

  const NAV_ITEMS = [
    ["/", "Dashboard"],
    ["/recommendations", "Smart Picks"],
    ["/waters", "Local Waters"],
    ["/species", "Species"],
    ["/rigs", "Rig Setups"],
    ["/reports", "Smart Trip Export"],
    ["/data-tools", "Data Tools"],
    ["/app-health", "App Health"]
  ];

  const MENU_ID = "aiGlobalMenuPanel";
  const BUTTON_ID = "aiGlobalMenuToggle";

  function activeForPath() {
    const path = window.location.pathname || "/";
    if (path === "/" || path === "") return "/";

    const matches = NAV_ITEMS
      .map(([href]) => href)
      .filter(href => href !== "/" && (path === href || path.startsWith(href + "/")))
      .sort((a, b) => b.length - a.length);

    return matches[0] || "/";
  }

  function buildNav() {
    const active = activeForPath();

    const nav = document.createElement("nav");
    nav.className = "ai-main-tabs ai-menu-shell";
    nav.setAttribute("aria-label", "Angler Intel navigation");

    const top = document.createElement("div");
    top.className = "ai-menu-top";

    const brand = document.createElement("a");
    brand.className = "ai-menu-brand";
    brand.href = "/";
    brand.textContent = "🎣 Angler Intel";

    const button = document.createElement("button");
    button.id = BUTTON_ID;
    button.className = "ai-menu-toggle";
    button.type = "button";
    button.setAttribute("aria-controls", MENU_ID);
    button.setAttribute("aria-expanded", "false");
    button.innerHTML = "<span aria-hidden='true'>☰</span> Menu";

    top.appendChild(brand);
    top.appendChild(button);

    const panel = document.createElement("div");
    panel.id = MENU_ID;
    panel.className = "ai-menu-panel";

    for (const [href, label] of NAV_ITEMS) {
      const a = document.createElement("a");
      a.href = href;
      a.textContent = label;
      a.className = href === active ? "ai-main-tab active" : "ai-main-tab";
      panel.appendChild(a);
    }

    nav.appendChild(top);
    nav.appendChild(panel);

    button.addEventListener("click", function () {
      const isOpen = nav.classList.toggle("open");
      button.setAttribute("aria-expanded", isOpen ? "true" : "false");
    });

    document.addEventListener("click", function (event) {
      if (!nav.contains(event.target)) {
        nav.classList.remove("open");
        button.setAttribute("aria-expanded", "false");
      }
    });

    document.addEventListener("keydown", function (event) {
      if (event.key === "Escape") {
        nav.classList.remove("open");
        button.setAttribute("aria-expanded", "false");
      }
    });

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
