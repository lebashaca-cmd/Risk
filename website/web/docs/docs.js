"use strict";
(function () {
  var home = document.querySelector("[data-home]");
  var onDocsHost = /^docs\./i.test(location.hostname);
  var mainOrigin = onDocsHost ? location.protocol + "//" + location.host.replace(/^docs\./i, "") : "";
  // Root-relative links point at the main site. On the docs host they need the main site's address.
  if (onDocsHost) {
    var links = document.querySelectorAll("a[data-main], a[data-home]");
    for (var i = 0; i < links.length; i++) links[i].setAttribute("href", mainOrigin + links[i].getAttribute("href"));
  }

  var side = document.querySelector("[data-side]");
  var menu = document.querySelector("[data-menu]");
  if (menu && side) {
    menu.addEventListener("click", function () {
      var open = side.classList.toggle("open");
      menu.setAttribute("aria-expanded", open ? "true" : "false");
    });
  }

  // Filter on the command pages.
  var filter = document.querySelector("[data-filter]");
  if (filter) {
    var items = document.querySelectorAll("[data-filter-list] .cmd");
    var none = document.querySelector("[data-filter-empty]");
    filter.addEventListener("input", function () {
      var q = filter.value.trim().toLowerCase();
      var shown = 0;
      for (var i = 0; i < items.length; i++) {
        var hit = !q || (items[i].getAttribute("data-search") || "").indexOf(q) !== -1;
        items[i].hidden = !hit;
        if (hit) shown++;
      }
      if (none) none.hidden = shown > 0;
    });
  }

  // Search across guides, commands and variables.
  var input = document.querySelector("[data-search-input]");
  var box = document.querySelector("[data-search-results]");
  if (!input || !box) return;
  var index = null;
  var loading = null;
  var active = -1;

  function load() {
    if (index) return Promise.resolve(index);
    if (!loading) {
      loading = fetch("search.json").then(function (r) { return r.json(); }).then(function (data) { index = data; return data; }).catch(function () { index = []; return index; });
    }
    return loading;
  }

  function score(item, q) {
    var t = item.t.toLowerCase();
    var bare = t.replace(/^[!{]/, "");
    if (t === q || bare === q) return 100;
    if (t.indexOf(q) === 0 || bare.indexOf(q) === 0) return 80;
    if (t.indexOf(q) !== -1) return 60;
    if (item.g.toLowerCase().indexOf(q) !== -1) return 30;
    if (item.x.toLowerCase().indexOf(q) !== -1) return 20;
    return 0;
  }

  function show(q) {
    box.textContent = "";
    active = -1;
    if (!q) { box.hidden = true; return; }
    var scored = [];
    for (var i = 0; i < index.length; i++) {
      var s = score(index[i], q);
      if (s) scored.push({ s: s, item: index[i] });
    }
    scored.sort(function (a, b) { return b.s - a.s; });
    scored = scored.slice(0, 9);
    if (!scored.length) {
      var li = document.createElement("li");
      li.className = "none";
      li.textContent = "Nothing matches that. Try a command name or a simpler word.";
      box.appendChild(li);
    }
    scored.forEach(function (entry) {
      var li = document.createElement("li");
      var a = document.createElement("a");
      a.href = entry.item.u;
      var strong = document.createElement("strong");
      strong.textContent = entry.item.t;
      var small = document.createElement("small");
      small.textContent = entry.item.g + (entry.item.x ? " · " + entry.item.x : "");
      a.appendChild(strong);
      a.appendChild(small);
      li.appendChild(a);
      box.appendChild(li);
    });
    box.hidden = false;
  }

  function move(step) {
    var links = box.querySelectorAll("a");
    if (!links.length) return;
    if (active >= 0) links[active].removeAttribute("aria-selected");
    active = (active + step + links.length) % links.length;
    links[active].setAttribute("aria-selected", "true");
    links[active].scrollIntoView({ block: "nearest" });
  }

  input.addEventListener("focus", load);
  input.addEventListener("input", function () {
    var q = input.value.trim().toLowerCase();
    load().then(function () { show(q); });
  });
  input.addEventListener("keydown", function (event) {
    if (event.key === "ArrowDown") { event.preventDefault(); move(1); }
    else if (event.key === "ArrowUp") { event.preventDefault(); move(-1); }
    else if (event.key === "Enter") {
      var links = box.querySelectorAll("a");
      var target = links[active >= 0 ? active : 0];
      if (target) { event.preventDefault(); location.href = target.getAttribute("href"); }
    } else if (event.key === "Escape") { box.hidden = true; input.blur(); }
  });
  document.addEventListener("click", function (event) {
    if (!box.contains(event.target) && event.target !== input) box.hidden = true;
  });
  document.addEventListener("keydown", function (event) {
    var tag = (event.target && event.target.tagName) || "";
    if (event.key === "/" && tag !== "INPUT" && tag !== "TEXTAREA") { event.preventDefault(); input.focus(); }
  });
})();
