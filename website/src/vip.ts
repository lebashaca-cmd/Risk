import { h } from "./dom.js";
import type { SiteConfig, VipPlan } from "./types.js";

const CORE = [
  "Scheduled announcements, from the dashboard or with !schedule",
  "Embed-style auto-replies and a custom accent colour",
  "!vippoll, !vipannounce, !vipsay and !vipembed",
  "!servercard, !userreport, !rolereport and !topmessages",
  "!vipcolor and !viprolecolor",
  "A VIP badge and tab in your server's dashboard",
];

type PlanKey = "basic" | "lifetime" | "white" | "supreme";

interface PlanInfo {
  key: PlanKey;
  name: string;
  period: string;
  note: string;
  perks: string[];
  featured?: boolean;
}

// Edit this list to change what each plan says. Prices and checkout links come from the site's environment.
const PLANS: PlanInfo[] = [
  { key: "basic", name: "Basic", period: "per month", note: "Cancel any time. VIP stays on until the end of the month you paid for.", perks: [...CORE, "Renews every month until you cancel"] },
  { key: "lifetime", name: "Lifetime", period: "one time", note: "Pay once. Every VIP feature, forever, on that server.", perks: ["Everything in Basic, VIP White and VIP Supreme", "Custom commands, auto reactions, welcome DM, auto delete, server lock, backups and more", "Up to 200 custom commands", "Lifetime-only: !founder supporter card and !motd message of the day", "Never expires, and new VIP features are included"], featured: true },
  {
    key: "white",
    name: "VIP White",
    period: "per month",
    note: "Everything in Basic, plus tools for running a community.",
    perks: ["Everything in Basic", "!customcmd: your own text commands (up to 50)", "!autoreact: react to chosen words", "!welcomedm: a private welcome message", "!embededit and !stafflist", "Priority support in the support server"],
  },
  {
    key: "supreme",
    name: "VIP Supreme",
    period: "per month",
    note: "Everything in White, plus power tools for big servers.",
    perks: ["Everything in VIP White", "!autodelete: clear a channel on a timer", "!lockall and !unlockall for the whole server", "!serverbackup and !permaudit", "!membercounter and !slowmodeall", "Up to 200 custom commands"],
  },
];

function plan(info: PlanInfo, data: VipPlan | undefined): HTMLElement {
  const action = data?.url
    ? h("a", { class: info.featured ? "btn btn-primary" : "btn btn-quiet", href: data.url, rel: "noopener noreferrer", target: "_blank" }, `Get ${info.name.toLowerCase()}`)
    : h("button", { class: "btn btn-quiet", type: "button", disabled: true }, "Not on sale yet");
  return h(
    "article",
    { class: `vip-plan${info.featured ? " vip-featured" : ""}`, "data-plan": info.key },
    h("h2", {}, info.name),
    h("p", { class: "vip-price" }, h("strong", {}, data?.price ?? ""), h("span", {}, info.period)),
    h("p", { class: "vip-note" }, info.note),
    h("p", { class: "vip-incl" }, "What's included"),
    h("ul", { class: "vip-list" }, ...info.perks.map((text) => h("li", {}, text))),
    action,
  );
}

/** A coverflow: the chosen plan sits flat in the middle and its neighbours tilt away on either side. */
function slider(cards: HTMLElement[], start: number): HTMLElement {
  let active = Math.min(Math.max(start, 0), cards.length - 1);
  const slots = cards.map((card) => h("div", { class: "vip-slot" }, card));
  const stage = h("div", { class: "vip-stage", tabindex: "0", role: "group", "aria-roledescription": "carousel", "aria-label": "VIP plans. Use the left and right arrow keys to change plan." }, ...slots);
  const dots = cards.map((_, i) => h("button", { class: "vip-dot", type: "button", "aria-label": `Show plan ${i + 1} of ${cards.length}` }));
  const dotRow = h("div", { class: "vip-dots" }, ...dots);

  const show = (next: number): void => {
    active = Math.min(Math.max(next, 0), cards.length - 1);
    slots.forEach((slot, i) => {
      const offset = i - active;
      slot.style.setProperty("--o", String(offset));
      slot.style.setProperty("--a", String(Math.abs(offset)));
      slot.dataset.pos = offset === 0 ? "center" : Math.abs(offset) === 1 ? "side" : "far";
      slot.setAttribute("aria-hidden", offset === 0 ? "false" : "true");
      cards[i]?.toggleAttribute("inert", offset !== 0);
    });
    dots.forEach((dot, i) => {
      dot.classList.toggle("on", i === active);
      if (i === active) dot.setAttribute("aria-current", "true");
      else dot.removeAttribute("aria-current");
    });
  };

  let swiped = false;
  slots.forEach((slot, i) => slot.addEventListener("click", () => !swiped && i !== active && show(i)));
  dots.forEach((dot, i) => dot.addEventListener("click", () => show(i)));
  stage.addEventListener("keydown", (event) => {
    if (event.key === "ArrowRight") show(active + 1);
    else if (event.key === "ArrowLeft") show(active - 1);
    else return;
    event.preventDefault();
  });

  // Swipe or drag sideways to change plan.
  let startX: number | null = null;
  stage.addEventListener("pointerdown", (event) => {
    startX = event.clientX;
  });
  stage.addEventListener("pointerup", (event) => {
    if (startX === null) return;
    const moved = event.clientX - startX;
    startX = null;
    if (Math.abs(moved) > 40) {
      swiped = true; // the click that follows a drag must not undo it
      window.setTimeout(() => (swiped = false), 0);
      show(active + (moved < 0 ? 1 : -1));
    }
  });
  stage.addEventListener("pointercancel", () => {
    startX = null;
  });

  show(active);
  return h("div", { class: "vip-slider" }, stage, dotRow);
}

export function renderVip(config: SiteConfig): HTMLElement {
  const vip = config.vip;
  const support = config.supportUrl;
  return h(
    "div",
    { class: "view container page vip" },
    h("h1", {}, "Risk VIP"),
    h("p", { class: "lede" }, "Extra tools for one server. Pay monthly, or once for good."),
    slider(PLANS.map((info) => plan(info, vip?.[info.key])), PLANS.findIndex((info) => info.featured)),
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
