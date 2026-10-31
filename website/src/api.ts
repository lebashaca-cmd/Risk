import type { BotStatus, CommandsPayload, SiteConfig, TosPayload } from "./types.js";

async function getJSON<T>(path: string): Promise<T> {
  const res = await fetch(path, { headers: { Accept: "application/json" } });
  if (!res.ok) throw new Error(`${path} answered ${res.status}`);
  return (await res.json()) as T;
}

export const api = {
  config: () => getJSON<SiteConfig>("/api/config"),
  status: () => getJSON<BotStatus>("/api/status"),
  commands: () => getJSON<CommandsPayload>("/api/commands"),
  tos: () => getJSON<TosPayload>("/api/tos"),
};
