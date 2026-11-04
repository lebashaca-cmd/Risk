import { ApiFailure, dashApi } from "./api.js";
import { uid } from "./dash-ui.js";
import { h } from "./dom.js";
import { toast } from "./ui.js";
const LIMITS = { avatar: 2_000_000, banner: 3_000_000 };
const ACCEPT = ["image/png", "image/jpeg", "image/gif"];
function readFile(file) {
    return new Promise((resolve, reject) => {
        const reader = new FileReader();
        reader.onload = () => resolve(String(reader.result));
        reader.onerror = () => reject(new Error("read"));
        reader.readAsDataURL(file);
    });
}
/** The bot's profile in this server, laid out like Discord's "Customize profile". */
export function profileCard(initial, guildId) {
    let saved = { ...initial };
    const draft = { nick: initial.nick, bio: initial.bio, avatar: undefined, banner: undefined };
    let busy = false;
    const nickId = uid("pf");
    const bioId = uid("pf");
    // Preview
    const banner = h("div", { class: "pf-banner" });
    const avatarImg = h("img", { class: "pf-avatar-img", alt: "", width: 80, height: 80, referrerpolicy: "no-referrer" });
    const name = h("strong", { class: "pf-name" });
    const handle = h("span", { class: "pf-handle" });
    const bio = h("p", { class: "pf-bio" });
    const preview = h("div", { class: "pf-card", "aria-label": "Preview of the bot's profile in this server", role: "group" }, banner, h("div", { class: "pf-avatar" }, avatarImg, h("span", { class: "pf-app" }, "APP")), h("div", { class: "pf-body" }, name, handle, bio));
    // Controls
    const nick = h("input", { type: "text", id: nickId, class: "dash-input", maxlength: 32, autocomplete: "off", placeholder: initial.botName });
    nick.value = draft.nick;
    const bioInput = h("textarea", { id: bioId, class: "dash-input dash-area", maxlength: 190, rows: 4, placeholder: "Tell people what Risk does in this server" });
    bioInput.value = draft.bio;
    const bioCount = h("span", { class: "dash-count", "aria-hidden": "true" });
    const note = h("p", { class: "dash-hint pf-note", role: "status" });
    const pick = (kind) => {
        const input = h("input", { type: "file", accept: ACCEPT.join(","), class: "sr-only", id: uid("pf"), "aria-label": `Choose a ${kind}` });
        const label = kind === "avatar" ? "avatar" : "banner";
        const choose = h("button", { type: "button", class: "btn btn-quiet btn-small" }, `Change ${label}`);
        const remove = h("button", { type: "button", class: "btn btn-quiet btn-small" }, "Remove");
        choose.addEventListener("click", () => input.click());
        input.addEventListener("change", async () => {
            const file = input.files?.[0];
            input.value = "";
            if (!file)
                return;
            if (!ACCEPT.includes(file.type))
                return void (note.textContent = `The ${label} must be a PNG, JPG or GIF.`);
            if (file.size > LIMITS[kind])
                return void (note.textContent = `The ${label} must be under ${LIMITS[kind] / 1_000_000} MB.`);
            try {
                draft[kind] = await readFile(file);
                note.textContent = "";
                update();
            }
            catch {
                note.textContent = "That file couldn't be read.";
            }
        });
        remove.addEventListener("click", () => {
            draft[kind] = null;
            update();
        });
        return h("div", { class: "pf-pick" }, choose, remove, input);
    };
    const save = h("button", { type: "button", class: "btn btn-primary" }, "Save profile");
    const reset = h("button", { type: "button", class: "btn btn-quiet" }, "Reset");
    const message = h("p", { class: "dash-savemsg", role: "status" });
    const changes = () => {
        const out = {};
        if (draft.nick.trim() !== saved.nick)
            out["nick"] = draft.nick.trim();
        if (draft.bio.trim() !== saved.bio)
            out["bio"] = draft.bio.trim();
        if (draft.avatar !== undefined)
            out["avatar"] = draft.avatar;
        if (draft.banner !== undefined)
            out["banner"] = draft.banner;
        return out;
    };
    const shownAvatar = () => (draft.avatar === undefined ? saved.avatar ?? saved.defaultAvatar : draft.avatar ?? saved.defaultAvatar);
    const shownBanner = () => (draft.banner === undefined ? saved.banner : draft.banner);
    function update() {
        const avatarUrl = shownAvatar();
        if (avatarUrl)
            avatarImg.setAttribute("src", avatarUrl);
        else
            avatarImg.removeAttribute("src");
        const bannerUrl = shownBanner();
        banner.style.backgroundImage = bannerUrl ? `url("${bannerUrl.replace(/"/g, "")}")` : "";
        banner.classList.toggle("has-image", Boolean(bannerUrl));
        name.textContent = draft.nick.trim() || saved.botName;
        handle.textContent = draft.nick.trim() ? saved.botName : "";
        bio.textContent = draft.bio.trim() || "No bio yet.";
        bio.classList.toggle("is-empty", !draft.bio.trim());
        bioCount.textContent = `${draft.bio.length}/190`;
        const dirty = Object.keys(changes()).length > 0;
        save.disabled = !dirty || busy;
        reset.disabled = !dirty || busy;
        if (!busy && !message.classList.contains("is-error"))
            message.textContent = dirty ? "You have unsaved profile changes." : message.dataset["saved"] ?? "";
    }
    nick.addEventListener("input", () => {
        draft.nick = nick.value;
        message.classList.remove("is-error");
        update();
    });
    bioInput.addEventListener("input", () => {
        draft.bio = bioInput.value;
        message.classList.remove("is-error");
        update();
    });
    reset.addEventListener("click", () => {
        draft.nick = saved.nick;
        draft.bio = saved.bio;
        draft.avatar = undefined;
        draft.banner = undefined;
        nick.value = saved.nick;
        bioInput.value = saved.bio;
        note.textContent = "";
        message.classList.remove("is-error");
        update();
    });
    save.addEventListener("click", async () => {
        const body = changes();
        if (busy || Object.keys(body).length === 0)
            return;
        busy = true;
        message.classList.remove("is-error");
        message.textContent = "Saving…";
        save.disabled = true;
        try {
            const result = await dashApi.saveProfile(guildId, body);
            saved = { ...result.profile };
            draft.nick = saved.nick;
            draft.bio = saved.bio;
            draft.avatar = undefined;
            draft.banner = undefined;
            nick.value = saved.nick;
            bioInput.value = saved.bio;
            message.dataset["saved"] = "Profile saved.";
            toast("Profile saved");
        }
        catch (error) {
            message.classList.add("is-error");
            message.textContent = error instanceof ApiFailure ? error.message : "That didn't save. Try again.";
        }
        finally {
            busy = false;
            if (!message.classList.contains("is-error"))
                message.textContent = message.dataset["saved"] ?? "";
            update();
        }
    });
    const form = h("div", { class: "pf-form" }, h("div", { class: "dash-field" }, h("label", { for: nickId }, "Display name in this server"), nick, h("p", { class: "dash-hint" }, `Leave empty to use ${initial.botName}.`)), h("div", { class: "dash-field" }, h("label", { for: bioId }, "About me"), h("div", { class: "dash-area-wrap" }, bioInput, bioCount)), h("div", { class: "dash-field" }, h("span", { class: "pf-label" }, "Avatar"), pick("avatar"), h("p", { class: "dash-hint" }, "PNG, JPG or GIF under 2 MB.")), h("div", { class: "dash-field" }, h("span", { class: "pf-label" }, "Banner"), pick("banner"), h("p", { class: "dash-hint" }, "PNG, JPG or GIF under 3 MB.")), note, h("div", { class: "pf-actions" }, message, reset, save), h("p", { class: "dash-hint" }, "This changes how Risk looks in this server only. Discord shows one online status for the bot everywhere, so it can't be set per server."));
    const root = h("section", { class: "pf", "aria-labelledby": "pf-title" }, h("header", { class: "dash-panel-head" }, h("h2", { id: "pf-title" }, "Bot profile"), h("p", { class: "lede" }, "Change Risk's name, picture, banner and bio in this server.")), h("div", { class: "pf-grid" }, form, preview));
    update();
    return root;
}
