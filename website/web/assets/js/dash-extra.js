import { group, lockControls, multiChannels, multiPicker, multiRoles, numberInput, selectInput, textArea, textInput, toggle, vipBadge } from "./dash-ui.js";
import { h } from "./dom.js";
import { toast } from "./ui.js";
const number = new Intl.NumberFormat();
function ago(unix) {
    const seconds = Math.max(0, Math.round(Date.now() / 1000 - unix));
    if (seconds < 60)
        return "just now";
    const units = [[86400, "day"], [3600, "hour"], [60, "minute"]];
    for (const [size, name] of units) {
        if (seconds >= size) {
            const count = Math.floor(seconds / size);
            return `${count} ${name}${count === 1 ? "" : "s"} ago`;
        }
    }
    return "just now";
}
function age(unix) {
    const days = Math.max(0, Math.floor(Date.now() / 1000 - unix) / 86400);
    if (days >= 365)
        return `${(days / 365).toFixed(1)} years`;
    return `${Math.floor(days)} days`;
}
function upsell(vip, what) {
    return h("div", { class: "dash-upsell" }, h("p", {}, vipBadge(), ` ${what}`), vip?.url ? h("a", { class: "btn btn-primary btn-small", href: vip.url, rel: "noopener" }, "Get VIP") : h("p", { class: "dash-hint" }, "Ask the bot owner to switch VIP on for this server."));
}
const SECTION_LABEL = {
    general: "General", welcome: "Welcome and leave", logs: "Server logs", levels: "Levels", automod: "Auto-moderation", community: "Community",
    profile: "Bot profile", commands: "Commands", responders: "Auto-replies", customcmds: "Custom commands", announcements: "Announcements", vip: "VIP",
};
// Overview
export const overview = (draft, _meta, _changed, ctx) => {
    const stats = draft.stats;
    const done = draft.checklist.filter((item) => item.done).length;
    const tile = (value, label, note) => h("div", { class: "dash-tile" }, h("strong", {}, value), h("span", {}, label), note ? h("small", {}, note) : null);
    const banner = h("div", { class: "dash-banner" }, ctx.guildIcon ? h("img", { class: "dash-banner-icon", src: ctx.guildIcon, alt: "", width: 64, height: 64, referrerpolicy: "no-referrer" }) : h("span", { class: "dash-banner-icon dash-initial", "aria-hidden": "true" }, ctx.guildName.charAt(0).toUpperCase()), h("div", { class: "dash-banner-text" }, h("h3", {}, ctx.guildName, draft.vip ? vipBadge() : null), h("p", {}, `${done} of ${draft.checklist.length} setup steps done`), h("div", { class: "dash-meter", role: "img", "aria-label": `${done} of ${draft.checklist.length} setup steps done` }, ...draft.checklist.map((item) => h("i", { class: item.done ? "is-done" : "" })))));
    const tiles = h("div", { class: "dash-tiles" }, tile(number.format(stats.members ?? 0), "members", `${number.format(stats.people)} people, ${number.format(stats.bots)} bots`), tile(String(stats.textChannels + stats.voiceChannels), "channels", `${stats.textChannels} text, ${stats.voiceChannels} voice`), tile(String(stats.roles), "roles", `${stats.emojis} emojis`), tile(`Level ${stats.boostTier}`, "boost", `${stats.boosts} boosts`), tile(age(stats.created), "old", stats.owner ? `Owned by ${stats.owner}` : undefined));
    const steps = h("ul", { class: "dash-steps" });
    for (const item of draft.checklist) {
        const go = h("button", { type: "button", class: "btn btn-quiet btn-small" }, item.done ? "Edit" : "Set up");
        go.addEventListener("click", () => ctx.go(item.section));
        steps.appendChild(h("li", { class: item.done ? "is-done" : "" }, h("span", { class: "dash-check", "aria-hidden": "true" }, item.done ? "✓" : ""), h("span", { class: "dash-step-label" }, item.label, h("span", { class: "sr-only" }, item.done ? " (done)" : " (not done)")), go));
    }
    const use = draft.usage;
    const usage = h("dl", { class: "dash-usage" }, ...[
        ["Commands switched off", use.disabledCommands],
        ["Command rules", use.commandRules],
        ["Auto-replies", use.responders],
        ["Announcements", use.announcements],
        ["Log types on", use.logCategories ?? "-"],
    ].flatMap(([label, value]) => [h("dt", {}, label), h("dd", {}, String(value))]));
    const feed = draft.activity.length
        ? h("ul", { class: "dash-feed" }, ...draft.activity.map((a) => h("li", {}, h("strong", {}, a.user), ` changed ${SECTION_LABEL[a.section] ?? a.section}`, h("span", { class: "dash-when" }, ago(a.at)))))
        : h("p", { class: "dash-empty" }, "No changes from the dashboard yet.");
    return [banner, tiles, group("Setup checklist", "Finish these to get the most out of Risk.", steps), h("div", { class: "dash-twin" }, group("In use", null, usage), group("Recent changes", "Saved from this dashboard.", feed))];
};
// Commands
export const commands = (draft, meta, changed) => {
    const list = h("div", { class: "dash-rules" });
    const count = h("p", { class: "dash-hint", role: "status" });
    const limit = meta.limits["command_rules"] ?? 500;
    const names = meta.commands.map((c) => c.name);
    const draw = () => {
        list.replaceChildren();
        count.textContent = `${draft.rules.length} ${draft.rules.length === 1 ? "rule" : "rules"}.`;
        if (draft.rules.length === 0)
            list.appendChild(h("p", { class: "dash-empty" }, "No rules yet. Everyone can use every switched-on command anywhere."));
        draft.rules.forEach((rule, index) => {
            const taken = new Set(draft.rules.map((r) => r.command));
            const choices = names.filter((n) => n === rule.command || !taken.has(n)).map((n) => ({ value: n, label: n }));
            const remove = h("button", { type: "button", class: "btn btn-quiet btn-small" }, "Remove");
            remove.addEventListener("click", () => {
                draft.rules.splice(index, 1);
                draw();
                changed();
            });
            list.appendChild(h("div", { class: "dash-card" }, selectInput("Command", choices, rule.command, (v) => { rule.command = v; draw(); changed(); }), multiRoles("Only these roles can use it", meta, rule.roles, (v) => { rule.roles = v; changed(); }, "Leave empty to allow everyone."), multiChannels("Only works in these channels", meta, rule.channels, (v) => { rule.channels = v; changed(); }, "Leave empty to allow every channel."), multiRoles("These roles can't use it", meta, rule.blockedRoles, (v) => { rule.blockedRoles = v; changed(); }, "Blocked roles win over the allowed list."), multiChannels("Turned off in these channels", meta, rule.blockedChannels, (v) => { rule.blockedChannels = v; changed(); }), toggle("Managers only", "Only members with Manage Server can use it.", rule.staffOnly, (v) => { rule.staffOnly = v; changed(); }), numberInput("Cooldown per member (seconds)", rule.cooldown, (v) => { rule.cooldown = v; changed(); }, 0, 3600, 1, "0 means no cooldown."), h("div", { class: "dash-card-actions" }, remove)));
        });
    };
    const add = h("button", { type: "button", class: "btn btn-quiet btn-small" }, "Add a rule");
    add.addEventListener("click", () => {
        if (draft.rules.length >= limit)
            return toast(`That is the most rules one server can have (${limit}).`);
        const taken = new Set(draft.rules.map((r) => r.command));
        const first = names.find((n) => !taken.has(n));
        if (!first)
            return;
        draft.rules.push({ command: first, roles: [], channels: [], blockedRoles: [], blockedChannels: [], staffOnly: false, cooldown: 10 });
        draw();
        changed();
    });
    draw();
    const basics = draft.basics;
    const basicRules = group("Basic rules", "These apply to every command. Members with Manage Server ignore them, and help always works.", multiChannels("Commands are off in these channels", meta, basics.blockedChannels, (v) => { basics.blockedChannels = v; changed(); }), multiChannels("Commands only work in these channels", meta, basics.onlyChannels, (v) => { basics.onlyChannels = v; changed(); }, "Leave empty to allow every channel."), multiRoles("These roles can't use commands", meta, basics.blockedRoles, (v) => { basics.blockedRoles = v; changed(); }), numberInput("Wait between a member's commands (seconds)", basics.cooldown, (v) => { basics.cooldown = v; changed(); }, 0, 60, 1, "0 means no wait."), toggle("Delete the command message", "Risk removes what the member typed after the command runs. Needs the Manage Messages permission.", basics.deleteInvocations, (v) => { basics.deleteInvocations = v; changed(); }));
    return [basicRules, group("Command rules", "Limit who can run one command, where, and how often. Members with Manage Server ignore these rules.", list, count, add)];
};
// Auto-replies
const MATCHES = [
    { value: "contains", label: "Message contains the trigger" },
    { value: "exact", label: "Message is exactly the trigger" },
    { value: "starts", label: "Message starts with the trigger" },
];
export const responders = (draft, meta, changed) => {
    const list = h("div", { class: "dash-rules" });
    const count = h("p", { class: "dash-hint", role: "status" });
    const limit = meta.limits["responders"] ?? 500;
    const draw = () => {
        list.replaceChildren();
        count.textContent = `${draft.items.length} ${draft.items.length === 1 ? "auto-reply" : "auto-replies"}.`;
        if (draft.items.length === 0)
            list.appendChild(h("p", { class: "dash-empty" }, "No auto-replies yet."));
        draft.items.forEach((item, index) => {
            const remove = h("button", { type: "button", class: "btn btn-quiet btn-small" }, "Remove");
            remove.addEventListener("click", () => {
                draft.items.splice(index, 1);
                draw();
                changed();
            });
            const embed = toggle("Send as an embed", "Uses your VIP colour.", item.embed, (v) => { item.embed = v; changed(); });
            list.appendChild(h("div", { class: "dash-card" }, textInput("Trigger", item.trigger, (v) => { item.trigger = v; changed(); }, { max: 60, placeholder: "for example: server ip" }), selectInput("When to reply", MATCHES, item.match, (v) => { item.match = v; changed(); }), textArea("Reply", item.reply, (v) => { item.reply = v; changed(); }, { max: 500, rows: 3, hint: "You can use {user}, {server}, {server.members}, {choose:a|b} and 40 more variables (see the docs). Risk waits 10 seconds before repeating a reply." }), meta.vip ? embed : h("div", {}, lockControls(embed, true), h("p", { class: "dash-hint" }, vipBadge(), " Embed replies are for VIP servers.")), h("div", { class: "dash-card-actions" }, remove)));
        });
    };
    const add = h("button", { type: "button", class: "btn btn-quiet btn-small" }, "Add an auto-reply");
    add.addEventListener("click", () => {
        if (draft.items.length >= limit)
            return toast(`That is the most auto-replies one server can have (${limit}).`);
        draft.items.push({ trigger: "", reply: "", match: "contains", embed: false });
        draw();
        changed();
    });
    draw();
    return [group("Auto-replies", "Risk answers when a message matches. Replies never ping anyone and skip channels where commands are ignored.", list, count, add)];
};
// Custom commands (VIP White and up)
const STEP_KINDS_OF_CHANNEL = { text: ["text", "announcement"], voice: ["voice"], stage: ["stage"], category: ["category"], forum: ["forum"] };
export const customcmds = (vip) => (draft, meta, changed) => {
    const list = h("div", { class: "dash-rules" });
    const count = h("p", { class: "dash-hint", role: "status" });
    const types = new Map(draft.actionTypes.map((t) => [t.type, t]));
    const fieldControl = (step, f) => {
        const set = (v) => { step[f.key] = v; changed(); };
        const value = step[f.key] ?? f.default ?? "";
        switch (f.kind) {
            case "text":
                return textArea(f.label, String(value), (v) => set(v), { max: 1900, rows: 3, variables: meta.variables, hint: f.hint ?? "Type { to find a variable." });
            case "name":
                return textInput(f.label, String(value), (v) => set(v), { max: 200, hint: f.hint ?? "Variables like {arg1} and {user} work here." });
            case "number":
                return numberInput(f.label, Number(value), (v) => set(v), f.min ?? 0, f.max ?? 1000, 1, f.hint);
            case "bool":
                return toggle(f.label, f.hint, Boolean(value), (v) => set(v));
            case "select":
                return selectInput(f.label, Object.entries(f.options ?? {}).map(([v, l]) => ({ value: v, label: l })), String(value), (v) => set(v), f.hint);
            case "role": {
                const choices = [{ value: "", label: "Pick a role" }, { value: "created", label: "The role made earlier in this command" }, ...meta.roles.map((r) => ({ value: r.id, label: `@${r.name}` }))];
                return selectInput(f.label, choices, String(value), (v) => set(v), f.hint);
            }
            default: {
                const wanted = new Set((f.kinds ?? ["text"]).flatMap((k) => (k === "any" ? ["text", "announcement", "voice", "stage", "category", "forum"] : STEP_KINDS_OF_CHANNEL[k] ?? [k])));
                const prefix = (t) => (t === "voice" || t === "stage" ? "\u{1F50A} " : t === "category" ? "\u{1F4C1} " : "#");
                const choices = [];
                if (!f.kinds)
                    choices.push({ value: "", label: "This channel" });
                else if (f.kinds.includes("category"))
                    choices.push({ value: "", label: "No category" });
                else
                    choices.push({ value: "", label: "Pick a channel" });
                choices.push({ value: "created", label: "The channel made earlier in this command" });
                for (const c of draft.allChannels)
                    if (wanted.has(c.type))
                        choices.push({ value: c.id, label: `${prefix(c.type)}${c.name}` });
                return selectInput(f.label, choices, String(value), (v) => set(v), f.hint);
            }
        }
    };
    const draw = () => {
        list.replaceChildren();
        count.textContent = `${draft.items.length} of ${draft.limit} custom commands. Saved values: ${draft.saved.length ? draft.saved.map((s) => `${s.name}=${s.value}`).join(", ") : "none yet"}.`;
        if (draft.items.length === 0)
            list.appendChild(h("p", { class: "dash-empty" }, "No custom commands yet."));
        draft.items.forEach((item, index) => {
            const remove = h("button", { type: "button", class: "btn btn-quiet btn-small" }, "Remove command");
            remove.addEventListener("click", () => {
                draft.items.splice(index, 1);
                draw();
                changed();
            });
            const risky = item.steps.some((s) => types.get(s.type)?.danger || ((s.type === "add_role" || s.type === "remove_role" || s.type === "toggle_role" || s.type === "nickname") && s.who === "target"));
            const steps = h("div", { class: "cc-steps" });
            item.steps.forEach((step, si) => {
                const info = types.get(step.type);
                if (!info)
                    return;
                const move = (by) => {
                    const to = si + by;
                    if (to < 0 || to >= item.steps.length)
                        return;
                    [item.steps[si], item.steps[to]] = [item.steps[to], item.steps[si]];
                    draw();
                    changed();
                };
                const small = (label, text, onClick, disabled = false) => {
                    const button = h("button", { type: "button", class: "btn btn-quiet btn-small", "aria-label": label }, text);
                    button.disabled = disabled;
                    button.addEventListener("click", onClick);
                    return button;
                };
                const controls = h("div", { class: "cc-step-controls" }, small("Move step up", "Up", () => move(-1), si === 0), small("Move step down", "Down", () => move(1), si === item.steps.length - 1), small("Remove step", "Remove", () => {
                    item.steps.splice(si, 1);
                    draw();
                    changed();
                }));
                steps.appendChild(h("div", { class: "cc-step" }, h("div", { class: "cc-step-head" }, h("span", { class: "cc-step-number", "aria-hidden": "true" }, String(si + 1)), h("div", { class: "cc-step-title" }, h("strong", {}, info.label), info.danger ? h("span", { class: "cc-step-note" }, "Changes the server") : ""), controls), ...(info.fields.length ? [h("div", { class: "cc-step-fields" }, ...info.fields.map((f) => fieldControl(step, f)))] : [h("p", { class: "dash-hint" }, "Nothing to set for this step.")])));
            });
            const addStep = (type) => {
                const info = types.get(type);
                if (!info)
                    return;
                if (item.steps.length >= 15)
                    return toast("A command can have up to 15 steps.");
                const step = { type };
                for (const f of info.fields)
                    step[f.key] = f.default ?? (f.kind === "bool" ? false : f.kind === "number" ? f.min ?? 0 : "");
                item.steps.push(step);
                if (info.danger && item.who === "everyone") {
                    item.who = "mods";
                    toast("This step changes the server, so the command now runs for moderators only. Change who can run it above.");
                }
                palette.open = false;
                draw();
                changed();
            };
            const palette = h("details", { class: "cc-palette" });
            palette.appendChild(h("summary", { class: "btn btn-quiet btn-small" }, item.steps.length ? "Add another step" : "Add a step"));
            const groups = new Map();
            for (const t of draft.actionTypes)
                groups.set(t.group, [...(groups.get(t.group) ?? []), t]);
            const panel = h("div", { class: "cc-palette-panel" });
            for (const [name, members] of groups) {
                const row = h("div", { class: "cc-palette-items" });
                for (const t of members) {
                    const button = h("button", { type: "button", class: "cc-palette-item", title: t.danger ? "Changes the server, so the command is limited to moderators" : t.label }, t.label);
                    button.addEventListener("click", () => addStep(t.type));
                    row.appendChild(button);
                }
                panel.appendChild(h("div", { class: "cc-palette-group" }, h("p", { class: "cc-palette-name" }, name), row));
            }
            palette.appendChild(panel);
            const who = selectInput("Who can run it", [
                { value: "everyone", label: "Everyone" },
                { value: "mods", label: "Moderators (Manage Server, Manage Messages or Timeout Members)" },
                { value: "roles", label: "Only certain roles" },
            ], item.who, (v) => {
                item.who = v;
                draw();
                changed();
            }, risky ? "This command changes roles, channels or members, so it can't be open to everyone." : "Server admins can always run it.");
            for (const option of Array.from(who.querySelectorAll("option")))
                if (risky && option.value === "everyone")
                    option.disabled = true;
            const card = h("div", { class: "dash-card" }, textInput("Command name", item.name, (v) => { item.name = v; changed(); }, { max: 20, placeholder: "for example: rules", hint: "Letters, numbers, _ and -. Members run it with ! ? , or your server's own prefix in front. Names of built-in commands can't be used." }), who, ...(item.who === "roles" ? [multiPicker("Roles that can run it", meta.roles.map((r) => ({ value: r.id, label: `@${r.name}` })), item.roles, (v) => { item.roles = v; changed(); })] : []), multiPicker("Only in these channels", meta.channels.map((c) => ({ value: c.id, label: `#${c.name}` })), item.channels, (v) => { item.channels = v; changed(); }, "Leave empty to allow it in every channel."), numberInput("Cooldown per person (seconds)", item.cooldown, (v) => { item.cooldown = v; changed(); }, 0, 3600, 1, "How long each person waits before running it again."), h("p", { class: "dash-hint" }, `Run ${item.uses} time${item.uses === 1 ? "" : "s"}. Steps run top to bottom. If one fails, the rest are skipped and the person is told why.`), steps, palette, h("div", { class: "dash-card-actions" }, remove));
            list.appendChild(card);
        });
    };
    const add = h("button", { type: "button", class: "btn btn-quiet btn-small" }, "Add a custom command");
    add.addEventListener("click", () => {
        if (draft.items.length >= draft.limit)
            return toast(`That is the most custom commands this server can have (${draft.limit}).`);
        draft.items.push({ name: "", steps: [{ type: "reply", text: "" }], who: "everyone", roles: [], channels: [], cooldown: 3, uses: 0 });
        draw();
        changed();
    });
    draw();
    if (!draft.unlocked)
        return [upsell(vip, "Custom commands are included with VIP White, VIP Supreme and Lifetime.")];
    return [group("Custom commands", "Commands you make up. Each one runs steps: reply, send an embed, give a role, make a channel or role, moderate, save values and more. Use {args}, {arg1} and {target} to read what the person typed. They can also be managed in chat with !customcmd.", list, count, add)];
};
// Music: equalizer, effects and player defaults
const EQ_MIN = -0.25;
const EQ_MAX = 0.5; // the slider stops here; Lavalink allows up to 1 but past 0.5 it distorts badly
const SVG_NS = "http://www.w3.org/2000/svg";
function signed(gain) {
    const pct = Math.round(gain * 100);
    return pct > 0 ? `+${pct}` : String(pct);
}
function slider(label, value, min, max, step, show, onChange) {
    const input = h("input", { type: "range", class: "fx-range", min, max, step, "aria-label": label });
    input.value = String(value);
    const out = h("output", { class: "fx-value" }, show(value));
    input.addEventListener("input", () => {
        const v = Number(input.value);
        out.textContent = show(v);
        onChange(v);
    });
    return h("div", { class: "fx-row" }, h("span", { class: "fx-label" }, label), input, out);
}
export const music = (draft, meta, changed) => {
    const roles = [{ value: "", label: "Anyone can control the music" }, ...meta.roles.map((r) => ({ value: r.id, label: `@${r.name}` }))];
    const status = h("p", { class: "dash-hint", role: "status" }, draft.ready ? "The music server is connected." : draft.problem ?? "The music server isn't connected yet.");
    // Equalizer: one vertical slider per band, with the bars and the curve redrawn as you drag
    const stage = h("div", { class: "eq-stage" });
    const curve = document.createElementNS(SVG_NS, "svg");
    curve.setAttribute("class", "eq-curve");
    curve.setAttribute("viewBox", "0 0 150 100");
    curve.setAttribute("preserveAspectRatio", "none");
    curve.setAttribute("aria-hidden", "true");
    const line = document.createElementNS(SVG_NS, "polyline");
    curve.appendChild(line);
    const bars = h("div", { class: "eq-bars" });
    const fills = [];
    const values = [];
    const total = EQ_MAX - EQ_MIN;
    const zero = (0 - EQ_MIN) / total; // where "unchanged" sits, from the bottom
    const place = (i) => {
        const g = draft.eq[i] ?? 0;
        const at = (g - EQ_MIN) / total;
        const fill = fills[i];
        fill.style.bottom = `${Math.min(at, zero) * 100}%`;
        fill.style.height = `${Math.abs(at - zero) * 100}%`;
        fill.classList.toggle("eq-cut", g < 0);
        values[i].textContent = signed(g);
    };
    const drawCurve = () => {
        line.setAttribute("points", draft.eq.map((g, i) => `${(i + 0.5) * 10},${100 - ((g - EQ_MIN) / total) * 100}`).join(" "));
    };
    const redraw = () => {
        draft.eq.forEach((_, i) => {
            place(i);
            const input = bars.querySelectorAll(".eq-input")[i];
            if (input)
                input.value = String(draft.eq[i]);
        });
        drawCurve();
    };
    draft.eq.forEach((gain, i) => {
        const input = h("input", { type: "range", class: "eq-input", min: EQ_MIN, max: EQ_MAX, step: 0.01, orient: "vertical", "aria-label": `${draft.bands[i]} Hz` });
        input.value = String(gain);
        input.addEventListener("input", () => {
            draft.eq[i] = Number(input.value);
            place(i);
            drawCurve();
            changed();
        });
        const fill = h("span", { class: "eq-fill" });
        const value = h("span", { class: "eq-num" });
        fills.push(fill);
        values.push(value);
        bars.appendChild(h("div", { class: "eq-band" }, value, h("div", { class: "eq-track" }, fill, input), h("span", { class: "eq-hz" }, draft.bands[i] ?? "")));
    });
    stage.append(h("div", { class: "eq-plot", "aria-hidden": "true" }, h("span", { class: "eq-zero", style: `bottom:${zero * 100}%` }), curve), bars);
    redraw();
    const chips = h("div", { class: "eq-presets", role: "group", "aria-label": "Equalizer presets" });
    for (const [name, levels] of Object.entries(draft.presets)) {
        const chip = h("button", { type: "button", class: "btn btn-quiet btn-small" }, name.charAt(0).toUpperCase() + name.slice(1));
        chip.addEventListener("click", () => {
            draft.eq = [...levels];
            redraw();
            changed();
        });
        chips.appendChild(chip);
    }
    return [
        group("Equalizer", "Drag a band up to boost it or down to cut it. Low bands are bass, middle bands are voices, high bands are treble. The bars and curve show the shape you set, not the live song. Anything you save applies right away to music that's already playing.", status, chips, stage),
        group("Bass and effects", "Bass adds extra boost to the lowest bands on top of the equalizer.", slider("Bass boost", draft.bass, 0, 100, 5, (v) => `${v}%`, (v) => { draft.bass = v; changed(); }), slider("Speed", draft.speed, 0.5, 2, 0.05, (v) => `${v.toFixed(2)}x`, (v) => { draft.speed = v; changed(); }), slider("Pitch", draft.pitch, 0.5, 2, 0.05, (v) => `${v.toFixed(2)}x`, (v) => { draft.pitch = v; changed(); }), toggle("8D audio", "The sound slowly circles your head. Best in headphones.", draft.rotation, (v) => { draft.rotation = v; changed(); }), toggle("Karaoke", "Tries to remove the singer's voice.", draft.karaoke, (v) => { draft.karaoke = v; changed(); })),
        group("Player", "Where the player starts each time Risk joins a voice channel. Anyone in the channel can still change these with chat commands while music plays.", numberInput("Default volume", draft.volume, (v) => { draft.volume = v; changed(); }, 1, 150, 1, "1 to 150. Above 100 can sound distorted."), selectInput("DJ role", roles, draft.dj ?? "", (v) => { draft.dj = v === "" ? null : v; changed(); }, "People with Manage Server can always control the music."), toggle("Send a message when a new song starts", "Posts the song in the channel where !play was used.", draft.announce, (v) => { draft.announce = v; changed(); })),
    ];
};
// Announcements (VIP)
export const announcements = (vip) => (draft, meta, changed) => {
    const limit = meta.limits["schedules"] ?? 0;
    const list = h("div", { class: "dash-rules" });
    const count = h("p", { class: "dash-hint", role: "status" });
    const draw = () => {
        list.replaceChildren();
        count.textContent = `${draft.items.length} of ${limit || 50} announcements.`;
        if (draft.items.length === 0)
            list.appendChild(h("p", { class: "dash-empty" }, "No announcements yet."));
        draft.items.forEach((item, index) => {
            const remove = h("button", { type: "button", class: "btn btn-quiet btn-small" }, "Remove");
            remove.addEventListener("click", () => {
                draft.items.splice(index, 1);
                draw();
                changed();
            });
            const channels = [{ value: "", label: "Pick a channel" }, ...meta.channels.map((c) => ({ value: c.id, label: `#${c.name}`, disabled: !c.canSend }))];
            list.appendChild(h("div", { class: "dash-card" }, selectInput("Channel", channels, item.channel ?? "", (v) => { item.channel = v === "" ? null : v; changed(); }), numberInput("Repeat every (minutes)", item.everyMinutes, (v) => { item.everyMinutes = v; changed(); }, 5, 43200, 5, "From 5 minutes to 30 days. 60 is hourly, 1440 is daily."), textArea("Message", item.text, (v) => { item.text = v; changed(); }, { max: 1500, rows: 3 }), toggle("Running", "Switch off to pause it without deleting it.", item.on, (v) => { item.on = v; changed(); }), h("div", { class: "dash-card-actions" }, remove)));
        });
    };
    const add = h("button", { type: "button", class: "btn btn-quiet btn-small" }, "Add an announcement");
    add.addEventListener("click", () => {
        if (draft.items.length >= limit)
            return toast(`You can set up to ${limit} announcements.`);
        draft.items.push({ channel: null, everyMinutes: 60, text: "", on: true });
        draw();
        changed();
    });
    draw();
    if (!meta.vip)
        return [upsell(vip, "Announcements repeat a message in a channel on a timer. They are included with VIP.")];
    return [group("Scheduled messages", "Risk posts each message again and again on its timer. The first post comes one interval after you save.", list, count, add)];
};
// VIP
export const vipSection = () => (draft, _meta, changed) => {
    const status = draft.active
        ? h("div", { class: "dash-vipcard is-on" }, h("h3", {}, vipBadge(), ` ${draft.tier ?? "VIP"} is on for this server`), h("p", {}, draft.until ? `Until ${new Date(draft.until * 1000).toLocaleDateString()}.` : "With no end date."))
        : h("div", { class: "dash-vipcard" }, h("h3", {}, "This server is on the free plan"), h("p", {}, "VIP unlocks a few extras. Nothing in the regular settings is limited."), upsell(draft, "Get VIP to unlock everything below."));
    const colorValue = draft.color ?? "#5865f2";
    const colorInput = h("input", { type: "color", class: "dash-color", id: "vip-color", value: colorValue, "aria-label": "Accent colour" });
    const clear = h("button", { type: "button", class: "btn btn-quiet btn-small" }, "Use the default");
    const note = h("p", { class: "dash-hint", role: "status" }, draft.color ? `Current colour: ${draft.color}` : "Using the default colour.");
    colorInput.addEventListener("input", () => {
        draft.color = colorInput.value;
        note.textContent = `Current colour: ${colorInput.value}`;
        changed();
    });
    clear.addEventListener("click", () => {
        draft.color = null;
        note.textContent = "Using the default colour.";
        changed();
    });
    const colour = h("div", { class: "dash-field" }, h("label", { for: "vip-color" }, "Accent colour"), h("div", { class: "dash-add" }, colorInput, clear), note, h("p", { class: "dash-hint" }, "Used for VIP embeds, embed auto-replies and !serverstats."));
    const lockedColour = draft.active ? colour : h("div", {}, lockControls(colour, true), h("p", { class: "dash-hint" }, vipBadge(), " The accent colour is for VIP servers."));
    return [
        status,
        group("What VIP includes", null, h("ul", { class: "dash-perks" }, ...draft.perks.map((perk) => h("li", {}, perk)))),
        group("Commands by plan", "Run !vipcommands in Discord for the same list.", ...draft.commands.map((set) => h("div", { class: "dash-field" }, h("label", {}, `${{ basic: "Every VIP plan", lifetime: "Lifetime", white: "VIP White and Supreme", supreme: "VIP Supreme" }[set.plan]}${draft.active ? (set.unlocked ? " (unlocked)" : " (locked)") : ""}`), h("p", { class: "dash-hint" }, set.names.map((name) => `!${name}`).join("  "))))),
        group("Appearance", null, lockedColour),
    ];
};
