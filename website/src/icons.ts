const NS = "http://www.w3.org/2000/svg";

export type IconName = "ticket" | "logs" | "welcome" | "ai" | "lookup" | "shield" | "tiktok" | "youtube" | "github" | "spotify" | "terminal" | "coin" | "gamepad" | "wrench" | "info" | "link" | "arrow";

const PATHS: Record<IconName, string[]> = {
  ticket: ["M4 6h16v3.5a2.5 2.5 0 0 0 0 5V18H4v-3.5a2.5 2.5 0 0 0 0-5z", "M9.5 9v6"],
  logs: ["M5 6h14", "M5 12h14", "M5 18h9"],
  welcome: ["M4 5h16v11h-9l-4.5 3.5V16H4z", "M8.5 10.5h.01", "M12 10.5h.01", "M15.5 10.5h.01"],
  ai: ["M11 3l1.8 5.2L18 10l-5.2 1.8L11 17l-1.8-5.2L4 10l5.2-1.8z", "M18 15l.8 2.2L21 18l-2.2.8L18 21l-.8-2.2L15 18l2.2-.8z"],
  lookup: ["M11 4a7 7 0 1 0 0 14 7 7 0 0 0 0-14z", "M16.2 16.2L21 21"],
  tiktok: ["M14 4v10.5a3.5 3.5 0 1 1-3.5-3.5", "M14 4c.4 2.4 2 4 4.5 4.2"],
  youtube: ["M3.5 8a2.5 2.5 0 0 1 2.5-2.5h12A2.5 2.5 0 0 1 20.5 8v8a2.5 2.5 0 0 1-2.5 2.5H6A2.5 2.5 0 0 1 3.5 16z", "M10.2 9.4v5.2l4.4-2.6z"],
  github: ["M9 19c-4 1.2-4-2-6-2.5", "M15 21v-3.2a2.8 2.8 0 0 0-.8-2.2c2.700-.3 5.500-1.300 5.500-6a4.600 4.600 0 0 0-1.300-3.200 4.300 4.300 0 0 0-.1-3.200s-1-.3-3.400 1.300a11.700 11.700 0 0 0-6 0C6.500 2.900 5.500 3.200 5.500 3.200a4.300 4.300 0 0 0-.1 3.200A4.600 4.600 0 0 0 4 9.600c0 4.600 2.800 5.600 5.500 6a2.800 2.800 0 0 0-.8 2.200V21"],
  spotify: ["M5 9.500c4.500-1.200 9-.9 13.500 1.500", "M6 13c3.700-.9 7-.6 10.500 1.300", "M7 16.300c3-.6 5.500-.4 8.200 1"],
  terminal: ["M4 5h16v14H4z", "M8 10l3 2-3 2", "M13 15h3"],
  coin: ["M12 3a9 9 0 1 0 0 18 9 9 0 0 0 0-18z", "M14.5 9.5c-.5-.8-1.400-1.200-2.500-1.200-1.400 0-2.400.7-2.400 1.800 0 2.500 5 1.200 5 3.700 0 1.100-1.100 1.900-2.600 1.900-1.200 0-2.200-.5-2.700-1.400", "M12 6.500v1.800", "M12 15.700v1.800"],
  gamepad: ["M7 8h10a4 4 0 0 1 4 4v1.500a2.500 2.500 0 0 1-4.300 1.700L15.500 14h-7l-1.200 1.200A2.500 2.500 0 0 1 3 13.500V12a4 4 0 0 1 4-4z", "M8 10.500v2", "M7 11.500h2", "M15.500 11h.01", "M17.500 12.500h.01"],
  wrench: ["M14.500 6.500a4 4 0 0 0-5 5L4 17l3 3 5.500-5.500a4 4 0 0 0 5-5l-2.500 2.500-2-2z"],
  info: ["M12 3a9 9 0 1 0 0 18 9 9 0 0 0 0-18z", "M12 11v5", "M12 7.800h.01"],
  arrow: ["M5 12h14", "M13 6l6 6-6 6"],
  link: ["M10 14a4 4 0 0 0 5.700 0l3-3a4 4 0 0 0-5.700-5.700l-1 1", "M14 10a4 4 0 0 0-5.700 0l-3 3a4 4 0 0 0 5.700 5.700l1-1"],
  shield: ["M12 3l7 3v5c0 5-3 8-7 10-4-2-7-5-7-10V6z", "M9 12l2 2 4-4"],
};

export function icon(name: IconName): SVGSVGElement {
  const svg = document.createElementNS(NS, "svg");
  svg.setAttribute("viewBox", "0 0 24 24");
  svg.setAttribute("class", "icon");
  svg.setAttribute("aria-hidden", "true");
  svg.setAttribute("focusable", "false");
  for (const d of PATHS[name]) {
    const path = document.createElementNS(NS, "path");
    path.setAttribute("d", d);
    path.setAttribute("pathLength", "1");
    svg.appendChild(path);
  }
  return svg;
}
