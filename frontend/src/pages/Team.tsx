import { FormEvent, useCallback, useEffect, useState } from "react";
import { Eye, Loader2, Plus, Users } from "lucide-react";
import { toast } from "sonner";
import { api, enterViewAs, filterPickerTenants, Tenant } from "../api";
import { useI18n } from "../i18n";
import { Button } from "../components/ui/button";
import { Input, Label } from "../components/ui/input";
import { Skeleton } from "../components/ui/avatar";
import { useNavigate } from "react-router-dom";

type DashUser = {
  id: number;
  username: string;
  role: string;
  tenant_id: number | null;
  tenant_name: string | null;
  created_at: string | null;
};

export default function TeamPage() {
  const { t } = useI18n();
  const navigate = useNavigate();
  const [users, setUsers] = useState<DashUser[]>([]);
  const [tenants, setTenants] = useState<Tenant[]>([]);
  const [loading, setLoading] = useState(true);
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [tenantId, setTenantId] = useState<number | "">("");
  const [busy, setBusy] = useState(false);
  const [viewBusy, setViewBusy] = useState<number | null>(null);

  const load = useCallback(() => {
    setLoading(true);
    Promise.all([
      api<{ items: DashUser[] }>("/api/dashboard/users", { tenant: false }),
      api<{ items?: Tenant[] } | Tenant[]>("/api/dashboard/tenants", { tenant: false }),
    ])
      .then(([u, raw]) => {
        setUsers(u.items || []);
        const all = Array.isArray(raw) ? raw : raw.items || [];
        const t = filterPickerTenants(all);
        setTenants(t);
        if (!tenantId && t[0]) setTenantId(t[0].id);
      })
      .catch((e) => toast.error(e.message))
      .finally(() => setLoading(false));
  }, [tenantId]);

  useEffect(() => {
    load();
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  async function onCreate(e: FormEvent) {
    e.preventDefault();
    if (!username.trim() || !password || tenantId === "") {
      toast.error("Username, password, and tenant required");
      return;
    }
    setBusy(true);
    try {
      await api("/api/dashboard/users", {
        method: "POST",
        body: JSON.stringify({
          username: username.trim(),
          password,
          tenant_id: Number(tenantId),
        }),
        tenant: false,
      });
      toast.success("Owner account created");
      setUsername("");
      setPassword("");
      load();
    } catch (err: unknown) {
      toast.error(err instanceof Error ? err.message : "Create failed");
    } finally {
      setBusy(false);
    }
  }

  async function viewAs(tid: number) {
    setViewBusy(tid);
    try {
      await enterViewAs(tid);
      toast.success("Opened support view");
      navigate("/", { replace: true });
      window.location.reload();
    } catch (err: unknown) {
      toast.error(err instanceof Error ? err.message : "View-as failed");
    } finally {
      setViewBusy(null);
    }
  }

  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">{t("team")}</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          Create owner logins and preview the client experience
        </p>
      </div>

      <form
        onSubmit={onCreate}
        className="grid gap-4 rounded-2xl border border-border bg-card p-5 sm:grid-cols-2"
      >
        <h2 className="sm:col-span-2 text-sm font-semibold">{t("createOwner")}</h2>
        <div>
          <Label>{t("username")}</Label>
          <Input
            className="mt-1.5"
            value={username}
            onChange={(e) => setUsername(e.target.value)}
            autoComplete="off"
          />
        </div>
        <div>
          <Label>{t("password")}</Label>
          <Input
            className="mt-1.5"
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            autoComplete="new-password"
          />
        </div>
        <div className="sm:col-span-2">
          <Label>{t("assignTenant")}</Label>
          <select
            className="mt-1.5 flex h-10 w-full rounded-lg border border-input bg-background px-3 text-sm"
            value={tenantId}
            onChange={(e) => setTenantId(e.target.value ? Number(e.target.value) : "")}
          >
            {tenants.map((tn) => (
              <option key={tn.id} value={tn.id}>
                {tn.name} ({tn.flow_mode})
              </option>
            ))}
          </select>
        </div>
        <div className="sm:col-span-2">
          <Button type="submit" disabled={busy}>
            {busy ? <Loader2 className="h-4 w-4 animate-spin" /> : <Plus className="h-4 w-4" />}
            {t("create")}
          </Button>
        </div>
      </form>

      <section>
        <h2 className="mb-3 flex items-center gap-2 text-sm font-semibold">
          <Users className="h-4 w-4" />
          Accounts
        </h2>
        {loading ? (
          <Skeleton className="h-32 w-full rounded-2xl" />
        ) : (
          <div className="overflow-hidden rounded-2xl border border-border">
            <table className="w-full text-sm">
              <thead className="bg-muted/40 text-left text-xs uppercase tracking-wider text-muted-foreground">
                <tr>
                  <th className="px-4 py-3">User</th>
                  <th className="px-4 py-3">Role</th>
                  <th className="px-4 py-3">Business</th>
                  <th className="px-4 py-3" />
                </tr>
              </thead>
              <tbody>
                {users.map((u) => (
                  <tr key={u.id} className="border-t border-border">
                    <td className="px-4 py-3 font-medium">{u.username}</td>
                    <td className="px-4 py-3 capitalize text-muted-foreground">{u.role}</td>
                    <td className="px-4 py-3 text-muted-foreground">
                      {u.tenant_name || (u.tenant_id ? `#${u.tenant_id}` : "—")}
                    </td>
                    <td className="px-4 py-3 text-right">
                      {u.tenant_id && (
                        <Button
                          size="sm"
                          variant="outline"
                          disabled={viewBusy === u.tenant_id}
                          onClick={() => void viewAs(u.tenant_id!)}
                        >
                          {viewBusy === u.tenant_id ? (
                            <Loader2 className="h-3.5 w-3.5 animate-spin" />
                          ) : (
                            <Eye className="h-3.5 w-3.5" />
                          )}
                          {t("viewAsOwner")}
                        </Button>
                      )}
                    </td>
                  </tr>
                ))}
                {!users.length && (
                  <tr>
                    <td colSpan={4} className="px-4 py-8 text-center text-muted-foreground">
                      No users yet
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        )}
      </section>

      <section>
        <h2 className="mb-3 text-sm font-semibold">Businesses — quick view-as</h2>
        <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
          {tenants.map((tn) => (
            <div
              key={tn.id}
              className="flex items-center justify-between gap-2 rounded-xl border border-border bg-card px-4 py-3"
            >
              <div className="min-w-0">
                <p className="truncate font-medium">{tn.name}</p>
                <p className="text-xs text-muted-foreground">{tn.flow_mode}</p>
              </div>
              <Button
                size="sm"
                variant="soft"
                disabled={viewBusy === tn.id}
                onClick={() => void viewAs(tn.id)}
              >
                <Eye className="h-3.5 w-3.5" />
              </Button>
            </div>
          ))}
        </div>
      </section>
    </div>
  );
}
