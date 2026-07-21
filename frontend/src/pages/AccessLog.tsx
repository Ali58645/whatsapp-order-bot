import { useCallback, useEffect, useMemo, useState } from "react";
import { api } from "../api";
import { Skeleton } from "../components/ui/avatar";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { InlineError, PageHeader } from "../components/ui/page-header";
import { EmptyState } from "../components/ui/empty-state";
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
  const [adminQ, setAdminQ] = useState("");
  const [actionQ, setActionQ] = useState("all");
  const [tenantQ, setTenantQ] = useState("");

  const load = useCallback(() => {
    setLoading(true);
    setError("");
    api<{ items: AccessLogItem[] }>("/api/dashboard/access-log?limit=200", { tenant: false })
      .then((r) => setItems(r.items || []))
      .catch((e) => setError(e instanceof Error ? e.message : "Failed to load"))
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const actions = useMemo(() => {
    const set = new Set(items.map((i) => i.action));
    return ["all", ...Array.from(set).sort()];
  }, [items]);

  const filtered = useMemo(() => {
    const aq = adminQ.trim().toLowerCase();
    const tq = tenantQ.trim().toLowerCase();
    return items.filter((row) => {
      if (actionQ !== "all" && row.action !== actionQ) return false;
      if (aq && !(row.admin_username || "").toLowerCase().includes(aq)) return false;
      if (
        tq &&
        !(row.tenant_name || "").toLowerCase().includes(tq) &&
        !String(row.tenant_id ?? "").includes(tq)
      ) {
        return false;
      }
      return true;
    });
  }, [items, adminQ, actionQ, tenantQ]);

  return (
    <div className="space-y-7">
      <PageHeader
        kicker="Security"
        title="Access Log"
        description="Admin support sessions and actions taken while viewing as a tenant"
        actions={
          <Button variant="outline" size="sm" onClick={load} disabled={loading}>
            Refresh
          </Button>
        }
      />

      {error && <InlineError message={error} onRetry={load} />}

      <div className="flex flex-wrap items-center gap-2">
        <Input
          className="h-9 max-w-[180px]"
          placeholder="Filter admin…"
          value={adminQ}
          onChange={(e) => setAdminQ(e.target.value)}
        />
        <Input
          className="h-9 max-w-[180px]"
          placeholder="Filter business…"
          value={tenantQ}
          onChange={(e) => setTenantQ(e.target.value)}
        />
        <select
          className="field-select !mt-0 h-9 max-w-[200px] py-0"
          value={actionQ}
          onChange={(e) => setActionQ(e.target.value)}
        >
          {actions.map((a) => (
            <option key={a} value={a}>
              {a === "all" ? "All actions" : actionLabel(a)}
            </option>
          ))}
        </select>
        <p className="ml-auto text-xs text-muted-foreground tabular-nums">
          {filtered.length} / {items.length}
        </p>
      </div>

      {loading ? (
        <div className="space-y-2">
          {[1, 2, 3, 4].map((i) => (
            <Skeleton key={i} className="h-14 w-full rounded-xl" />
          ))}
        </div>
      ) : items.length === 0 ? (
        <EmptyState
          title="No support access events yet"
          description="View-as sessions and support mutations will appear here."
        />
      ) : filtered.length === 0 ? (
        <EmptyState
          illustration="search"
          title="No matching events"
          description="Try clearing filters."
        />
      ) : (
        <div className="surface overflow-hidden">
          <table className="w-full text-sm">
            <thead className="bg-muted/30 text-left text-[10px] uppercase tracking-[0.1em] text-muted-foreground">
              <tr>
                <th className="px-4 py-3 font-semibold">When</th>
                <th className="px-4 py-3 font-semibold">Admin</th>
                <th className="px-4 py-3 font-semibold">Action</th>
                <th className="px-4 py-3 font-semibold">Business</th>
              </tr>
            </thead>
            <tbody>
              {filtered.map((row) => (
                <tr key={row.id} className="border-t border-border/70">
                  <td className="px-4 py-3 text-xs text-muted-foreground">
                    <span title={row.created_at || undefined}>
                      {row.created_at ? relativeTime(row.created_at) : "—"}
                    </span>
                  </td>
                  <td className="px-4 py-3 font-medium">{row.admin_username}</td>
                  <td className="px-4 py-3">{actionLabel(row.action)}</td>
                  <td className="px-4 py-3 text-muted-foreground">
                    {row.tenant_name ||
                      (row.tenant_id != null ? `Tenant #${row.tenant_id}` : "—")}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
