"use strict";
(function () {
  var root = document.getElementById("root");
  var state = { page: "overview", status: null, timer: null, cleanup: null };

  // ---------------------------------------------------------------- helpers
  function h(tag, attrs) {
    var el = document.createElement(tag);
    for (var k in attrs || {}) {
      var v = attrs[k];
      if (v === false || v == null) continue;
      if (k === "class") el.className = v;
      else if (k.slice(0, 2) === "on") el.addEventListener(k.slice(2), v);
      else if (k === "value") el.value = v;
      else el.setAttribute(k, v === true ? "" : v);
    }
    for (var i = 2; i < arguments.length; i++) add(el, arguments[i]);
    return el;
  }
  function add(el, c) {
    if (c == null || c === false) return;
    if (Array.isArray(c)) c.forEach(function (x) { add(el, x); });
    else el.appendChild(typeof c === "string" || typeof c === "number" ? document.createTextNode(String(c)) : c);
  }
  function clear(el) { while (el.firstChild) el.removeChild(el.firstChild); }
  function num(n) { return Number(n || 0).toLocaleString(); }
  function dur(s) {
    var d = Math.floor(s / 86400), hr = Math.floor(s % 86400 / 3600), m = Math.floor(s % 3600 / 60);
    return (d ? d + "d " : "") + (d || hr ? hr + "h " : "") + m + "m";
  }
  function when(ts) { return ts ? new Date(ts * 1000).toLocaleString() : ""; }

  function toast(text, bad) {
    var t = h("div", { class: "toast" + (bad ? " err" : ""), role: bad ? "alert" : "status" }, text);
    var stack = document.getElementById("toasts");
    if (!stack) { stack = h("div", { id: "toasts", class: "toasts" }); document.body.appendChild(stack); }
    stack.appendChild(t);
    setTimeout(function () { t.remove(); }, bad ? 7000 : 3500);
  }

  function api(method, path, body) {
    return fetch("/api/" + path, {
      method: method, headers: { "X-Panel": "1", "Content-Type": "application/json" },
      body: body === undefined ? undefined : JSON.stringify(body),
    }).then(function (r) {
      return r.json().catch(function () { return {}; }).then(function (data) {
        if (!r.ok) throw new Error(data.error || "Something went wrong (" + r.status + ").");
        return data;
      });
    });
  }
  function act(label, promise, then) {
    return promise.then(function (d) { toast(label); if (then) then(d); return d; }).catch(function (e) { toast(e.message, true); });
  }

  function confirmBox(title, text, word, go) {
    var input = word ? h("input", { placeholder: 'Type ' + word, "aria-label": "Type " + word }) : null;
    var yes = h("button", { class: "btn bad", disabled: !!word }, "Confirm");
    var overlay = h("div", { class: "overlay" }, h("div", { class: "modal", role: "dialog", "aria-modal": "true" },
      h("h2", null, title), h("p", { class: "muted" }, text), input,
      h("div", { class: "actions" }, h("button", { class: "btn quiet", onclick: function () { overlay.remove(); } }, "Cancel"), yes)));
    if (input) input.addEventListener("input", function () { yes.disabled = input.value.trim().toUpperCase() !== word; });
    yes.addEventListener("click", function () { overlay.remove(); go(); });
    document.body.appendChild(overlay);
    (input || yes).focus();
  }

  function field(label, input) { return h("div", { class: "field" }, h("label", null, label), input); }
  function table(head, rows, empty) {
    if (!rows.length) return h("p", { class: "muted" }, empty || "Nothing here yet.");
    return h("table", { class: "table" }, h("thead", null, h("tr", null, head.map(function (x) { return h("th", null, x); }))), h("tbody", null, rows));
  }
  function searchBox(onInput, placeholder) {
    return h("input", { class: "search", type: "search", placeholder: placeholder || "Search", "aria-label": placeholder || "Search", oninput: function (e) { onInput(e.target.value.trim().toLowerCase()); } });
  }

  // ---------------------------------------------------------------- setup
  function setup(existing) {
    clear(root);
    var url = h("input", { value: existing ? existing.url : "", placeholder: "http://12.34.56.78:25239", autocomplete: "off" });
    var key = h("input", { type: "password", placeholder: existing && existing.keyHint ? "Saved (" + existing.keyHint + "). Leave blank to keep it." : "Your OWNER_PANEL_KEY", autocomplete: "off" });
    var go = h("button", { class: "btn", onclick: function () {
      go.disabled = true;
      fetch("/local/config", { method: "POST", headers: { "X-Panel": "1", "Content-Type": "application/json" }, body: JSON.stringify({ url: url.value, key: key.value }) })
        .then(function (r) { return r.json().then(function (d) { if (!r.ok) throw new Error(d.error); }); })
        .then(function () { toast("Connected."); start(); })
        .catch(function (e) { toast(e.message, true); go.disabled = false; });
    } }, "Connect");
    root.appendChild(h("div", { class: "center" },
      h("h1", null, "Risk Control Panel"),
      h("p", { class: "lead" }, "Connect this app to your bot. Both values are on your bot's host: the address is where its web server listens (the SERVER_PORT), and the key is the OWNER_PANEL_KEY environment variable you set."),
      h("div", { class: "card" }, field("Bot address", url), h("p", null), field("Owner key", key),
        h("p", { class: "muted small" }, "The key is saved only in a file next to this program, and it is never sent over the network. Each request is signed with it instead. If your address starts with http://, the signed requests can't be forged, but what the bot answers is readable on the network."),
        h("div", { class: "actions" }, existing && existing.configured ? h("button", { class: "btn quiet", onclick: start }, "Back") : null, go))));
  }

  // ---------------------------------------------------------------- shell
  var PAGES = [["overview", "Overview"], ["servers", "Servers"], ["banned", "Banned servers"], ["commands", "Commands"], ["users", "Blocked users"], ["staff", "Staff and roles"], ["prices", "Prices"], ["console", "Console"], ["bot", "Bot and cogs"], ["settings", "Connection"]];

  function frame() {
    clear(root);
    var content = h("div", { class: "page", id: "page" });
    var bar = h("div", { class: "bar", id: "bar" });
    root.appendChild(h("div", { class: "shell" },
      h("nav", { class: "rail", "aria-label": "Sections" },
        h("div", { class: "brand" }, "Risk Control", h("small", null, "Owner only")),
        PAGES.map(function (p) { return h("button", { class: "nav", "data-page": p[0], "aria-current": p[0] === state.page ? "page" : false, onclick: function () { go(p[0]); } }, p[1]); }),
        h("div", { class: "grow" }),
        h("button", { class: "nav", onclick: function () { fetch("/local/quit", { method: "POST", headers: { "X-Panel": "1" } }); document.body.textContent = "You can close this window."; } }, "Quit panel")),
      h("div", { class: "main" }, bar, content)));
    refreshBar();
  }

  function refreshBar() {
    api("GET", "status").then(function (s) {
      state.status = s;
      var bar = document.getElementById("bar");
      if (!bar) return;
      clear(bar);
      bar.appendChild(h("span", null, h("span", { class: "dot on" }), s.name || "Bot", " is online"));
      bar.appendChild(h("span", null, "Ping ", s.latencyMs == null ? "?" : s.latencyMs + "ms"));
      bar.appendChild(h("span", null, "Up ", dur(s.uptime)));
      bar.appendChild(h("span", null, num(s.servers), " servers, ", num(s.members), " members"));
      if (s.maintenance.on) bar.appendChild(h("span", { class: "tag warn" }, "Maintenance on"));
    }).catch(function (e) {
      var bar = document.getElementById("bar");
      if (!bar) return;
      clear(bar);
      bar.appendChild(h("span", null, h("span", { class: "dot off" }), e.message));
    });
  }

  function go(page) {
    if (state.cleanup) { state.cleanup(); state.cleanup = null; }
    state.page = page;
    document.querySelectorAll(".nav[data-page]").forEach(function (b) { b.setAttribute("aria-current", b.getAttribute("data-page") === page ? "page" : "false"); });
    var el = document.getElementById("page");
    clear(el);
    el.scrollTop = 0;
    var wrap = h("div", { class: "wrap" });
    el.appendChild(wrap);
    var view = VIEWS[page];
    view(wrap);
    refreshBar();
  }
  function reload() { go(state.page); }

  function load(wrap, path, render) {
    wrap.appendChild(h("p", { class: "muted", id: "loading" }, "Loading..."));
    api("GET", path).then(function (d) { var l = wrap.querySelector("#loading"); if (l) l.remove(); render(d); })
      .catch(function (e) { var l = wrap.querySelector("#loading"); if (l) l.remove(); wrap.appendChild(h("p", { class: "tag bad" }, e.message)); });
  }

  // ---------------------------------------------------------------- views
  var VIEWS = {};

  VIEWS.overview = function (wrap) {
    wrap.appendChild(h("h1", null, "Overview"));
    wrap.appendChild(h("p", { class: "lead" }, "Everything about the bot at a glance, plus the switches that affect every server."));
    load(wrap, "status", function (s) {
      wrap.appendChild(h("div", { class: "tiles" },
        [["Servers", num(s.servers)], ["Members", num(s.members)], ["Commands", num(s.commands)], ["Ping", s.latencyMs == null ? "?" : s.latencyMs + "ms"], ["Uptime", dur(s.uptime)], ["Cogs", s.cogs.length], ["Turned off", num(s.disabled)], ["Blocked users", num(s.blocked)]]
          .map(function (t) { return h("div", { class: "tile" }, h("b", null, t[1]), h("span", null, t[0])); })));
      var failed = Object.keys(s.failed || {});
      if (failed.length) wrap.appendChild(h("div", { class: "card" }, h("h2", null, "Parts that failed to load"), failed.map(function (k) { return h("p", null, h("b", null, k), " ", h("span", { class: "muted" }, s.failed[k])); })));

      var on = h("input", { type: "checkbox", id: "maint" });
      on.checked = s.maintenance.on;
      var msg = h("input", { value: s.maintenance.message, placeholder: "Shown to members, for example: Back at 5pm" });
      wrap.appendChild(h("div", { class: "card" }, h("h2", null, "Maintenance mode"),
        h("p", { class: "muted" }, "While on, every command from everyone except you answers with your message. Use it before an update."),
        h("div", { class: "row" }, h("label", { class: "switch" }, on, h("i")), h("span", null, "Maintenance on"), field("Message", msg),
          h("button", { class: "btn", onclick: function () { act("Maintenance saved.", api("POST", "maintenance", { on: on.checked, message: msg.value }), refreshBar); } }, "Save"))));

      var kind = h("select", null, [["", "None"], ["playing", "Playing"], ["watching", "Watching"], ["listening", "Listening to"], ["competing", "Competing in"]].map(function (o) { return h("option", { value: o[0] }, o[1]); }));
      kind.value = s.presence.kind || "";
      var text = h("input", { value: s.presence.text || "", maxlength: "100", placeholder: "What the bot shows" });
      var status = h("select", null, [["online", "Online"], ["idle", "Idle"], ["dnd", "Do not disturb"]].map(function (o) { return h("option", { value: o[0] }, o[1]); }));
      status.value = s.presence.status || "online";
      wrap.appendChild(h("div", { class: "card" }, h("h2", null, "Status shown on Discord"),
        h("div", { class: "row" }, field("Activity", kind), field("Text", text), field("Status", status),
          h("button", { class: "btn", onclick: function () { act("Status updated.", api("POST", "presence", { kind: kind.value, text: text.value, status: status.value })); } }, "Update"))));

      wrap.appendChild(h("div", { class: "card" }, h("h2", null, "Power"),
        h("p", { class: "muted" }, "Restart reloads the bot's code. Shut down stops it completely. Your host might start it again by itself, and if it doesn't you'll have to start it from the host's panel."),
        h("div", { class: "row" },
          h("button", { class: "btn quiet", onclick: function () { confirmBox("Restart the bot?", "It will go offline for a few seconds.", "", function () { act("Restarting.", api("POST", "restart", {})); }); } }, "Restart bot"),
          h("button", { class: "btn bad", onclick: function () { confirmBox("Shut the bot down?", "It stops answering in every server until you start it again from your host.", "SHUT DOWN", function () { act("Shutting down.", api("POST", "shutdown", {})); }); } }, "Shut down bot"))));
    });
  };

  VIEWS.servers = function (wrap) {
    wrap.appendChild(h("h1", null, "Servers"));
    wrap.appendChild(h("p", { class: "lead" }, "Every server Risk is in, biggest first. Open one to give or take VIP, ban it, make Risk leave or post a message."));
    var list = h("div");
    var rowsData = [];
    var search = searchBox(function (q) { draw(q); }, "Search by name or ID");
    wrap.appendChild(search);
    wrap.appendChild(list);
    function draw(q) {
      clear(list);
      var rows = rowsData.filter(function (s) { return !q || s.name.toLowerCase().indexOf(q) !== -1 || s.id.indexOf(q) !== -1; }).slice(0, 300).map(function (s) {
        return h("tr", { class: "click", tabindex: "0", onclick: function () { openServer(s.id); }, onkeydown: function (e) { if (e.key === "Enter") openServer(s.id); } },
          h("td", null, s.name), h("td", { class: "mono" }, s.id), h("td", null, num(s.members)),
          h("td", null, s.vip ? h("span", { class: "tag ok" }, s.tier || "VIP") : h("span", { class: "muted" }, "Free")));
      });
      list.appendChild(table(["Server", "ID", "Members", "Plan"], rows, "No server matches that."));
    }
    load(wrap, "panel", function (p) { rowsData = p.serverList; wrap.state = p; draw(""); });
  };

  function openServer(id) {
    api("GET", "guild/" + id).then(function (g) {
      var tier = h("select", null, [["basic", "Basic"], ["white", "VIP White"], ["supreme", "VIP Supreme"], ["lifetime", "Lifetime"]].map(function (o) { return h("option", { value: o[0] }, o[1]); }));
      var days = h("input", { type: "number", min: "0", max: "3650", value: "30" });
      var reason = h("input", { placeholder: "Reason (optional)" });
      var channel = h("select", null, g.channels.map(function (c) { return h("option", { value: c.id }, "#" + c.name); }));
      var text = h("textarea", { placeholder: "Message to post as Risk", maxlength: "2000" });
      var overlay;
      function close() { overlay.remove(); }
      overlay = h("div", { class: "overlay" }, h("div", { class: "modal" },
        h("h2", null, g.name),
        h("p", { class: "muted" }, num(g.members), " members, ", g.boosts, " boosts, created ", when(g.created), h("br"), "ID ", h("span", { class: "mono" }, g.id), " · owner ", h("span", { class: "mono" }, g.owner)),
        h("p", null, "Plan: ", g.vip ? h("span", { class: "tag ok" }, (g.tier || "VIP") + (g.until ? " until " + when(g.until) : " (no end)")) : h("span", { class: "muted" }, "Free")),
        h("h2", null, "VIP"),
        h("div", { class: "row" }, field("Plan", tier), field("Days (0 = no end)", days),
          h("button", { class: "btn", onclick: function () { act("VIP granted.", api("POST", "vip", { guild_id: g.id, action: "grant", tier: tier.value, days: Number(days.value) }), function () { close(); reload(); }); } }, "Give VIP"),
          h("button", { class: "btn quiet", onclick: function () { act("VIP removed.", api("POST", "vip", { guild_id: g.id, action: "revoke" }), function () { close(); reload(); }); } }, "Take VIP")),
        h("h2", null, "Post a message"),
        h("div", { class: "row" }, field("Channel", channel)), text,
        h("div", { class: "actions" }, h("button", { class: "btn", onclick: function () { act("Posted.", api("POST", "say", { channel_id: channel.value, text: text.value }), function () { text.value = ""; }); } }, "Send")),
        h("h2", null, "Remove from this server"),
        h("div", { class: "row" }, field("Ban reason", reason),
          h("button", { class: "btn bad", onclick: function () { confirmBox("Ban " + g.name + "?", "Risk leaves, its VIP is removed, and it can't be added back until you unban it.", "", function () { act("Server banned.", api("POST", "ban", { guild_id: g.id, reason: reason.value }), function () { close(); reload(); }); }); } }, "Ban server"),
          h("button", { class: "btn quiet", onclick: function () { confirmBox("Leave " + g.name + "?", "Risk leaves the server. It can be added again.", "", function () { act("Left the server.", api("POST", "leave", { guild_id: g.id }), function () { close(); reload(); }); }); } }, "Leave server")),
        h("div", { class: "actions" }, h("button", { class: "btn quiet", onclick: close }, "Close"))));
      document.body.appendChild(overlay);
    }).catch(function (e) { toast(e.message, true); });
  }

  VIEWS.banned = function (wrap) {
    wrap.appendChild(h("h1", null, "Banned servers"));
    wrap.appendChild(h("p", { class: "lead" }, "Banned servers can't keep Risk. It leaves, and leaves again if they re-add it."));
    var id = h("input", { placeholder: "Server ID" }), reason = h("input", { placeholder: "Reason (optional)" });
    wrap.appendChild(h("div", { class: "card" }, h("h2", null, "Ban a server by ID"), h("div", { class: "row" }, field("Server ID", id), field("Reason", reason),
      h("button", { class: "btn bad", onclick: function () { act("Server banned.", api("POST", "ban", { guild_id: id.value, reason: reason.value }), reload); } }, "Ban"))));
    load(wrap, "panel", function (p) {
      wrap.appendChild(table(["Server", "ID", "Reason", "Banned", ""], p.bannedList.map(function (b) {
        return h("tr", null, h("td", null, b.name || "Unknown"), h("td", { class: "mono" }, b.id), h("td", null, b.reason || ""), h("td", null, when(b.at)),
          h("td", null, h("button", { class: "btn quiet", onclick: function () { act("Unbanned.", api("POST", "unban", { guild_id: b.id }), reload); } }, "Unban")));
      }), "No banned servers."));
    });
  };

  VIEWS.commands = function (wrap) {
    wrap.appendChild(h("h1", null, "Commands"));
    wrap.appendChild(h("p", { class: "lead" }, "Turn a command off in every server at once. You can still use it yourself. Subcommands go with their parent."));
    var list = h("div"), data = [];
    wrap.appendChild(searchBox(function (q) { draw(q); }, "Search commands"));
    wrap.appendChild(list);
    function draw(q) {
      clear(list);
      var cats = {};
      data.filter(function (c) { return !q || c.name.indexOf(q) !== -1 || c.category.toLowerCase().indexOf(q) !== -1 || c.description.toLowerCase().indexOf(q) !== -1; }).forEach(function (c) { (cats[c.category] = cats[c.category] || []).push(c); });
      var names = Object.keys(cats);
      if (!names.length) list.appendChild(h("p", { class: "muted" }, "No command matches that."));
      names.forEach(function (cat) {
        list.appendChild(h("h2", null, cat));
        list.appendChild(table(["Command", "What it does", "Off"], cats[cat].map(function (c) {
          var box = h("input", { type: "checkbox", "aria-label": "Turn off " + c.name });
          box.checked = c.off;
          box.addEventListener("change", function () {
            api("POST", "commands", { name: c.name, off: box.checked }).then(function () { c.off = box.checked; toast(c.name + (box.checked ? " is off everywhere." : " is back on.")); refreshBar(); })
              .catch(function (e) { box.checked = !box.checked; toast(e.message, true); });
          });
          return h("tr", null, h("td", { class: "mono" }, "!" + c.name), h("td", { class: "muted" }, c.description), h("td", null, h("label", { class: "switch" }, box, h("i"))));
        })));
      });
    }
    load(wrap, "commands", function (d) { data = d.commands; draw(""); });
  };

  VIEWS.users = function (wrap) {
    wrap.appendChild(h("h1", null, "Blocked users"));
    wrap.appendChild(h("p", { class: "lead" }, "A blocked person can't use any Risk command in any server. Risk ignores them silently."));
    var id = h("input", { placeholder: "User ID" }), reason = h("input", { placeholder: "Reason (optional)" });
    wrap.appendChild(h("div", { class: "card" }, h("h2", null, "Block someone"), h("div", { class: "row" }, field("User ID", id), field("Reason", reason),
      h("button", { class: "btn bad", onclick: function () { act("User blocked.", api("POST", "blocked/add", { user_id: id.value, reason: reason.value }), reload); } }, "Block"))));
    load(wrap, "blocked", function (d) {
      wrap.appendChild(table(["User ID", "Reason", "Blocked", ""], d.blocked.map(function (b) {
        return h("tr", null, h("td", { class: "mono" }, b.id), h("td", null, b.reason), h("td", null, when(b.at)),
          h("td", null, h("button", { class: "btn quiet", onclick: function () { act("Unblocked.", api("POST", "blocked/remove", { user_id: b.id }), reload); } }, "Unblock")));
      }), "Nobody is blocked."));
    });
  };

  VIEWS.staff = function (wrap) {
    wrap.appendChild(h("h1", null, "Staff and roles"));
    wrap.appendChild(h("p", { class: "lead" }, "Panel roles for people in your staff server. Staff see totals on the website panel, developers and owners get the owner tools."));
    var id = h("input", { placeholder: "User ID" });
    var role = h("select", null, [["staff", "Staff"], ["developer", "Developer"], ["owner", "Owner"], ["none", "Remove role"]].map(function (o) { return h("option", { value: o[0] }, o[1]); }));
    wrap.appendChild(h("div", { class: "card" }, h("h2", null, "Assign a role"), h("div", { class: "row" }, field("User ID", id), field("Role", role),
      h("button", { class: "btn", onclick: function () { act("Role saved.", api("POST", "roles", { user_id: id.value, role: role.value }), reload); } }, "Save"))));
    load(wrap, "panel", function (p) {
      wrap.appendChild(h("h2", null, "Assigned roles"));
      wrap.appendChild(table(["User", "ID", "Role"], p.roles.map(function (r) { return h("tr", null, h("td", null, r.name || "Not in the staff server"), h("td", { class: "mono" }, r.id), h("td", null, h("span", { class: "tag" }, r.role))); }), "No roles assigned here. Roles from your Discord server's role IDs are not listed."));
      wrap.appendChild(h("h2", null, "Recent changes"));
      wrap.appendChild(table(["When", "By", "What", "Detail"], p.log.map(function (e) { return h("tr", null, h("td", null, when(e.at)), h("td", { class: "mono" }, e.by), h("td", null, e.action), h("td", { class: "muted" }, e.detail)); }), "Nothing has been changed yet."));
    });
  };

  VIEWS.prices = function (wrap) {
    wrap.appendChild(h("h1", null, "Prices"));
    wrap.appendChild(h("p", { class: "lead" }, "The price and checkout link shown on the website's VIP page. Blank means use the site's own setting. Links must start with https://."));
    load(wrap, "panel", function (p) {
      var names = { basic: "Basic", lifetime: "Lifetime", white: "VIP White", supreme: "VIP Supreme" };
      var inputs = {};
      var card = h("div", { class: "card" });
      p.plans.forEach(function (plan) {
        var cur = p.prices[plan] || {};
        inputs[plan] = { price: h("input", { value: cur.price || "", maxlength: "20", placeholder: "$4.99" }), url: h("input", { value: cur.url || "", placeholder: "https://..." }) };
        card.appendChild(h("div", { class: "row" }, h("div", { class: "field" }, h("b", null, names[plan] || plan)), field("Price", inputs[plan].price), field("Checkout link", inputs[plan].url)));
      });
      card.appendChild(h("div", { class: "actions" }, h("button", { class: "btn", onclick: function () {
        var body = {};
        p.plans.forEach(function (plan) { body[plan] = { price: inputs[plan].price.value, url: inputs[plan].url.value }; });
        act("Prices saved. The site updates within a minute.", api("POST", "prices", body));
      } }, "Save prices")));
      wrap.appendChild(card);
    });
  };

  VIEWS.console = function (wrap) {
    wrap.appendChild(h("h1", null, "Console"));
    wrap.appendChild(h("p", { class: "lead" }, "The bot's most recent console lines. Errors show up here."));
    var box = h("div", { class: "console", role: "log", "aria-live": "off" });
    var auto = h("input", { type: "checkbox", checked: true, id: "auto" });
    wrap.appendChild(h("div", { class: "row" }, h("label", { class: "small" }, auto, " Refresh every 3 seconds"), h("button", { class: "btn quiet", onclick: pull }, "Refresh now")));
    wrap.appendChild(box);
    var first = true;
    function pull() {
      api("GET", "logs").then(function (d) {
        var atEnd = first || box.scrollTop + box.clientHeight >= box.scrollHeight - 30;
        first = false;
        box.textContent = d.lines.length ? d.lines.join("\n") : "Nothing printed yet.";
        if (atEnd) box.scrollTop = box.scrollHeight;
      }).catch(function (e) { box.textContent = e.message; });
    }
    pull();
    var t = setInterval(function () { if (auto.checked) pull(); }, 3000);
    state.cleanup = function () { clearInterval(t); };
  };

  VIEWS.bot = function (wrap) {
    wrap.appendChild(h("h1", null, "Bot and cogs"));
    wrap.appendChild(h("p", { class: "lead" }, "Reload one part of the bot after uploading a new file, without restarting everything."));
    var name = h("input", { placeholder: "For example levels" });
    wrap.appendChild(h("div", { class: "card" }, h("h2", null, "Reload or load a cog"), h("div", { class: "row" }, field("Cog file name", name),
      h("button", { class: "btn", onclick: function () { act("Reloaded.", api("POST", "reload", { cog: name.value }), reload); } }, "Reload"))));
    load(wrap, "status", function (s) {
      wrap.appendChild(h("div", { class: "card" }, h("h2", null, "Running"), h("p", null, "Python ", s.python, ", discord.py ", s.discord), h("p", { class: "muted" }, s.cogs.join(", "))));
    });
  };

  VIEWS.settings = function (wrap) {
    wrap.appendChild(h("h1", null, "Connection"));
    fetch("/local/config").then(function (r) { return r.json(); }).then(function (c) {
      wrap.appendChild(h("p", { class: "lead" }, "Connected to ", h("span", { class: "mono" }, c.url), " with a key ", c.keyHint, "."));
      wrap.appendChild(h("p", { class: "muted small" }, "Settings file: ", h("span", { class: "mono" }, c.path)));
      wrap.appendChild(h("button", { class: "btn quiet", onclick: function () { setup(c); } }, "Change address or key"));
    });
  };

  // ---------------------------------------------------------------- start
  function start() {
    fetch("/local/config").then(function (r) { return r.json(); }).then(function (c) {
      if (!c.configured) return setup(c);
      frame();
      go(state.page);
    }).catch(function () { root.textContent = "Can't talk to the panel program. Close this window and open it again."; });
  }

  setInterval(function () { fetch("/local/ping", { method: "POST", headers: { "X-Panel": "1" } }).catch(function () {}); }, 5000);
  fetch("/local/ping", { method: "POST", headers: { "X-Panel": "1" } }).catch(function () {});
  setInterval(function () { if (document.getElementById("bar")) refreshBar(); }, 15000);
  start();
})();
