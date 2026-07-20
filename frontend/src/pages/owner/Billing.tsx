import { useEffect, useState } from "react";
import { api, BillingInfo } from "../../api";
import { useI18n } from "../../i18n";
import { Skeleton } from "../../components/ui/avatar";

export default function BillingPage() {
  const { t } = useI18n();
  const [data, setData] = useState<BillingInfo | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    api<BillingInfo>("/api/dashboard/billing", { tenant: false })
      .then(setData)
      .catch((e) => setError(e.message));
  }, []);

  if (!data && !error) {
    return (
      <div className="space-y-4">
        <Skeleton className="h-10 w-40" />
        <Skeleton className="h-40 w-full rounded-2xl" />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">{t("billing")}</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          {data?.tenant_name || "Your plan"} · {data?.period}
        </p>
      </div>
      {error && (
        <p className="rounded-lg bg-destructive/10 px-3 py-2 text-sm text-destructive">{error}</p>
      )}
      {data && (
        <div className="grid gap-4 sm:grid-cols-2">
          <div className="rounded-2xl border border-border bg-card p-5">
            <p className="text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">
              {t("plan")}
            </p>
            <p className="mt-2 text-2xl font-bold">{data.plan_name}</p>
            <p className="mt-1 text-sm capitalize text-emerald-400">{data.status}</p>
          </div>
          <div className="rounded-2xl border border-border bg-card p-5">
            <p className="text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">
              {t("usage")}
            </p>
            <div className="mt-3 space-y-2 text-sm">
              <p className="flex justify-between">
                <span className="text-muted-foreground">{t("messagesSent")}</span>
                <span className="font-semibold tabular">{data.usage.messages_sent}</span>
              </p>
              <p className="flex justify-between">
                <span className="text-muted-foreground">{t("templatesSent")}</span>
                <span className="font-semibold tabular">{data.usage.templates_sent}</span>
              </p>
            </div>
            {data.placeholder && (
              <p className="mt-4 text-xs text-muted-foreground">{t("placeholderBilling")}</p>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
