import { useCallback, useEffect, useState } from "react";
import { ScrollText } from "lucide-react";
import { api } from "../api";
import { Skeleton } from "../components/ui/avatar";
import { Button } from "../components/ui/button";
import { relativeTime } from "../lib/utils";

type AccessLogItem = {
  id: number;
  admin_username: string;
  tenant_id: number | null;
  tenant_name: string;
  action: string;
  detail: Record<string, unknown>;
  created_at: string | null;
};

function actionLabel(action: string) {
  const map: Record<string, string> = {
    view_as_enter: "View as tenant",
    config_save: "Saved config",
    menu_publish: "Published menu",
    messages_publish: "Published messages",
    menu_test_send: "Menu test send",
    apply_template: "Applied template",
    reply: "Sent reply",
    mute: "Muted bot",
    unmute: "Unmuted bot",
  };
  return map[action] || action;
}

export default function AccessLogPage() {
  const [items, setItems] = useState<AccessLogItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const load = useCallback(() => {
    setLoading(true);
    setError("");
    api<{ items: AccessLogItem[] }>("/api/dashboard/access-log", { tenant: false })
      .then((r) => setItems(r.items || []))
      .catch((e) => setError(e instanceof Error ? e.message : "Failed to load"))
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">Access Log</h1>
          <p className="mt-1 text-sm text-muted-foreground">
            Admin support sessions and actions taken while viewing as a tenant
          </p>
        </div>
        <Button variant="outline" size="sm" onClick={load} disabled={loading}>
          Refresh
        </Button>
      </div>

      {error && (
        <p className="rounded-lg bg-destructive/10 px-3 py-2 text-sm text-destructive">{error}</p>
      )}

      {loading ? (
        <div className="space-y-2">
          {[1, 2, 3, 4].map((i) => (
            <Skeleton key={i} className="h-14 w-full rounded-xl" />
          ))}
        </div>
      ) : items.length === 0 ? (
        <div className="rounded-2xl border border-dashed border-border bg-card/50 p-12 text-center">
          <ScrollText className="mx-auto h-10 w-10 text-muted-foreground" />
          <p className="mt-3 text-sm text-muted-foreground">No support access events yet</p>
        </div>
      ) : (
        <ul className="divide-y divide-border overflow-hidden rounded-2xl border border-border bg-card">
          {items.map((row) => (
            <li key={row.id} className="flex flex-wrap items-start justify-between gap-3 px-4 py-3">
              <div className="min-w-0">
                <p className="text-sm font-medium">
                  <span className="text-foreground">{row.admin_username}</span>
                  <span className="mx-1.5 text-muted-foreground">·</span>
                  {actionLabel(row.action)}
                </p>
                <p className="mt-0.5 text-xs text-muted-foreground">
                  {row.tenant_name || (row.tenant_id != null ? `Tenant #${row.tenant_id}` : "—")}
                </p>
              </div>
              <p className="shrink-0 text-xs text-muted-foreground">
                {row.created_at ? relativeTime(row.created_at) : "—"}
              </p>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
