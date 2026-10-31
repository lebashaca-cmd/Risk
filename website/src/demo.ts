import { h } from "./dom.js";

interface Scenario {
  id: string;
  label: string;
  blurb: string;
  command: string;
  reply: () => Node[];
}

const wait = (ms: number) => new Promise<void>((resolve) => setTimeout(resolve, ms));

function embed(bar: string, title: string, description: string | null, fields: [string, string][], footer?: string): HTMLElement {
  return h(
    "div",
    { class: `embed bar-${bar}` },
    h("div", { class: "embed-title" }, title),
    description ? h("div", { class: "embed-desc" }, description) : null,
    fields.length
      ? h(
          "div",
          { class: "embed-fields" },
          ...fields.map(([name, value], i) =>
            h("div", { class: "embed-field", style: `--f:${i}` }, h("div", { class: "embed-field-name" }, name), h("div", {}, value)),
          ),
        )
      : null,
    footer ? h("div", { class: "embed-footer" }, footer) : null,
  );
}

const SCENARIOS: Scenario[] = [
  {
    id: "tickets",
    label: "Tickets",
    blurb: "Members press a button and get a private channel with your staff.",
    command: ",ticket 123456789012345678 @Staff",
    reply: () => [
      embed(
        "blurple",
        "🎫 Support Tickets",
        "Need help? Press the button below to open a private ticket. @Staff will be notified as soon as you open one.",
        [],
        "One open ticket per person.",
      ),
      h("div", { class: "button-row" }, h("span", { class: "dbtn" }, "🎫 Open Ticket")),
    ],
  },
  {
    id: "lookups",
    label: "Lookups",
    blurb: "Profiles, repos, videos and songs as one clean embed.",
    command: ",github adalin",
    reply: () => [
      embed("grey", "Ada Lin (adalin)", "Compilers and tiny tools.", [
        ["Followers", "1,284"],
        ["Following", "31"],
        ["Public Repos", "42"],
        ["Location", "Lisbon"],
      ]),
    ],
  },
  {
    id: "ai",
    label: "AI answers",
    blurb: "Ask a question. Code comes back in a highlighted block.",
    command: ",ask write hello world in lua",
    reply: () => [
      h("div", { class: "msg-text" }, "Here you go:"),
      h("div", { class: "codeblock" }, h("span", { class: "codelang" }, "lua"), h("code", {}, 'print("Hello, world!")')),
    ],
  },
];

function message(kind: "user" | "bot", ...body: Node[]): HTMLElement {
  const name = kind === "bot" ? "Risk" : "mara";
  return h(
    "div",
    { class: "msg" },
    h("div", { class: `avatar ${kind}`, "aria-hidden": "true" }, name.charAt(0).toUpperCase()),
    h(
      "div",
      { class: "msg-body" },
      h("div", { class: "msg-head" }, h("span", { class: "msg-name" }, name), kind === "bot" ? h("span", { class: "tag" }, "APP") : null),
      ...body,
    ),
  );
}

const typingIndicator = (): HTMLElement =>
  message("bot", h("div", { class: "typing", "aria-label": "Risk is typing" }, h("i"), h("i"), h("i")));

export function mountDemo(root: HTMLElement): () => void {
  const reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  let run = 0;
  let active = 0;

  const log = h("div", { class: "chat-log" });
  const typed = h("span", { class: "composer-text" });
  const composer = h(
    "div",
    { class: "composer", "aria-hidden": "true" },
    h("span", { class: "composer-plus" }, "+"),
    typed,
    h("span", { class: "caret" }),
  );
  const panel = h("div", { class: "chat", id: "chat-panel", role: "tabpanel", "aria-label": "Example conversation" }, log, composer);

  const tabs = SCENARIOS.map((scenario, index) =>
    h(
      "button",
      {
        class: "scenario",
        type: "button",
        role: "tab",
        id: `tab-${scenario.id}`,
        "aria-controls": "chat-panel",
        "aria-selected": "false",
        tabindex: "-1",
        onclick: () => select(index),
        onkeydown: (event: Event) => {
          const key = (event as KeyboardEvent).key;
          const forward = key === "ArrowDown" || key === "ArrowRight";
          const back = key === "ArrowUp" || key === "ArrowLeft";
          if (!forward && !back) return;
          event.preventDefault();
          const to = (index + (forward ? 1 : -1) + SCENARIOS.length) % SCENARIOS.length;
          select(to);
          tabs[to]?.focus();
        },
      },
      h("strong", {}, scenario.label),
      h("span", { class: "blurb" }, scenario.blurb),
      h("code", {}, scenario.command),
    ),
  );

  async function play(index: number, animate: boolean): Promise<void> {
    const token = ++run;
    const scenario = SCENARIOS[index];
    if (!scenario) return;
    log.replaceChildren();
    typed.textContent = "";
    root.classList.remove("is-typing");

    if (!animate || reduceMotion) {
      log.append(message("user", h("div", { class: "msg-text" }, scenario.command)), message("bot", ...scenario.reply()));
      return;
    }

    root.classList.add("is-typing");
    for (const char of scenario.command) {
      typed.textContent += char;
      await wait(26 + Math.random() * 34);
      if (token !== run) return;
    }
    await wait(260);
    if (token !== run) return;
    typed.textContent = "";
    root.classList.remove("is-typing");
    log.append(message("user", h("div", { class: "msg-text" }, scenario.command)));
    await wait(450);
    if (token !== run) return;
    const dots = typingIndicator();
    log.append(dots);
    await wait(900);
    if (token !== run) return;
    dots.replaceWith(message("bot", ...scenario.reply()));
  }

  function mark(index: number): void {
    active = index;
    tabs.forEach((tab, i) => {
      tab.setAttribute("aria-selected", String(i === index));
      tab.tabIndex = i === index ? 0 : -1;
    });
    const scenario = SCENARIOS[index];
    if (scenario) panel.setAttribute("aria-labelledby", `tab-${scenario.id}`);
  }

  function select(index: number): void {
    mark(index);
    void play(index, true);
  }

  root.replaceChildren(
    h("div", { class: "scenario-list", role: "tablist", "aria-label": "Example commands", "aria-orientation": "vertical" }, ...tabs),
    h("div", { class: "demo-stage" }, panel, h("p", { class: "fine" }, "Example output. Your server shows real results.")),
  );

  mark(0);
  void play(0, false);

  let observer: IntersectionObserver | null = null;
  if (!reduceMotion && "IntersectionObserver" in window) {
    observer = new IntersectionObserver(
      (entries) => {
        if (!entries.some((entry) => entry.isIntersecting)) return;
        observer?.disconnect();
        void play(active, true);
      },
      { threshold: 0.4 },
    );
    observer.observe(panel);
  }

  return () => {
    run += 1;
    observer?.disconnect();
  };
}
