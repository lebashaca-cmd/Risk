import { api } from "./api.js";
import { h, mount } from "./dom.js";
import type { PageButton, PageIncident, SiteConfig, StatusPageData } from "./types.js";

const SPA_PATHS = new Set(["/", "/commands", "/terms", "/privacy", "/vip", "/status", "/staff"]);
const REFRESH_MS = 30_000;

/** Turns {invite}, {site}, {docs}, {dashboard}, {vip}, {status} (plus an optional path) into a real link, or null when it has no target yet. */
export function resolveLink(url: string, config: SiteConfig): string | null {
  const match = /^\{(invite|site|docs|dashboard|vip|status)\}(\/\S*)?$/.exec(url);
  if (!match) return /^https:\/\/\S+$/.test(url) || /^\/(?!\/)\S*$/.test(url) ? url : null;
  const [, token, rest = ""] = match;
  const base: Record<string, string | null | undefined> = {
    invite: config.inviteUrl,
    site: location.origin,
    docs: config.docsUrl ?? "/docs/",
    dashboard: config.dashboardUrl ?? "/dashboard",
    vip: "/vip",
    status: "/status",
  };
  const found = base[token ?? ""];
  if (!found) return null;
  return token === "invite" ? found : found.replace(/\/$/, "") + rest || found;
}

function buttonNode(button: PageButton, config: SiteConfig): HTMLElement | null {
  const href = resolveLink(button.url, config);
  if (!href) return null;
  const klass = button.style === "primary" ? "btn btn-primary" : "btn btn-quiet";
  const internal = href.startsWith("/") && SPA_PATHS.has(href.split(/[?#]/)[0] ?? "");
  const local = href.startsWith("/") || href.startsWith(location.origin);
  return h("a", local ? { class: klass, href, "data-link": internal || href.startsWith(location.origin) } : { class: klass, href, target: "_blank", rel: "noopener noreferrer" }, button.label);
}

function duration(seconds: number): string {
  if (seconds < 90) return "under a minute";
  const minutes = Math.floor(seconds / 60);
  if (minutes < 90) return `${minutes} minutes`;
  const hours = Math.floor(minutes / 60);
  if (hours < 48) return `${hours} hours`;
  return `${Math.floor(hours / 24)} days`;
}

function when(seconds: number | null): string {
  if (!seconds) return "";
  return new Date(seconds * 1000).toLocaleString(undefined, { month: "short", day: "numeric", hour: "numeric", minute: "2-digit" });
}

function level(percent: number | null): string {
  if (percent === null) return "none";
  if (percent >= 99.5) return "full";
  if (percent >= 95) return "high";
  if (percent >= 80) return "mid";
  return "low";
}

function tile(label: string, value: string, note?: string): HTMLElement {
  return h("div", { class: "sp-tile" }, h("strong", {}, value), h("span", {}, label), note ? h("small", {}, note) : null);
}

function fmt(n: number | null | undefined): string {
  return n === null || n === undefined ? "–" : n.toLocaleString();
}

function incident(item: PageIncident): HTMLElement {
  const state = item.resolved_at ? "Resolved" : "Ongoing";
  return h(
    "article",
    { class: "sp-incident", "data-level": item.resolved_at ? "good" : item.level },
    h("header", {}, h("h3", {}, item.title), h("span", { class: "sp-badge" }, state)),
    item.text ? h("p", {}, item.text) : null,
    h("small", {}, item.resolved_at ? `${when(item.at)}, resolved ${when(item.resolved_at)}` : `Since ${when(item.at)}`),
  );
}

function view(data: StatusPageData, config: SiteConfig): HTMLElement[] {
  const { status, page } = data;
  const online = status.state === "online";
  const headline = online ? "Risk is online" : status.state === "offline" ? "Risk is offline" : "Status unavailable";
  const sub = online ? (page.sinceSeconds ? `Up for ${duration(page.sinceSeconds)}.` : "Everything is running.") : status.state === "offline" ? "The bot isn't answering right now. It usually comes back within a few minutes." : "We couldn't check the bot just now.";
  const buttons = (page.buttons ?? []).map((b) => buttonNode(b, config)).filter((n): n is HTMLElement => n !== null);
  const parts: HTMLElement[] = [
    h(
      "section",
      { class: "sp-hero", "data-state": status.state },
      h("span", { class: "status-dot", "data-state": status.state }),
      h("h1", {}, headline),
      h("p", {}, sub),
      buttons.length ? h("div", { class: "sp-actions" }, ...buttons) : null,
    ),
  ];
  if (page.notice.on && page.notice.text) parts.push(h("p", { class: "sp-notice", "data-level": page.notice.level, role: "status" }, page.notice.text));
  const usage = page.usage;
  parts.push(
    h(
      "section",
      { class: "sp-tiles", "aria-label": "Numbers" },
      tile("Ping", online && status.latencyMs !== null ? `${status.latencyMs} ms` : "–"),
      tile("Servers", fmt(online ? status.guilds : null)),
      tile("Uptime, 30 days", page.uptime?.percent != null ? `${page.uptime.percent}%` : "–"),
      tile("Commands today", fmt(usage?.today)),
      tile("Commands this week", fmt(usage?.week)),
      tile("Commands ever", fmt(usage?.total)),
    ),
  );
  if (page.uptime) {
    const days = page.uptime.days;
    parts.push(
      h(
        "section",
        { class: "sp-uptime" },
        h("h2", {}, "Last 30 days"),
        h("div", { class: "sp-bars", role: "img", "aria-label": `Daily uptime for the last ${days.length} days` }, ...days.map((d) => h("i", { class: "sp-bar", "data-level": level(d.percent), title: d.percent === null ? `${d.date}: no data` : `${d.date}: ${d.percent}% up` }))),
        h("p", { class: "sp-legend" }, h("span", {}, "30 days ago"), h("span", {}, "Today")),
      ),
    );
  }
  if (usage && usage.top.length) {
    const max = Math.max(...usage.top.map((t) => t.count), 1);
    parts.push(
      h(
        "section",
        { class: "sp-top" },
        h("h2", {}, "Most used commands"),
        h("ol", {}, ...usage.top.map((t) => h("li", {}, h("code", {}, `!${t.name}`), h("meter", { min: 0, max, value: t.count }), h("span", {}, t.count.toLocaleString())))),
      ),
    );
  }
  parts.push(
    h(
      "section",
      { class: "sp-incidents" },
      h("h2", {}, "Incidents"),
      page.incidents.length ? h("div", { class: "sp-list" }, ...page.incidents.map(incident)) : h("p", { class: "sp-empty" }, "Nothing reported lately."),
    ),
  );
  return parts;
}

export function renderStatusPage(config: SiteConfig): { node: HTMLElement; cleanup: () => void } {
  const body = h("div", { class: "sp-body" }, h("p", { class: "sp-empty" }, "Checking status…"));
  const node = h("div", { class: "container sp" }, body);
  let alive = true;
  const load = async () => {
    try {
      const data = await api.statusPage();
      if (alive) mount(body, ...view(data, config));
    } catch {
      if (alive && !body.querySelector(".sp-hero")) mount(body, h("p", { class: "sp-empty" }, "The status service didn't answer. Try again in a minute."));
    }
  };
  void load();
  const timer = window.setInterval(() => {
    if (document.visibilityState === "visible") void load();
  }, REFRESH_MS);
  return { node, cleanup: () => { alive = false; window.clearInterval(timer); } };
}
