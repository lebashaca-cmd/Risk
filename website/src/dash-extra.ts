import type { Announcement, CommandRule, Meta, OverviewSettings, Responder, RespondersSettings, SectionId, VipSettings, AnnouncementsSettings, CommandsSettings } from "./dash-types.js";
import { group, lockControls, multiChannels, multiRoles, numberInput, selectInput, textArea, textInput, toggle, vipBadge } from "./dash-ui.js";
import type { Choice } from "./dash-ui.js";
import { h } from "./dom.js";
import { toast } from "./ui.js";

export interface Ctx {
  go: (section: SectionId) => void;
  guildName: string;
  guildIcon: string | null;
}

export type ExtraRenderer<T> = (draft: T, meta: Meta, changed: () => void, ctx: Ctx) => HTMLElement[];

const number = new Intl.NumberFormat();

function ago(unix: number): string {
  const seconds = Math.max(0, Math.round(Date.now() / 1000 - unix));
  if (seconds < 60) return "just now";
  const units: [number, string][] = [[86400, "day"], [3600, "hour"], [60, "minute"]];
  for (const [size, name] of units) {
    if (seconds >= size) {
      const count = Math.floor(seconds / size);
      return `${count} ${name}${count === 1 ? "" : "s"} ago`;
    }
  }
  return "just now";
}

function age(unix: number): string {
  const days = Math.max(0, Math.floor(Date.now() / 1000 - unix) / 86400);
  if (days >= 365) return `${(days / 365).toFixed(1)} years`;
  return `${Math.floor(days)} days`;
}

function upsell(vip: VipSettings | null, what: string): HTMLElement {
  return h(
    "div",
    { class: "dash-upsell" },
    h("p", {}, vipBadge(), ` ${what}`),
    vip?.url ? h("a", { class: "btn btn-primary btn-small", href: vip.url, rel: "noopener" }, "Get VIP") : h("p", { class: "dash-hint" }, "Ask the bot owner to switch VIP on for this server."),
  );
}

const SECTION_LABEL: Record<string, string> = {
  general: "General", welcome: "Welcome and leave", logs: "Server logs", levels: "Levels", automod: "Auto-moderation", community: "Community",
  profile: "Bot profile", commands: "Commands", responders: "Auto-replies", announcements: "Announcements", vip: "VIP",
};

// Overview
export const overview: ExtraRenderer<OverviewSettings> = (draft, _meta, _changed, ctx) => {
  const stats = draft.stats;
  const done = draft.checklist.filter((item) => item.done).length;
  const tile = (value: string, label: string, note?: string): HTMLElement =>
    h("div", { class: "dash-tile" }, h("strong", {}, value), h("span", {}, label), note ? h("small", {}, note) : null);

  const banner = h(
    "div",
    { class: "dash-banner" },
    ctx.guildIcon ? h("img", { class: "dash-banner-icon", src: ctx.guildIcon, alt: "", width: 64, height: 64, referrerpolicy: "no-referrer" }) : h("span", { class: "dash-banner-icon dash-initial", "aria-hidden": "true" }, ctx.guildName.charAt(0).toUpperCase()),
    h(
      "div",
      { class: "dash-banner-text" },
      h("h3", {}, ctx.guildName, draft.vip ? vipBadge() : null),
      h("p", {}, `${done} of ${draft.checklist.length} setup steps done`),
      h("div", { class: "dash-meter", role: "img", "aria-label": `${done} of ${draft.checklist.length} setup steps done` }, ...draft.checklist.map((item) => h("i", { class: item.done ? "is-done" : "" }))),
    ),
  );

  const tiles = h(
    "div",
    { class: "dash-tiles" },
    tile(number.format(stats.members ?? 0), "members", `${number.format(stats.people)} people, ${number.format(stats.bots)} bots`),
    tile(String(stats.textChannels + stats.voiceChannels), "channels", `${stats.textChannels} text, ${stats.voiceChannels} voice`),
    tile(String(stats.roles), "roles", `${stats.emojis} emojis`),
    tile(`Level ${stats.boostTier}`, "boost", `${stats.boosts} boosts`),
    tile(age(stats.created), "old", stats.owner ? `Owned by ${stats.owner}` : undefined),
  );

  const steps = h("ul", { class: "dash-steps" });
  for (const item of draft.checklist) {
    const go = h("button", { type: "button", class: "btn btn-quiet btn-small" }, item.done ? "Edit" : "Set up");
    go.addEventListener("click", () => ctx.go(item.section));
    steps.appendChild(h("li", { class: item.done ? "is-done" : "" }, h("span", { class: "dash-check", "aria-hidden": "true" }, item.done ? "✓" : ""), h("span", { class: "dash-step-label" }, item.label, h("span", { class: "sr-only" }, item.done ? " (done)" : " (not done)")), go));
  }

  const use = draft.usage;
  const usage = h(
    "dl",
    { class: "dash-usage" },
    ...([
      ["Commands switched off", use.disabledCommands],
      ["Command rules", use.commandRules],
      ["Auto-replies", use.responders],
      ["Announcements", use.announcements],
      ["Log types on", use.logCategories ?? "-"],
    ] as [string, number | string][]).flatMap(([label, value]) => [h("dt", {}, label), h("dd", {}, String(value))]),
  );

  const feed = draft.activity.length
    ? h("ul", { class: "dash-feed" }, ...draft.activity.map((a) => h("li", {}, h("strong", {}, a.user), ` changed ${SECTION_LABEL[a.section] ?? a.section}`, h("span", { class: "dash-when" }, ago(a.at)))))
    : h("p", { class: "dash-empty" }, "No changes from the dashboard yet.");

  return [banner, tiles, group("Setup checklist", "Finish these to get the most out of Risk.", steps), h("div", { class: "dash-twin" }, group("In use", null, usage), group("Recent changes", "Saved from this dashboard.", feed))];
};

// Commands
export const commands: ExtraRenderer<CommandsSettings> = (draft, meta, changed) => {
  const list = h("div", { class: "dash-rules" });
  const count = h("p", { class: "dash-hint", role: "status" });
  const limit = meta.limits["command_rules"] ?? 500;
  const names = meta.commands.map((c) => c.name);

  const draw = (): void => {
    list.replaceChildren();
    count.textContent = `${draft.rules.length} ${draft.rules.length === 1 ? "rule" : "rules"}.`;
    if (draft.rules.length === 0) list.appendChild(h("p", { class: "dash-empty" }, "No rules yet. Everyone can use every switched-on command anywhere."));
    draft.rules.forEach((rule: CommandRule, index) => {
      const taken = new Set(draft.rules.map((r) => r.command));
      const choices: Choice[] = names.filter((n) => n === rule.command || !taken.has(n)).map((n) => ({ value: n, label: n }));
      const remove = h("button", { type: "button", class: "btn btn-quiet btn-small" }, "Remove");
      remove.addEventListener("click", () => {
        draft.rules.splice(index, 1);
        draw();
        changed();
      });
      list.appendChild(
        h(
          "div",
          { class: "dash-card" },
          selectInput("Command", choices, rule.command, (v) => { rule.command = v; draw(); changed(); }),
          multiRoles("Only these roles can use it", meta, rule.roles, (v) => { rule.roles = v; changed(); }, "Leave empty to allow everyone."),
          multiChannels("Only works in these channels", meta, rule.channels, (v) => { rule.channels = v; changed(); }, "Leave empty to allow every channel."),
          numberInput("Cooldown per member (seconds)", rule.cooldown, (v) => { rule.cooldown = v; changed(); }, 0, 3600, 1, "0 means no cooldown."),
          h("div", { class: "dash-card-actions" }, remove),
        ),
      );
    });
  };
  const add = h("button", { type: "button", class: "btn btn-quiet btn-small" }, "Add a rule");
  add.addEventListener("click", () => {
    if (draft.rules.length >= limit) return toast(`That is the most rules one server can have (${limit}).`);
    const taken = new Set(draft.rules.map((r) => r.command));
    const first = names.find((n) => !taken.has(n));
    if (!first) return;
    draft.rules.push({ command: first, roles: [], channels: [], cooldown: 10 });
    draw();
    changed();
  });
  draw();
  return [group("Command rules", "Limit who can run a command, where, and how often. Members with Manage Server ignore these rules.", list, count, add)];
};

// Auto-replies
const MATCHES: Choice[] = [
  { value: "contains", label: "Message contains the trigger" },
  { value: "exact", label: "Message is exactly the trigger" },
  { value: "starts", label: "Message starts with the trigger" },
];

export const responders: ExtraRenderer<RespondersSettings> = (draft, meta, changed) => {
  const list = h("div", { class: "dash-rules" });
  const count = h("p", { class: "dash-hint", role: "status" });
  const limit = meta.limits["responders"] ?? 500;
  const draw = (): void => {
    list.replaceChildren();
    count.textContent = `${draft.items.length} ${draft.items.length === 1 ? "auto-reply" : "auto-replies"}.`;
    if (draft.items.length === 0) list.appendChild(h("p", { class: "dash-empty" }, "No auto-replies yet."));
    draft.items.forEach((item: Responder, index) => {
      const remove = h("button", { type: "button", class: "btn btn-quiet btn-small" }, "Remove");
      remove.addEventListener("click", () => {
        draft.items.splice(index, 1);
        draw();
        changed();
      });
      const embed = toggle("Send as an embed", "Uses your VIP colour.", item.embed, (v) => { item.embed = v; changed(); });
      list.appendChild(
        h(
          "div",
          { class: "dash-card" },
          textInput("Trigger", item.trigger, (v) => { item.trigger = v; changed(); }, { max: 60, placeholder: "for example: server ip" }),
          selectInput("When to reply", MATCHES, item.match, (v) => { item.match = v as Responder["match"]; changed(); }),
          textArea("Reply", item.reply, (v) => { item.reply = v; changed(); }, { max: 500, rows: 3, hint: "You can use {user} and {server}. Risk waits 10 seconds before repeating a reply." }),
          meta.vip ? embed : h("div", {}, lockControls(embed, true), h("p", { class: "dash-hint" }, vipBadge(), " Embed replies are for VIP servers.")),
          h("div", { class: "dash-card-actions" }, remove),
        ),
      );
    });
  };
  const add = h("button", { type: "button", class: "btn btn-quiet btn-small" }, "Add an auto-reply");
  add.addEventListener("click", () => {
    if (draft.items.length >= limit) return toast(`That is the most auto-replies one server can have (${limit}).`);
    draft.items.push({ trigger: "", reply: "", match: "contains", embed: false });
    draw();
    changed();
  });
  draw();
  return [group("Auto-replies", "Risk answers when a message matches. Replies never ping anyone and skip channels where commands are ignored.", list, count, add)];
};

// Announcements (VIP)
export const announcements = (vip: VipSettings | null): ExtraRenderer<AnnouncementsSettings> => (draft, meta, changed) => {
  const limit = meta.limits["schedules"] ?? 0;
  const list = h("div", { class: "dash-rules" });
  const count = h("p", { class: "dash-hint", role: "status" });
  const draw = (): void => {
    list.replaceChildren();
    count.textContent = `${draft.items.length} of ${limit || 50} announcements.`;
    if (draft.items.length === 0) list.appendChild(h("p", { class: "dash-empty" }, "No announcements yet."));
    draft.items.forEach((item: Announcement, index) => {
      const remove = h("button", { type: "button", class: "btn btn-quiet btn-small" }, "Remove");
      remove.addEventListener("click", () => {
        draft.items.splice(index, 1);
        draw();
        changed();
      });
      const channels: Choice[] = [{ value: "", label: "Pick a channel" }, ...meta.channels.map((c) => ({ value: c.id, label: `#${c.name}`, disabled: !c.canSend }))];
      list.appendChild(
        h(
          "div",
          { class: "dash-card" },
          selectInput("Channel", channels, item.channel ?? "", (v) => { item.channel = v === "" ? null : v; changed(); }),
          numberInput("Repeat every (minutes)", item.everyMinutes, (v) => { item.everyMinutes = v; changed(); }, 5, 43200, 5, "From 5 minutes to 30 days. 60 is hourly, 1440 is daily."),
          textArea("Message", item.text, (v) => { item.text = v; changed(); }, { max: 1500, rows: 3 }),
          toggle("Running", "Switch off to pause it without deleting it.", item.on, (v) => { item.on = v; changed(); }),
          h("div", { class: "dash-card-actions" }, remove),
        ),
      );
    });
  };
  const add = h("button", { type: "button", class: "btn btn-quiet btn-small" }, "Add an announcement");
  add.addEventListener("click", () => {
    if (draft.items.length >= limit) return toast(`You can set up to ${limit} announcements.`);
    draft.items.push({ channel: null, everyMinutes: 60, text: "", on: true });
    draw();
    changed();
  });
  draw();
  if (!meta.vip) return [upsell(vip, "Announcements repeat a message in a channel on a timer. They are included with VIP.")];
  return [group("Scheduled messages", "Risk posts each message again and again on its timer. The first post comes one interval after you save.", list, count, add)];
};

// VIP
export const vipSection = (): ExtraRenderer<VipSettings> => (draft, _meta, changed) => {
  const status = draft.active
    ? h("div", { class: "dash-vipcard is-on" }, h("h3", {}, vipBadge(), ` ${draft.tier ?? "VIP"} is on for this server`), h("p", {}, draft.until ? `Until ${new Date(draft.until * 1000).toLocaleDateString()}.` : "With no end date."))
    : h("div", { class: "dash-vipcard" }, h("h3", {}, "This server is on the free plan"), h("p", {}, "VIP unlocks a few extras. Nothing in the regular settings is limited."), upsell(draft, "Get VIP to unlock everything below."));

  const colorValue = draft.color ?? "#5865f2";
  const colorInput = h("input", { type: "color", class: "dash-color", id: "vip-color", value: colorValue, "aria-label": "Accent colour" });
  const clear = h("button", { type: "button", class: "btn btn-quiet btn-small" }, "Use the default");
  const note = h("p", { class: "dash-hint", role: "status" }, draft.color ? `Current colour: ${draft.color}` : "Using the default colour.");
  colorInput.addEventListener("input", () => {
    draft.color = colorInput.value;
    note.textContent = `Current colour: ${colorInput.value}`;
    changed();
  });
  clear.addEventListener("click", () => {
    draft.color = null;
    note.textContent = "Using the default colour.";
    changed();
  });
  const colour = h("div", { class: "dash-field" }, h("label", { for: "vip-color" }, "Accent colour"), h("div", { class: "dash-add" }, colorInput, clear), note, h("p", { class: "dash-hint" }, "Used for VIP embeds, embed auto-replies and !serverstats."));
  const lockedColour = draft.active ? colour : h("div", {}, lockControls(colour, true), h("p", { class: "dash-hint" }, vipBadge(), " The accent colour is for VIP servers."));

  return [
    status,
    group("What VIP includes", null, h("ul", { class: "dash-perks" }, ...draft.perks.map((perk) => h("li", {}, perk)))),
    group(
      "Commands by plan",
      "Run !vipcommands in Discord for the same list.",
      ...draft.commands.map((set) =>
        h(
          "div",
          { class: "dash-field" },
          h("label", {}, `${{ basic: "Every VIP plan", lifetime: "Lifetime", white: "VIP White and Supreme", supreme: "VIP Supreme" }[set.plan]}${draft.active ? (set.unlocked ? " (unlocked)" : " (locked)") : ""}`),
          h("p", { class: "dash-hint" }, set.names.map((name) => `!${name}`).join("  ")),
        ),
      ),
    ),
    group("Appearance", null, lockedColour),
  ];
};

export type { RespondersSettings };
