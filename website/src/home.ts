import { api } from "./api.js";
import { h } from "./dom.js";
import { playIntro, revealOnScroll, scrollFx, splitWords } from "./anim.js";
import { mountDemo } from "./demo.js";
import { icon, type IconName } from "./icons.js";
import { applyStatus, currentStatus, onStatus, setExtraStat } from "./status.js";
import type { CommandInfo, ServerInfo, SiteConfig } from "./types.js";

function serverCard(server: ServerInfo): HTMLElement {
  const initial = (server.name.trim()[0] ?? "?").toUpperCase();
  const avatar = h("span", { class: "savatar" }, h("span", { class: "sinitial", "aria-hidden": "true" }, initial));
  if (server.icon) {
    const img = h("img", { src: server.icon, alt: "", width: "56", height: "56", loading: "lazy", referrerpolicy: "no-referrer" });
    img.addEventListener("error", () => img.remove());
    avatar.appendChild(img);
  }
  const members = server.members === null ? "" : `${server.members.toLocaleString()} member${server.members === 1 ? "" : "s"}`;
  return h("div", { class: "fcard server" }, avatar, h("span", { class: "ftext" }, h("strong", {}, server.name), members ? h("span", {}, members) : null));
}

function placeholderCard(): HTMLElement {
  return h(
    "div",
    { class: "fcard server ghost" },
    h("span", { class: "savatar" }, h("span", { class: "sinitial", "aria-hidden": "true" }, "+")),
    h("span", { class: "ftext" }, h("strong", {}, "Your server"), h("span", {}, "Add Risk to see it here")),
  );
}

function serverRow(servers: ServerInfo[]): HTMLElement {
  const cards = (): HTMLElement[] => (servers.length > 0 ? servers.map(serverCard) : Array.from({ length: 4 }, placeholderCard));
  const per = servers.length > 0 ? servers.length : 4;
  const copies = Math.max(1, Math.ceil(10 / per));
  const track = h("div", { class: "track" });
  for (const hidden of [false, true]) {
    const group = h("div", { class: "group" });
    for (let i = 0; i < copies; i += 1) group.append(...cards());
    if (hidden) group.setAttribute("aria-hidden", "true");
    track.appendChild(group);
  }
  return h("div", { class: "marquee", role: "group", "aria-label": "Servers using Risk" }, track);
}

const CATEGORY_META: Record<string, { ic: IconName; blurb: string }> = {
  Info: { ic: "info", blurb: "Latency, uptime, terms and the full command list." },
  Utility: { ic: "wrench", blurb: "Avatars, polls, reminders, AFK, calculator and more." },
  Moderation: { ic: "shield", blurb: "Timeouts, warnings, bans, locks and cleanup." },
  Fun: { ic: "gamepad", blurb: "Games, jokes, trivia and little actions." },
  Economy: { ic: "coin", blurb: "Daily coins, work, slots, betting and a leaderboard." },
  Tickets: { ic: "ticket", blurb: "Private support channels with transcripts." },
  "Server logs": { ic: "logs", blurb: "Deletes, edits, voice, roles and joins in one place." },
  Welcome: { ic: "welcome", blurb: "Greet new members with your own message." },
  AI: { ic: "ai", blurb: "Ask a question, get code in a block or a file." },
  Lookups: { ic: "lookup", blurb: "TikTok, YouTube, GitHub and Spotify profiles." },
};

function categoryRow(name: string, items: CommandInfo[], prefix: string, index: number): HTMLElement {
  const meta = CATEGORY_META[name] ?? { ic: "terminal" as IconName, blurb: "" };
  const samples = items.filter((c) => c.kind === "prefix").slice(0, 4);
  return h(
    "a",
    { class: "row", href: "/commands", "data-link": true, style: `--n:${index % 6}`, "aria-label": `${name}: ${items.length} commands` },
    h("span", { class: "row-ic" }, icon(meta.ic)),
    h("span", { class: "row-name" }, h("strong", {}, name), h("span", { class: "row-count" }, `${items.length} command${items.length === 1 ? "" : "s"}`)),
    h("span", { class: "row-blurb" }, meta.blurb),
    h("span", { class: "row-samples" }, ...samples.map((c) => h("code", {}, `${prefix}${c.name}`))),
    h("span", { class: "row-go", "aria-hidden": "true" }, icon("arrow")),
  );
}

function statLine(): HTMLElement {
  const stat = (key: string, label: string, unit = "") =>
    h("span", { class: "stat-inline" }, h("b", { class: "num", "data-stat": key, "data-empty": "true" }, "\u2013"), unit, ` ${label}`);
  return h(
    "p",
    { class: "hero-stats", "data-step": true, style: "--s:2", id: "status" },
    h("span", { class: "live" }, h("span", { class: "status-dot", "data-status-dot": true, "data-state": "checking" }), h("span", { "data-status-label": true }, "Checking status")),
    h("span", { class: "sep", "aria-hidden": "true" }, "\u00B7"),
    stat("guilds", "servers"),
    h("span", { class: "sep", "aria-hidden": "true" }, "\u00B7"),
    stat("commands", "commands"),
    h("span", { class: "sep", "aria-hidden": "true" }, "\u00B7"),
    stat("latency", "latency", "ms"),
  );
}

export function renderHome(config: SiteConfig): { node: HTMLElement; cleanup: () => void } {
  const main = h("span", { class: "h1-main" }, "Run your server");
  splitWords(main);
  const title = h("h1", { id: "hero-title" }, main, h("span", { class: "h1-script", "data-step": true, style: "--s:1" }, "with Risk"));

  const invite = config.inviteUrl ? h("a", { class: "btn btn-primary", href: config.inviteUrl, rel: "noopener" }, icon("link"), "Add to Discord") : null;
  const hero = h(
    "section",
    { class: "hero container", "aria-labelledby": "hero-title" },
    h(
      "div",
      { class: "hero-copy" },
      title,
      statLine(),
      h("p", { class: "lede", "data-step": true, style: "--s:3" }, "Tickets, logs, moderation, games, an economy and AI answers in one Discord bot. Start a command with !, ? or , whichever you like."),
      h("div", { class: "actions", "data-step": true, style: "--s:4" }, invite, h("a", { class: "btn btn-quiet", href: "/commands", "data-link": true }, icon("terminal"), "View Commands")),
    ),
    h(
      "figure",
      { class: "portrait", "data-step": true, style: "--s:2" },
      h("div", { class: "frame" }, h("img", { src: "/assets/portrait.jpg", alt: "Risk's logo: an anime girl hiding one eye behind her hand", width: "640", height: "800", decoding: "async" })),
    ),
  );

  const rows = h("section", { class: "feature-rows", "aria-label": "Servers using Risk", "data-step": true, style: "--s:5" });
  let shown = "";
  const fillRows = (servers: ServerInfo[]): void => {
    const key = JSON.stringify(servers);
    if (key === shown && rows.firstChild) return;
    shown = key;
    rows.replaceChildren(h("p", { class: "strip-label" }, servers.length > 0 ? "Servers running Risk" : "Servers running Risk will show up here"), serverRow(servers));
  };
  fillRows(currentStatus()?.servers ?? []);
  const stopStatus = onStatus((status) => fillRows(status?.servers ?? []));

  const catGrid = h("div", { class: "index" });
  const cats = h(
    "section",
    { class: "container cats", "aria-labelledby": "cats-title", "data-reveal": true },
    h(
      "div",
      { class: "paper" },
      h("div", { class: "sec-head" }, h("h2", { id: "cats-title" }, "Everything in one bot"), h("p", { class: "lede" }, "Pick a category to see every command in it.")),
      catGrid,
    ),
  );

  const demoRoot = h("div", { class: "demo-grid" });
  const demo = h(
    "section",
    { class: "container demo", "aria-labelledby": "demo-title", "data-reveal": true },
    h("div", { class: "sec-head" }, h("h2", { id: "demo-title" }, "See a command run"), h("p", { class: "lede" }, "Pick one to watch Risk reply.")),
    demoRoot,
  );

  const cta = h(
    "section",
    { class: "container cta-sec", "aria-labelledby": "cta-title", "data-reveal": true },
    h(
      "div",
      { class: "cta-panel" },
      h("h2", { id: "cta-title" }, "Put Risk in your server"),
      h("p", { class: "lede" }, "Add it in one click, then post your first ticket panel."),
      h(
        "div",
        { class: "actions" },
        config.inviteUrl ? h("a", { class: "btn btn-primary", href: config.inviteUrl, rel: "noopener" }, icon("link"), "Add to Discord") : null,
        config.supportUrl ? h("a", { class: "btn btn-quiet", href: config.supportUrl, rel: "noopener" }, "Support server") : h("a", { class: "btn btn-quiet", href: "/commands", "data-link": true }, "View Commands"),
      ),
    ),
  );

  const node = h("div", { class: "view intro" }, hero, rows, cats, demo, cta);

  let stopRows: () => void = () => undefined;
  const stopReveal = revealOnScroll(node, "[data-reveal]", "in", 0.15);
  const stopFx = scrollFx(node);
  const stopDemo = mountDemo(demoRoot);
  applyStatus(node);
  playIntro(node);

  api
    .commands()
    .then((data) => {
      setExtraStat("commands", data.commands.length);
      const groups = new Map<string, CommandInfo[]>();
      for (const command of data.commands) groups.set(command.category, [...(groups.get(command.category) ?? []), command]);
      const prefix = data.prefixes[0] ?? "!";
      catGrid.replaceChildren(...[...groups].map(([name, items], i) => categoryRow(name, items, prefix, i)));
      stopRows();
      stopRows = revealOnScroll(catGrid, ".row", "in", 0.2);
    })
    .catch(() => cats.remove());

  return {
    node,
    cleanup: () => {
      stopDemo();
      stopStatus();
      stopReveal();
      stopRows();
      stopFx();
    },
  };
}
