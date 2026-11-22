import { channelSelect, group, lockControls, multiChannels, multiRoles, numberInput, selectInput, textArea, textInput, toggle, vipBadge } from "./dash-ui.js";
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
    profile: "Bot profile", commands: "Commands", responders: "Auto-replies", customcmds: "Custom commands", games: "Games", announcements: "Announcements", vip: "VIP",
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
export const customcmds = (vip) => (draft, meta, changed) => {
    const list = h("div", { class: "dash-rules" });
    const count = h("p", { class: "dash-hint", role: "status" });
    const draw = () => {
        list.replaceChildren();
        count.textContent = `${draft.items.length} of ${draft.limit} custom commands.`;
        if (draft.items.length === 0)
            list.appendChild(h("p", { class: "dash-empty" }, "No custom commands yet."));
        draft.items.forEach((item, index) => {
            const remove = h("button", { type: "button", class: "btn btn-quiet btn-small" }, "Remove");
            remove.addEventListener("click", () => {
                draft.items.splice(index, 1);
                draw();
                changed();
            });
            list.appendChild(h("div", { class: "dash-card" }, textInput("Command name", item.name, (v) => { item.name = v; changed(); }, { max: 20, placeholder: "for example: rules", hint: "Letters, numbers, _ and -. Members run it with ! ? , or your server's own prefix in front. Names of built-in commands can't be used." }), textArea("Reply", item.reply, (v) => { item.reply = v; changed(); }, { max: 1500, rows: 4, variables: meta.variables, hint: "Plain text. Type { to find a variable, or see the docs for the full list." }), h("div", { class: "dash-card-actions" }, remove)));
        });
    };
    const add = h("button", { type: "button", class: "btn btn-quiet btn-small" }, "Add a custom command");
    add.addEventListener("click", () => {
        if (draft.items.length >= draft.limit)
            return toast(`That is the most custom commands this server can have (${draft.limit}).`);
        draft.items.push({ name: "", reply: "" });
        draw();
        changed();
    });
    draw();
    if (!draft.unlocked)
        return [upsell(vip, "Custom commands are included with VIP White, VIP Supreme and Lifetime.")];
    return [group("Custom commands", "Commands you make up. Anyone in the server can run them. They can also be managed in chat with !customcmd.", list, count, add)];
};
// Games: servers Risk watches and can manage
const secretBox = (label, saved, hint, set, clear) => {
    const box = textInput(label, "", set, { max: 300, placeholder: saved ? "Saved. Type to replace it." : "Not set", hint });
    box.querySelector("input")?.setAttribute("type", "password");
    box.querySelector("input")?.setAttribute("autocomplete", "new-password");
    if (!saved)
        return box;
    return h("div", {}, box, toggle(`Remove the saved ${label.toLowerCase()}`, undefined, false, clear));
};
export const games = (draft, meta, changed) => {
    const list = h("div", { class: "dash-rules" });
    const count = h("p", { class: "dash-hint", role: "status" });
    const draw = () => {
        list.replaceChildren();
        count.textContent = `${draft.items.length} of 10 game servers.`;
        if (draft.items.length === 0)
            list.appendChild(h("p", { class: "dash-empty" }, "No game servers yet. Add one to see who is online and get join and leave posts."));
        draft.items.forEach((item, index) => {
            const remove = h("button", { type: "button", class: "btn btn-quiet btn-small" }, "Remove");
            remove.addEventListener("click", () => {
                draft.items.splice(index, 1);
                draw();
                changed();
            });
            const kinds = Object.entries(draft.games).map(([value, label]) => ({ value, label }));
            const s = item.status;
            const live = s ? (s.online ? `Online, ${s.count}/${s.max} players${s.players.length ? `: ${s.players.slice(0, 12).join(", ")}` : ""}${s.world ? `. World: ${s.world}` : ""}.` : "Offline at the last check.") : "Not checked yet. Risk checks every minute.";
            const parts = [
                h("p", { class: "dash-hint", role: "status" }, item.isNew ? "Saved when you press Save." : live),
                item.isNew
                    ? textInput("Name", item.name, (v) => { item.name = v.toLowerCase(); changed(); }, { max: 20, placeholder: "for example: survival", hint: "Letters, numbers, _ and -. You use it in commands, so it can't be changed later." })
                    : h("p", {}, h("strong", {}, item.name)),
                selectInput("Game", kinds, item.game, (v) => { item.game = v; changed(); }, "Minecraft Bedrock, Steam games (CS2, Rust, ARK, Garry's Mod, Valheim) and Terraria need the matching game type."),
                textInput("Address", item.host, (v) => { item.host = v; changed(); }, { max: 253, placeholder: "play.example.com", hint: "The public address players use. Private network addresses are refused." }),
                numberInput("Port", item.port, (v) => { item.port = v; changed(); }, 1, 65535, 1, "Minecraft 25565, Bedrock 19132, Steam games 27015, Terraria TShock REST 7878."),
                toggle("Track joins and leaves", "Remember who plays and for how long. Used by seen, top and the feed.", item.track, (v) => { item.track = v; changed(); }),
            ];
            if (item.game === "minecraft") {
                parts.push(numberInput("Query port", item.queryPort ?? 0, (v) => { item.queryPort = v || null; changed(); }, 0, 65535, 1, "Set enable-query=true in server.properties, then use the same port as the game (25565). Gives the full player list and the world name. 0 is off."), numberInput("RCON port", item.rconPort ?? 0, (v) => { item.rconPort = v || null; changed(); }, 0, 65535, 1, "Turns on running commands, saying, kicking and the whitelist from Discord. Set enable-rcon=true. 0 is off."));
            }
            if (item.game === "minecraft" || item.game === "source") {
                parts.push(secretBox("RCON password", !!item.hasRconPassword, "Never shown again after you save it.", (v) => { item.rconPassword = v; changed(); }, (v) => { item.clearRconPassword = v; changed(); }));
                if (item.game === "source")
                    parts.push(numberInput("RCON port", item.rconPort ?? 0, (v) => { item.rconPort = v || null; changed(); }, 0, 65535, 1, "Usually the same as the game port. 0 is off."));
            }
            if (item.game === "terraria") {
                parts.push(secretBox("REST token", !!item.hasToken, "The TShock REST application token. Needed for players and commands.", (v) => { item.token = v; changed(); }, (v) => { item.clearToken = v; changed(); }));
            }
            if (item.game === "minecraft") {
                parts.push(textInput("Live map link", item.mapUrl, (v) => { item.mapUrl = v; changed(); }, { max: 200, placeholder: "https://map.example.com", hint: "Your Dynmap or BlueMap page. !gameserver map links to it." }), textInput("Panel address", item.panelUrl, (v) => { item.panelUrl = v; changed(); }, { max: 200, placeholder: "https://panel.example.com", hint: "Pterodactyl panel. Needed for restart and world reset." }), textInput("Panel server id", item.panelId, (v) => { item.panelId = v; changed(); }, { max: 60, placeholder: "8 characters, like 1a2b3c4d" }), secretBox("Panel API key", !!item.hasPanelKey, "A client API key from your panel account. Never shown again after you save it.", (v) => { item.panelKey = v; changed(); }, (v) => { item.clearPanelKey = v; changed(); }));
            }
            parts.push(h("div", { class: "dash-card-actions" }, remove));
            list.appendChild(h("div", { class: "dash-card" }, ...parts));
        });
    };
    const add = h("button", { type: "button", class: "btn btn-quiet btn-small" }, "Add a game server");
    add.addEventListener("click", () => {
        if (draft.items.length >= 10)
            return toast("A server can have up to 10 game servers.");
        draft.items.push({ name: "", game: "minecraft", host: "", port: 25565, queryPort: null, rconPort: null, mapUrl: "", track: true, panelUrl: "", panelId: "", isNew: true });
        draw();
        changed();
    });
    draw();
    return [
        group("Game servers", "Risk checks each server every minute. Commands: !gameserver status, players, seen, top, map. Fortnite stats: !fortnite <name>.", list, count, add),
        group("Feed", "Post when someone joins or leaves, and when a server goes down or comes back.", channelSelect("Feed channel", meta, draft.feed || null, (v) => { draft.feed = v ?? ""; changed(); }, "Off", "Joins and leaves are exact for servers with Query (Minecraft), Steam games and Terraria.")),
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
