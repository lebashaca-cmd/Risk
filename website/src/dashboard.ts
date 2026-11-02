import { ApiFailure, dashApi } from "./api.js";
import type { AllSettings, DashGuildCard, GuildPayload, MePayload, Meta, SectionId } from "./dash-types.js";
import {
  channelChoices,
  channelSelect,
  group,
  multiChannels,
  multiRoles,
  numberInput,
  roleSelect,
  selectInput,
  tagEditor,
  textArea,
  textInput,
  toggle,
  uid,
} from "./dash-ui.js";
import { h, mount } from "./dom.js";
import { toast } from "./ui.js";

type View = { node: HTMLElement; cleanup: () => void };
type Renderer<K extends SectionId> = (draft: AllSettings[K], meta: Meta, changed: () => void) => HTMLElement[];

const SECTION_META: { id: SectionId; label: string; blurb: string }[] = [
  { id: "general", label: "General", blurb: "Prefix, which commands work, and where commands are ignored." },
  { id: "welcome", label: "Welcome and leave", blurb: "Messages when members join or leave." },
  { id: "logs", label: "Server logs", blurb: "Where each kind of log goes, and what is left out." },
  { id: "levels", label: "Levels", blurb: "XP speed, level-up messages and role rewards." },
  { id: "automod", label: "Auto-moderation", blurb: "Blocks links, invites, spam and listed words." },
  { id: "community", label: "Community", blurb: "Auto role, suggestions, starboard, birthdays, reports, counting and rules." },
];

const clone = <T,>(value: T): T => JSON.parse(JSON.stringify(value)) as T;

function notice(kind: "error" | "info", text: string): HTMLElement {
  return h("div", { class: `dash-notice dash-notice-${kind}`, role: kind === "error" ? "alert" : "status" }, text);
}

function avatar(url: string | null, name: string, className: string): HTMLElement {
  if (url) return h("img", { class: className, src: url, alt: "", width: 48, height: 48, loading: "lazy", referrerpolicy: "no-referrer" });
  return h("span", { class: `${className} dash-initial`, "aria-hidden": "true" }, name.trim().charAt(0).toUpperCase() || "?");
}

// Section forms
const general: Renderer<"general"> = (draft, meta, changed) => {
  const filter = h("input", { type: "search", class: "dash-input", placeholder: "Search commands", "aria-label": "Search commands", autocomplete: "off" });
  const list = h("div", { class: "dash-commands" });
  const categories = [...new Set(meta.commands.map((c) => c.category))];
  const rows = new Map<string, HTMLElement>();
  const sections: { box: HTMLElement; names: string[] }[] = [];

  for (const category of categories) {
    const names = meta.commands.filter((c) => c.category === category).map((c) => c.name);
    const items = h("div", { class: "dash-cmd-grid" });
    for (const name of names) {
      const id = uid("cmd");
      const box = h("input", { type: "checkbox", id });
      box.checked = !draft.disabledCommands.includes(name);
      box.addEventListener("change", () => {
        draft.disabledCommands = box.checked ? draft.disabledCommands.filter((n) => n !== name) : [...draft.disabledCommands, name];
        changed();
      });
      const row = h("label", { class: "dash-cmd", for: id }, box, h("span", {}, name));
      rows.set(name, row);
      items.appendChild(row);
    }
    const setAll = (on: boolean): void => {
      draft.disabledCommands = on ? draft.disabledCommands.filter((n) => !names.includes(n)) : [...new Set([...draft.disabledCommands, ...names])];
      items.querySelectorAll<HTMLInputElement>("input").forEach((el) => (el.checked = on));
      changed();
    };
    const on = h("button", { type: "button", class: "btn btn-quiet btn-small" }, "All on");
    const off = h("button", { type: "button", class: "btn btn-quiet btn-small" }, "All off");
    on.addEventListener("click", () => setAll(true));
    off.addEventListener("click", () => setAll(false));
    const box = h("div", { class: "dash-cmd-group" }, h("div", { class: "dash-cmd-head" }, h("h4", {}, `${category} (${names.length})`), h("div", { class: "dash-cmd-actions" }, on, off)), items);
    sections.push({ box, names });
    list.appendChild(box);
  }
  filter.addEventListener("input", () => {
    const term = filter.value.trim().toLowerCase();
    for (const section of sections) {
      let shown = 0;
      for (const name of section.names) {
        const match = !term || name.includes(term);
        const row = rows.get(name);
        if (row) row.hidden = !match;
        if (match) shown += 1;
      }
      section.box.hidden = shown === 0;
    }
  });

  return [
    group(
      "Prefix",
      "Risk always answers to ! ? and , . You can add one more prefix that only works in this server.",
      textInput("Extra prefix", draft.prefix ?? "", (v) => {
        draft.prefix = v.trim() === "" ? null : v.trim();
        changed();
      }, { max: 3, placeholder: "For example $", hint: "Up to 3 characters. No spaces, and not ! ? or ,. Leave empty for none." }),
    ),
    group(
      "Channels where commands are ignored",
      "Members with Manage Server can still use commands there.",
      multiChannels("Ignored channels", meta, draft.ignoredChannels, (v) => {
        draft.ignoredChannels = v;
        changed();
      }),
    ),
    group("Commands", "Switch off any command you don't want members to use here. Members with Manage Server can still run switched-off commands.", filter, list),
  ];
};

const welcome: Renderer<"welcome"> = (draft, meta, changed) => {
  const join = h("div", { class: "dash-stack" });
  const leave = h("div", { class: "dash-stack" });
  const drawJoin = (): void => {
    join.replaceChildren();
    if (!draft.enabled) return;
    join.append(
      channelSelect("Welcome channel", meta, draft.channel, (v) => { draft.channel = v; changed(); }, "Choose a channel"),
      textArea("Welcome message", draft.text, (v) => { draft.text = v; changed(); }, { max: 1500, hint: "Write New_user where the member should be mentioned." }),
    );
  };
  const drawLeave = (): void => {
    leave.replaceChildren();
    if (!draft.leaveEnabled) return;
    leave.append(
      channelSelect("Leave channel", meta, draft.leaveChannel, (v) => { draft.leaveChannel = v; changed(); }, "Choose a channel"),
      textArea("Leave message", draft.leaveText, (v) => { draft.leaveText = v; changed(); }, { max: 1500, hint: "Write New_user where the member's name should go." }),
    );
  };
  drawJoin();
  drawLeave();
  return [
    group("When someone joins", null, toggle("Send a welcome message", undefined, draft.enabled, (v) => { draft.enabled = v; drawJoin(); changed(); }), join),
    group("When someone leaves", null, toggle("Send a leave message", undefined, draft.leaveEnabled, (v) => { draft.leaveEnabled = v; drawLeave(); changed(); }), leave),
  ];
};

const logs: Renderer<"logs"> = (draft, meta, changed) => {
  const rows = h("div", { class: "dash-routes" });
  for (const category of meta.logCategories) {
    const id = uid("route");
    const enabled = !draft.disabled.includes(category.id);
    const box = h("input", { type: "checkbox", id: `${id}-on`, "aria-label": `Log ${category.label}` });
    box.checked = enabled;
    const select = h("select", { class: "dash-input", id, "aria-label": `Channel for ${category.label}` });
    for (const choice of channelChoices(meta, "Default log channel")) {
      const option = h("option", { value: choice.value, disabled: choice.disabled ?? false }, choice.label);
      if (choice.value === (draft.routes[category.id] ?? "")) option.selected = true;
      select.appendChild(option);
    }
    select.disabled = !enabled;
    box.addEventListener("change", () => {
      draft.disabled = box.checked ? draft.disabled.filter((c) => c !== category.id) : [...draft.disabled, category.id];
      select.disabled = !box.checked;
      changed();
    });
    select.addEventListener("change", () => {
      if (select.value) draft.routes[category.id] = select.value;
      else delete draft.routes[category.id];
      changed();
    });
    rows.appendChild(h("div", { class: "dash-route" }, h("label", { class: "dash-route-name", for: `${id}-on` }, box, h("span", {}, category.label)), select));
  }
  return [
    group("Default log channel", "Logs go here unless a category has its own channel. Leave it off to stop all logging.", channelSelect("Log channel", meta, draft.channel, (v) => { draft.channel = v; changed(); })),
    group("What gets logged", "Untick a category to stop logging it. Pick a channel to send that category somewhere else.", rows),
    group("Ignored channels", "Messages and voice activity in these channels are not logged.", multiChannels("Ignored channels", meta, draft.ignoredChannels, (v) => { draft.ignoredChannels = v; changed(); })),
  ];
};

const levels: Renderer<"levels"> = (draft, meta, changed) => {
  const rewards = h("div", { class: "dash-rewards" });
  const roleChoices = meta.roles.map((r) => ({ value: r.id, label: r.assignable ? `@${r.name}` : `@${r.name}  (above my role)`, disabled: !r.assignable }));
  const drawRewards = (): void => {
    rewards.replaceChildren();
    draft.rewards.sort((a, b) => a.level - b.level);
    if (draft.rewards.length === 0) rewards.appendChild(h("p", { class: "dash-empty" }, "No rewards yet."));
    draft.rewards.forEach((reward, index) => {
      const levelId = uid("rl");
      const level = h("input", { type: "number", id: levelId, class: "dash-input dash-number", min: 1, max: 1000, "aria-label": "Level" });
      level.value = String(reward.level);
      level.addEventListener("input", () => {
        const parsed = Number(level.value);
        if (Number.isFinite(parsed)) reward.level = parsed;
        changed();
      });
      level.addEventListener("change", drawRewards);
      const role = h("select", { class: "dash-input", "aria-label": "Role" });
      role.appendChild(h("option", { value: "" }, "Choose a role"));
      for (const choice of roleChoices) {
        const option = h("option", { value: choice.value, disabled: choice.disabled ?? false }, choice.label);
        if (choice.value === reward.role) option.selected = true;
        role.appendChild(option);
      }
      role.addEventListener("change", () => { reward.role = role.value || null; changed(); });
      const remove = h("button", { type: "button", class: "btn btn-quiet btn-small", "aria-label": `Remove the level ${reward.level} reward` }, "Remove");
      remove.addEventListener("click", () => { draft.rewards.splice(index, 1); drawRewards(); changed(); });
      rewards.appendChild(h("div", { class: "dash-reward" }, h("label", { for: levelId }, "At level"), level, role, remove));
    });
  };
  const add = h("button", { type: "button", class: "btn btn-quiet btn-small" }, "Add a reward");
  add.addEventListener("click", () => {
    if (draft.rewards.length >= 25) return toast("You can set up to 25 rewards.");
    const last = draft.rewards.at(-1);
    draft.rewards.push({ level: Math.min(1000, (last?.level ?? 0) + 5), role: null });
    drawRewards();
    changed();
  });
  drawRewards();
  return [
    group(
      "XP",
      "Each message earns 15 to 25 XP, multiplied by the setting below.",
      numberInput("XP multiplier", draft.multiplier, (v) => { draft.multiplier = v; changed(); }, 0.5, 5, 0.1, "From 0.5 to 5. Try 2 for double XP."),
      numberInput("Seconds between XP gains", draft.cooldown, (v) => { draft.cooldown = v; changed(); }, 10, 600, 1, "A member earns XP at most once in this time."),
      multiChannels("Channels that earn no XP", meta, draft.noxpChannels, (v) => { draft.noxpChannels = v; changed(); }),
      multiRoles("Roles that earn no XP", meta, draft.noxpRoles, (v) => { draft.noxpRoles = v; changed(); }),
    ),
    group(
      "Level-up message",
      null,
      selectInput("Where to announce", channelChoices(meta, null, [{ value: "same", label: "In the channel where they levelled up" }, { value: "off", label: "Don't announce" }]), draft.announce, (v) => { draft.announce = v; changed(); }),
      textArea("Message", draft.message, (v) => { draft.message = v; changed(); }, { max: 500, rows: 3, hint: "Use {user} to mention them, {name} for their name and {level} for the new level. Leave empty for the default." }),
    ),
    group(
      "Role rewards",
      "Members get a role when they reach a level.",
      selectInput("When a member reaches a new reward", [{ value: "stack", label: "Keep earlier reward roles" }, { value: "replace", label: "Replace earlier reward roles" }], draft.mode, (v) => { draft.mode = v === "replace" ? "replace" : "stack"; changed(); }),
      rewards,
      add,
    ),
  ];
};

const automod: Renderer<"automod"> = (draft, meta, changed) => [
  group(
    "Protections",
    "Members with Manage Messages or Administrator are never checked.",
    toggle("Block links", "Deletes messages that contain a link.", draft.antilink, (v) => { draft.antilink = v; changed(); }),
    toggle("Block Discord invites", "Deletes messages that advertise another server.", draft.antiinvite, (v) => { draft.antiinvite = v; changed(); }),
    toggle("Stop spam", "Deletes message floods (6 messages in 5 seconds) and times the sender out for 5 minutes.", draft.antispam, (v) => { draft.antispam = v; changed(); }),
    numberInput("Mention limit", draft.maxMentions, (v) => { draft.maxMentions = v; changed(); }, 0, 50, 1, "Deletes messages that mention more people or roles than this. Use 0 to turn it off."),
  ),
  group("Blocked words", "Messages that contain one of these words or phrases are deleted.", tagEditor("Words and phrases", draft.badWords, (v) => { draft.badWords = v; changed(); }, { max: 100, maxLength: 40, minLength: 2, lower: true, placeholder: "Type a word and press Enter" })),
  group(
    "Exceptions",
    null,
    multiChannels("Channels automod leaves alone", meta, draft.ignoreChannels, (v) => { draft.ignoreChannels = v; changed(); }),
    multiRoles("Roles automod leaves alone", meta, draft.ignoreRoles, (v) => { draft.ignoreRoles = v; changed(); }),
  ),
];

const community: Renderer<"community"> = (draft, meta, changed) => [
  group("New members", null, roleSelect("Auto role", meta, draft.autorole, (v) => { draft.autorole = v; changed(); }, "No auto role", "Given to every new member. Pick a role below Risk's role.")),
  group(
    "Channels",
    "Each feature stays off until you pick a channel.",
    channelSelect("Suggestions", meta, draft.suggestionChannel, (v) => { draft.suggestionChannel = v; changed(); }, "Off", "Where !suggest posts go for voting."),
    channelSelect("Starboard", meta, draft.starboardChannel, (v) => { draft.starboardChannel = v; changed(); }, "Off", "Messages with enough ⭐ reactions are copied here."),
    numberInput("Stars needed", draft.starboardThreshold, (v) => { draft.starboardThreshold = v; changed(); }, 1, 25),
    channelSelect("Birthdays", meta, draft.birthdayChannel, (v) => { draft.birthdayChannel = v; changed(); }, "Off", "Happy-birthday messages are posted here."),
    channelSelect("Member reports", meta, draft.reportChannel, (v) => { draft.reportChannel = v; changed(); }, "Off", "Where !report sends reports for your staff."),
    channelSelect("Counting game", meta, draft.countingChannel, (v) => { draft.countingChannel = v; changed(); }, "Off", "Changing this restarts the count at 0."),
    channelSelect("Ticket transcripts", meta, draft.ticketLogChannel, (v) => { draft.ticketLogChannel = v; changed(); }, "Off", "Closed tickets are logged here."),
  ),
  group("Server rules", "Shown when someone uses !rules.", textArea("Rules", draft.rules, (v) => { draft.rules = v; changed(); }, { max: 1500, rows: 7 })),
];

const RENDERERS: { [K in SectionId]: Renderer<K> } = { general, welcome, logs, levels, automod, community };

// Settings editor for one server
function renderEditor(payload: GuildPayload, guildId: string): View {
  const settings = clone(payload.settings);
  const drafts = clone(payload.settings);
  let current: SectionId = "general";
  let saving = false;
  let status: { text: string; error: boolean } = { text: "", error: false };

  const root = h("div", { class: "dash-editor" });
  const nav = h("nav", { class: "dash-tabs", "aria-label": "Settings sections" });
  const panel = h("div", { class: "dash-panel", id: "dash-panel", tabindex: -1 });
  const bar = h("div", { class: "dash-savebar" });
  const message = h("p", { class: "dash-savemsg", role: "status" });
  const save = h("button", { type: "button", class: "btn btn-primary" }, "Save changes");
  const discard = h("button", { type: "button", class: "btn btn-quiet" }, "Discard");
  bar.append(message, discard, save);

  const isDirty = (id: SectionId): boolean => JSON.stringify(drafts[id]) !== JSON.stringify(settings[id]);
  const anyDirty = (): boolean => SECTION_META.some((s) => isDirty(s.id));

  const refresh = (): void => {
    const dirty = isDirty(current);
    save.disabled = !dirty || saving;
    discard.disabled = !dirty || saving;
    const shown = dirty && !status.error ? { text: "You have unsaved changes.", error: false } : status;
    message.textContent = saving ? "" : shown.text;
    message.classList.toggle("is-error", shown.error && !saving);
    message.setAttribute("role", shown.error ? "alert" : "status");
    nav.querySelectorAll<HTMLButtonElement>("button").forEach((button) => {
      const id = button.dataset.section as SectionId;
      button.classList.toggle("is-dirty", isDirty(id));
      button.setAttribute("aria-selected", String(id === current));
      button.tabIndex = id === current ? 0 : -1;
    });
  };

  const draw = (): void => {
    const info = SECTION_META.find((s) => s.id === current);
    const body = (RENDERERS[current] as Renderer<SectionId>)(drafts[current], payload.meta, refresh);
    panel.replaceChildren(h("header", { class: "dash-panel-head" }, h("h2", {}, info?.label ?? ""), h("p", { class: "lede" }, info?.blurb ?? "")), ...body);
    panel.setAttribute("aria-labelledby", `tab-${current}`);
    refresh();
  };

  const select = (id: SectionId): void => {
    current = id;
    draw();
  };

  for (const info of SECTION_META) {
    const button = h("button", { type: "button", role: "tab", class: "dash-tab", id: `tab-${info.id}`, "data-section": info.id, "aria-controls": "dash-panel" }, info.label);
    button.addEventListener("click", () => select(info.id));
    nav.appendChild(button);
  }
  nav.setAttribute("role", "tablist");
  nav.addEventListener("keydown", (event) => {
    if (event.key !== "ArrowDown" && event.key !== "ArrowUp" && event.key !== "ArrowLeft" && event.key !== "ArrowRight") return;
    const index = SECTION_META.findIndex((s) => s.id === current);
    const step = event.key === "ArrowDown" || event.key === "ArrowRight" ? 1 : -1;
    const next = SECTION_META[(index + step + SECTION_META.length) % SECTION_META.length];
    if (!next) return;
    event.preventDefault();
    select(next.id);
    nav.querySelector<HTMLButtonElement>(`[data-section="${next.id}"]`)?.focus();
  });

  discard.addEventListener("click", () => {
    drafts[current] = clone(settings[current]) as never;
    draw();
  });

  save.addEventListener("click", async () => {
    if (saving || !isDirty(current)) return;
    const section = current;
    saving = true;
    status = { text: "", error: false };
    save.textContent = "Saving…";
    refresh();
    try {
      const result = await dashApi.save(guildId, section, drafts[section] as never);
      settings[section] = clone(result.settings) as never;
      drafts[section] = clone(result.settings) as never;
      status = { text: "Saved.", error: false };
      toast("Saved");
      saving = false;
      if (current === section) draw();
    } catch (error) {
      saving = false;
      status = { text: error instanceof ApiFailure ? error.message : "That didn't save. Try again.", error: true };
    } finally {
      saving = false;
      save.textContent = "Save changes";
      refresh();
    }
  });

  // Typing clears an old error so it doesn't linger next to new edits.
  panel.addEventListener("input", () => {
    if (status.error) status = { text: "", error: false };
  });
  panel.addEventListener("change", () => {
    if (status.error) status = { text: "", error: false };
  });

  const warn = (event: BeforeUnloadEvent): void => {
    if (!anyDirty()) return;
    event.preventDefault();
    event.returnValue = "";
  };
  window.addEventListener("beforeunload", warn);

  root.append(h("aside", { class: "dash-side" }, nav), h("div", { class: "dash-main" }, panel, bar));
  draw();
  return { node: root, cleanup: () => window.removeEventListener("beforeunload", warn) };
}

// Pages
const LOGIN_PROBLEMS: Record<string, () => string> = {
  denied: () => "Sign-in was cancelled or expired. Try again.",
  secret: () => "Discord rejected the site's client secret. The site owner should copy DISCORD_CLIENT_SECRET again from the Developer Portal (OAuth2 page, Reset Secret) and update it on the host.",
  redirect: () => `Discord says the redirect address doesn't match. The site owner should add ${window.location.origin}/api/auth/callback under OAuth2, Redirects in the Developer Portal.`,
  expired: () => "That sign-in link was already used or expired. Try again.",
  busy: () => "Discord is limiting requests from this site right now. Wait a minute and try again.",
  blocked: () => "Discord refused the request from this site's host. The site owner can find the details in the host's logs.",
  unreachable: () => "The site couldn't reach Discord. Try again in a moment.",
  failed: () => "Discord didn't complete the sign-in. Try again in a moment.",
};

function signInView(reason: string | null, enabled: boolean): HTMLElement {
  const text = reason ? (LOGIN_PROBLEMS[reason] ?? LOGIN_PROBLEMS["failed"])?.() ?? null : null;
  return h(
    "div",
    { class: "dash-hero" },
    h("h1", {}, "Dashboard"),
    h("p", { class: "lede" }, "Change how Risk works in your server: welcome messages, logs, levels, auto-moderation and more."),
    text ? notice("error", text) : null,
    enabled
      ? h("div", { class: "actions" }, h("a", { class: "btn btn-primary", href: "/api/auth/login" }, "Sign in with Discord"))
      : notice("info", "The dashboard isn't switched on yet. Check back soon."),
    h("p", { class: "dash-fine" }, "Risk sees your Discord name, avatar and the servers you manage. It doesn't get your messages and can't act as you. See the privacy policy for details."),
  );
}

function serverCard(guild: DashGuildCard, base: string): HTMLElement {
  const body = [
    avatar(guild.icon, guild.name, "dash-server-icon"),
    h("div", { class: "dash-server-text" }, h("strong", {}, guild.name), h("span", {}, guild.botPresent === true ? "Risk is here" : guild.botPresent === false ? "Risk isn't here yet" : "Status unknown")),
  ];
  if (guild.botPresent === true) {
    return h("a", { class: "dash-server", href: `${base}/${guild.id}`, "data-link": true }, ...body, h("span", { class: "dash-go" }, "Open settings"));
  }
  if (guild.invite) {
    return h("a", { class: "dash-server dash-server-add", href: guild.invite, rel: "noopener" }, ...body, h("span", { class: "dash-go" }, "Add Risk"));
  }
  return h("div", { class: "dash-server dash-server-off" }, ...body);
}

function userBar(me: MePayload, home: string): HTMLElement {
  const user = me.user;
  if (!user) return h("div");
  const out = h("button", { type: "button", class: "btn btn-quiet btn-small" }, "Sign out");
  out.addEventListener("click", async () => {
    out.disabled = true;
    try {
      await dashApi.logout();
    } catch {
      /* the cookie expires on its own */
    }
    window.location.assign(home);
  });
  return h("div", { class: "dash-user" }, avatar(user.avatar, user.name, "dash-user-icon"), h("span", {}, user.name), out);
}

function serverList(me: MePayload, base: string): HTMLElement {
  const guilds = me.guilds;
  return h(
    "div",
    { class: "dash-list" },
    h("div", { class: "dash-top" }, h("h1", {}, "Your servers"), userBar(me, base || "/")),
    me.botReachable === false ? notice("info", "Risk is offline right now, so server status can't be checked. Servers are listed anyway.") : null,
    guilds.length === 0
      ? notice("info", "You don't manage any servers. You need the Manage Server permission to change Risk's settings.")
      : h("div", { class: "dash-servers" }, ...guilds.map((g) => serverCard(g, base))),
    h("p", { class: "dash-fine" }, "Only servers where you are the owner or have Manage Server or Administrator are listed. If a server is missing, sign out and back in to refresh the list."),
  );
}

/** `base` is "" on the dashboard subdomain (ids live at /<id>) and "/dashboard" on the main site. */
export function renderDashboard(guildId: string | null, base: string): View {
  const root = h("div", { class: "view container page dash" });
  let cleanup: () => void = () => undefined;
  let alive = true;
  const home = base || "/";
  const loading = h("p", { class: "dash-loading", role: "status" }, "Loading");
  root.appendChild(loading);

  const failure = (error: unknown): void => {
    const text = error instanceof ApiFailure ? error.message : "Something went wrong. Refresh the page and try again.";
    mount(root, h("h1", {}, "Dashboard"), notice("error", text), h("div", { class: "actions" }, h("a", { class: "btn btn-quiet", href: home, "data-link": true }, "Back to your servers")));
  };

  void (async () => {
    try {
      const me = await dashApi.me();
      if (!alive) return;
      if (!me.user) {
        const reason = new URLSearchParams(window.location.search).get("login");
        mount(root, signInView(reason, me.enabled));
        return;
      }
      if (!guildId) {
        mount(root, serverList(me, base));
        return;
      }
      const id = guildId;
      const payload = await dashApi.guild(id);
      if (!alive) return;
      const editor = renderEditor(payload, id);
      cleanup = editor.cleanup;
      mount(
        root,
        h(
          "div",
          { class: "dash-top" },
          h("div", { class: "dash-title" }, avatar(payload.guild.icon, payload.guild.name, "dash-server-icon"), h("div", {}, h("a", { class: "dash-back", href: home, "data-link": true }, "All servers"), h("h1", {}, payload.guild.name))),
          userBar(me, home),
        ),
        editor.node,
      );
    } catch (error) {
      if (alive) failure(error);
    }
  })();

  return {
    node: root,
    cleanup: () => {
      alive = false;
      cleanup();
    },
  };
}
