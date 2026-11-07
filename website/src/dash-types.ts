export interface DashUser {
  id: string;
  name: string;
  avatar: string | null;
  banner?: string | null;
  accent?: string | null;
  username?: string | null;
  tag?: { text: string; badge: string | null } | null;
  badges?: string[];
  nitro?: string | null;
  created?: number | null;
}

export interface AccountStats {
  level: number;
  xp: number;
  progress: number;
  needed: number;
  messages: number;
  rank: number | null;
  bestLevel: number;
  bestServer: string | null;
  money: number;
  servers: number;
  managed: number;
  vip: number;
  streams: number;
  streamSeconds: number;
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
  vip: boolean;
  limits: Record<string, number>;
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

export interface CommandRule {
  command: string;
  roles: string[];
  channels: string[];
  cooldown: number;
}

export interface CommandsSettings {
  rules: CommandRule[];
}

export interface Responder {
  trigger: string;
  reply: string;
  match: "contains" | "exact" | "starts";
  embed: boolean;
}

export interface RespondersSettings {
  items: Responder[];
}

export interface Announcement {
  id?: number;
  channel: string | null;
  everyMinutes: number;
  text: string;
  on: boolean;
}

export interface AnnouncementsSettings {
  items: Announcement[];
  locked?: boolean;
}

export interface VipSettings {
  active: boolean;
  source: "env" | "granted" | null;
  until: number | null;
  color: string | null;
  perks: string[];
  free: Record<string, number>;
  vipLimits: Record<string, number>;
  url: string | null;
}

export interface OverviewSettings {
  stats: {
    members: number | null;
    people: number;
    bots: number;
    textChannels: number;
    voiceChannels: number;
    roles: number;
    emojis: number;
    boostTier: number;
    boosts: number;
    created: number;
    owner: string | null;
  };
  checklist: { id: string; label: string; section: SectionId; done: boolean }[];
  usage: { disabledCommands: number; commandRules: number; responders: number; announcements: number; logCategories: number | null };
  activity: { user: string; section: string; at: number }[];
  vip: boolean;
}

export interface AllSettings {
  overview: OverviewSettings;
  commands: CommandsSettings;
  responders: RespondersSettings;
  announcements: AnnouncementsSettings;
  vip: VipSettings;
  general: GeneralSettings;
  welcome: WelcomeSettings;
  logs: LogsSettings;
  levels: LevelsSettings;
  automod: AutomodSettings;
  community: CommunitySettings;
}

export type SectionId = keyof AllSettings;

export interface BotProfile {
  nick: string;
  bio: string;
  avatar: string | null;
  banner: string | null;
  botName: string;
  defaultAvatar: string | null;
}

export interface GuildPayload {
  profile?: BotProfile;
  guild: { id: string; name: string; icon: string | null; members: number | null };
  meta: Meta;
  settings: AllSettings;
  unavailable?: Partial<Record<SectionId, string>>;
}
