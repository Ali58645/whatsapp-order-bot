import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import {
  api,
  fetchMe,
  MeResponse,
  TenantConfigResponse,
} from "../../api";
import { MenuBuilder } from "../../components/MenuBuilder";
import { EmptyState } from "../../components/ui/empty-state";
import { Skeleton } from "../../components/ui/avatar";
import { useI18n } from "../../i18n";

/**
 * Owner Order Menu — restaurant / order-flow bots only.
 * Lead tenants never see this in nav; deep links land on a clear empty state.
 */
export default function OwnerMenu() {
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
        <Skeleton className="h-40 w-full rounded-2xl" />
        <Skeleton className="h-64 w-full rounded-2xl" />
      </div>
    );
  }

  const flow = cfg?.flow_mode || me?.tenant?.flow_mode || "lead";
  if (flow !== "order") {
    return (
      <div className="space-y-6">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">{t("menu")}</h1>
          <p className="mt-1 text-sm text-muted-foreground">
            For restaurant ordering bots only
          </p>
        </div>
        <EmptyState
          title="Your bot collects leads, not orders"
          description="Order Menu is for restaurants. Use My Bot to edit greeting, questions, and FAQ."
          illustration="orders"
          action={
            <Link
              to="/my-bot"
              className="text-sm font-medium text-primary underline-offset-2 hover:underline"
            >
              Open My Bot →
            </Link>
          }
        />
      </div>
    );
  }

  const tenantId = cfg?.id ?? me?.tenant?.id ?? me?.tenant_id;
  if (!tenantId || !cfg) {
    return (
      <div className="space-y-4">
        <h1 className="text-2xl font-bold tracking-tight">{t("menu")}</h1>
        <p className="text-sm text-destructive">{error || "Could not load menu"}</p>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">{t("menu")}</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          Categories and prices customers see on WhatsApp · Publish when ready
        </p>
      </div>

      {error && (
        <p className="rounded-lg bg-destructive/10 px-3 py-2 text-sm text-destructive">{error}</p>
      )}

      <MenuBuilder
        tenantDbId={tenantId}
        initial={cfg.config.menu_v2_draft || cfg.config.menu_v2}
        published={cfg.config.menu_v2}
        simple
        onSaved={(draftMenu, published) =>
          setCfg({
            ...cfg,
            config: {
              ...cfg.config,
              menu_v2_draft: draftMenu,
              menu_v2: published ?? cfg.config.menu_v2,
            },
          })
        }
      />
    </div>
  );
}
