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
/**
 * Gives scrolling some weight: the page value is eased toward the real scroll
 * position, so parallax layers trail slightly and settle, and the server strip
 * speeds up while you scroll and glides back to its pace afterwards.
 */
export function scrollFx(root) {
    const doc = document.documentElement;
    let current = window.scrollY;
    let rate = 1;
    let frame = 0;
    const tracks = () => Array.from(root.querySelectorAll(".marquee .track")).flatMap((track) => track.getAnimations());
    const tick = () => {
        frame = 0;
        const target = window.scrollY;
        const delta = target - current;
        current += delta * 0.085;
        const speed = Math.abs(delta);
        const wantedRate = 1 + Math.min(7, speed * 0.045);
        rate += (wantedRate - rate) * 0.12;
        const max = Math.max(1, doc.scrollHeight - window.innerHeight);
        doc.style.setProperty("--prog", String(Math.min(1, Math.max(0, target / max))));
        root.style.setProperty("--py", `${(current * -0.08).toFixed(2)}px`);
        root.style.setProperty("--py2", `${(current * 0.05).toFixed(2)}px`);
        root.style.setProperty("--tilt", `${Math.max(-4, Math.min(4, delta * 0.02)).toFixed(2)}deg`);
        root.style.setProperty("--hy", `${(current * -0.14).toFixed(2)}px`);
        for (const animation of tracks())
            animation.playbackRate = rate;
        if (Math.abs(delta) > 0.3 || Math.abs(rate - 1) > 0.02)
            frame = requestAnimationFrame(tick);
    };
    const wake = () => {
        if (!frame)
            frame = requestAnimationFrame(tick);
    };
    window.addEventListener("scroll", wake, { passive: true });
    window.addEventListener("resize", wake, { passive: true });
    wake();
    return () => {
        window.removeEventListener("scroll", wake);
        window.removeEventListener("resize", wake);
        if (frame)
            cancelAnimationFrame(frame);
        doc.style.removeProperty("--prog");
    };
}
/**
 * Inertial mouse-wheel scrolling. The wheel moves a target position and the
 * page glides toward it, so each flick has momentum and settles gently.
 * Touch, keyboard, find-in-page and links keep the browser's own scrolling.
 */
export function smoothScroll() {
    if (!window.matchMedia("(pointer: fine)").matches)
        return;
    let target = window.scrollY;
    let current = target;
    let lastSet = target;
    let frame = 0;
    let last = 0;
    const limit = () => Math.max(0, document.documentElement.scrollHeight - window.innerHeight);
    const clamp = (value) => Math.min(limit(), Math.max(0, value));
    const canScroll = (el) => {
        for (let node = el; node && node !== document.body; node = node.parentElement) {
            const style = getComputedStyle(node);
            const scrolls = /(auto|scroll)/.test(style.overflowY) && node.scrollHeight > node.clientHeight + 1;
            if (scrolls)
                return true;
        }
        return false;
    };
    const step = (now) => {
        frame = 0;
        const dt = Math.min(64, now - last || 16);
        last = now;
        current += (target - current) * (1 - Math.exp(-dt / 140));
        if (Math.abs(target - current) < 0.4)
            current = target;
        lastSet = current;
        window.scrollTo({ top: current, behavior: "instant" });
        if (current !== target)
            frame = requestAnimationFrame(step);
    };
    window.addEventListener("wheel", (event) => {
        if (event.ctrlKey || event.defaultPrevented || event.deltaY === 0 || Math.abs(event.deltaX) > Math.abs(event.deltaY))
            return;
        if (canScroll(event.target))
            return;
        event.preventDefault();
        const unit = event.deltaMode === 1 ? 36 : event.deltaMode === 2 ? window.innerHeight : 1;
        target = clamp(target + Math.max(-240, Math.min(240, event.deltaY * unit)) * 1.15);
        if (!frame) {
            last = performance.now();
            frame = requestAnimationFrame(step);
        }
    }, { passive: false });
    window.addEventListener("scroll", () => {
        if (Math.abs(window.scrollY - lastSet) > 2) {
            target = current = lastSet = window.scrollY;
            if (frame)
                cancelAnimationFrame(frame);
            frame = 0;
        }
    }, { passive: true });
}
