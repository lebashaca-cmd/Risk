import { h } from "./dom.js";
import type { Child } from "./dom.js";
import type { Meta } from "./dash-types.js";

let counter = 0;
export function uid(prefix: string): string {
  counter += 1;
  return `${prefix}-${counter}`;
}

export function group(title: string, hint: string | null, ...children: Child[]): HTMLElement {
  return h("section", { class: "dash-group" }, h("h3", {}, title), hint ? h("p", { class: "dash-hint" }, hint) : null, ...children);
}

function labelled(id: string, label: string, control: HTMLElement, hint?: string): HTMLElement {
  return h(
    "div",
    { class: "dash-field" },
    h("label", { for: id }, label),
    control,
    hint ? h("p", { class: "dash-hint", id: `${id}-hint` }, hint) : null,
  );
}

export function toggle(label: string, hint: string | undefined, value: boolean, onChange: (value: boolean) => void): HTMLElement {
  const id = uid("sw");
  const input = h("input", { type: "checkbox", id, role: "switch", class: "dash-switch-input", "aria-describedby": hint ? `${id}-hint` : null });
  input.checked = value;
  input.addEventListener("change", () => onChange(input.checked));
  return h(
    "div",
    { class: "dash-toggle" },
    input,
    h("label", { for: id, class: "dash-switch", "aria-hidden": "true" }),
    h("div", { class: "dash-toggle-text" }, h("label", { for: id }, label), hint ? h("p", { class: "dash-hint", id: `${id}-hint` }, hint) : null),
  );
}

interface TextOptions {
  max?: number;
  placeholder?: string;
  hint?: string;
  rows?: number;
}

export function textInput(label: string, value: string, onChange: (value: string) => void, options: TextOptions = {}): HTMLElement {
  const id = uid("tx");
  const input = h("input", { type: "text", id, class: "dash-input", maxlength: options.max ?? 200, placeholder: options.placeholder ?? "", autocomplete: "off", spellcheck: false, "aria-describedby": options.hint ? `${id}-hint` : null });
  input.value = value;
  input.addEventListener("input", () => onChange(input.value));
  return labelled(id, label, input, options.hint);
}

export function textArea(label: string, value: string, onChange: (value: string) => void, options: TextOptions = {}): HTMLElement {
  const id = uid("ta");
  const area = h("textarea", { id, class: "dash-input dash-area", maxlength: options.max ?? 1500, rows: options.rows ?? 4, placeholder: options.placeholder ?? "", "aria-describedby": options.hint ? `${id}-hint` : null });
  area.value = value;
  const counterEl = h("span", { class: "dash-count", "aria-hidden": "true" }, `${value.length}/${options.max ?? 1500}`);
  area.addEventListener("input", () => {
    counterEl.textContent = `${area.value.length}/${options.max ?? 1500}`;
    onChange(area.value);
  });
  return labelled(id, label, h("div", { class: "dash-area-wrap" }, area, counterEl), options.hint);
}

export function numberInput(label: string, value: number, onChange: (value: number) => void, min: number, max: number, step = 1, hint?: string): HTMLElement {
  const id = uid("nm");
  const input = h("input", { type: "number", id, class: "dash-input dash-number", min, max, step, inputmode: "decimal", "aria-describedby": hint ? `${id}-hint` : null });
  input.value = String(value);
  input.addEventListener("input", () => {
    const parsed = Number(input.value);
    if (input.value !== "" && Number.isFinite(parsed)) onChange(parsed);
  });
  return labelled(id, label, input, hint ?? `From ${min} to ${max}.`);
}

export interface Choice {
  value: string;
  label: string;
  disabled?: boolean;
}

export function selectInput(label: string, choices: Choice[], value: string, onChange: (value: string) => void, hint?: string): HTMLElement {
  const id = uid("sl");
  const select = h("select", { id, class: "dash-input", "aria-describedby": hint ? `${id}-hint` : null });
  for (const choice of choices) {
    const option = h("option", { value: choice.value, disabled: choice.disabled ?? false }, choice.label);
    if (choice.value === value) option.selected = true;
    select.appendChild(option);
  }
  select.addEventListener("change", () => onChange(select.value));
  return labelled(id, label, select, hint);
}

export function channelChoices(meta: Meta, none: string | null, extra: Choice[] = []): Choice[] {
  const choices: Choice[] = [];
  if (none !== null) choices.push({ value: "", label: none });
  choices.push(...extra);
  for (const channel of meta.channels) {
    choices.push({ value: channel.id, label: `#${channel.name}${channel.category ? `  (${channel.category})` : ""}${channel.canSend ? "" : "  (I can't post here)"}`, disabled: !channel.canSend });
  }
  return choices;
}

export function channelSelect(label: string, meta: Meta, value: string | null, onChange: (value: string | null) => void, none = "Off", hint?: string): HTMLElement {
  const known = value && !meta.channels.some((c) => c.id === value) ? [{ value, label: "A channel that no longer exists" }] : [];
  return selectInput(label, [...channelChoices(meta, none), ...known], value ?? "", (v) => onChange(v === "" ? null : v), hint);
}

export function roleSelect(label: string, meta: Meta, value: string | null, onChange: (value: string | null) => void, none = "None", hint?: string): HTMLElement {
  const choices: Choice[] = [{ value: "", label: none }];
  for (const role of meta.roles) choices.push({ value: role.id, label: role.assignable ? `@${role.name}` : `@${role.name}  (above my role)`, disabled: !role.assignable });
  if (value && !meta.roles.some((r) => r.id === value)) choices.push({ value, label: "A role that no longer exists" });
  return selectInput(label, choices, value ?? "", (v) => onChange(v === "" ? null : v), hint);
}

function chip(text: string, onRemove: () => void, color?: string | null): HTMLElement {
  const remove = h("button", { type: "button", class: "dash-chip-x", "aria-label": `Remove ${text}` }, "×");
  remove.addEventListener("click", onRemove);
  return h("span", { class: "dash-chip" }, color ? h("i", { class: "dash-dot", style: `background:${color}` }) : null, text, remove);
}

/** A list of chips with a picker to add more. `pool` is the choices; `values` is the current selection. */
export function multiPicker(label: string, pool: Choice[], values: string[], onChange: (values: string[]) => void, hint?: string, empty = "Nothing added."): HTMLElement {
  const id = uid("mp");
  const list = h("div", { class: "dash-chips", "aria-live": "polite" });
  const select = h("select", { id, class: "dash-input", "aria-describedby": hint ? `${id}-hint` : null });
  const names = new Map(pool.map((c) => [c.value, c.label.replace(/\s{2,}\(.*\)$/, "")]));
  const draw = (): void => {
    list.replaceChildren();
    if (values.length === 0) list.appendChild(h("span", { class: "dash-empty" }, empty));
    for (const value of values) {
      list.appendChild(
        chip(names.get(value) ?? "Removed item", () => {
          values = values.filter((v) => v !== value);
          onChange(values);
          draw();
        }),
      );
    }
    select.replaceChildren(h("option", { value: "" }, "Add…"));
    for (const choice of pool) {
      if (values.includes(choice.value) || choice.value === "") continue;
      select.appendChild(h("option", { value: choice.value }, choice.label));
    }
  };
  select.addEventListener("change", () => {
    if (!select.value) return;
    values = [...values, select.value];
    onChange(values);
    draw();
    select.focus();
  });
  draw();
  return labelled(id, label, h("div", { class: "dash-multi" }, list, select), hint);
}

export function multiChannels(label: string, meta: Meta, values: string[], onChange: (values: string[]) => void, hint?: string): HTMLElement {
  const pool = meta.channels.map((c) => ({ value: c.id, label: `#${c.name}${c.category ? `  (${c.category})` : ""}` }));
  return multiPicker(label, pool, values, onChange, hint);
}

export function multiRoles(label: string, meta: Meta, values: string[], onChange: (values: string[]) => void, hint?: string): HTMLElement {
  return multiPicker(label, meta.roles.map((r) => ({ value: r.id, label: `@${r.name}` })), values, onChange, hint);
}

/** Free-text tags: type a value and press Enter or Add. */
export function tagEditor(label: string, values: string[], onChange: (values: string[]) => void, options: { max: number; maxLength: number; minLength?: number; placeholder?: string; hint?: string; lower?: boolean }): HTMLElement {
  const id = uid("tg");
  const list = h("div", { class: "dash-chips", "aria-live": "polite" });
  const input = h("input", { type: "text", id, class: "dash-input", maxlength: options.maxLength, placeholder: options.placeholder ?? "", autocomplete: "off", "aria-describedby": options.hint ? `${id}-hint` : null });
  const add = h("button", { type: "button", class: "btn btn-quiet btn-small" }, "Add");
  const note = h("p", { class: "dash-hint dash-note", role: "status" });
  const draw = (): void => {
    list.replaceChildren();
    if (values.length === 0) list.appendChild(h("span", { class: "dash-empty" }, "Nothing added."));
    for (const value of values) {
      list.appendChild(
        chip(value, () => {
          values = values.filter((v) => v !== value);
          onChange(values);
          draw();
        }),
      );
    }
  };
  const commit = (): void => {
    let text = input.value.trim();
    if (options.lower) text = text.toLowerCase();
    if (!text) return;
    if (text.length < (options.minLength ?? 1)) {
      note.textContent = `Use at least ${options.minLength} characters.`;
      return;
    }
    if (values.includes(text)) {
      note.textContent = "That one is already on the list.";
      return;
    }
    if (values.length >= options.max) {
      note.textContent = `The list is full (${options.max}).`;
      return;
    }
    note.textContent = "";
    values = [...values, text];
    input.value = "";
    onChange(values);
    draw();
  };
  add.addEventListener("click", commit);
  input.addEventListener("keydown", (event) => {
    if (event.key === "Enter") {
      event.preventDefault();
      commit();
    }
  });
  draw();
  return labelled(id, label, h("div", { class: "dash-multi" }, list, h("div", { class: "dash-add" }, input, add), note), options.hint);
}
