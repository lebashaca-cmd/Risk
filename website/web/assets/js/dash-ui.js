import { h } from "./dom.js";
let counter = 0;
export function uid(prefix) {
    counter += 1;
    return `${prefix}-${counter}`;
}
export function group(title, hint, ...children) {
    return h("section", { class: "dash-group" }, h("h3", {}, title), hint ? h("p", { class: "dash-hint" }, hint) : null, ...children);
}
function labelled(id, label, control, hint) {
    return h("div", { class: "dash-field" }, h("label", { for: id }, label), control, hint ? h("p", { class: "dash-hint", id: `${id}-hint` }, hint) : null);
}
export function toggle(label, hint, value, onChange) {
    const id = uid("sw");
    const input = h("input", { type: "checkbox", id, role: "switch", class: "dash-switch-input", "aria-describedby": hint ? `${id}-hint` : null });
    input.checked = value;
    input.addEventListener("change", () => onChange(input.checked));
    return h("div", { class: "dash-toggle" }, input, h("label", { for: id, class: "dash-switch", "aria-hidden": "true" }), h("div", { class: "dash-toggle-text" }, h("label", { for: id }, label), hint ? h("p", { class: "dash-hint", id: `${id}-hint` }, hint) : null));
}
export function textInput(label, value, onChange, options = {}) {
    const id = uid("tx");
    const input = h("input", { type: "text", id, class: "dash-input", maxlength: options.max ?? 200, placeholder: options.placeholder ?? "", autocomplete: "off", spellcheck: false, "aria-describedby": options.hint ? `${id}-hint` : null });
    input.value = value;
    input.addEventListener("input", () => onChange(input.value));
    return labelled(id, label, input, options.hint);
}
export function textArea(label, value, onChange, options = {}) {
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
export function numberInput(label, value, onChange, min, max, step = 1, hint) {
    const id = uid("nm");
    const input = h("input", { type: "number", id, class: "dash-input dash-number", min, max, step, inputmode: "decimal", "aria-describedby": hint ? `${id}-hint` : null });
    input.value = String(value);
    input.addEventListener("input", () => {
        const parsed = Number(input.value);
        if (input.value !== "" && Number.isFinite(parsed))
            onChange(parsed);
    });
    return labelled(id, label, input, hint ?? `From ${min} to ${max}.`);
}
export function selectInput(label, choices, value, onChange, hint) {
    const id = uid("sl");
    const select = h("select", { id, class: "dash-input", "aria-describedby": hint ? `${id}-hint` : null });
    for (const choice of choices) {
        const option = h("option", { value: choice.value, disabled: choice.disabled ?? false }, choice.label);
        if (choice.value === value)
            option.selected = true;
        select.appendChild(option);
    }
    select.addEventListener("change", () => onChange(select.value));
    return labelled(id, label, select, hint);
}
export function channelChoices(meta, none, extra = []) {
    const choices = [];
    if (none !== null)
        choices.push({ value: "", label: none });
    choices.push(...extra);
    for (const channel of meta.channels) {
        choices.push({ value: channel.id, label: `#${channel.name}${channel.category ? `  (${channel.category})` : ""}${channel.canSend ? "" : "  (I can't post here)"}`, disabled: !channel.canSend });
    }
    return choices;
}
export function channelSelect(label, meta, value, onChange, none = "Off", hint) {
    const known = value && !meta.channels.some((c) => c.id === value) ? [{ value, label: "A channel that no longer exists" }] : [];
    return selectInput(label, [...channelChoices(meta, none), ...known], value ?? "", (v) => onChange(v === "" ? null : v), hint);
}
export function roleSelect(label, meta, value, onChange, none = "None", hint) {
    const choices = [{ value: "", label: none }];
    for (const role of meta.roles)
        choices.push({ value: role.id, label: role.assignable ? `@${role.name}` : `@${role.name}  (above my role)`, disabled: !role.assignable });
    if (value && !meta.roles.some((r) => r.id === value))
        choices.push({ value, label: "A role that no longer exists" });
    return selectInput(label, choices, value ?? "", (v) => onChange(v === "" ? null : v), hint);
}
function chip(text, onRemove, color) {
    const remove = h("button", { type: "button", class: "dash-chip-x", "aria-label": `Remove ${text}` }, "×");
    remove.addEventListener("click", onRemove);
    return h("span", { class: "dash-chip" }, color ? h("i", { class: "dash-dot", style: `background:${color}` }) : null, text, remove);
}
/** A list of chips with a picker to add more. `pool` is the choices; `values` is the current selection. */
export function multiPicker(label, pool, values, onChange, hint, empty = "Nothing added.") {
    const id = uid("mp");
    const list = h("div", { class: "dash-chips", "aria-live": "polite" });
    const select = h("select", { id, class: "dash-input", "aria-describedby": hint ? `${id}-hint` : null });
    const names = new Map(pool.map((c) => [c.value, c.label.replace(/\s{2,}\(.*\)$/, "")]));
    const draw = () => {
        list.replaceChildren();
        if (values.length === 0)
            list.appendChild(h("span", { class: "dash-empty" }, empty));
        for (const value of values) {
            list.appendChild(chip(names.get(value) ?? "Removed item", () => {
                values = values.filter((v) => v !== value);
                onChange(values);
                draw();
            }));
        }
        select.replaceChildren(h("option", { value: "" }, "Add…"));
        for (const choice of pool) {
            if (values.includes(choice.value) || choice.value === "")
                continue;
            select.appendChild(h("option", { value: choice.value }, choice.label));
        }
    };
    select.addEventListener("change", () => {
        if (!select.value)
            return;
        values = [...values, select.value];
        onChange(values);
        draw();
        select.focus();
    });
    draw();
    return labelled(id, label, h("div", { class: "dash-multi" }, list, select), hint);
}
export function multiChannels(label, meta, values, onChange, hint) {
    const pool = meta.channels.map((c) => ({ value: c.id, label: `#${c.name}${c.category ? `  (${c.category})` : ""}` }));
    return multiPicker(label, pool, values, onChange, hint);
}
export function multiRoles(label, meta, values, onChange, hint) {
    return multiPicker(label, meta.roles.map((r) => ({ value: r.id, label: `@${r.name}` })), values, onChange, hint);
}
const SHOWN_TAGS = 200;
/** Pulls words out of a .txt or .env file: one per line, or comma separated. KEY=value lines use the value. */
export function wordsFromText(text, minLength, maxLength, lower) {
    const words = [];
    let skipped = 0;
    for (let line of text.replace(/^\uFEFF/, "").split(/\r?\n/)) {
        line = line.trim();
        if (!line || line.startsWith("#") || line.startsWith("//"))
            continue;
        line = line.replace(/^export\s+/, "");
        const assignment = /^[A-Za-z_][\w.-]*\s*=(.*)$/.exec(line);
        if (assignment)
            line = (assignment[1] ?? "").trim().replace(/^(["'])(.*)\1$/, "$2");
        for (const part of line.split(/[,;]/)) {
            let word = part.trim().replace(/^(["'])(.*)\1$/, "$2").trim();
            if (lower)
                word = word.toLowerCase();
            if (!word)
                continue;
            if (word.length < minLength || word.length > maxLength) {
                skipped += 1;
                continue;
            }
            words.push(word);
        }
    }
    return { words, skipped };
}
/** Free-text tags: type a value and press Enter or Add. With `importFile`, also load many at once from a .txt or .env file. */
export function tagEditor(label, values, onChange, options) {
    const id = uid("tg");
    const list = h("div", { class: "dash-chips", "aria-live": "polite" });
    const input = h("input", { type: "text", id, class: "dash-input", maxlength: options.maxLength, placeholder: options.placeholder ?? "", autocomplete: "off", "aria-describedby": options.hint ? `${id}-hint` : null });
    const add = h("button", { type: "button", class: "btn btn-quiet btn-small" }, "Add");
    const note = h("p", { class: "dash-hint dash-note", role: "status" });
    const count = h("p", { class: "dash-hint" });
    const find = h("input", { type: "search", class: "dash-input", placeholder: "Search the list", "aria-label": `Search ${label.toLowerCase()}`, autocomplete: "off" });
    let query = "";
    const draw = () => {
        list.replaceChildren();
        const matches = query ? values.filter((v) => v.includes(query)) : values;
        if (values.length === 0)
            list.appendChild(h("span", { class: "dash-empty" }, "Nothing added."));
        else if (matches.length === 0)
            list.appendChild(h("span", { class: "dash-empty" }, "Nothing matches."));
        const fragment = document.createDocumentFragment();
        for (const value of matches.slice(0, SHOWN_TAGS)) {
            fragment.appendChild(chip(value, () => {
                values = values.filter((v) => v !== value);
                onChange(values);
                draw();
            }));
        }
        list.appendChild(fragment);
        count.textContent = `${values.length} in the list.` + (matches.length > SHOWN_TAGS ? ` Showing the first ${SHOWN_TAGS}${query ? " matches" : ". Search to find the rest"}.` : "");
        find.hidden = values.length <= SHOWN_TAGS && !query;
    };
    const merge = (incoming) => {
        const have = new Set(values);
        const fresh = [];
        let duplicates = 0;
        let full = 0;
        for (const word of incoming) {
            if (have.has(word)) {
                duplicates += 1;
                continue;
            }
            if (values.length + fresh.length >= options.max) {
                full += 1;
                continue;
            }
            have.add(word);
            fresh.push(word);
        }
        if (fresh.length) {
            values = [...values, ...fresh];
            onChange(values);
        }
        return { added: fresh.length, duplicates, full };
    };
    const commit = () => {
        let text = input.value.trim();
        if (options.lower)
            text = text.toLowerCase();
        if (!text)
            return;
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
    find.addEventListener("input", () => {
        query = options.lower ? find.value.trim().toLowerCase() : find.value.trim();
        draw();
    });
    const tools = h("div", { class: "dash-add" });
    if (options.importFile) {
        const file = h("input", { type: "file", accept: ".txt,.env,text/plain", class: "sr-only", "aria-label": `Import ${label.toLowerCase()} from a file` });
        const choose = h("button", { type: "button", class: "btn btn-quiet btn-small" }, "Import from a file");
        const clear = h("button", { type: "button", class: "btn btn-quiet btn-small" }, "Clear all");
        choose.addEventListener("click", () => file.click());
        file.addEventListener("change", async () => {
            const chosen = file.files?.[0];
            file.value = "";
            if (!chosen)
                return;
            if (chosen.size > 1_000_000) {
                note.textContent = "That file is over 1 MB. Split it into smaller files.";
                return;
            }
            let text;
            try {
                text = await chosen.text();
            }
            catch {
                note.textContent = "That file couldn't be read.";
                return;
            }
            if (text.includes("\u0000")) {
                note.textContent = "That doesn't look like a text file.";
                return;
            }
            const found = wordsFromText(text, options.minLength ?? 1, options.maxLength, Boolean(options.lower));
            const result = merge(found.words);
            draw();
            const parts = [`Added ${result.added}.`];
            if (result.duplicates)
                parts.push(`${result.duplicates} were already on the list.`);
            if (found.skipped)
                parts.push(`${found.skipped} skipped (needs ${options.minLength ?? 1} to ${options.maxLength} characters).`);
            if (result.full)
                parts.push(`${result.full} didn't fit (the list holds ${options.max}).`);
            if (!found.words.length && !found.skipped)
                parts.push("The file had no words in it.");
            note.textContent = parts.join(" ") + (result.added ? " Save to apply them." : "");
        });
        clear.addEventListener("click", () => {
            if (values.length === 0)
                return;
            if (!window.confirm(`Remove all ${values.length} from the list? You can still discard before saving.`))
                return;
            values = [];
            onChange(values);
            note.textContent = "";
            draw();
        });
        tools.append(choose, clear, file);
    }
    draw();
    return labelled(id, label, h("div", { class: "dash-multi" }, find, list, count, h("div", { class: "dash-add" }, input, add), tools, note), options.hint ? options.hint : options.importFile ? "Import a .txt or .env file with one word per line, or words separated by commas. Lines starting with # are ignored." : undefined);
}
/** Disables every control inside an element (used for features a server hasn't unlocked). */
export function lockControls(root, locked) {
    if (locked)
        root.querySelectorAll("input, select, textarea, button").forEach((el) => el.setAttribute("disabled", ""));
    root.classList.toggle("is-locked", locked);
    return root;
}
export function vipBadge() {
    return h("span", { class: "dash-vip" }, "VIP");
}
