export type Tenant = {
  id: number;
  phone_number_id: string;
  name: string;
  flow_mode: string;
  status?: string;
  business_wa_id?: string;
  owner_whatsapp?: string;
  leads_today?: number;
  orders_today?: number;
  stat_today?: number;
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
  config: TenantConfig;
};

const ROLE_KEY = "dash_role";
const USER_TENANT_KEY = "dash_user_tenant_id";

export function getRole(): string | null {
  return localStorage.getItem(ROLE_KEY);
}

export function getUserTenantId(): number | null {
  const v = localStorage.getItem(USER_TENANT_KEY);
  return v ? Number(v) : null;
}

export type Overview = {
  leads_today: number;
  leads_this_week: number;
  leads_by_status: Record<string, number>;
  demos_scheduled: number;
  orders_today: number;
  revenue_today: number;
  active_conversations: number;
  recent_events: EventItem[];
};

export type ContactBrief = {
  id: number | null;
  wa_id: string;
  profile_name: string;
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
  created_at: string | null;
  updated_at: string | null;
  last_activity: string | null;
  contact: ContactBrief;
  history?: { role: string; content: string }[];
  phase?: string | null;
  session_status?: string | null;
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
    setToken(null);
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

export async function login(username: string, password: string) {
  const data = await api<{ access_token: string; role?: string; tenant_id?: number | null }>(
    "/api/auth/login",
    { method: "POST", body: JSON.stringify({ username, password }), tenant: false },
  );
  setToken(data.access_token);
  if (data.role) localStorage.setItem(ROLE_KEY, data.role);
  if (data.tenant_id != null) localStorage.setItem(USER_TENANT_KEY, String(data.tenant_id));
  else localStorage.removeItem(USER_TENANT_KEY);
  return data;
}
