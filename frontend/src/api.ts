export type ChecklistItem = {
  id: string;
  label: string;
  done: boolean;
};

export type OnboardingChecklist = {
  tenant_id: number;
  status: string;
  template_id?: string | null;
  items: ChecklistItem[];
  done_count: number;
  total_count: number;
  complete: boolean;
};

export type OnboardingTemplate = {
  id: string;
  name: string;
  description?: string;
  blurb?: string;
  vertical: string;
  flow_mode: "lead" | "order" | string;
  icon?: string;
  languages?: string[];
};

export type Tenant = {
  id: number;
  phone_number_id: string;
  name: string;
  flow_mode: string;
  status?: string;
  logo_url?: string;
  business_wa_id?: string;
  owner_whatsapp?: string;
  leads_today?: number;
  orders_today?: number;
  stat_today?: number;
  checklist?: OnboardingChecklist;
  template_id?: string | null;
};

/** Normalize status; missing → live. */
export function tenantStatus(t: { status?: string | null }): string {
  return (t.status || "live").toLowerCase();
}

/**
 * Tenants shown in Settings / Team / command palette pickers.
 * Paused + archived are lifecycle-only (Businesses filters).
 */
export function isPickerTenant(t: { status?: string | null }): boolean {
  const s = tenantStatus(t);
  return s === "live" || s === "draft";
}

export function filterPickerTenants<T extends { status?: string | null }>(tenants: T[]): T[] {
  return tenants.filter(isPickerTenant);
}

export type TenantStatusCounts = {
  all: number;
  live: number;
  paused: number;
  archived: number;
  draft: number;
};

export type TenantsListResponse = {
  items: Tenant[];
  counts: TenantStatusCounts;
};

/** Normalize tenants list (supports new {items,counts} and legacy array). */
export async function fetchTenants(status?: string): Promise<TenantsListResponse> {
  const q = status && status !== "all" ? `?status=${encodeURIComponent(status)}` : "";
  const raw = await api<Tenant[] | TenantsListResponse>(`/api/dashboard/tenants${q}`, {
    tenant: false,
  });
  if (Array.isArray(raw)) {
    const counts: TenantStatusCounts = {
      all: raw.length,
      live: 0,
      paused: 0,
      archived: 0,
      draft: 0,
    };
    for (const t of raw) {
      const st = (t.status || "live").toLowerCase() as keyof TenantStatusCounts;
      if (st in counts && st !== "all") counts[st] += 1;
    }
    return { items: raw, counts };
  }
  return {
    items: raw.items || [],
    counts: raw.counts || { all: 0, live: 0, paused: 0, archived: 0, draft: 0 },
  };
}

export type FlowStepOption = {
  id: string;
  title: string;
  description?: string;
  value?: string;
  sheet_value?: string;
};

export type FlowStep = {
  id: string;
  key: string;
  type: "text_question" | "button_options" | "list_options" | "free_text_capture" | string;
  question_text?: string;
  question_key?: string | null;
  options_key?: string | null;
  options?: FlowStepOption[];
  capture_field?: string | null;
  required?: boolean;
  skip_if_declined?: boolean;
  reserved?: boolean;
  system?: boolean;
};

export type TenantConfig = {
  greeting_text: string;
  greeting_language: string;
  campaign_phrase: string;
  demo_slots: string[];
  facts_features: string;
  facts_pricing_note: string;
  facts_claims_note: string;
  faq: { question: string; answer: string }[];
  menu?: {
    shop_name: string;
    delivery_fee?: number | null;
    delivery_area?: string;
    categories: { name: string; items: { name: string; price: number; available?: boolean }[] }[];
  } | null;
  menu_v2?: MenuV2 | null;
  menu_v2_draft?: MenuV2 | null;
  messages?: Record<string, unknown> | null;
  messages_draft?: Record<string, unknown> | null;
  business_wa_id: string;
  owner_whatsapp: string;
  greeting_image_url?: string;
  greeting_variants?: string[];
  greeting_blocks?: { text: string; image_url?: string }[];
  business_hours?: {
    enabled?: boolean;
    timezone?: string;
    away_message?: string;
    days?: Record<string, string[][]>;
  };
  flow?: FlowStep[];
};

export type MenuV2Option = { id: string; label: string; price_delta: number };
export type MenuV2Modifier = { id: string; name: string; options: MenuV2Option[] };
export type MenuV2Item = {
  id: string;
  category_id: string;
  name: string;
  description: string;
  price: number;
  available: boolean;
  sort: number;
  modifiers: MenuV2Modifier[];
};
export type MenuV2Category = {
  id: string;
  name: string;
  sort: number;
  visible: boolean;
};
export type MenuV2 = {
  categories: MenuV2Category[];
  items: MenuV2Item[];
  settings: {
    greeting_text: string;
    menu_button_label: string;
    delivery: {
      enabled: boolean;
      charge: number;
      free_above: number;
      area_note: string;
    };
    order_confirm_note: string;
    currency: string;
  };
};

export type TenantConfigResponse = {
  id: number;
  phone_number_id: string;
  name: string;
  flow_mode: string;
  status?: string;
  updated_at: string | null;
  wiring?: {
    phone_number_id: string;
    waba_id: string;
    flow_mode: string;
    managed_by: string;
    read_only: boolean;
  };
  config: TenantConfig;
};

const ROLE_KEY = "dash_role";
const USER_TENANT_KEY = "dash_user_tenant_id";
const READONLY_KEY = "dash_readonly";
const IMPERSONATOR_KEY = "dash_impersonated_by";
const VIEW_AS_TENANT_NAME_KEY = "dash_view_as_tenant_name";
const ADMIN_TOKEN_BACKUP = "dash_admin_token_backup";
const UI_LANG_KEY = "dash_ui_lang";

export function getRole(): string | null {
  return localStorage.getItem(ROLE_KEY);
}

export function getUserTenantId(): number | null {
  const v = localStorage.getItem(USER_TENANT_KEY);
  return v ? Number(v) : null;
}

export function isOwner(): boolean {
  return getRole() === "owner";
}

export function isAdmin(): boolean {
  return getRole() === "admin";
}

export function isReadonlySession(): boolean {
  return localStorage.getItem(READONLY_KEY) === "1";
}

/** Admin viewing a tenant workspace (support mode). */
export function isSupportSession(): boolean {
  return Boolean(getImpersonatedBy());
}

export function getImpersonatedBy(): string | null {
  return localStorage.getItem(IMPERSONATOR_KEY);
}

export function getViewAsTenantName(): string | null {
  return localStorage.getItem(VIEW_AS_TENANT_NAME_KEY);
}

export function getUiLang(): "en" | "ur" {
  return localStorage.getItem(UI_LANG_KEY) === "ur" ? "ur" : "en";
}

export function setUiLang(lang: "en" | "ur") {
  localStorage.setItem(UI_LANG_KEY, lang);
  window.dispatchEvent(new Event("ui-lang-change"));
}

export type MeResponse = {
  username: string;
  role: string;
  tenant_id: number | null;
  readonly: boolean;
  impersonated_by: string | null;
  tenant: Tenant | null;
};

export type BillingInfo = {
  plan_name: string;
  status: string;
  period: string;
  tenant_id: number | null;
  tenant_name: string | null;
  usage: {
    messages_sent: number;
    templates_sent: number;
    note: string;
  };
  placeholder: boolean;
};

export type Overview = {
  leads_today: number;
  leads_this_week: number;
  leads_by_status: Record<string, number>;
  demos_scheduled: number;
  orders_today: number;
  orders_this_week?: number;
  revenue_today: number;
  active_conversations: number;
  recent_events: EventItem[];
};

export type ContactBrief = {
  id: number | null;
  wa_id: string;
  profile_name: string;
  channel?: string;
};

export type Lead = {
  id: number;
  tenant_id: number;
  contact_id: number;
  session_id: number;
  business_name: string;
  business_type: string;
  locations: string;
  current_system: string;
  demo_slot: string;
  entry_intent: string;
  ad_source: string;
  status: string;
  notes?: string;
  tags?: string[];
  created_at: string | null;
  updated_at: string | null;
  last_activity: string | null;
  last_message_preview?: string;
  last_message_role?: string;
  human_takeover?: boolean;
  muted_until?: string | null;
  contact: ContactBrief;
  history?: { role: string; content: string; sender?: string }[];
  phase?: string | null;
  session_status?: string | null;
};

export type Conversation = {
  contact: ContactBrief & { tenant_id: number; first_seen?: string | null; last_seen?: string | null };
  muted_until: string | null;
  window_open: boolean;
  last_inbound_at: string | null;
  history: { role: string; content: string; sender?: string }[];
  timeline?: { role: string; content: string; sender?: string }[];
  phase?: string | null;
};

export type Order = {
  id: number;
  tenant_id: number;
  contact_id: number;
  items: { name?: string; qty?: number; price?: number }[];
  total: number;
  delivery_address: string;
  status: string;
  created_at: string | null;
  contact: ContactBrief;
};

export type EventItem = {
  id: number;
  tenant_id: number;
  contact_id: number | null;
  type: string;
  payload: Record<string, unknown>;
  created_at: string | null;
  contact?: ContactBrief | null;
};

const TOKEN_KEY = "dash_token";
const TENANT_KEY = "dash_tenant";

export function getToken(): string | null {
  return localStorage.getItem(TOKEN_KEY);
}

export function setToken(token: string | null) {
  if (token) localStorage.setItem(TOKEN_KEY, token);
  else localStorage.removeItem(TOKEN_KEY);
}

export function clearSession() {
  localStorage.removeItem(TOKEN_KEY);
  localStorage.removeItem(ROLE_KEY);
  localStorage.removeItem(USER_TENANT_KEY);
  localStorage.removeItem(READONLY_KEY);
  localStorage.removeItem(IMPERSONATOR_KEY);
  localStorage.removeItem(VIEW_AS_TENANT_NAME_KEY);
  localStorage.removeItem(TENANT_KEY);
  clearMeCache();
}

/** Short-lived /me cache — Layout + every page were hitting this repeatedly. */
let _meCache: { at: number; data: MeResponse } | null = null;
const ME_TTL_MS = 30_000;

export function clearMeCache() {
  _meCache = null;
}

export async function fetchMe(opts?: { force?: boolean }): Promise<MeResponse> {
  const now = Date.now();
  if (!opts?.force && _meCache && now - _meCache.at < ME_TTL_MS) {
    return _meCache.data;
  }
  const data = await api<MeResponse>("/api/dashboard/me", { tenant: false });
  _meCache = { at: now, data };
  return data;
}

function applySession(data: {
  access_token: string;
  role?: string;
  tenant_id?: number | null;
  readonly?: boolean;
  impersonated_by?: string | null;
  tenant_name?: string | null;
}) {
  setToken(data.access_token);
  if (data.role) localStorage.setItem(ROLE_KEY, data.role);
  if (data.tenant_id != null) localStorage.setItem(USER_TENANT_KEY, String(data.tenant_id));
  else localStorage.removeItem(USER_TENANT_KEY);
  if (data.readonly) localStorage.setItem(READONLY_KEY, "1");
  else localStorage.removeItem(READONLY_KEY);
  if (data.impersonated_by) localStorage.setItem(IMPERSONATOR_KEY, data.impersonated_by);
  else localStorage.removeItem(IMPERSONATOR_KEY);
  if (data.impersonated_by && data.tenant_name) {
    localStorage.setItem(VIEW_AS_TENANT_NAME_KEY, data.tenant_name);
  } else if (!data.impersonated_by) {
    localStorage.removeItem(VIEW_AS_TENANT_NAME_KEY);
  }
}

export async function login(username: string, password: string) {
  const data = await api<{
    access_token: string;
    role?: string;
    tenant_id?: number | null;
    readonly?: boolean;
    impersonated_by?: string | null;
  }>("/api/auth/login", {
    method: "POST",
    body: JSON.stringify({ username, password }),
    tenant: false,
  });
  applySession(data);
  clearMeCache();
  return data;
}

export async function enterViewAs(tenantDbId: number) {
  const current = getToken();
  if (current && getRole() === "admin") {
    localStorage.setItem(ADMIN_TOKEN_BACKUP, current);
  }
  const data = await api<{
    access_token: string;
    role: string;
    tenant_id: number;
    readonly: boolean;
    impersonated_by: string;
    tenant_name?: string;
    support_mode?: boolean;
  }>(`/api/dashboard/admin/view-as/${tenantDbId}`, {
    method: "POST",
    tenant: false,
  });
  applySession(data);
  clearMeCache();
  return data;
}

export function exitViewAs(): boolean {
  const backup = localStorage.getItem(ADMIN_TOKEN_BACKUP);
  if (!backup) return false;
  localStorage.removeItem(ADMIN_TOKEN_BACKUP);
  localStorage.removeItem(READONLY_KEY);
  localStorage.removeItem(IMPERSONATOR_KEY);
  localStorage.removeItem(VIEW_AS_TENANT_NAME_KEY);
  setToken(backup);
  localStorage.setItem(ROLE_KEY, "admin");
  localStorage.removeItem(USER_TENANT_KEY);
  clearMeCache();
  return true;
}

export function getTenantFilter(): string {
  return localStorage.getItem(TENANT_KEY) || "all";
}

export function setTenantFilter(id: string) {
  localStorage.setItem(TENANT_KEY, id);
}

export class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

export async function api<T>(
  path: string,
  opts: RequestInit & { tenant?: boolean } = {}
): Promise<T> {
  const headers = new Headers(opts.headers || {});
  headers.set("Content-Type", "application/json");
  const token = getToken();
  if (token) headers.set("Authorization", `Bearer ${token}`);

  let url = path;
  if (opts.tenant !== false && !path.includes("tenant_id=")) {
    const tid = getTenantFilter();
    const join = path.includes("?") ? "&" : "?";
    url = `${path}${join}tenant_id=${encodeURIComponent(tid)}`;
  }

  const { tenant: _t, ...rest } = opts;
  const res = await fetch(url, { ...rest, headers });
  if (res.status === 401) {
    clearSession();
    throw new ApiError(401, "Unauthorized");
  }
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const body = await res.json();
      detail = body.detail || detail;
    } catch {
      /* ignore */
    }
    throw new ApiError(res.status, typeof detail === "string" ? detail : JSON.stringify(detail));
  }
  if (res.status === 204) return undefined as T;
  return res.json() as Promise<T>;
}

/** Download authenticated CSV (or other binary) from dashboard API. */
export async function downloadAuthenticated(path: string, filename: string): Promise<void> {
  const headers = new Headers();
  const token = getToken();
  if (token) headers.set("Authorization", `Bearer ${token}`);
  const res = await fetch(path, { headers });
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const body = await res.json();
      detail = body.detail || detail;
    } catch {
      /* ignore */
    }
    throw new ApiError(res.status, typeof detail === "string" ? detail : "Download failed");
  }
  const blob = await res.blob();
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
}
