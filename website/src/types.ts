export interface SiteConfig {
  name: string;
  inviteUrl: string | null;
  supportUrl: string | null;
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
