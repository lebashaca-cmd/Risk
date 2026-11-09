import type { AccountStats, AllSettings, BotProfile, GuildPayload, MePayload, PlanKey, SectionId, StaffControl, StaffMe, StaffOverview, StaffOwnerPanel, StaffRole } from "./dash-types.js";
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
  privacy: () => getJSON<TosPayload>("/api/privacy"),
};

export class ApiFailure extends Error {
  constructor(
    message: string,
    readonly status: number,
  ) {
    super(message);
  }
}

async function send<T>(method: string, path: string, body?: unknown): Promise<T> {
  let res: Response;
  try {
    res = await fetch(path, {
      method,
      credentials: "same-origin",
      headers: { Accept: "application/json", "X-Requested-With": "risk", ...(body === undefined ? {} : { "Content-Type": "application/json" }) },
      body: body === undefined ? undefined : JSON.stringify(body),
    });
  } catch {
    throw new ApiFailure("Couldn't reach the site. Check your connection and try again.", 0);
  }
  let payload: unknown = null;
  try {
    payload = await res.json();
  } catch {
    payload = null;
  }
  if (!res.ok) {
    const message = payload && typeof payload === "object" && "error" in payload && typeof payload.error === "string" ? payload.error : `The request failed (${res.status}).`;
    throw new ApiFailure(message, res.status);
  }
  return payload as T;
}

export const dashApi = {
  me: () => send<MePayload>("GET", "/api/auth/me"),
  account: () => send<AccountStats>("GET", "/api/dash/account"),
  guild: (id: string) => send<GuildPayload>("GET", `/api/dash/guild/${encodeURIComponent(id)}`),
  save: <K extends SectionId>(id: string, section: K, body: AllSettings[K]) =>
    send<{ settings: AllSettings[K] }>("PUT", `/api/dash/guild/${encodeURIComponent(id)}/${section}`, body),
  saveProfile: (id: string, body: { nick?: string; bio?: string; avatar?: string | null; banner?: string | null }) =>
    send<{ profile: BotProfile }>("PUT", `/api/dash/guild/${encodeURIComponent(id)}/profile`, body),
  logout: () => send<{ ok: boolean }>("POST", "/api/auth/logout"),
};

export const staffApi = {
  me: () => send<StaffMe>("GET", "/api/staff/me"),
  overview: () => send<StaffOverview>("GET", "/api/staff/overview"),
  owner: () => send<StaffOwnerPanel>("GET", "/api/staff/owner"),
  control: () => send<StaffControl>("GET", "/api/staff/control"),
  setCommand: (name: string, off: boolean) => send<{ name: string; off: boolean }>("POST", "/api/staff/control-commands", { name, off }),
  block: (user_id: string, reason: string, remove = false) => send<{ id: string }>("POST", "/api/staff/control-blocked", { user_id, reason, remove }),
  maintenance: (on: boolean, message: string) => send<{ on: boolean; message: string }>("POST", "/api/staff/control-maintenance", { on, message }),
  savePrices: (prices: Partial<Record<PlanKey, { price: string; url: string }>>) => send<{ prices: StaffOwnerPanel["prices"] }>("PUT", "/api/staff/prices", prices),
  vip: (body: { guild_id: string; action: "grant" | "revoke"; days?: number; tier?: PlanKey; note?: string }) => send<{ id: string; vip: boolean; tier: string | null; until: number | null }>("POST", "/api/staff/vip", body),
  ban: (guild_id: string, reason: string) => send<{ id: string; left: boolean; banned: number }>("POST", "/api/staff/ban", { guild_id, reason }),
  unban: (guild_id: string) => send<{ id: string; banned: number }>("POST", "/api/staff/unban", { guild_id }),
  role: (user_id: string, role: StaffRole | "none") => send<{ id: string; role: StaffRole | null }>("POST", "/api/staff/roles", { user_id, role }),
};
