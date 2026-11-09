import { ApiFailure, dashApi, staffApi } from "./api.js";
import { h, mount } from "./dom.js";
import { statusPageSection } from "./staff-status.js";
import { toast } from "./ui.js";
const PLAN_NAMES = { basic: "Basic", lifetime: "Lifetime", white: "VIP White", supreme: "VIP Supreme" };
const nf = new Intl.NumberFormat("en");
function notice(kind, text) {
    return h("div", { class: `dash-notice dash-notice-${kind}`, role: kind === "error" ? "alert" : "status" }, text);
}
function messageOf(error) {
    return error instanceof ApiFailure ? error.message : "Something went wrong. Refresh the page and try again.";
}
function field(label, control, hint) {
    return h("div", { class: "dash-field" }, h("label", {}, label), control, hint ? h("p", { class: "dash-hint" }, hint) : null);
}
function input(value = "", placeholder = "", extra = {}) {
    return h("input", { class: "dash-input", type: "text", value, placeholder, autocomplete: "off", spellcheck: "false", ...extra });
}
function select(choices, value) {
    const el = h("select", { class: "dash-input" }, ...choices.map(([id, label]) => h("option", { value: id }, label)));
    el.value = value;
    return el;
}
function span(seconds) {
    const d = Math.floor(seconds / 86400);
    const hours = Math.floor((seconds % 86400) / 3600);
    const minutes = Math.floor((seconds % 3600) / 60);
    return `${d ? `${d}d ` : ""}${d || hours ? `${hours}h ` : ""}${minutes}m`;
}
function tiles(t) {
    const tile = (label, value) => h("div", { class: "dash-tile" }, h("strong", {}, typeof value === "number" ? nf.format(value) : value), h("span", {}, label));
    const group = (title, ...items) => h("section", { class: "staff-group", "aria-label": title }, h("h2", { class: "staff-sub" }, title), h("div", { class: "dash-tiles staff-tiles" }, ...items));
    return h("div", { class: "staff-overview" }, group("Reach", tile("Servers", t.servers), tile("Members", t.members), tile("Joined in 7 days", t.newServers), tile("Biggest server", t.biggest)), group("VIP and bans", tile("VIP servers", t.vip), tile("Basic", t.planCounts.basic), tile("VIP White", t.planCounts.white), tile("VIP Supreme", t.planCounts.supreme), tile("Lifetime", t.planCounts.lifetime), tile("Banned servers", t.banned)), group("The bot", tile("Ping", t.latencyMs == null ? "…" : `${t.latencyMs}ms`), tile("Online for", span(t.uptime)), tile("Commands", t.commands)));
}
function when(stamp) {
    return new Date(stamp * 1000).toLocaleString("en", { dateStyle: "medium", timeStyle: "short" });
}
function serversSection(panel, refresh) {
    const search = h("input", { class: "dash-input", type: "search", placeholder: "Search servers by name or ID", "aria-label": "Search servers", autocomplete: "off" });
    const body = h("div", { class: "staff-servers" });
    const plan = select(panel.plans.map((p) => [p, PLAN_NAMES[p]]), "basic");
    const days = input("30", "Days", { inputmode: "numeric", "aria-label": "Days of VIP" });
    const note = input("", "Note (optional)", { maxlength: 100, "aria-label": "Note" });
    const run = async (job, done) => {
        try {
            await job();
            toast(done);
            await refresh();
        }
        catch (error) {
            toast(messageOf(error));
        }
    };
    const row = (s) => {
        const status = s.vip ? `${s.tier ?? "VIP"}${s.until ? `, until ${when(s.until)}` : ", no end"}` : "No VIP";
        const give = h("button", { class: "btn btn-quiet btn-small", type: "button" }, "Give VIP");
        give.addEventListener("click", () => {
            const count = Number(days.value.trim() || "0");
            if (!Number.isInteger(count) || count < 0 || count > 3650)
                return toast("Days must be a whole number from 0 to 3650 (0 means no end).");
            void run(() => staffApi.vip({ guild_id: s.id, action: "grant", days: count, tier: plan.value, note: note.value }), `${PLAN_NAMES[plan.value]} given to ${s.name}.`);
        });
        const take = h("button", { class: "btn btn-quiet btn-small", type: "button" }, "Take VIP");
        take.disabled = !s.vip || s.source === "env";
        take.title = s.source === "env" ? "This server is VIP through the bot's settings, not a grant." : "";
        take.addEventListener("click", () => {
            if (window.confirm(`Take VIP away from ${s.name}?`))
                void run(() => staffApi.vip({ guild_id: s.id, action: "revoke" }), `VIP taken from ${s.name}.`);
        });
        const ban = h("button", { class: "btn btn-quiet btn-small staff-danger", type: "button" }, "Ban");
        ban.addEventListener("click", () => {
            const reason = window.prompt(`Ban ${s.name}? Risk will leave it and refuse to rejoin.\n\nReason (optional):`);
            if (reason !== null)
                void run(() => staffApi.ban(s.id, reason), `${s.name} is banned.`);
        });
        return h("div", { class: "staff-row" }, h("div", { class: "staff-row-text" }, h("strong", {}, s.name), h("span", {}, `${nf.format(s.members)} members · ID ${s.id}`), h("span", { class: s.vip ? "staff-vip" : "" }, status)), h("div", { class: "staff-row-actions" }, give, take, ban));
    };
    const draw = () => {
        const q = search.value.trim().toLowerCase();
        const shown = panel.serverList.filter((s) => !q || s.name.toLowerCase().includes(q) || s.id.includes(q));
        mount(body, ...(shown.length ? shown.slice(0, 100).map(row) : [h("p", { class: "dash-hint" }, "No servers match.")]), shown.length > 100 ? h("p", { class: "dash-hint" }, `Showing 100 of ${shown.length}. Search to narrow it down.`) : null);
    };
    search.addEventListener("input", draw);
    draw();
    return h("section", { class: "dash-card staff-card", "aria-labelledby": "staff-servers" }, h("h2", { id: "staff-servers" }, "Servers"), h("p", { class: "dash-hint" }, "Give or take VIP, or ban a server. The plan, days and note below apply to Give VIP. 0 days means no end."), h("div", { class: "staff-grant" }, field("Plan", plan), field("Days", days), field("Note", note)), search, body);
}
function pricesSection(panel, refresh) {
    const rows = panel.plans.map((key) => {
        const saved = panel.prices[key];
        return { key, price: input(saved?.price ?? "", "e.g. $4.99", { maxlength: 20, "aria-label": `${PLAN_NAMES[key]} price` }), url: input(saved?.url ?? "", "https://… checkout link", { "aria-label": `${PLAN_NAMES[key]} checkout link` }) };
    });
    const save = h("button", { class: "btn btn-primary", type: "button" }, "Save prices");
    save.addEventListener("click", async () => {
        save.disabled = true;
        try {
            await staffApi.savePrices(Object.fromEntries(rows.map((r) => [r.key, { price: r.price.value.trim(), url: r.url.value.trim() }])));
            toast("Prices saved. The VIP page updates within a minute.");
            await refresh();
        }
        catch (error) {
            toast(messageOf(error));
        }
        finally {
            save.disabled = false;
        }
    });
    return h("section", { class: "dash-card staff-card", "aria-labelledby": "staff-prices" }, h("h2", { id: "staff-prices" }, "Prices"), h("p", { class: "dash-hint" }, "What the VIP page shows. Leave a price empty to use the site's default. A checkout link must start with https://."), ...rows.map((r) => h("div", { class: "staff-price" }, h("h3", {}, PLAN_NAMES[r.key]), field("Price", r.price), field("Checkout link", r.url))), h("div", { class: "actions" }, save));
}
function bansSection(panel, refresh) {
    const id = input("", "Server ID", { inputmode: "numeric", "aria-label": "Server ID to ban" });
    const reason = input("", "Reason (optional)", { maxlength: 200, "aria-label": "Reason" });
    const add = h("button", { class: "btn btn-quiet staff-danger", type: "button" }, "Ban server");
    add.addEventListener("click", async () => {
        if (!/^\d{15,21}$/.test(id.value.trim()))
            return toast("Enter the server's ID (15 to 21 digits).");
        if (!window.confirm("Ban this server? Risk will leave it (if it's there) and refuse to rejoin."))
            return;
        try {
            await staffApi.ban(id.value.trim(), reason.value);
            toast("Server banned.");
            await refresh();
        }
        catch (error) {
            toast(messageOf(error));
        }
    });
    const list = panel.bannedList.map((b) => {
        const undo = h("button", { class: "btn btn-quiet btn-small", type: "button" }, "Unban");
        undo.addEventListener("click", async () => {
            try {
                await staffApi.unban(b.id);
                toast("Server unbanned. It can add Risk again.");
                await refresh();
            }
            catch (error) {
                toast(messageOf(error));
            }
        });
        return h("div", { class: "staff-row" }, h("div", { class: "staff-row-text" }, h("strong", {}, b.name || "Unknown server"), h("span", {}, `ID ${b.id}${b.at ? ` · banned ${when(b.at)}` : ""}`), b.reason ? h("span", {}, `Reason: ${b.reason}`) : null), h("div", { class: "staff-row-actions" }, undo));
    });
    return h("section", { class: "dash-card staff-card", "aria-labelledby": "staff-bans" }, h("h2", { id: "staff-bans" }, "Banned servers"), h("p", { class: "dash-hint" }, "A banned server loses its VIP, Risk leaves it, and Risk leaves again if someone adds it back."), h("div", { class: "staff-grant" }, field("Server ID", id), field("Reason", reason)), h("div", { class: "actions" }, add), ...(list.length ? list : [h("p", { class: "dash-hint" }, "No banned servers.")]));
}
function rolesSection(panel, refresh) {
    const choices = [["staff", "Staff"], ...(panel.role === "owner" ? [["developer", "Developer"], ["owner", "Owner"]] : [])];
    const user = input("", "Discord user ID", { inputmode: "numeric", "aria-label": "Discord user ID" });
    const role = select(choices, "staff");
    const assign = h("button", { class: "btn btn-primary", type: "button" }, "Assign role");
    const apply = async (userId, value, done) => {
        try {
            await staffApi.role(userId, value);
            toast(done);
            await refresh();
        }
        catch (error) {
            toast(messageOf(error));
        }
    };
    assign.addEventListener("click", () => {
        if (!/^\d{15,21}$/.test(user.value.trim()))
            return toast("Enter the person's Discord user ID (15 to 21 digits).");
        void apply(user.value.trim(), role.value, "Role assigned.");
    });
    const list = panel.roles.map((r) => {
        const remove = h("button", { class: "btn btn-quiet btn-small", type: "button" }, "Remove");
        remove.disabled = panel.role !== "owner" && r.role !== "staff";
        remove.addEventListener("click", () => {
            if (window.confirm(`Remove the ${r.role} role from ${r.name ?? r.id}?`))
                void apply(r.id, "none", "Role removed.");
        });
        return h("div", { class: "staff-row" }, h("div", { class: "staff-row-text" }, h("strong", {}, r.name ?? "Not in the staff server"), h("span", {}, `ID ${r.id}`), h("span", {}, r.role)), h("div", { class: "staff-row-actions" }, remove));
    });
    return h("section", { class: "dash-card staff-card", "aria-labelledby": "staff-roles" }, h("h2", { id: "staff-roles" }, "Roles"), h("p", { class: "dash-hint" }, panel.role === "owner" ? "Staff see the totals. Developers and owners also get this owner panel. The person must be in the staff server." : "You can add and remove staff. Ask an owner to make a developer or owner. The person must be in the staff server."), h("div", { class: "staff-grant" }, field("User ID", user), field("Role", role)), h("div", { class: "actions" }, assign), ...(list.length ? list : [h("p", { class: "dash-hint" }, "No roles have been assigned here. People can also get a role from a Discord role in the staff server.")]));
}
function commandsSection(control) {
    const search = h("input", { class: "dash-input", type: "search", placeholder: "Search commands", "aria-label": "Search commands", autocomplete: "off" });
    const body = h("div", { class: "staff-servers" });
    const draw = () => {
        const q = search.value.trim().toLowerCase();
        const shown = control.commands.filter((c) => !q || c.name.includes(q) || c.category.toLowerCase().includes(q) || c.description.toLowerCase().includes(q));
        mount(body, ...(shown.length
            ? shown.slice(0, 150).map((c) => {
                const box = h("input", { type: "checkbox", "aria-label": `Turn off ${c.name} in every server` });
                box.checked = c.off;
                box.addEventListener("change", async () => {
                    try {
                        await staffApi.setCommand(c.name, box.checked);
                        c.off = box.checked;
                        toast(box.checked ? `${c.name} is off in every server.` : `${c.name} is back on.`);
                    }
                    catch (error) {
                        box.checked = !box.checked;
                        toast(messageOf(error));
                    }
                });
                return h("label", { class: "staff-row staff-switch" }, h("div", { class: "staff-row-text" }, h("strong", {}, `!${c.name}`), h("span", {}, `${c.category} · ${c.description}`)), h("span", { class: "staff-off" }, box, "Off everywhere"));
            })
            : [h("p", { class: "dash-hint" }, "No command matches.")]), shown.length > 150 ? h("p", { class: "dash-hint" }, `Showing 150 of ${shown.length}. Search to narrow it down.`) : null);
    };
    search.addEventListener("input", draw);
    draw();
    return h("section", { class: "dash-card staff-card", "aria-labelledby": "staff-commands" }, h("h2", { id: "staff-commands" }, "Commands"), h("p", { class: "dash-hint" }, "Turn a command off in every server at once. Owners of the bot can still use it. Subcommands go with their parent."), search, body);
}
function blockedSection(control, refresh) {
    const id = input("", "Discord user ID", { inputmode: "numeric", "aria-label": "User ID to block" });
    const reason = input("", "Reason (optional)", { maxlength: 200, "aria-label": "Reason" });
    const add = h("button", { class: "btn btn-quiet staff-danger", type: "button" }, "Block user");
    add.addEventListener("click", async () => {
        if (!/^\d{15,21}$/.test(id.value.trim()))
            return toast("Enter the person's Discord user ID (15 to 21 digits).");
        try {
            await staffApi.block(id.value.trim(), reason.value);
            toast("User blocked.");
            await refresh();
        }
        catch (error) {
            toast(messageOf(error));
        }
    });
    const list = control.blocked.map((b) => {
        const undo = h("button", { class: "btn btn-quiet btn-small", type: "button" }, "Unblock");
        undo.addEventListener("click", async () => {
            try {
                await staffApi.block(b.id, "", true);
                toast("User unblocked.");
                await refresh();
            }
            catch (error) {
                toast(messageOf(error));
            }
        });
        return h("div", { class: "staff-row" }, h("div", { class: "staff-row-text" }, h("strong", {}, `ID ${b.id}`), h("span", {}, `${b.at ? `blocked ${when(b.at)}` : ""}${b.reason ? ` · ${b.reason}` : ""}`)), h("div", { class: "staff-row-actions" }, undo));
    });
    return h("section", { class: "dash-card staff-card", "aria-labelledby": "staff-blocked" }, h("h2", { id: "staff-blocked" }, "Blocked users"), h("p", { class: "dash-hint" }, "A blocked person can't use any Risk command in any server. Risk ignores them without a reply."), h("div", { class: "staff-grant" }, field("User ID", id), field("Reason", reason)), h("div", { class: "actions" }, add), ...(list.length ? list : [h("p", { class: "dash-hint" }, "Nobody is blocked.")]));
}
function botSection(control, refresh) {
    const on = h("input", { type: "checkbox", "aria-label": "Maintenance mode" });
    on.checked = control.maintenance.on;
    const message = input(control.maintenance.message, "Shown to members, e.g. Back at 5pm", { maxlength: 300, "aria-label": "Maintenance message" });
    const save = h("button", { class: "btn btn-primary", type: "button" }, "Save");
    save.addEventListener("click", async () => {
        try {
            await staffApi.maintenance(on.checked, message.value);
            toast(on.checked ? "Maintenance mode is on." : "Maintenance mode is off.");
            await refresh();
        }
        catch (error) {
            toast(messageOf(error));
        }
    });
    return h("section", { class: "dash-card staff-card", "aria-labelledby": "staff-bot" }, h("h2", { id: "staff-bot" }, "Maintenance mode"), h("p", { class: "dash-hint" }, "While it's on, every command from everyone except the bot's owners answers with your message. Shutting the bot down or restarting it is done from the owner's control panel app."), h("label", { class: "staff-off staff-maint" }, on, "Maintenance mode on"), field("Message", message), h("div", { class: "actions" }, save));
}
function logSection(panel) {
    return h("section", { class: "dash-card staff-card", "aria-labelledby": "staff-log" }, h("h2", { id: "staff-log" }, "Recent changes"), ...(panel.log.length
        ? panel.log.map((e) => h("div", { class: "staff-log" }, h("span", {}, when(e.at)), h("strong", {}, e.action), h("span", {}, `${e.detail} (by ${e.by})`)))
        : [h("p", { class: "dash-hint" }, "Nothing yet.")]));
}
export function renderStaff() {
    const root = h("div", { class: "view container page dash staff" });
    let alive = true;
    mount(root, h("p", { class: "dash-loading", role: "status" }, "Loading"));
    const reasonText = new URLSearchParams(window.location.search).get("login");
    const signIn = (enabled) => h("div", { class: "dash-hero" }, h("h1", {}, "Staff panel"), h("p", { class: "lede" }, "For the Risk team. Sign in with Discord to continue."), reasonText ? notice("error", "Sign-in didn't finish. Try again.") : null, enabled ? h("div", { class: "actions" }, h("a", { class: "btn btn-primary", href: "/api/auth/login?next=/staff" }, "Sign in with Discord")) : notice("info", "Sign-in isn't switched on for this site yet."));
    const draw = (overview, panel, control, refresh) => {
        const groups = panel
            ? [
                ["People and servers", [["servers", "Servers", () => serversSection(panel, refresh)], ["bans", "Banned servers", () => bansSection(panel, refresh)], ["roles", "Roles", () => rolesSection(panel, refresh)]]],
                ["Bot control", control ? [["commands", "Commands", () => commandsSection(control)], ["blocked", "Blocked users", () => blockedSection(control, refresh)], ["bot", "Maintenance", () => botSection(control, refresh)]] : []],
                ["Public pages", [...(control ? [["status", "Status page", () => statusPageSection(control.statusPage, refresh)]] : []), ["prices", "Prices", () => pricesSection(panel, refresh)]]],
                ["History", [["log", "Recent changes", () => logSection(panel)]]],
            ]
            : [];
        const sections = groups.flatMap(([, items]) => items);
        const holder = h("div", { class: "staff-body" });
        const side = h("nav", { class: "staff-side", role: "tablist", "aria-label": "Owner panel", "aria-orientation": "vertical" });
        const open = (id) => {
            const found = sections.find(([key]) => key === id);
            if (!found)
                return;
            sessionStorageSet(id);
            side.querySelectorAll("button").forEach((b) => b.setAttribute("aria-selected", String(b.dataset.tab === id)));
            mount(holder, found[2]());
        };
        for (const [title, items] of groups) {
            if (!items.length)
                continue;
            side.appendChild(h("p", { class: "staff-side-title" }, title));
            for (const [id, label] of items) {
                const tab = h("button", { class: "dash-tab", type: "button", role: "tab", "data-tab": id }, label);
                tab.addEventListener("click", () => open(id));
                side.appendChild(tab);
            }
        }
        mount(root, h("h1", {}, "Staff panel"), h("p", { class: "lede" }, `You're signed in as ${overview.role}. ${panel ? "The owner panel is below the totals." : "You can see the totals."}`), tiles(overview), panel ? h("h2", { class: "staff-sub" }, "Owner panel") : null, panel ? h("div", { class: "staff-shell" }, side, holder) : null, h("p", { class: "dash-fine" }, "This page is only for the Risk staff team. Servers that have Risk installed don't get access."));
        if (panel)
            open(sessionStorageGet() ?? "servers");
    };
    const load = async () => {
        const overview = await staffApi.overview();
        // The global controls come from a separate part of the bot. If it isn't uploaded the rest still works.
        const [panel, control] = overview.owner ? await Promise.all([staffApi.owner(), staffApi.control().catch(() => null)]) : [null, null];
        if (alive)
            draw(overview, panel, control, load);
    };
    void (async () => {
        try {
            const me = await dashApi.me();
            if (!alive)
                return;
            if (!me.user)
                return mount(root, signIn(me.enabled));
            const status = await staffApi.me();
            if (!alive)
                return;
            if (!status.role) {
                return mount(root, h("h1", {}, "Staff panel"), notice("error", status.staffServer ? "Your Discord account isn't on the Risk staff team." : "The staff panel isn't set up yet. The bot owner needs to set STAFF_GUILD_ID."), h("div", { class: "actions" }, h("a", { class: "btn btn-quiet", href: "/", "data-link": true }, "Back to the site")));
            }
            await load();
        }
        catch (error) {
            if (alive)
                mount(root, h("h1", {}, "Staff panel"), notice("error", messageOf(error)));
        }
    })();
    return { node: root, cleanup: () => { alive = false; } };
}
function sessionStorageGet() {
    try {
        return window.sessionStorage.getItem("risk-staff-tab");
    }
    catch {
        return null;
    }
}
function sessionStorageSet(value) {
    try {
        window.sessionStorage.setItem("risk-staff-tab", value);
    }
    catch {
        /* remembering the tab is optional */
    }
}
