export function prefersReduced() {
    return window.matchMedia("(prefers-reduced-motion: reduce)").matches;
}
export function initMotionFlag() {
    const query = window.matchMedia("(prefers-reduced-motion: reduce)");
    const apply = () => document.documentElement.classList.toggle("anim", !query.matches);
    apply();
    query.addEventListener("change", apply);
}
export function splitWords(el) {
    const text = (el.textContent ?? "").trim();
    const words = text.split(/\s+/).filter(Boolean);
    el.setAttribute("aria-label", text);
    const nodes = [];
    words.forEach((word, i) => {
        const outer = document.createElement("span");
        outer.className = "w";
        outer.setAttribute("aria-hidden", "true");
        const inner = document.createElement("span");
        inner.className = "wi";
        inner.style.setProperty("--i", String(i));
        inner.textContent = word;
        outer.appendChild(inner);
        nodes.push(outer);
        if (i < words.length - 1)
            nodes.push(document.createTextNode(" "));
    });
    el.replaceChildren(...nodes);
}
export function playIntro(root) {
    if (!document.documentElement.classList.contains("anim"))
        return;
    requestAnimationFrame(() => requestAnimationFrame(() => root.classList.add("is-in")));
}
export function revealOnScroll(root, selector, className = "in", threshold = 0.3) {
    const items = Array.from(root.querySelectorAll(selector));
    if (!("IntersectionObserver" in window)) {
        items.forEach((item) => item.classList.add(className));
        return () => undefined;
    }
    const observer = new IntersectionObserver((entries) => {
        for (const entry of entries) {
            if (!entry.isIntersecting)
                continue;
            entry.target.classList.add(className);
            observer.unobserve(entry.target);
        }
    }, { threshold, rootMargin: "0px 0px -6% 0px" });
    items.forEach((item) => observer.observe(item));
    return () => observer.disconnect();
}
