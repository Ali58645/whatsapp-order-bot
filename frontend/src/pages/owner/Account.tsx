import { FormEvent, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { Building2, KeyRound, Loader2, Sparkles } from "lucide-react";
import { toast } from "sonner";
import {
  api,
  clearMeCache,
  fetchMe,
  getRole,
  isOwner,
  isReadonlySession,
} from "../../api";
import { Button } from "../../components/ui/button";
import { Input, Label } from "../../components/ui/input";
import { Skeleton } from "../../components/ui/avatar";
import { cn, initials, avatarStyle } from "../../lib/utils";

export default function AccountPage() {
  const [loading, setLoading] = useState(true);
  const [name, setName] = useState("");
  const [logoUrl, setLogoUrl] = useState("");
  const [username, setUsername] = useState("");
  const [profileBusy, setProfileBusy] = useState(false);

  const [current, setCurrent] = useState("");
  const [next, setNext] = useState("");
  const [confirm, setConfirm] = useState("");
  const [pwBusy, setPwBusy] = useState(false);

  const readonly = isReadonlySession();

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const me = await fetchMe({ force: true });
        if (cancelled) return;
        setUsername(me.username);
        setName(me.tenant?.name || "");
        setLogoUrl(me.tenant?.logo_url || "");
      } catch (e: unknown) {
        toast.error(e instanceof Error ? e.message : "Failed to load profile");
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  async function saveProfile(e: FormEvent) {
    e.preventDefault();
    if (readonly) return;
    const trimmed = name.trim();
    if (!trimmed) {
      toast.error("Business name is required");
      return;
    }
    const logo = logoUrl.trim();
    if (logo && !/^https:\/\//i.test(logo)) {
      toast.error("Picture must be an https:// link");
      return;
    }
    setProfileBusy(true);
    try {
      const res = await api<{ name: string; logo_url: string }>(
        "/api/dashboard/my-business/profile",
        {
          method: "PATCH",
          body: JSON.stringify({ name: trimmed, logo_url: logo }),
          tenant: false,
        }
      );
      setName(res.name);
      setLogoUrl(res.logo_url || "");
      clearMeCache();
      window.dispatchEvent(new Event("tenant-change"));
      toast.success("Profile saved");
    } catch (err: unknown) {
      toast.error(err instanceof Error ? err.message : "Failed to save");
    } finally {
      setProfileBusy(false);
    }
  }

  async function onPassword(e: FormEvent) {
    e.preventDefault();
    if (readonly) return;
    if (next.length < 8) {
      toast.error("New password must be at least 8 characters");
      return;
    }
    if (next !== confirm) {
      toast.error("New passwords do not match");
      return;
    }
    setPwBusy(true);
    try {
      await api("/api/dashboard/me/password", {
        method: "POST",
        body: JSON.stringify({ current_password: current, new_password: next }),
        tenant: false,
      });
      toast.success("Password updated");
      setCurrent("");
      setNext("");
      setConfirm("");
    } catch (err: unknown) {
      toast.error(err instanceof Error ? err.message : "Failed");
    } finally {
      setPwBusy(false);
    }
  }

  if (loading) {
    return (
      <div className="mx-auto w-full max-w-3xl space-y-4">
        <Skeleton className="h-8 w-40" />
        <Skeleton className="h-48 w-full rounded-2xl" />
      </div>
    );
  }

  return (
    <div className="w-full max-w-3xl space-y-6">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">Account</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          {isOwner() || getRole() === "owner"
            ? "Your business profile and login"
            : "Profile and password"}
        </p>
      </div>

      <form
        onSubmit={(e) => void saveProfile(e)}
        className="space-y-4 rounded-2xl border border-border bg-card p-5"
      >
        <div className="flex items-center gap-2 text-sm font-semibold">
          <Building2 className="h-4 w-4" />
          Business profile
        </div>

        <div className="flex items-center gap-4">
          {logoUrl.trim() ? (
            <img
              src={logoUrl.trim()}
              alt=""
              className="h-16 w-16 rounded-full object-cover ring-1 ring-border"
              onError={(e) => {
                (e.target as HTMLImageElement).style.display = "none";
              }}
            />
          ) : (
            <div
              className={cn(
                "inline-flex h-16 w-16 shrink-0 items-center justify-center rounded-full text-lg font-semibold"
              )}
              style={avatarStyle(name || username)}
              aria-hidden
            >
              {initials(name || username, "?")}
            </div>
          )}
          <div className="min-w-0 text-sm text-muted-foreground">
            <p className="truncate font-medium text-foreground">{name || "Your business"}</p>
            <p className="truncate text-xs">Login: {username}</p>
          </div>
        </div>

        <div>
          <Label>Business name</Label>
          <Input
            className="mt-1.5"
            value={name}
            onChange={(e) => setName(e.target.value)}
            required
            maxLength={256}
            disabled={readonly}
            placeholder="e.g. Bahi POS"
          />
        </div>
        <div>
          <Label>Profile picture URL</Label>
          <Input
            className="mt-1.5"
            value={logoUrl}
            onChange={(e) => setLogoUrl(e.target.value)}
            disabled={readonly}
            placeholder="https://…"
            inputMode="url"
          />
          <p className="mt-1.5 text-xs text-muted-foreground">
            Paste an https image link. Shown in your dashboard (not WhatsApp yet).
          </p>
        </div>
        <Button type="submit" disabled={profileBusy || readonly}>
          {profileBusy ? <Loader2 className="h-4 w-4 animate-spin" /> : null}
          Save profile
        </Button>
      </form>

      {(isOwner() || getRole() === "owner") && (
        <div className="space-y-3 rounded-2xl border border-border bg-card p-5">
          <div className="flex items-center gap-2 text-sm font-semibold">
            <Sparkles className="h-4 w-4" />
            Business setup
          </div>
          <p className="text-sm text-muted-foreground">
            Re-run the guided setup to refresh your knowledge base, greeting, questions, and
            replies from a category template.
          </p>
          <Button type="button" variant="outline" asChild>
            <Link to="/setup?rerun=1">Re-run setup wizard</Link>
          </Button>
        </div>
      )}

      <form
        onSubmit={(e) => void onPassword(e)}
        className="space-y-4 rounded-2xl border border-border bg-card p-5"
      >
        <div className="flex items-center gap-2 text-sm font-semibold">
          <KeyRound className="h-4 w-4" />
          Change password
        </div>
        <div>
          <Label>Current password</Label>
          <Input
            type="password"
            className="mt-1.5"
            value={current}
            onChange={(e) => setCurrent(e.target.value)}
            required
            autoComplete="current-password"
            disabled={readonly}
          />
        </div>
        <div>
          <Label>New password</Label>
          <Input
            type="password"
            className="mt-1.5"
            value={next}
            onChange={(e) => setNext(e.target.value)}
            required
            minLength={8}
            autoComplete="new-password"
            disabled={readonly}
          />
        </div>
        <div>
          <Label>Confirm new password</Label>
          <Input
            type="password"
            className="mt-1.5"
            value={confirm}
            onChange={(e) => setConfirm(e.target.value)}
            required
            minLength={8}
            autoComplete="new-password"
            disabled={readonly}
          />
        </div>
        <Button type="submit" disabled={pwBusy || readonly}>
          {pwBusy ? <Loader2 className="h-4 w-4 animate-spin" /> : null}
          Update password
        </Button>
      </form>
    </div>
  );
}
