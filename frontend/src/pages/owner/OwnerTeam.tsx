import { FormEvent, useCallback, useEffect, useState } from "react";
import { Loader2, UserPlus } from "lucide-react";
import { toast } from "sonner";
import { api } from "../../api";
import { Button } from "../../components/ui/button";
import { Input, Label } from "../../components/ui/input";
import { Skeleton } from "../../components/ui/avatar";

type Member = { id: number; username: string; role: string };

export default function OwnerTeam() {
  const [items, setItems] = useState<Member[]>([]);
  const [loading, setLoading] = useState(true);
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);

  const load = useCallback(() => {
    setLoading(true);
    api<{ items: Member[] }>("/api/dashboard/my-team", { tenant: false })
      .then((r) => setItems(r.items))
      .catch(() => setItems([]))
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  async function invite(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    try {
      await api("/api/dashboard/my-team", {
        method: "POST",
        body: JSON.stringify({ username: username.trim(), password }),
        tenant: false,
      });
      toast.success(`Invited ${username.trim()}`);
      setUsername("");
      setPassword("");
      load();
    } catch (err: unknown) {
      toast.error(err instanceof Error ? err.message : "Invite failed");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="mx-auto max-w-lg space-y-6">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">Team</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          People who can log in and manage this business (same access as you).
        </p>
      </div>

      {loading ? (
        <Skeleton className="h-32 w-full rounded-2xl" />
      ) : (
        <ul className="divide-y divide-border overflow-hidden rounded-2xl border border-border bg-card">
          {items.map((m) => (
            <li key={m.id} className="flex items-center justify-between px-4 py-3 text-sm">
              <span className="font-medium">{m.username}</span>
              <span className="text-xs capitalize text-muted-foreground">{m.role}</span>
            </li>
          ))}
          {!items.length && (
            <li className="px-4 py-8 text-center text-sm text-muted-foreground">No logins yet</li>
          )}
        </ul>
      )}

      <form
        onSubmit={(e) => void invite(e)}
        className="space-y-3 rounded-2xl border border-border bg-card p-5"
      >
        <div className="flex items-center gap-2 text-sm font-semibold">
          <UserPlus className="h-4 w-4" />
          Invite helper
        </div>
        <div>
          <Label>Username</Label>
          <Input
            className="mt-1.5"
            value={username}
            onChange={(e) => setUsername(e.target.value)}
            required
            minLength={3}
          />
        </div>
        <div>
          <Label>Temporary password</Label>
          <Input
            type="password"
            className="mt-1.5"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            required
            minLength={8}
          />
        </div>
        <Button type="submit" disabled={busy}>
          {busy ? <Loader2 className="h-4 w-4 animate-spin" /> : null}
          Create login
        </Button>
      </form>
    </div>
  );
}
