// A soft white glow that trails the pointer. The position goes into --gx / --gy and CSS draws it.
export function startGlow(): void {
  const root = document.documentElement;
  if (matchMedia("(prefers-reduced-motion: reduce)").matches) return;
  const target = { x: innerWidth * 0.6, y: innerHeight * 0.3 };
  const now = { ...target };
  let running = false;
  const frame = (): void => {
    now.x += (target.x - now.x) * 0.08;
    now.y += (target.y - now.y) * 0.08;
    root.style.setProperty("--gx", `${now.x.toFixed(1)}px`);
    root.style.setProperty("--gy", `${now.y.toFixed(1)}px`);
    if (Math.abs(target.x - now.x) + Math.abs(target.y - now.y) > 0.5) requestAnimationFrame(frame);
    else running = false;
  };
  const move = (event: PointerEvent): void => {
    target.x = event.clientX;
    target.y = event.clientY;
    if (!running) {
      running = true;
      requestAnimationFrame(frame);
    }
  };
  addEventListener("pointermove", move, { passive: true });
  running = true;
  requestAnimationFrame(frame);
}
