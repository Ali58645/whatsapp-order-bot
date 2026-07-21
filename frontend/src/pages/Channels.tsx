import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import {
  api,
  filterPickerTenants,
  getRole,
  getTenantFilter,
  isOwner,
  MeResponse,
  setTenantFilter,
  Tenant,
} from "../api";
import { ChannelBadge } from "../components/ChannelBadge";
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

export default function ChannelsPage() {
  const [me, setMe] = useState<MeResponse | null>(null);
  const [tenants, setTenants] = useState<Tenant[]>([]);
  const [selectedDbId, setSelectedDbId] = useState<number | null>(null);
  const [data, setData] = useState<ChannelsResponse | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const isAdmin = getRole() === "admin" && !isOwner();
  const pickerTenants = filterPickerTenants(tenants);

  const resolveTenantId = useCallback(
    (list: Tenant[], profile: MeResponse | null): number | null => {
      if (profile?.tenant?.id) return profile.tenant.id;
      if (profile?.tenant_id) return profile.tenant_id;
      const filter = getTenantFilter();
      if (filter && filter !== "all") {
        const match = list.find((t) => t.phone_number_id === filter);
        if (match) return match.id;
      }
      return list[0]?.id ?? null;
    },
    []
  );

  useEffect(() => {
    setLoading(true);
    api<MeResponse>("/api/dashboard/me", { tenant: false })
      .then((profile) => {
        setMe(profile);
        return api<{ items?: Tenant[] } | Tenant[]>("/api/dashboard/tenants", {
          tenant: false,
        }).then((raw) => {
          const all = Array.isArray(raw) ? raw : raw.items || [];
          setTenants(all);
          const picked = resolveTenantId(filterPickerTenants(all), profile);
          setSelectedDbId(picked);
        });
      })
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, [resolveTenantId]);

  useEffect(() => {
    const onTenantChange = () => {
      const list = filterPickerTenants(tenants);
      const filter = getTenantFilter();
      const match =
        filter === "all"
          ? list[0]
          : list.find((t) => t.phone_number_id === filter) || list[0];
      if (match) setSelectedDbId(match.id);
    };
    window.addEventListener("tenant-change", onTenantChange);
    return () => window.removeEventListener("tenant-change", onTenantChange);
  }, [tenants]);

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

  const activeTenant = tenants.find((t) => t.id === selectedDbId);

  if (loading && !data) {
    return (
      <div className="space-y-4">
        <Skeleton className="h-8 w-48" />
        <Skeleton className="h-10 w-full max-w-sm rounded-xl" />
        <Skeleton className="h-40 w-full rounded-2xl" />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">Channels</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          Connect WhatsApp, Instagram, and Messenger. IG/FB activate after Meta App Review.
        </p>
      </div>

      {error && (
        <p className="rounded-lg bg-destructive/10 px-3 py-2 text-sm text-destructive">{error}</p>
      )}

      {isAdmin && pickerTenants.length > 0 && (
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

      {activeTenant && (
        <p className="text-sm text-muted-foreground">
          Managing channels for <span className="font-medium text-foreground">{activeTenant.name}</span>
        </p>
      )}

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {(data?.channels || []).map((ch) => (
          <article key={ch.channel} className="surface p-5">
            <div className="flex items-center justify-between gap-2">
              <div className="flex items-center gap-2">
                <ChannelBadge channel={ch.channel} />
                <h2 className="font-semibold">{ch.label}</h2>
              </div>
              <span
                className={cn(
                  "text-xs font-medium capitalize",
                  ch.connected ? "text-emerald-400" : "text-muted-foreground"
                )}
              >
                {ch.status}
              </span>
            </div>
            <p className="mt-3 text-xs text-muted-foreground">{ch.note}</p>
            {ch.account_id && (
              <p className="mt-2 font-mono text-[11px] text-muted-foreground">
                ID: {ch.account_id}
              </p>
            )}
            {ch.oauth_pending && ch.channel !== "whatsapp" && (
              <p className="mt-2 text-xs text-amber-400">Pending Meta approval</p>
            )}
            <div className="mt-4">
              {ch.channel === "whatsapp" ? (
                <Button variant="outline" size="sm" asChild>
                  <Link to={isAdmin ? "/settings" : "/my-bot"}>Manage in Wiring</Link>
                </Button>
              ) : (
                <Button
                  variant="outline"
                  size="sm"
                  disabled={busy === ch.channel}
                  onClick={() => void connect(ch.channel)}
                >
                  {busy === ch.channel ? "…" : "Connect"}
                </Button>
              )}
            </div>
          </article>
        ))}
      </div>
    </div>
  );
}
