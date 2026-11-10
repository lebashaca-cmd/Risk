import { h } from "./dom.js";
const nf = new Intl.NumberFormat("en");
const PLAN_NAMES = { basic: "Basic", lifetime: "Lifetime", white: "VIP White", supreme: "VIP Supreme" };
export function span(seconds) {
    const d = Math.floor(seconds / 86400);
    const hours = Math.floor((seconds % 86400) / 3600);
    const minutes = Math.floor((seconds % 3600) / 60);
    return `${d ? `${d}d ` : ""}${d || hours ? `${hours}h ` : ""}${minutes}m`;
}
function stat(label, value, note) {
    return h("div", { class: "sa-stat" }, h("strong", {}, typeof value === "number" ? nf.format(value) : value), h("span", {}, label), note ? h("small", {}, note) : null);
}
function panelBox(title, hint, ...body) {
    return h("section", { class: "sa-box" }, h("header", {}, h("h2", {}, title), hint ? h("p", {}, hint) : null), ...body);
}
/** The first thing the team sees: how the bot is doing, the numbers, who is on VIP and what changed lately. */
export function overviewSection(overview, panel, control, go) {
    const parts = [];
    const maintenance = control?.maintenance.on ?? false;
    parts.push(h("section", { class: "sa-state", "data-state": maintenance ? "maintenance" : "online" }, h("span", { class: "status-dot", "data-state": "online" }), h("div", {}, h("strong", {}, maintenance ? "Maintenance mode is on" : "Risk is running"), h("p", {}, `${overview.latencyMs == null ? "Ping not measured yet" : `Ping ${overview.latencyMs} ms`}. Online for ${span(overview.uptime)}. ${nf.format(overview.commands)} commands.`)), control ? h("button", { class: "btn btn-quiet", type: "button", "data-go": "bot" }, maintenance ? "Turn it off" : "Maintenance") : null));
    const toBot = parts[0]?.querySelector("[data-go]");
    toBot?.addEventListener("click", () => go("bot"));
    parts.push(h("div", { class: "sa-stats" }, stat("Servers", overview.servers, `${nf.format(overview.newServers)} joined this week`), stat("Members", overview.members, `Biggest server ${nf.format(overview.biggest)}`), stat("VIP servers", overview.vip), stat("Banned servers", overview.banned)));
    const plans = Object.keys(PLAN_NAMES).map((key) => ({ key, count: overview.planCounts[key] ?? 0 }));
    const most = Math.max(1, ...plans.map((p) => p.count));
    parts.push(panelBox("VIP plans", overview.vip ? `${nf.format(overview.vip)} servers have a plan right now.` : "No server has a plan right now.", h("ul", { class: "sa-bars" }, ...plans.map((p) => h("li", {}, h("span", {}, PLAN_NAMES[p.key]), h("meter", { min: 0, max: most, value: p.count, "aria-label": `${PLAN_NAMES[p.key]} servers` }), h("b", {}, nf.format(p.count)))))));
    if (panel) {
        const biggest = [...panel.serverList].sort((a, b) => b.members - a.members).slice(0, 6);
        parts.push(panelBox("Biggest servers", null, biggest.length
            ? h("ol", { class: "sa-list" }, ...biggest.map((s) => h("li", {}, h("span", { class: "sa-name" }, s.name), h("span", { class: "sa-meta" }, `${nf.format(s.members)} members`), s.vip ? h("span", { class: "sa-pill" }, s.tier ? (PLAN_NAMES[s.tier] ?? s.tier) : "VIP") : null)))
            : h("p", { class: "dash-hint" }, "No servers yet."), h("button", { class: "btn btn-quiet", type: "button", "data-go": "servers" }, "See all servers")));
        const recent = panel.log.slice(0, 6);
        parts.push(panelBox("Recent changes", null, recent.length
            ? h("ul", { class: "sa-list" }, ...recent.map((l) => h("li", { class: "sa-stack" }, h("span", { class: "sa-name" }, `${l.action}${l.detail ? `: ${l.detail}` : ""}`.slice(0, 90)), h("span", { class: "sa-meta" }, `${/^\d+$/.test(l.by) ? "" : `${l.by}, `}${new Date(l.at * 1000).toLocaleString("en", { dateStyle: "medium", timeStyle: "short" })}`))))
            : h("p", { class: "dash-hint" }, "Nothing changed yet."), h("button", { class: "btn btn-quiet", type: "button", "data-go": "log" }, "Full history")));
        if (control) {
            const off = control.commands.filter((c) => c.off).length;
            const page = control.statusPage;
            parts.push(panelBox("Right now", null, h("ul", { class: "sa-list" }, h("li", {}, h("span", { class: "sa-name" }, "Commands switched off"), h("span", { class: "sa-pill" }, nf.format(off))), h("li", {}, h("span", { class: "sa-name" }, "Blocked users"), h("span", { class: "sa-pill" }, nf.format(control.blocked.length))), h("li", {}, h("span", { class: "sa-name" }, "Status page notice"), h("span", { class: "sa-pill" }, page?.notice.on ? "Showing" : "Hidden")), h("li", {}, h("span", { class: "sa-name" }, "Open incidents"), h("span", { class: "sa-pill" }, nf.format(page?.incidents.filter((i) => !i.resolved_at).length ?? 0)))), h("button", { class: "btn btn-quiet", type: "button", "data-go": "status" }, "Edit the status page")));
        }
        for (const section of parts) {
            section.querySelectorAll("[data-go]").forEach((b) => {
                if (b.dataset.go && !b.hasAttribute("data-bound")) {
                    b.setAttribute("data-bound", "1");
                    b.addEventListener("click", () => go(b.dataset.go ?? "overview"));
                }
            });
        }
    }
    return h("div", { class: "sa-overview" }, ...parts);
}
