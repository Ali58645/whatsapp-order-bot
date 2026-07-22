import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { CheckCircle2, MessageCircle, Radio } from "lucide-react";
import {
  api,
  fetchMe,
  filterPickerTenants,
  getRole,
  getTenantFilter,
  isOwner,
  isSupportSession,
  MeResponse,
  setTenantFilter,
  Tenant,
  TenantConfigResponse,
} from "../api";
import { useI18n } from "../i18n";
import { Button } from "../components/ui/button";
import { Label } from "../components/ui/input";
import { Skeleton } from "../components/ui/avatar";
import { cn } from "../lib/utils";

type ChannelRow = {
  channel: string;
  label: string;
  status: string;
  connected: boolean;
  account_id: string;
  oauth_pending: boolean;
  connect_type: string;
  note: string;
};

type ChannelsResponse = {
  tenant_id: number;
  channels: ChannelRow[];
};

/** Owner: WhatsApp status only — no IG/Messenger noise. */
function OwnerChannels() {
  const { t } = useI18n();
  const [me, setMe] = useState<MeResponse | null>(null);
  const [cfg, setCfg] = useState<TenantConfigResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const profile = await fetchMe();
      setMe(profile);
      const tid = profile.tenant?.id ?? profile.tenant_id;
      if (!tid) {
        setCfg(null);
        setError("No business linked to this account");
        return;
      }
      const data = await api<TenantConfigResponse>(`/api/dashboard/tenants/${tid}/config`, {
        tenant: false,
      });
      setCfg(data);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Failed to load");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  if (loading) {
    return (
      <div className="space-y-4">
        <Skeleton className="h-8 w-48" />
        <Skeleton className="h-40 w-full max-w-lg rounded-2xl" />
      </div>
    );
  }

  const phoneId = cfg?.wiring?.phone_number_id || cfg?.phone_number_id || "";
  const waNumber = (cfg?.config.business_wa_id || "").trim();
  const live = (cfg?.status || me?.tenant?.status || "live") === "live";
  const connected = Boolean(phoneId) && live;

  return (
    <div className="w-full max-w-3xl space-y-6">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">{t("channels")}</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          Your WhatsApp line — the only channel customers use today
        </p>
      </div>

      {error && (
        <p className="rounded-lg bg-destructive/10 px-3 py-2 text-sm text-destructive">{error}</p>
      )}

      <article className="rounded-2xl border border-border bg-card p-6">
        <div className="flex items-start gap-4">
          <div
            className={cn(
              "flex h-12 w-12 shrink-0 items-center justify-center rounded-2xl",
              connected ? "bg-emerald-500/15 text-emerald-400" : "bg-muted text-muted-foreground"
            )}
          >
            <Radio className="h-6 w-6" />
          </div>
          <div className="min-w-0 flex-1">
            <div className="flex flex-wrap items-center gap-2">
              <h2 className="text-lg font-semibold">WhatsApp</h2>
              <span
                className={cn(
                  "inline-flex items-center gap-1 rounded-full px-2.5 py-0.5 text-[11px] font-semibold",
                  connected
                    ? "bg-emerald-500/15 text-emerald-400"
                    : "bg-amber-500/15 text-amber-400"
                )}
              >
                {connected ? (
                  <>
                    <CheckCircle2 className="h-3 w-3" />
                    Connected
                  </>
                ) : (
                  "Needs setup"
                )}
              </span>
            </div>
            <p className="mt-2 text-sm text-muted-foreground">
              {connected
                ? "Customers can message this number and your bot will reply."
                : "Your WhatsApp number is set up by AccellionX. Contact support if chats are not arriving."}
            </p>
          </div>
        </div>

        <dl className="mt-5 space-y-3 rounded-xl border border-border/80 bg-muted/20 px-4 py-3 text-sm">
          <div className="flex justify-between gap-3">
            <dt className="text-muted-foreground">Business</dt>
            <dd className="truncate font-medium">{cfg?.name || me?.tenant?.name || "—"}</dd>
          </div>
          <div className="flex justify-between gap-3">
            <dt className="text-muted-foreground">WhatsApp number</dt>
            <dd className="font-mono text-xs font-medium">{waNumber || "Set by your admin"}</dd>
          </div>
          {phoneId ? (
            <div className="flex justify-between gap-3">
              <dt className="text-muted-foreground">Line ID</dt>
              <dd className="truncate font-mono text-[11px] text-muted-foreground">{phoneId}</dd>
            </div>
          ) : null}
        </dl>

        <p className="mt-4 text-xs text-muted-foreground">{t("wiringNote")}</p>

        <div className="mt-5 flex flex-wrap gap-2">
          <Button size="sm" asChild>
            <Link to="/conversations">
              <MessageCircle className="mr-1.5 h-3.5 w-3.5" />
              Open conversations
            </Link>
          </Button>
          <Button size="sm" variant="outline" asChild>
            <Link to="/my-bot">Edit bot replies</Link>
          </Button>
        </div>
      </article>

      <p className="text-center text-xs text-muted-foreground">
        Instagram & Messenger — coming later. WhatsApp is enough for now.
      </p>
    </div>
  );
}

/** Admin: WhatsApp primary; other channels tucked under Coming later. */
function AdminChannels() {
  const [tenants, setTenants] = useState<Tenant[]>([]);
  const [selectedDbId, setSelectedDbId] = useState<number | null>(null);
  const [data, setData] = useState<ChannelsResponse | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const pickerTenants = filterPickerTenants(tenants);

  const resolveTenantId = useCallback((list: Tenant[]): number | null => {
    const filter = getTenantFilter();
    if (filter && filter !== "all") {
      const match = list.find((t) => t.phone_number_id === filter);
      if (match) return match.id;
    }
    return list[0]?.id ?? null;
  }, []);

  useEffect(() => {
    setLoading(true);
    api<{ items?: Tenant[] } | Tenant[]>("/api/dashboard/tenants", { tenant: false })
      .then((raw) => {
        const all = Array.isArray(raw) ? raw : raw.items || [];
        setTenants(all);
        setSelectedDbId(resolveTenantId(filterPickerTenants(all)));
      })
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, [resolveTenantId]);

  useEffect(() => {
    const onTenantChange = () => {
      setSelectedDbId(resolveTenantId(filterPickerTenants(tenants)));
    };
    window.addEventListener("tenant-change", onTenantChange);
    return () => window.removeEventListener("tenant-change", onTenantChange);
  }, [tenants, resolveTenantId]);

  useEffect(() => {
    if (!selectedDbId) {
      setData(null);
      return;
    }
    api<ChannelsResponse>(`/api/dashboard/tenants/${selectedDbId}/channels`, {
      tenant: false,
    })
      .then(setData)
      .catch((e) => setError(e.message));
  }, [selectedDbId]);

  function onPickTenant(id: number) {
    setSelectedDbId(id);
    const row = tenants.find((t) => t.id === id);
    if (row) {
      setTenantFilter(row.phone_number_id);
      window.dispatchEvent(new Event("tenant-change"));
    }
  }

  async function connect(ch: string) {
    if (!selectedDbId) return;
    setBusy(ch);
    try {
      const res = await api<{ message: string }>(
        `/api/dashboard/tenants/${selectedDbId}/channels/${ch}/connect`,
        { method: "POST", tenant: false }
      );
      alert(res.message);
    } catch (e: unknown) {
      alert(e instanceof Error ? e.message : "Connect failed");
    } finally {
      setBusy(null);
    }
  }

  const channels = data?.channels || [];
  const whatsapp = channels.find((c) => c.channel === "whatsapp");
  const later = channels.filter((c) => c.channel !== "whatsapp");
  const activeTenant = tenants.find((t) => t.id === selectedDbId);

  if (loading && !data) {
    return (
      <div className="space-y-4">
        <Skeleton className="h-8 w-48" />
        <Skeleton className="h-40 w-full rounded-2xl" />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">Channels</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          Connect WhatsApp for this business. Other Meta channels are not live yet.
        </p>
      </div>

      {error && (
        <p className="rounded-lg bg-destructive/10 px-3 py-2 text-sm text-destructive">{error}</p>
      )}

      {pickerTenants.length > 0 && (
        <div className="max-w-md space-y-2">
          <Label htmlFor="channel-tenant">Business</Label>
          <select
            id="channel-tenant"
            value={selectedDbId ?? ""}
            onChange={(e) => onPickTenant(Number(e.target.value))}
            className="w-full rounded-xl border border-border bg-card px-3 py-2.5 text-sm"
          >
            {pickerTenants.map((t) => (
              <option key={t.id} value={t.id}>
                {t.name} ({t.status || "live"})
              </option>
            ))}
          </select>
        </div>
      )}

      {!pickerTenants.length && (
        <p className="text-sm text-muted-foreground">
          No businesses yet.{" "}
          <Link to="/" className="text-primary underline">
            Create one on Businesses
          </Link>
          .
        </p>
      )}

      {activeTenant && whatsapp && (
        <article className="max-w-xl rounded-2xl border border-border bg-card p-5">
          <div className="flex items-center justify-between gap-2">
            <h2 className="text-lg font-semibold">WhatsApp</h2>
            <span
              className={cn(
                "text-xs font-semibold capitalize",
                whatsapp.connected ? "text-emerald-400" : "text-amber-400"
              )}
            >
              {whatsapp.connected ? "Connected" : whatsapp.status}
            </span>
          </div>
          <p className="mt-2 text-sm text-muted-foreground">
            Phone number ID and tokens live in Settings → Wiring.
          </p>
          {whatsapp.account_id ? (
            <p className="mt-2 font-mono text-[11px] text-muted-foreground">
              ID: {whatsapp.account_id}
            </p>
          ) : null}
          <div className="mt-4">
            <Button variant="outline" size="sm" asChild>
              <Link to="/settings">Open Wiring</Link>
            </Button>
          </div>
        </article>
      )}

      {later.length > 0 && (
        <details className="max-w-xl rounded-2xl border border-dashed border-border/80 bg-muted/10 px-4 py-3">
          <summary className="cursor-pointer text-sm font-medium text-muted-foreground">
            Coming later · Instagram & Messenger
          </summary>
          <ul className="mt-3 space-y-3">
            {later.map((ch) => (
              <li key={ch.channel} className="rounded-xl border border-border/60 bg-card/50 p-3">
                <div className="flex items-center justify-between gap-2">
                  <p className="text-sm font-semibold">{ch.label}</p>
                  <span className="text-[11px] text-muted-foreground">Not available</span>
                </div>
                <p className="mt-1 text-xs text-muted-foreground">{ch.note}</p>
                <Button
                  className="mt-2"
                  variant="ghost"
                  size="sm"
                  disabled={busy === ch.channel}
                  onClick={() => void connect(ch.channel)}
                >
                  {busy === ch.channel ? "…" : "Check status"}
                </Button>
              </li>
            ))}
          </ul>
        </details>
      )}
    </div>
  );
}

export default function ChannelsPage() {
  if (isOwner() || isSupportSession()) return <OwnerChannels />;
  if (getRole() === "admin") return <AdminChannels />;
  return <OwnerChannels />;
}
