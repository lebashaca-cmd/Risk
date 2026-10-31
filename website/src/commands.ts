import { api } from "./api.js";
import { h, mount, type Child } from "./dom.js";
import { copyWithToast, flashCopied } from "./ui.js";
import type { CommandInfo, CommandsPayload } from "./types.js";

function usageLines(command: CommandInfo, prefix: string): string[] {
  if (command.kind === "slash") return [`/${command.name}`];
  const base = `${prefix}${command.name}`;
  if (!command.examples.length) return [base];
  return command.examples.map((args) => (args ? `${base} ${args}` : base));
}

function matches(command: CommandInfo, query: string): boolean {
  if (!query) return true;
  const haystack = `${command.name} ${command.description} ${command.category} ${command.examples.join(" ")}`.toLowerCase();
  return query
    .toLowerCase()
    .split(/\s+/)
    .every((word) => haystack.includes(word));
}

function escapeRegExp(text: string): string {
  return text.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}

function highlight(text: string, query: string): Child[] {
  const words = query.split(/\s+/).filter(Boolean).map(escapeRegExp);
  if (!words.length) return [text];
  const parts = text.split(new RegExp(`(${words.join("|")})`, "ig"));
  return parts.map((part, i) => (i % 2 === 1 ? h("mark", {}, part) : part));
}

export function renderCommands(): { node: HTMLElement; cleanup: () => void } {
  const node = h("div", { class: "view container page" });
  const body = h("div", { class: "commands-body" }, h("p", { class: "muted" }, "Loading commands"));
  node.append(h("h1", {}, "Commands"), body);

  const onKey = (event: KeyboardEvent) => {
    if (event.key !== "/" || event.metaKey || event.ctrlKey || event.altKey) return;
    const active = document.activeElement;
    if (active instanceof HTMLInputElement || active instanceof HTMLTextAreaElement) return;
    const search = document.getElementById("command-search");
    if (!search) return;
    event.preventDefault();
    search.focus();
  };
  document.addEventListener("keydown", onKey);

  api
    .commands()
    .then((data) => build(body, data))
    .catch(() => {
      mount(body, h("p", { class: "empty" }, "The command list didn't load. Refresh the page, or type !commands in your server."));
    });

  return { node, cleanup: () => document.removeEventListener("keydown", onKey) };
}

function build(body: HTMLElement, data: CommandsPayload): void {
  let query = "";
  let category = "All";
  let prefix = data.prefixes[0] ?? "!";
  let animateNext = true;

  const categories = ["All", ...Array.from(new Set(data.commands.map((c) => c.category)))];
  const countOf = (name: string) => (name === "All" ? data.commands.length : data.commands.filter((c) => c.category === name).length);

  const search = h("input", {
    class: "search",
    type: "search",
    id: "command-search",
    placeholder: "Search by name or what it does",
    autocomplete: "off",
    spellcheck: "false",
    oninput: (event: Event) => {
      query = (event.target as HTMLInputElement).value.trim();
      renderList();
    },
  });

  const chipButtons = categories.map((name) =>
    h(
      "button",
      { class: "chip", type: "button", "aria-pressed": String(name === category), onclick: () => setCategory(name) },
      name,
      h("span", { class: "count" }, String(countOf(name))),
    ),
  );
  const prefixButtons = data.prefixes.map((p) =>
    h("button", { class: "chip chip-mono", type: "button", "aria-pressed": String(p === prefix), onclick: () => setPrefix(p) }, p),
  );

  const summary = h("p", { class: "summary", role: "status" });
  const list = h("div", { class: "command-groups" });

  function setCategory(name: string): void {
    category = name;
    animateNext = true;
    chipButtons.forEach((button, i) => button.setAttribute("aria-pressed", String(categories[i] === name)));
    renderList();
  }

  function setPrefix(value: string): void {
    prefix = value;
    prefixButtons.forEach((button, i) => button.setAttribute("aria-pressed", String(data.prefixes[i] === value)));
    renderList();
  }

  function renderList(): void {
    const visible = data.commands.filter((c) => (category === "All" || c.category === category) && matches(c, query));
    summary.textContent = `${visible.length} ${visible.length === 1 ? "command" : "commands"}`;
    list.classList.toggle("stagger", animateNext);
    animateNext = false;

    if (!visible.length) {
      mount(
        list,
        h(
          "div",
          { class: "empty" },
          h("p", {}, query ? `Nothing matches "${query}".` : "No commands in this category."),
          h(
            "button",
            {
              class: "btn btn-quiet",
              type: "button",
              onclick: () => {
                query = "";
                (search as HTMLInputElement).value = "";
                setCategory("All");
              },
            },
            "Show all commands",
          ),
        ),
      );
      return;
    }

    const groups = new Map<string, CommandInfo[]>();
    for (const command of visible) groups.set(command.category, [...(groups.get(command.category) ?? []), command]);

    let index = 0;
    mount(
      list,
      ...Array.from(groups, ([name, commands]) =>
        h(
          "section",
          { class: "command-group", "aria-label": name },
          h("h2", {}, name),
          h(
            "ul",
            { class: "command-list" },
            ...commands.map((command) => {
              const order = Math.min(index++, 14);
              return h(
                "li",
                { class: "command", style: `--i:${order}` },
                h(
                  "div",
                  { class: "command-use" },
                  ...usageLines(command, prefix).map((line) => {
                    const button = h(
                      "button",
                      {
                        class: "usage",
                        type: "button",
                        title: "Copy this command",
                        "aria-label": `Copy ${line}`,
                        onclick: () => {
                          flashCopied(button);
                          void copyWithToast(line);
                        },
                      },
                      h("code", {}, ...highlight(line, query)),
                    );
                    return button;
                  }),
                ),
                h(
                  "div",
                  { class: "command-info" },
                  h("p", {}, ...highlight(command.description || "No description yet.", query)),
                  command.permission ? h("p", { class: "perm" }, `Needs ${command.permission}`) : null,
                ),
              );
            }),
          ),
        ),
      ),
    );
  }

  mount(
    body,
    h(
      "div",
      { class: "controls" },
      h(
        "div",
        { class: "search-wrap" },
        h("label", { class: "sr-only", for: "command-search" }, "Search commands"),
        search,
        h("kbd", { class: "kbd", "aria-hidden": "true" }, "/"),
      ),
      h("div", { class: "chip-row", role: "group", "aria-label": "Category" }, ...chipButtons),
      data.prefixes.length > 1
        ? h("div", { class: "chip-row", role: "group", "aria-label": "Prefix" }, h("span", { class: "chip-label" }, "Prefix"), ...prefixButtons)
        : null,
    ),
    summary,
    list,
  );
  renderList();
}
