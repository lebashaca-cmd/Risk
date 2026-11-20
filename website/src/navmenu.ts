import { prefersReduced } from "./anim.js";

/** The hanging menu tab: opens into the page links, and an eye on it looks around while it is closed. */
export function initNavMenu(): void {
  const nav = document.querySelector<HTMLElement>(".nav");
  const toggle = nav?.querySelector<HTMLButtonElement>(".nav-toggle");
  const panel = nav?.querySelector<HTMLElement>(".nav-panel");
  const eyes = Array.from(nav?.querySelectorAll<HTMLElement>(".nav-eye") ?? []);
  const eyeBox = nav?.querySelector<HTMLElement>(".nav-eyes");
  const hint = document.querySelector<HTMLElement>(".nav-hint");
  if (!nav || !toggle || !panel) return;

  const isOpen = () => nav.dataset.open === "true";
  const inner = panel.querySelector<HTMLElement>(".nav-panel-in");
  // Height is set explicitly so it can animate smoothly along with the width.
  const fit = () => nav.style.setProperty("--nav-h", isOpen() && inner ? `${inner.offsetHeight}px` : "3.4rem");
  if (inner && "ResizeObserver" in window) new ResizeObserver(() => { if (isOpen()) fit(); }).observe(inner);
  const setOpen = (open: boolean, focusToggle = false) => {
    nav.dataset.open = String(open);
    fit();
    toggle.setAttribute("aria-expanded", String(open));
    toggle.setAttribute("aria-label", open ? "Close menu" : "Open menu");
    panel.toggleAttribute("inert", !open);
    if (open) look(0, 5);
    else if (focusToggle) toggle.focus();
  };
  setOpen(false);

  toggle.addEventListener("click", () => setOpen(!isOpen()));
  panel.addEventListener("click", (event) => {
    if ((event.target as Element).closest("a")) setOpen(false);
  });
  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape" && isOpen()) setOpen(false, true);
  });
  document.addEventListener("pointerdown", (event) => {
    if (isOpen() && !nav.contains(event.target as Node)) setOpen(false);
  });

  // The eye. Positions are in the eye's own units (the SVG is 40 x 24; the iris can travel about 8 x 3.5).
  const balls = eyes.map((eye) => eye.querySelector<SVGGElement>(".eye-ball")).filter((b): b is SVGGElement => !!b);
  function look(x: number, y: number) {
    for (const ball of balls) {
      ball.style.setProperty("--ex", `${Math.max(-8, Math.min(8, x))}px`);
      ball.style.setProperty("--ey", `${Math.max(-3.5, Math.min(3.5, y))}px`);
    }
  }
  if (!eyeBox || !balls.length || prefersReduced()) return;

  const rand = (min: number, max: number) => min + Math.random() * (max - min);
  let pointer: { x: number; y: number; at: number } | null = null;
  window.addEventListener("pointermove", (event) => { pointer = { x: event.clientX, y: event.clientY, at: performance.now() }; }, { passive: true });

  function lookAt(px: number, py: number) {
    const box = eyeBox!.getBoundingClientRect();
    const dx = px - (box.left + box.width / 2);
    const dy = py - (box.top + box.height / 2);
    const dist = Math.hypot(dx, dy) || 1;
    const reach = Math.min(1, dist / 220);
    look((dx / dist) * 8 * reach, (dy / dist) * 3.5 * reach);
  }
  function wander() {
    if (document.hidden || isOpen()) return;
    // Mostly glance at random spots on the page, sometimes follow the cursor if it moved recently.
    if (pointer && performance.now() - pointer.at < 1800 && Math.random() < 0.6) lookAt(pointer.x, pointer.y);
    else lookAt(rand(0, window.innerWidth), rand(0, window.innerHeight));
  }
  function blink() {
    for (const eye of eyes) eye.classList.remove("is-blink");
    void eyeBox!.getBoundingClientRect();
    for (const eye of eyes) eye.classList.add("is-blink");
  }
  function loop(fn: () => void, min: number, max: number) {
    const tick = () => { fn(); window.setTimeout(tick, rand(min, max)); };
    window.setTimeout(tick, rand(min, max));
  }
  loop(wander, 700, 2200);
  loop(blink, 2600, 6000);

  // Now and then a "click me" bubble pops up under the tab.
  if (hint) {
    const showHint = () => {
      if (isOpen() || document.hidden) return;
      look(0, 3.5);
      hint.classList.add("is-on");
      window.setTimeout(() => hint.classList.remove("is-on"), 2600);
    };
    window.setTimeout(showHint, 3500);
    loop(showHint, 9000, 16000);
  }
}
