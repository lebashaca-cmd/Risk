import { api } from "./api.js";
import { initMotionFlag, prefersReduced } from "./anim.js";
import { h, mount } from "./dom.js";
import { renderCommands } from "./commands.js";
import { renderHome } from "./home.js";
import { applyStatus, startStatusPolling } from "./status.js";
import { renderTerms } from "./terms.js";
const outlet = document.getElementById("app");
const fallbackConfig = { name: "Risk", inviteUrl: null, supportUrl: null };
let config = fallbackConfig;
let cleanup = null;
let firstRender = true;
let indicatorPlaced = false;
const TITLES = {
    "/": "Risk: tickets, logs and moderation for Discord",
    "/commands": "Commands · Risk",
    "/terms": "Terms of Service · Risk",
};
function normalize(path) {
    const trimmed = path.replace(/\/+$/, "");
    return trimmed === "" ? "/" : trimmed;
}
function activeLink() {
    return document.querySelector(".nav-links a[aria-current='page']");
}
function moveIndicator(target) {
    const indicator = document.querySelector(".nav-ind");
    if (!indicator)
        return;
    if (!target) {
        indicator.style.opacity = "0";
        return;
    }
    if (!indicatorPlaced) {
        indicator.style.transition = "none";
        indicator.style.transform = `translateX(${target.offsetLeft}px)`;
        indicator.style.width = `${target.offsetWidth}px`;
        void indicator.offsetWidth;
        indicator.style.transition = "";
        indicatorPlaced = true;
    }
    indicator.style.opacity = "1";
    indicator.style.width = `${target.offsetWidth}px`;
    indicator.style.transform = `translateX(${target.offsetLeft}px)`;
}
function bindNav() {
    const nav = document.querySelector(".nav-links");
    if (!nav)
        return;
    nav.querySelectorAll("a").forEach((link) => {
        link.addEventListener("mouseenter", () => moveIndicator(link));
        link.addEventListener("focus", () => moveIndicator(link));
    });
    nav.addEventListener("mouseleave", () => moveIndicator(activeLink()));
    nav.addEventListener("focusout", () => moveIndicator(activeLink()));
    window.addEventListener("resize", () => moveIndicator(activeLink()));
    void document.fonts?.ready.then(() => moveIndicator(activeLink()));
}
function notFound() {
    return h("div", { class: "view container page" }, h("h1", {}, "That page doesn't exist"), h("p", { class: "lede" }, "The link may be old or mistyped."), h("div", { class: "actions" }, h("a", { class: "btn btn-primary", href: "/", "data-link": true }, "Go to the home page")));
}
function render() {
    if (!outlet)
        return;
    cleanup?.();
    cleanup = null;
    const path = normalize(window.location.pathname);
    let node;
    switch (path) {
        case "/": {
            const home = renderHome(config);
            node = home.node;
            cleanup = home.cleanup;
            break;
        }
        case "/commands": {
            const view = renderCommands();
            node = view.node;
            cleanup = view.cleanup;
            break;
        }
        case "/terms": {
            const view = renderTerms();
            node = view.node;
            cleanup = view.cleanup;
            break;
        }
        default:
            node = notFound();
    }
    mount(outlet, node);
    document.title = TITLES[path] ?? "Page not found · Risk";
    document.querySelectorAll("nav a[data-link]").forEach((link) => {
        if (normalize(new URL(link.href).pathname) === path)
            link.setAttribute("aria-current", "page");
        else
            link.removeAttribute("aria-current");
    });
    moveIndicator(activeLink());
    applyStatus();
    if (!firstRender) {
        window.scrollTo(0, 0);
        const heading = node.querySelector("h1");
        if (heading) {
            heading.tabIndex = -1;
            heading.focus({ preventScroll: true });
        }
    }
    firstRender = false;
}
function transition(update) {
    const doc = document;
    if (doc.startViewTransition && !prefersReduced())
        doc.startViewTransition(update);
    else
        update();
}
function navigate(url) {
    if (url.pathname + url.search === window.location.pathname + window.location.search) {
        transition(render);
        return;
    }
    window.history.pushState({}, "", url.pathname + url.search);
    transition(render);
}
document.addEventListener("click", (event) => {
    if (event.defaultPrevented || event.button !== 0 || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey)
        return;
    const link = event.target?.closest("a[data-link]");
    if (!link)
        return;
    const url = new URL(link.href, window.location.origin);
    if (url.origin !== window.location.origin)
        return;
    event.preventDefault();
    navigate(url);
});
window.addEventListener("popstate", () => transition(render));
function watchHeader() {
    const nav = document.querySelector(".nav");
    if (!nav || !("IntersectionObserver" in window))
        return;
    const sentinel = document.createElement("div");
    sentinel.setAttribute("aria-hidden", "true");
    sentinel.style.cssText = "position:absolute;top:0;left:0;width:1px;height:24px;pointer-events:none";
    document.body.prepend(sentinel);
    new IntersectionObserver(([entry]) => nav.classList.toggle("is-stuck", !!entry && !entry.isIntersecting)).observe(sentinel);
}
async function start() {
    initMotionFlag();
    watchHeader();
    bindNav();
    try {
        config = await api.config();
    }
    catch {
        config = fallbackConfig;
    }
    document.querySelectorAll("[data-invite]").forEach((link) => {
        if (config.inviteUrl)
            link.href = config.inviteUrl;
        else
            link.hidden = true;
    });
    render();
    startStatusPolling();
}
void start();
