import { api } from "./api.js";
import { prefersReduced } from "./anim.js";
import type { BotStatus } from "./types.js";

const POLL_MS = 30_000;
let latest: BotStatus | null = null;
const listeners = new Set<(status: BotStatus | null) => void>();

export function currentStatus(): BotStatus | null {
  return latest;
}

export function onStatus(listener: (status: BotStatus | null) => void): () => void {
  listeners.add(listener);
  return () => listeners.delete(listener);
}
let timer: number | undefined;
const extra: Record<string, number | null> = {};
const lastShown = new Map<string, number>();

function describe(status: BotStatus | null): { state: string; label: string } {
  if (!status) return { state: "checking", label: "Checking status" };
  if (status.state === "online") return { state: "online", label: "Risk is online" };
  if (status.state === "offline") return { state: "offline", label: "Risk is offline" };
  return { state: "unknown", label: "Status unavailable" };
}

function countTo(el: HTMLElement, key: string, to: number): void {
  const from = lastShown.get(key);
  lastShown.set(key, to);
  if (prefersReduced() || from === to) {
    el.textContent = to.toLocaleString();
    return;
  }
  const start = from ?? 0;
  const t0 = performance.now();
  const duration = 900;
  el.textContent = start.toLocaleString();
  const step = (now: number) => {
    const p = Math.min(1, (now - t0) / duration);
    const eased = 1 - Math.pow(1 - p, 3);
    el.textContent = Math.round(start + (to - start) * eased).toLocaleString();
    if (p < 1 && el.isConnected) requestAnimationFrame(step);
    else el.textContent = to.toLocaleString();
  };
  requestAnimationFrame(step);
}

export function applyStatus(root: ParentNode = document): void {
  const { state, label } = describe(latest);
  root.querySelectorAll<HTMLElement>("[data-status-dot], [data-status-state]").forEach((el) => (el.dataset.state = state));
  root.querySelectorAll<HTMLElement>("[data-status-label]").forEach((el) => (el.textContent = label));

  const online = latest?.state === "online";
  const values: Record<string, number | null | undefined> = {
    latency: online ? latest?.latencyMs : null,
    guilds: online ? latest?.guilds : null,
    commands: extra["commands"],
  };
  root.querySelectorAll<HTMLElement>("[data-stat]").forEach((el) => {
    const key = el.dataset.stat ?? "";
    const value = values[key];
    if (value === null || value === undefined) {
      el.textContent = "–";
      el.dataset.empty = "true";
      lastShown.delete(key);
      return;
    }
    delete el.dataset.empty;
    countTo(el, key, value);
  });
}

export function setExtraStat(key: string, value: number | null): void {
  extra[key] = value;
  applyStatus();
}

async function refresh(): Promise<void> {
  try {
    latest = await api.status();
  } catch {
    latest = { state: "unknown", latencyMs: null, guilds: null, servers: [], checkedAt: Date.now() / 1000 };
  }
  applyStatus();
  listeners.forEach((listener) => listener(latest));
}

export function startStatusPolling(): void {
  void refresh();
  window.clearInterval(timer);
  timer = window.setInterval(() => {
    if (document.visibilityState === "visible") void refresh();
  }, POLL_MS);
  document.addEventListener("visibilitychange", () => {
    if (document.visibilityState === "visible") void refresh();
  });
}
