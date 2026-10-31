import { api } from "./api.js";
import { h, mount } from "./dom.js";
function slug(title, index) {
    const text = title
        .replace(/^\d+\.\s*/, "")
        .toLowerCase()
        .replace(/[^a-z0-9]+/g, "-")
        .replace(/^-|-$/g, "");
    return text || `section-${index + 1}`;
}
export function renderTerms() {
    const body = h("div", { class: "terms-layout" }, h("p", { class: "muted" }, "Loading terms"));
    const node = h("div", { class: "view container page" }, h("h1", {}, "Terms of Service"), body);
    let onScroll = null;
    let onUnpin = null;
    let pinned = null;
    let frame = 0;
    const show = (tos) => {
        if (!tos.sections.length) {
            mount(body, h("p", { class: "empty" }, "The terms aren't published yet."));
            return;
        }
        const sections = tos.sections.map((section, i) => ({ ...section, id: slug(section.title, i) }));
        const toc = h("nav", { class: "toc", "aria-label": "On this page" }, h("ol", {}, ...sections.map((s) => h("li", {}, h("a", { href: `#${s.id}`, "data-toc": s.id }, s.title)))));
        const prose = h("div", { class: "prose" }, tos.updated ? h("p", { class: "muted" }, `Last updated ${tos.updated}`) : null, ...sections.flatMap((s) => [h("h2", { id: s.id }, s.title), h("p", {}, s.text)]));
        mount(body, toc, prose);
        const headings = Array.from(prose.querySelectorAll("h2"));
        const links = Array.from(toc.querySelectorAll("a"));
        const update = () => {
            frame = 0;
            const line = window.innerHeight * 0.3;
            const atBottom = window.innerHeight + window.scrollY >= document.documentElement.scrollHeight - 4;
            let current = headings[0];
            if (pinned)
                current = headings.find((heading) => heading.id === pinned) ?? current;
            else if (window.scrollY > 8) {
                for (const heading of headings)
                    if (heading.getBoundingClientRect().top <= line)
                        current = heading;
                if (atBottom)
                    current = headings[headings.length - 1];
            }
            links.forEach((a) => (a.dataset.toc === current?.id ? a.setAttribute("aria-current", "true") : a.removeAttribute("aria-current")));
        };
        const schedule = () => {
            if (!frame)
                frame = requestAnimationFrame(update);
        };
        const unpin = () => {
            pinned = null;
            schedule();
        };
        toc.addEventListener("click", (event) => {
            const link = event.target.closest("a[data-toc]");
            if (!link)
                return;
            pinned = link.dataset.toc ?? null;
            schedule();
        });
        onScroll = schedule;
        onUnpin = unpin;
        window.addEventListener("scroll", schedule, { passive: true });
        window.addEventListener("resize", schedule, { passive: true });
        window.addEventListener("wheel", unpin, { passive: true });
        window.addEventListener("touchmove", unpin, { passive: true });
        window.addEventListener("keydown", unpin);
        if (window.location.hash)
            pinned = window.location.hash.slice(1);
        update();
        if (window.location.hash)
            document.getElementById(window.location.hash.slice(1))?.scrollIntoView();
    };
    api
        .tos()
        .then(show)
        .catch(() => mount(body, h("p", { class: "empty" }, "The terms didn't load. Refresh the page and try again.")));
    return {
        node,
        cleanup: () => {
            if (onScroll) {
                window.removeEventListener("scroll", onScroll);
                window.removeEventListener("resize", onScroll);
            }
            if (onUnpin) {
                window.removeEventListener("wheel", onUnpin);
                window.removeEventListener("touchmove", onUnpin);
                window.removeEventListener("keydown", onUnpin);
            }
            cancelAnimationFrame(frame);
        },
    };
}
