export interface SiteConfig {
  name: string;
  inviteUrl: string | null;
  supportUrl: string | null;
  dashboardUrl?: string;
  dashboardHost?: boolean;
  staffUrl?: string;
  docsUrl?: string;
  vip?: Record<"basic" | "lifetime" | "white" | "supreme", VipPlan>;
}

export interface VipPlan {
  price: string;
  url: string | null;
}

export interface ServerInfo {
  name: string;
  icon: string | null;
  members: number | null;
}

export interface BotStatus {
  state: "online" | "offline" | "unknown";
  latencyMs: number | null;
  guilds: number | null;
  servers: ServerInfo[];
  checkedAt: number;
}

export type Level = "info" | "good" | "warn" | "bad";

export interface PageButton {
  label: string;
  url: string;
  style: "primary" | "quiet";
}

export interface PageIncident {
  id: string;
  title: string;
  text: string;
  level: Level;
  at: number | null;
  resolved_at: number | null;
}

export interface StatusPageData {
  status: BotStatus;
  page: {
    buttons: PageButton[] | null;
    notice: { on: boolean; level: Level; text: string };
    incidents: PageIncident[];
    usage: { today: number; week: number; total: number; errorsToday: number; top: { name: string; count: number }[] } | null;
    uptime: { days: { date: string; percent: number | null }[]; percent: number | null } | null;
    sinceSeconds: number | null;
  };
}

export interface CommandInfo {
  name: string;
  kind: "prefix" | "slash";
  category: string;
  description: string;
  examples: string[];
  permission: string | null;
}

export interface CommandsPayload {
  prefixes: string[];
  commands: CommandInfo[];
}

export interface TosPayload {
  sections: { title: string; text: string }[];
  updated: string | null;
}
