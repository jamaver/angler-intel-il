(() => {
  "use strict";
  document.addEventListener("click", (event) => {
    document.querySelectorAll(".ai-more-menu[open]").forEach((menu) => {
      if (!menu.contains(event.target)) menu.removeAttribute("open");
    });
  });
  document.addEventListener("keydown", (event) => {
    if (event.key !== "Escape") return;
    document.querySelectorAll(".ai-more-menu[open]").forEach((menu) => menu.removeAttribute("open"));
  });
})();
