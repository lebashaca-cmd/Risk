export interface DashUser {
  id: string;
  name: string;
  avatar: string | null;
}

export interface DashGuildCard {
  id: string;
  name: string;
  icon: string | null;
  botPresent: boolean | null;
  invite: string | null;
}

export interface MePayload {
  enabled: boolean;
  user: DashUser | null;
  guilds: DashGuildCard[];
  botReachable?: boolean;
}

export interface ChannelOption {
  id: string;
  name: string;
  category: string | null;
  canSend: boolean;
}

export interface RoleOption {
  id: string;
  name: string;
  color: string | null;
  assignable: boolean;
}

export interface Meta {
  channels: ChannelOption[];
  roles: RoleOption[];
  commands: { name: string; category: string }[];
  logCategories: { id: string; label: string }[];
  defaultPrefixes: string[];
}

export interface GeneralSettings {
  prefix: string | null;
  disabledCommands: string[];
  ignoredChannels: string[];
}

export interface WelcomeSettings {
  enabled: boolean;
  channel: string | null;
  text: string;
  leaveEnabled: boolean;
  leaveChannel: string | null;
  leaveText: string;
}

export interface LogsSettings {
  channel: string | null;
  disabled: string[];
  routes: Record<string, string>;
  ignoredChannels: string[];
}

export interface LevelsSettings {
  announce: string;
  message: string;
  multiplier: number;
  cooldown: number;
  mode: "stack" | "replace";
  noxpChannels: string[];
  noxpRoles: string[];
  rewards: { level: number; role: string | null }[];
}

export interface AutomodSettings {
  antilink: boolean;
  antiinvite: boolean;
  antispam: boolean;
  maxMentions: number;
  badWords: string[];
  ignoreChannels: string[];
  ignoreRoles: string[];
}

export interface CommunitySettings {
  autorole: string | null;
  suggestionChannel: string | null;
  starboardChannel: string | null;
  starboardThreshold: number;
  birthdayChannel: string | null;
  reportChannel: string | null;
  countingChannel: string | null;
  ticketLogChannel: string | null;
  rules: string;
}

export interface AllSettings {
  general: GeneralSettings;
  welcome: WelcomeSettings;
  logs: LogsSettings;
  levels: LevelsSettings;
  automod: AutomodSettings;
  community: CommunitySettings;
}

export type SectionId = keyof AllSettings;

export interface GuildPayload {
  guild: { id: string; name: string; icon: string | null; members: number | null };
  meta: Meta;
  settings: AllSettings;
  unavailable?: Partial<Record<SectionId, string>>;
}
