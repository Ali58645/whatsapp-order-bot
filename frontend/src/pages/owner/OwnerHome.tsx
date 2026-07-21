import { useCallback, useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { RefreshCw, Sparkles, AlertTriangle } from "lucide-react";
import {
  api,
  MeResponse,
  Overview as OverviewData,
  TenantConfigResponse,
} from "../../api";
import { useI18n } from "../../i18n";
import { StatCard } from "../../components/ui/stat-card";
import { Button } from "../../components/ui/button";
import { cn, relativeTime, eventIconType, eventsByDay } from "../../lib/utils";

export default function OwnerHome() {
  const { t } = useI18n();
  const [data, setData] = useState<OverviewData | null>(null);
  const [me, setMe] = useState<MeResponse | null>(null);
  const [nudge, setNudge] = useState<{ greeting?: boolean; menu?: boolean }>({});
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const [overview, meRes] = await Promise.all([
        api<OverviewData>("/api/dashboard/overview"),
        api<MeResponse>("/api/dashboard/me", { tenant: false }),
      ]);
      setData(overview);
      setMe(meRes);
      if (meRes.tenant?.id) {
        try {
          const cfg = await api<TenantConfigResponse>(
            `/api/dashboard/tenants/${meRes.tenant.id}/config`,
            { tenant: false }
          );
          const greet = (cfg.config.greeting_text || "").toLowerCase();
          const defaultish =
            !greet ||
            greet.includes("assalam o alaikum! menu") ||
            greet.includes("[business]") ||
            greet.includes("kaise madad");
          const menuEmpty =
            cfg.flow_mode === "order" &&
            !(cfg.config.menu_v2_draft?.items?.length || cfg.config.menu_v2?.items?.length);
          setNudge({ greeting: defaultish, menu: menuEmpty });
        } catch {
          setNudge({});
        }
      }
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Failed to load");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  const series = useMemo(
    () => eventsByDay(data?.recent_events || [], 7),
    [data?.recent_events]
  );

  const live = (me?.tenant?.status || "live") === "live";
  const isOrder = me?.tenant?.flow_mode === "order";

  return (
    <div className="space-y-8">
      <div className="flex items-end justify-between gap-4">
        <div>
          <p className="page-kicker">{me?.tenant?.name || "Home"}</p>
          <h1 className="page-title mt-1">{t("welcomeHome")}</h1>
          <p className="page-subtitle">{t("homeSubtitle")}</p>
        </div>
        <Button variant="outline" size="sm" onClick={() => void load()} disabled={loading}>
          <RefreshCw className={cn("h-3.5 w-3.5", loading && "animate-spin")} />
          {t("refresh")}
        </Button>
      </div>

      {(nudge.greeting || nudge.menu) && (
        <div className="flex flex-wrap items-center gap-3 rounded-2xl border border-amber-500/30 bg-amber-500/10 px-4 py-3 text-sm">
          <AlertTriangle className="h-4 w-4 text-amber-400" />
          <span className="font-medium">{t("completeBot")}</span>
          {nudge.greeting && (
            <Link to="/my-bot" className="text-primary underline-offset-2 hover:underline">
              {t("completeGreeting")}
            </Link>
          )}
          {nudge.menu && (
            <Link to="/menu" className="text-primary underline-offset-2 hover:underline">
              {t("completeMenu")}
            </Link>
          )}
        </div>
      )}

      <div
        className={cn(
          "inline-flex items-center gap-2 rounded-full px-3 py-1 text-xs font-semibold",
          live
            ? "bg-emerald-500/15 text-emerald-400"
            : "bg-orange-500/15 text-orange-400"
        )}
      >
        <Sparkles className="h-3.5 w-3.5" />
        {live ? t("botLive") : t("botPaused")}
      </div>

      {error && (
        <p className="rounded-lg bg-destructive/10 px-3 py-2 text-sm text-destructive">{error}</p>
      )}

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <StatCard
          label={isOrder ? t("ordersToday") : t("newCustomers")}
          value={isOrder ? data?.orders_today ?? 0 : data?.leads_today ?? 0}
          series={series}
          glow
          loading={loading}
        />
        <StatCard
          label={t("thisWeek")}
          value={isOrder ? data?.orders_this_week ?? 0 : data?.leads_this_week ?? 0}
          series={series}
          loading={loading}
        />
        {!isOrder && (
          <StatCard
            label={t("demos")}
            value={data?.demos_scheduled ?? 0}
            series={series}
            loading={loading}
          />
        )}
        {isOrder && (
          <StatCard
            label={t("revenueToday")}
            value={data?.revenue_today ?? 0}
            series={series}
            prefix="Rs "
            loading={loading}
          />
        )}
        <Link to="/conversations" className="block transition hover:opacity-90">
          <StatCard
            label={t("conversations")}
            value={data?.active_conversations ?? 0}
            series={series}
            loading={loading}
          />
        </Link>
      </div>

      <section>
        <h2 className="mb-3 text-sm font-semibold uppercase tracking-wider text-muted-foreground">
          {t("recentActivity")}
        </h2>
        <div className="space-y-2 rounded-2xl border border-border bg-card p-4">
          {(data?.recent_events || []).slice(0, 8).map((ev) => (
            <div
              key={ev.id}
              className="flex items-center justify-between gap-3 border-b border-border/50 py-2 last:border-0"
            >
              <div className="min-w-0">
                <p className="truncate text-sm font-medium">
                  {eventIconType(ev.type)} · {ev.type}
                </p>
                <p className="truncate text-xs text-muted-foreground">
                  {ev.contact?.profile_name || ev.contact?.wa_id || "—"}
                </p>
              </div>
              <span className="shrink-0 text-[11px] text-muted-foreground">
                {relativeTime(ev.created_at)}
              </span>
            </div>
          ))}
          {!loading && !(data?.recent_events || []).length && (
            <p className="py-6 text-center text-sm text-muted-foreground">No activity yet</p>
          )}
        </div>
      </section>
    </div>
  );
}
