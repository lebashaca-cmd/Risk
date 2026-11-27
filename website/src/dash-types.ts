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

export interface TemplateVariable {
  token: string;
  group: string;
  description: string;
  example: string;
}

export interface Meta {
  channels: ChannelOption[];
  roles: RoleOption[];
  commands: { name: string; category: string }[];
  variables: TemplateVariable[];
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
  card: boolean;
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
  blockedRoles: string[];
  blockedChannels: string[];
  staffOnly: boolean;
  cooldown: number;
}

export interface CommandBasics {
  blockedChannels: string[];
  onlyChannels: string[];
  blockedRoles: string[];
  deleteInvocations: boolean;
  cooldown: number;
}

export interface CommandsSettings {
  rules: CommandRule[];
  basics: CommandBasics;
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

export type StepValue = string | number | boolean;
export type Step = { type: string } & Record<string, StepValue>;

export interface ActionField {
  key: string;
  label: string;
  kind: "text" | "name" | "number" | "bool" | "select" | "role" | "channel";
  hint?: string;
  options?: Record<string, string>;
  min?: number;
  max?: number;
  default?: StepValue;
  kinds?: string[];
}

export interface ActionType {
  type: string;
  label: string;
  group: string;
  danger: boolean;
  fields: ActionField[];
}

export interface CustomCommand {
  name: string;
  steps: Step[];
  who: "everyone" | "mods" | "roles";
  roles: string[];
  channels: string[];
  cooldown: number;
  uses: number;
}

export interface CustomCommandsSettings {
  items: CustomCommand[];
  unlocked: boolean;
  limit: number;
  actionTypes: ActionType[];
  allChannels: { id: string; name: string; type: string }[];
  saved: { name: string; value: string }[];
}

export interface Announcement {
  id?: number;
  channel: string | null;
  everyMinutes: number;
  text: string;
  on: boolean;
}

export interface MusicSettings {
  volume: number;
  bass: number;
  announce: boolean;
  dj: string | null;
  eq: number[];
  speed: number;
  pitch: number;
  rotation: boolean;
  karaoke: boolean;
  bands: string[];
  presets: Record<string, number[]>;
  ready: boolean;
  problem: string | null;
}

export interface AnnouncementsSettings {
  items: Announcement[];
  locked?: boolean;
}

export interface VipSettings {
  active: boolean;
  tier: string | null;
  commands: { plan: "basic" | "lifetime" | "white" | "supreme"; unlocked: boolean; names: string[] }[];
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
  customcmds: CustomCommandsSettings;
  announcements: AnnouncementsSettings;
  music: MusicSettings;
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

// Staff panel
export type StaffRole = "staff" | "developer" | "owner";
export type PlanKey = "basic" | "lifetime" | "white" | "supreme";

export interface StaffMe {
  role: StaffRole | null;
  owner: boolean;
  staffServer: boolean;
}

export interface StaffTotals {
  servers: number;
  members: number;
  vip: number;
  banned: number;
  planCounts: Record<PlanKey, number>;
  newServers: number;
  biggest: number;
  uptime: number;
  latencyMs: number | null;
  commands: number;
}

export interface StaffControl {
  commands: { name: string; category: string; description: string; off: boolean }[];
  blocked: { id: string; reason: string; at: number | null }[];
  maintenance: { on: boolean; message: string };
  statusPage: StaffStatusPage | null;
}

export interface StaffStatusPage {
  buttons: { label: string; url: string; style: "primary" | "quiet" }[];
  customButtons: boolean;
  defaults: { label: string; url: string; style: "primary" | "quiet" }[];
  notice: { on: boolean; level: "info" | "good" | "warn" | "bad"; text: string };
  incidents: { id: string; title: string; text: string; level: "info" | "good" | "warn" | "bad"; at: number; resolved_at: number | null }[];
}

export interface StaffOverview extends StaffTotals {
  role: StaffRole;
  owner: boolean;
}

export interface StaffServer {
  id: string;
  name: string;
  members: number;
  vip: boolean;
  tier: string | null;
  until: number | null;
  source: "env" | "granted" | null;
}

export interface StaffOwnerPanel extends StaffTotals {
  role: StaffRole;
  canAssignOwner: boolean;
  serverList: StaffServer[];
  bannedList: { id: string; name?: string | null; reason?: string; by?: string; at?: number }[];
  prices: Partial<Record<PlanKey, { price: string | null; url: string | null }>>;
  plans: PlanKey[];
  roles: { id: string; role: StaffRole; name: string | null }[];
  log: { at: number; by: string; action: string; detail: string }[];
}
