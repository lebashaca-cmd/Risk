import { h } from "./dom.js";
import type { SiteConfig, VipPlan } from "./types.js";

const PERKS = [
  "Scheduled announcements, from the dashboard or with !schedule",
  "Embed-style auto-replies",
  "A custom accent colour for Risk's embeds in your server",
  "VIP-only commands: !vipembed, !serverstats and !schedule",
  "A VIP badge and tab in your server's dashboard",
];

function plan(name: string, price: string, period: string, note: string, data: VipPlan | undefined, featured: boolean): HTMLElement {
  const action = data?.url
    ? h("a", { class: featured ? "btn btn-primary" : "btn btn-quiet", href: data.url, rel: "noopener noreferrer", target: "_blank" }, `Get ${name.toLowerCase()}`)
    : h("button", { class: "btn btn-quiet", type: "button", disabled: true }, "Not on sale yet");
  return h(
    "article",
    { class: `vip-plan${featured ? " vip-featured" : ""}` },
    h("h2", {}, name),
    h("p", { class: "vip-price" }, h("strong", {}, price), h("span", {}, period)),
    h("p", { class: "vip-note" }, note),
    action,
  );
}

export function renderVip(config: SiteConfig): HTMLElement {
  const vip = config.vip;
  const support = config.supportUrl;
  return h(
    "div",
    { class: "view container page vip" },
    h("h1", {}, "Risk VIP"),
    h("p", { class: "lede" }, "Extra tools for one server. Pay monthly, or once for good."),
    h(
      "div",
      { class: "vip-plans" },
      plan("Monthly", vip?.monthly.price ?? "", "per month", "Cancel any time. VIP stays on until the end of the month you paid for.", vip?.monthly, false),
      plan("Lifetime", vip?.lifetime.price ?? "", "one time", "Pay once. VIP never expires on that server.", vip?.lifetime, true),
    ),
    h("h2", { class: "vip-sub" }, "Both plans include"),
    h("ul", { class: "vip-perks" }, ...PERKS.map((text) => h("li", {}, text))),
    h("h2", { class: "vip-sub" }, "After you pay"),
    h(
      "ol",
      { class: "vip-steps" },
      h("li", {}, "Copy your server's ID: turn on Developer Mode in Discord, then right-click the server and choose Copy Server ID."),
      h("li", {}, support ? h("span", {}, "Send the ID and your receipt in the ", h("a", { href: support, rel: "noopener noreferrer", target: "_blank" }, "support server"), ".") : "Send the ID and your receipt to the bot owner."),
      h("li", {}, "VIP is switched on for that server, and the VIP tab in the dashboard unlocks."),
    ),
    h("p", { class: "dash-fine" }, "VIP belongs to one server. Payments are handled by the payment provider, and Risk never sees your card details."),
  );
}
