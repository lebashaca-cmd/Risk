// Cookie and privacy choices. Standalone on purpose: the main site and the docs both load this one file.
// Risk's pages use no analytics, ads or marketing scripts. The only optional extra is the Google Fonts stylesheet,
// which makes the visitor's browser contact Google, so it is held back until the visitor says yes.
// The choice is saved in this browser's localStorage under "risk-consent" (not a cookie).

const KEY = "risk-consent";
const FONTS =
  "https://fonts.googleapis.com/css2?family=Poppins:ital,wght@0,300;0,400;0,500;0,600;1,300&family=JetBrains+Mono:wght@400;500&display=swap";

type Choice = "granted" | "denied";

function read(): Choice | null {
  try {
    const raw = window.localStorage.getItem(KEY);
    if (!raw) return null;
    const value = (JSON.parse(raw) as { choice?: string }).choice;
    return value === "granted" || value === "denied" ? value : null;
  } catch {
    return null;
  }
}

function write(choice: Choice): void {
  try {
    window.localStorage.setItem(KEY, JSON.stringify({ choice, at: new Date().toISOString() }));
  } catch {
    // Private windows can refuse storage. The choice still applies until the page closes.
  }
}

function clear(): void {
  try {
    window.localStorage.removeItem(KEY);
  } catch {
    // Nothing to clear.
  }
}

function loadFonts(): void {
  if (document.querySelector("link[data-consent-fonts]")) return;
  const link = document.createElement("link");
  link.rel = "stylesheet";
  link.href = FONTS;
  link.setAttribute("data-consent-fonts", "");
  document.head.append(link);
}

function unloadFonts(): void {
  document.querySelectorAll("link[data-consent-fonts]").forEach((node) => node.remove());
}

let banner: HTMLElement | null = null;

function closeBanner(): void {
  banner?.remove();
  banner = null;
}

function choose(choice: Choice, opener: HTMLElement | null): void {
  write(choice);
  if (choice === "granted") loadFonts();
  else unloadFonts();
  closeBanner();
  opener?.focus();
}

function openBanner(opener: HTMLElement | null): void {
  if (banner) {
    banner.querySelector<HTMLElement>("button")?.focus();
    return;
  }
  const box = document.createElement("section");
  box.className = "consent";
  box.setAttribute("role", "region");
  box.setAttribute("aria-labelledby", "consent-title");
  box.setAttribute("aria-describedby", "consent-text");

  const title = document.createElement("h2");
  title.id = "consent-title";
  title.textContent = "Cookies and fonts";

  const text = document.createElement("p");
  text.id = "consent-text";
  text.append(
    "Risk sets no tracking or advertising cookies and runs no analytics. Signing in to the dashboard uses one essential session cookie. ",
    "The optional Poppins and JetBrains Mono fonts come from Google, which then sees your IP address. Without them you get your device's own fonts. ",
  );
  const more = document.createElement("a");
  const docsHost = /^docs\./i.test(window.location.hostname);
  more.href = (docsHost ? `${window.location.protocol}//${window.location.host.replace(/^docs\./i, "")}` : "") + "/privacy#cookies-and-tracking-technologies";
  more.textContent = "Read the cookie policy";
  text.append(more, ".");

  const actions = document.createElement("div");
  actions.className = "consent-actions";
  const decline = document.createElement("button");
  decline.type = "button";
  decline.className = "btn btn-quiet btn-small";
  decline.textContent = "Essential only";
  decline.addEventListener("click", () => choose("denied", opener));
  const accept = document.createElement("button");
  accept.type = "button";
  accept.className = "btn btn-primary btn-small";
  accept.textContent = "Allow Google Fonts";
  accept.addEventListener("click", () => choose("granted", opener));
  actions.append(decline, accept);

  box.append(title, text, actions);
  box.addEventListener("keydown", (event) => {
    if (event.key === "Escape") choose("denied", opener);
  });
  document.body.append(box);
  banner = box;
  if (opener) accept.focus();
}

function start(): void {
  const saved = read();
  if (saved === "granted") loadFonts();
  if (saved === null) openBanner(null);
  document.querySelectorAll<HTMLElement>("[data-consent-open]").forEach((button) => {
    button.addEventListener("click", () => {
      clear();
      unloadFonts();
      openBanner(button);
    });
  });
}

if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", start);
else start();
