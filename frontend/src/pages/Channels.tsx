import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api, getRole, isOwner, MeResponse } from "../api";
import { ChannelBadge } from "../components/ChannelBadge";
import { Button } from "../components/ui/button";
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
  const [data, setData] = useState<ChannelsResponse | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState("");

  const tenantId = me?.tenant?.id ?? me?.tenant_id;

  useEffect(() => {
    api<MeResponse>("/api/dashboard/me", { tenant: false })
      .then(setMe)
      .catch((e) => setError(e.message));
  }, []);

  useEffect(() => {
    if (!tenantId) return;
    api<ChannelsResponse>(`/api/dashboard/tenants/${tenantId}/channels`, {
      tenant: false,
    })
      .then(setData)
      .catch((e) => setError(e.message));
  }, [tenantId]);

  async function connect(ch: string) {
    if (!tenantId) return;
    setBusy(ch);
    try {
      const res = await api<{ message: string }>(
        `/api/dashboard/tenants/${tenantId}/channels/${ch}/connect`,
        { method: "POST", tenant: false }
      );
      alert(res.message);
    } catch (e: unknown) {
      alert(e instanceof Error ? e.message : "Connect failed");
    } finally {
      setBusy(null);
    }
  }

  const isAdmin = getRole() === "admin" && !isOwner();

  if (!me && !error) {
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
          Connect WhatsApp, Instagram, and Messenger. IG/FB activate after Meta App Review.
        </p>
      </div>

      {error && (
        <p className="rounded-lg bg-destructive/10 px-3 py-2 text-sm text-destructive">{error}</p>
      )}

      {!tenantId && isAdmin && (
        <p className="text-sm text-muted-foreground">
          Select a business in{" "}
          <Link to="/settings" className="text-primary underline">
            Settings
          </Link>{" "}
          to manage channels, or use View as from Businesses.
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
