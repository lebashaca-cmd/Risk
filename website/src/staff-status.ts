import { ApiFailure, staffApi } from "./api.js";
import type { StaffStatusPage } from "./dash-types.js";
import { h, mount } from "./dom.js";
import { toast } from "./ui.js";

type Refresh = () => Promise<void>;
type Btn = StaffStatusPage["buttons"][number];

const TOKENS = "{invite} {site} {docs} {dashboard} {vip} {status}";
const LEVELS: [string, string][] = [["info", "Info"], ["good", "Good news"], ["warn", "Warning"], ["bad", "Problem"]];

function messageOf(error: unknown): string {
  return error instanceof ApiFailure ? error.message : "Something went wrong. Refresh the page and try again.";
}

function when(stamp: number): string {
  return new Date(stamp * 1000).toLocaleString("en", { dateStyle: "medium", timeStyle: "short" });
}

function field(label: string, control: HTMLElement, hint?: string): HTMLElement {
  return h("div", { class: "dash-field" }, h("label", {}, label), control, hint ? h("p", { class: "dash-hint" }, hint) : null);
}

function text(value = "", placeholder = "", label = "", max = 0): HTMLInputElement {
  return h("input", { class: "dash-input", type: "text", value, placeholder, "aria-label": label || placeholder, autocomplete: "off", spellcheck: "false", maxlength: max || null });
}

function choose(options: [string, string][], value: string, label: string): HTMLSelectElement {
  const el = h("select", { class: "dash-input", "aria-label": label }, ...options.map(([id, name]) => h("option", { value: id }, name)));
  el.value = value;
  return el;
}

async function run(job: () => Promise<unknown>, done: string, refresh: Refresh): Promise<void> {
  try {
    await job();
    toast(done);
    await refresh();
  } catch (error) {
    toast(messageOf(error));
  }
}

function buttonsCard(page: StaffStatusPage, refresh: Refresh): HTMLElement {
  const rows: { label: HTMLInputElement; url: HTMLInputElement; style: HTMLSelectElement; node: HTMLElement }[] = [];
  const list = h("div", { class: "sp-edit-list" });
  const add = (b: Btn): void => {
    const label = text(b.label, "Label", "Button label", 30);
    const url = text(b.url, "https://… or /vip or {invite}", "Button link");
    const style = choose([["primary", "Bright"], ["quiet", "Quiet"]], b.style, "Button style");
    const remove = h("button", { class: "btn btn-quiet btn-small", type: "button", "aria-label": `Remove ${b.label || "button"}` }, "Remove");
    const up = h("button", { class: "btn btn-quiet btn-small", type: "button", "aria-label": "Move up" }, "Up");
    const node = h("div", { class: "sp-edit-row" }, label, url, style, up, remove);
    const row = { label, url, style, node };
    remove.addEventListener("click", () => {
      rows.splice(rows.indexOf(row), 1);
      node.remove();
    });
    up.addEventListener("click", () => {
      const i = rows.indexOf(row);
      if (i < 1) return;
      rows.splice(i, 1);
      rows.splice(i - 1, 0, row);
      list.insertBefore(node, rows[i]?.node ?? null);
    });
    rows.push(row);
    list.appendChild(node);
  };
  page.buttons.forEach(add);
  const addBtn = h("button", { class: "btn btn-quiet", type: "button" }, "Add a button");
  addBtn.addEventListener("click", () => {
    if (rows.length >= 8) return toast("A status page can have up to 8 buttons.");
    add({ label: "", url: "", style: "quiet" });
  });
  const save = h("button", { class: "btn btn-primary", type: "button" }, "Save buttons");
  save.addEventListener("click", () => void run(() => staffApi.setButtons(rows.map((r) => ({ label: r.label.value.trim(), url: r.url.value.trim(), style: r.style.value }))), "Buttons saved. The status page updates within a minute.", refresh));
  const reset = h("button", { class: "btn btn-quiet", type: "button" }, "Use the defaults");
  reset.addEventListener("click", () => void run(() => staffApi.setButtons(null), "Back to the default buttons.", refresh));
  return h(
    "section",
    { class: "dash-card staff-card", "aria-labelledby": "sp-buttons" },
    h("h2", { id: "sp-buttons" }, "Buttons"),
    h("p", { class: "dash-hint" }, `Shown under the headline on /status. A link can start with https://, be a path like /vip, or use ${TOKENS} (add a path after it, like {docs}/faq).`),
    list,
    h("div", { class: "actions" }, addBtn, save, reset),
  );
}

function noticeCard(page: StaffStatusPage, refresh: Refresh): HTMLElement {
  const on = h("input", { type: "checkbox", "aria-label": "Show the notice" });
  on.checked = page.notice.on;
  const level = choose(LEVELS, page.notice.level, "Notice level");
  const body = text(page.notice.text, "e.g. Maintenance at 5pm UTC", "Notice text", 300);
  const save = h("button", { class: "btn btn-primary", type: "button" }, "Save notice");
  save.addEventListener("click", () => void run(() => staffApi.setNotice(on.checked, level.value, body.value), on.checked ? "The notice is showing." : "The notice is hidden.", refresh));
  return h(
    "section",
    { class: "dash-card staff-card", "aria-labelledby": "sp-notice" },
    h("h2", { id: "sp-notice" }, "Notice banner"),
    h("p", { class: "dash-hint" }, "A line of text shown above the numbers. Use it for planned work or news."),
    h("label", { class: "staff-off staff-maint" }, on, "Show the notice"),
    field("Level", level),
    field("Text", body),
    h("div", { class: "actions" }, save),
  );
}

function incidentsCard(page: StaffStatusPage, refresh: Refresh): HTMLElement {
  const title = text("", "What's wrong", "Incident title", 80);
  const body = text("", "Details (optional)", "Incident details", 500);
  const level = choose(LEVELS, "warn", "Incident level");
  const add = h("button", { class: "btn btn-primary", type: "button" }, "Post incident");
  add.addEventListener("click", () => {
    if (!title.value.trim()) return toast("Give the incident a title.");
    void run(() => staffApi.addIncident(title.value, body.value, level.value), "Incident posted.", refresh);
  });
  const rows = page.incidents.map((i) => {
    const resolve = h("button", { class: "btn btn-quiet btn-small", type: "button" }, "Mark resolved");
    resolve.disabled = i.resolved_at !== null;
    resolve.addEventListener("click", () => void run(() => staffApi.resolveIncident(i.id, ""), "Marked resolved.", refresh));
    const remove = h("button", { class: "btn btn-quiet btn-small staff-danger", type: "button" }, "Delete");
    remove.addEventListener("click", () => {
      if (window.confirm(`Delete "${i.title}"?`)) void run(() => staffApi.removeIncident(i.id), "Incident deleted.", refresh);
    });
    return h("div", { class: "staff-row" }, h("div", { class: "staff-row-text" }, h("strong", {}, i.title), h("span", {}, `${i.resolved_at ? `Resolved ${when(i.resolved_at)}` : "Ongoing"} · posted ${when(i.at)}`), i.text ? h("span", {}, i.text) : null), h("div", { class: "staff-row-actions" }, resolve, remove));
  });
  return h(
    "section",
    { class: "dash-card staff-card", "aria-labelledby": "sp-incidents" },
    h("h2", { id: "sp-incidents" }, "Incidents"),
    h("p", { class: "dash-hint" }, "Shown on the status page, newest first. Mark one resolved when it's fixed."),
    h("div", { class: "staff-grant" }, field("Title", title), field("Level", level), field("Details", body)),
    h("div", { class: "actions" }, add),
    ...(rows.length ? rows : [h("p", { class: "dash-hint" }, "No incidents.")]),
  );
}

export function statusPageSection(page: StaffStatusPage | null, refresh: Refresh): HTMLElement {
  const wrap = h("div", { class: "staff-stack" });
  if (!page) {
    mount(wrap, h("p", { class: "dash-hint" }, "The status page isn't on the bot yet. Upload cogs/status_page.py and restart the bot."));
    return wrap;
  }
  mount(wrap, h("p", { class: "dash-hint" }, h("a", { href: "/status", target: "_blank", rel: "noopener" }, "Open the status page"), " to see your changes."), buttonsCard(page, refresh), noticeCard(page, refresh), incidentsCard(page, refresh));
  return wrap;
}
