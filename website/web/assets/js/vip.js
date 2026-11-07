import { h } from "./dom.js";
const CORE = [
    "Scheduled announcements, from the dashboard or with !schedule",
    "Embed-style auto-replies",
    "A custom accent colour for Risk's embeds in your server",
    "VIP-only commands: !vipembed, !serverstats and !schedule",
    "A VIP badge and tab in your server's dashboard",
];
// Edit this list to change what each plan says. Prices and checkout links come from the site's environment.
const PLANS = [
    { key: "basic", name: "Basic", period: "per month", note: "Cancel any time. VIP stays on until the end of the month you paid for.", perks: [...CORE, "Renews every month until you cancel"] },
    { key: "lifetime", name: "Lifetime", period: "one time", note: "Pay once. VIP never expires on that server.", perks: [...CORE, "Never expires, and every future VIP feature is included"], featured: true },
    { key: "white", name: "VIP White", period: "per month", note: "Everything in Basic, with priority help.", perks: ["Everything in Basic", "Priority support in the support server", "Ask for a feature and it goes to the front of the list", "A White role in the support server"] },
    { key: "supreme", name: "VIP Supreme", period: "per month", note: "Everything in White, for the biggest servers.", perks: ["Everything in VIP White", "Early access to new features", "Direct help setting up your server", "A Supreme role in the support server"] },
];
function plan(info, data) {
    const action = data?.url
        ? h("a", { class: info.featured ? "btn btn-primary" : "btn btn-quiet", href: data.url, rel: "noopener noreferrer", target: "_blank" }, `Get ${info.name.toLowerCase()}`)
        : h("button", { class: "btn btn-quiet", type: "button", disabled: true }, "Not on sale yet");
    return h("article", { class: `vip-plan${info.featured ? " vip-featured" : ""}`, "data-plan": info.key }, h("h2", {}, info.name), h("p", { class: "vip-price" }, h("strong", {}, data?.price ?? ""), h("span", {}, info.period)), h("p", { class: "vip-note" }, info.note), h("p", { class: "vip-incl" }, "What's included"), h("ul", { class: "vip-list" }, ...info.perks.map((text) => h("li", {}, text))), action);
}
/** Cards in a row you can swipe or scroll, with a slider underneath that moves the row. */
function slider(cards) {
    const track = h("div", { class: "vip-track", tabindex: "0", role: "group", "aria-label": "VIP plans" }, ...cards);
    const range = h("input", { class: "vip-range", type: "range", min: "0", max: "100", step: "1", value: "0", "aria-label": "Slide to see more VIP plans" });
    let syncing = false;
    const maxScroll = () => Math.max(0, track.scrollWidth - track.clientWidth);
    const nearest = () => {
        const step = cards.length > 1 ? (cards[1]?.offsetLeft ?? 0) - (cards[0]?.offsetLeft ?? 0) : 1;
        return Math.min(maxScroll(), Math.round(track.scrollLeft / Math.max(step, 1)) * step);
    };
    const fromTrack = () => {
        if (syncing)
            return;
        const max = maxScroll();
        range.value = max > 0 ? String(Math.round((track.scrollLeft / max) * 100)) : "0";
        range.disabled = max <= 0;
    };
    const fromRange = () => {
        syncing = true;
        track.scrollLeft = (Number(range.value) / 100) * maxScroll();
        window.setTimeout(() => (syncing = false), 60);
    };
    track.addEventListener("scroll", fromTrack, { passive: true });
    range.addEventListener("input", fromRange);
    range.addEventListener("change", () => track.scrollTo({ left: nearest(), behavior: "smooth" }));
    window.addEventListener("resize", fromTrack);
    window.requestAnimationFrame(fromTrack);
    const dots = h("p", { class: "vip-hint" }, "Slide to see all plans");
    return h("div", { class: "vip-slider" }, track, range, dots);
}
export function renderVip(config) {
    const vip = config.vip;
    const support = config.supportUrl;
    return h("div", { class: "view container page vip" }, h("h1", {}, "Risk VIP"), h("p", { class: "lede" }, "Extra tools for one server. Pay monthly, or once for good."), slider(PLANS.map((info) => plan(info, vip?.[info.key]))), h("h2", { class: "vip-sub" }, "After you pay"), h("ol", { class: "vip-steps" }, h("li", {}, "Copy your server's ID: turn on Developer Mode in Discord, then right-click the server and choose Copy Server ID."), h("li", {}, support ? h("span", {}, "Send the ID and your receipt in the ", h("a", { href: support, rel: "noopener noreferrer", target: "_blank" }, "support server"), ".") : "Send the ID and your receipt to the bot owner."), h("li", {}, "VIP is switched on for that server, and the VIP tab in the dashboard unlocks.")), h("p", { class: "dash-fine" }, "VIP belongs to one server. Payments are handled by the payment provider, and Risk never sees your card details."));
}
