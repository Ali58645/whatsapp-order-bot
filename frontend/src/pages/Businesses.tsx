import { useCallback, useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import {
  Archive,
  Building2,
  CheckCircle2,
  ChevronLeft,
  ChevronRight,
  Loader2,
  Pause,
  Play,
  Plus,
  Settings,
  ShieldAlert,
} from "lucide-react";
import { toast } from "sonner";
import {
  api,
  getRole,
  setTenantFilter,
  Tenant,
} from "../api";
import { Badge } from "../components/ui/badge";
import { Button } from "../components/ui/button";
import { Dialog, DialogContent } from "../components/ui/dialog";
import { Input, Label } from "../components/ui/input";
import { Skeleton } from "../components/ui/avatar";
import { cn } from "../lib/utils";

type WizardStep = 1 | 2 | 3 | 4;

type VerifyResult = {
  ok: boolean;
  verified_name?: string;
  display_phone_number?: string;
};

type CreateResult = {
  id: number;
  phone_number_id: string;
  name: string;
  flow_mode: string;
  status: string;
};

const STATUS_BADGE: Record<string, string> = {
  draft: "bg-amber-500/15 text-amber-400 ring-1 ring-amber-500/25",
  live: "bg-emerald-500/15 text-emerald-400 ring-1 ring-emerald-500/25",
  paused: "bg-orange-500/15 text-orange-400 ring-1 ring-orange-500/25",
  archived: "bg-zinc-500/15 text-zinc-400 ring-1 ring-zinc-500/25",
};

function statusLabel(s: string) {
  const map: Record<string, string> = {
    draft: "Draft",
    live: "Live",
    paused: "Paused",
    archived: "Archived",
  };
  return map[s?.toLowerCase()] || s || "Live";
}

function flowLabel(mode: string) {
  return mode === "order" ? "Order Taking" : "Lead Qualification";
}

export default function BusinessesPage() {
  const navigate = useNavigate();
  const isAdmin = getRole() === "admin";

  const [tenants, setTenants] = useState<Tenant[]>([]);
  const [loading, setLoading] = useState(true);
  const [busyId, setBusyId] = useState<number | null>(null);

  const [wizardOpen, setWizardOpen] = useState(false);
  const [step, setStep] = useState<WizardStep>(1);
  const [name, setName] = useState("");
  const [flowMode, setFlowMode] = useState<"lead" | "order">("lead");
  const [phoneNumberId, setPhoneNumberId] = useState("");
  const [businessWaId, setBusinessWaId] = useState("");
  const [ownerWhatsapp, setOwnerWhatsapp] = useState("");
  const [language, setLanguage] = useState("roman_urdu");
  const [verifying, setVerifying] = useState(false);
  const [verifyResult, setVerifyResult] = useState<VerifyResult | null>(null);
  const [verifyError, setVerifyError] = useState("");
  const [creating, setCreating] = useState(false);
  const [created, setCreated] = useState<CreateResult | null>(null);
  const [publishing, setPublishing] = useState(false);

  const load = useCallback(() => {
    setLoading(true);
    api<Tenant[]>("/api/dashboard/tenants", { tenant: false })
      .then(setTenants)
      .catch(() => setTenants([]))
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => {
    if (isAdmin) load();
  }, [isAdmin, load]);

  function resetWizard() {
    setStep(1);
    setName("");
    setFlowMode("lead");
    setPhoneNumberId("");
    setBusinessWaId("");
    setOwnerWhatsapp("");
    setLanguage("roman_urdu");
    setVerifyResult(null);
    setVerifyError("");
    setCreated(null);
  }

  function openWizard() {
    resetWizard();
    setWizardOpen(true);
  }

  function closeWizard() {
    setWizardOpen(false);
    if (created) load();
  }

  async function setStatus(id: number, status: string) {
    setBusyId(id);
    try {
      await api(`/api/dashboard/tenants/${id}/status`, {
        method: "POST",
        body: JSON.stringify({ status }),
        tenant: false,
      });
      toast.success(`Business ${statusLabel(status).toLowerCase()}`);
      load();
    } catch (e: unknown) {
      toast.error(e instanceof Error ? e.message : "Action failed");
    } finally {
      setBusyId(null);
    }
  }

  function openSettings(t: Tenant) {
    setTenantFilter(t.phone_number_id);
    window.dispatchEvent(new Event("tenant-change"));
    navigate("/settings");
  }

  async function verifyConnection() {
    if (!phoneNumberId.trim()) {
      toast.error("Enter a phone number ID first");
      return;
    }
    setVerifying(true);
    setVerifyError("");
    setVerifyResult(null);
    try {
      const res = await api<VerifyResult>("/api/dashboard/whatsapp/verify", {
        method: "POST",
        body: JSON.stringify({ phone_number_id: phoneNumberId.trim() }),
        tenant: false,
      });
      setVerifyResult(res);
      toast.success("Connection verified");
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : "Verification failed";
      setVerifyError(msg);
      toast.error(msg);
    } finally {
      setVerifying(false);
    }
  }

  async function createBusiness() {
    setCreating(true);
    try {
      const res = await api<CreateResult>("/api/dashboard/tenants", {
        method: "POST",
        body: JSON.stringify({
          name: name.trim(),
          flow_mode: flowMode,
          phone_number_id: phoneNumberId.trim(),
          business_wa_id: businessWaId.trim(),
          owner_whatsapp: ownerWhatsapp.trim(),
          greeting_language: language,
          publish: false,
        }),
        tenant: false,
      });
      setCreated(res);
      toast.success("Business created as draft");
    } catch (e: unknown) {
      toast.error(e instanceof Error ? e.message : "Create failed");
    } finally {
      setCreating(false);
    }
  }

  async function publishCreated() {
    if (!created) return;
    setPublishing(true);
    try {
      await api(`/api/dashboard/tenants/${created.id}/publish`, {
        method: "POST",
        tenant: false,
      });
      toast.success("Business published — now live");
      setCreated({ ...created, status: "live" });
      load();
    } catch (e: unknown) {
      toast.error(e instanceof Error ? e.message : "Publish failed");
    } finally {
      setPublishing(false);
    }
  }

  function canAdvance(): boolean {
    if (step === 1) return name.trim().length > 0;
    if (step === 2) return !!flowMode;
    if (step === 3) return phoneNumberId.trim().length > 0;
    return true;
  }

  if (!isAdmin) {
    return (
      <div className="flex flex-col items-center justify-center gap-4 py-24 text-center">
        <ShieldAlert className="h-12 w-12 text-muted-foreground" />
        <h1 className="text-xl font-bold">Admin only</h1>
        <p className="max-w-sm text-sm text-muted-foreground">
          Business management is restricted to administrators.
        </p>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">Businesses</h1>
          <p className="mt-1 text-sm text-muted-foreground">
            Manage WhatsApp tenants — create, pause, and configure
          </p>
        </div>
        <Button onClick={openWizard}>
          <Plus className="h-4 w-4" />
          New Business
        </Button>
      </div>

      {loading ? (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {[1, 2, 3].map((i) => (
            <Skeleton key={i} className="h-44 w-full rounded-2xl" />
          ))}
        </div>
      ) : tenants.length === 0 ? (
        <div className="rounded-2xl border border-dashed border-border bg-card/50 p-12 text-center">
          <Building2 className="mx-auto h-10 w-10 text-muted-foreground" />
          <p className="mt-3 text-sm text-muted-foreground">No businesses yet</p>
          <Button className="mt-4" onClick={openWizard}>
            <Plus className="h-4 w-4" />
            Create your first business
          </Button>
        </div>
      ) : (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {tenants.map((t) => {
            const st = (t.status || "live").toLowerCase();
            const statLabel = t.flow_mode === "order" ? "Orders today" : "Leads today";
            return (
              <article
                key={t.id}
                className="flex flex-col rounded-2xl border border-border bg-card p-5"
              >
                <div className="flex items-start justify-between gap-2">
                  <div className="min-w-0">
                    <h2 className="truncate font-semibold">{t.name}</h2>
                    <p className="mt-0.5 text-xs text-muted-foreground">
                      {flowLabel(t.flow_mode)}
                    </p>
                  </div>
                  <Badge className={STATUS_BADGE[st] || STATUS_BADGE.live}>
                    {statusLabel(st)}
                  </Badge>
                </div>

                <div className="mt-3 space-y-1 text-xs text-muted-foreground">
                  <p className="truncate font-mono">{t.phone_number_id}</p>
                  <p>
                    <span className="text-foreground">{t.stat_today ?? 0}</span>{" "}
                    {statLabel.toLowerCase()}
                  </p>
                </div>

                <div className="mt-4 flex flex-wrap gap-1.5 border-t border-border pt-4">
                  {st === "live" && (
                    <Button
                      variant="outline"
                      size="sm"
                      disabled={busyId === t.id}
                      onClick={() => setStatus(t.id, "paused")}
                    >
                      {busyId === t.id ? (
                        <Loader2 className="h-3.5 w-3.5 animate-spin" />
                      ) : (
                        <Pause className="h-3.5 w-3.5" />
                      )}
                      Pause
                    </Button>
                  )}
                  {st === "paused" && (
                    <Button
                      variant="outline"
                      size="sm"
                      disabled={busyId === t.id}
                      onClick={() => setStatus(t.id, "live")}
                    >
                      {busyId === t.id ? (
                        <Loader2 className="h-3.5 w-3.5 animate-spin" />
                      ) : (
                        <Play className="h-3.5 w-3.5" />
                      )}
                      Resume
                    </Button>
                  )}
                  {st !== "archived" && (
                    <Button
                      variant="outline"
                      size="sm"
                      disabled={busyId === t.id}
                      onClick={() => setStatus(t.id, "archived")}
                    >
                      <Archive className="h-3.5 w-3.5" />
                      Archive
                    </Button>
                  )}
                  <Button variant="soft" size="sm" onClick={() => openSettings(t)}>
                    <Settings className="h-3.5 w-3.5" />
                    Settings
                  </Button>
                </div>
              </article>
            );
          })}
        </div>
      )}

      <Dialog open={wizardOpen} onOpenChange={(o) => !o && closeWizard()}>
        <DialogContent className="max-h-[85vh] overflow-y-auto p-0 sm:max-w-md">
          <div className="border-b border-border px-5 py-4">
            <h2 className="text-lg font-semibold">
              {created ? "Business created" : "New Business"}
            </h2>
            {!created && (
              <p className="mt-0.5 text-xs text-muted-foreground">Step {step} of 4</p>
            )}
          </div>

          <div className="space-y-4 px-5 py-4">
            {created ? (
              <div className="space-y-4 text-center">
                <CheckCircle2 className="mx-auto h-12 w-12 text-emerald-400" />
                <div>
                  <p className="font-medium">{created.name}</p>
                  <p className="text-sm text-muted-foreground">
                    Created as draft — publish when ready to go live
                  </p>
                </div>
                <div className="flex flex-col gap-2">
                  {created.status !== "live" && (
                    <Button disabled={publishing} onClick={publishCreated}>
                      {publishing ? (
                        <Loader2 className="h-4 w-4 animate-spin" />
                      ) : (
                        "Publish"
                      )}
                    </Button>
                  )}
                  <Button
                    variant="outline"
                    onClick={() => {
                      openSettings(created as unknown as Tenant);
                      closeWizard();
                    }}
                  >
                    Open Settings
                  </Button>
                  <Button variant="ghost" onClick={closeWizard}>
                    Done
                  </Button>
                </div>
              </div>
            ) : (
              <>
                {step === 1 && (
                  <div>
                    <Label>Business name</Label>
                    <Input
                      className="mt-1.5"
                      placeholder="e.g. Bahi POS Demo"
                      value={name}
                      onChange={(e) => setName(e.target.value)}
                      autoFocus
                    />
                  </div>
                )}

                {step === 2 && (
                  <div className="space-y-2">
                    <Label>Flow type</Label>
                    {(
                      [
                        { id: "lead" as const, label: "Lead Qualification" },
                        { id: "order" as const, label: "Order Taking" },
                      ] as const
                    ).map((opt) => (
                      <button
                        key={opt.id}
                        type="button"
                        onClick={() => setFlowMode(opt.id)}
                        className={cn(
                          "flex w-full items-center rounded-xl border px-4 py-3 text-left text-sm transition",
                          flowMode === opt.id
                            ? "border-primary bg-primary/10 text-foreground"
                            : "border-border hover:bg-muted/50"
                        )}
                      >
                        {opt.label}
                      </button>
                    ))}
                  </div>
                )}

                {step === 3 && (
                  <div className="space-y-4">
                    <div>
                      <Label>Phone number ID</Label>
                      <Input
                        className="mt-1.5 font-mono text-xs"
                        placeholder="Meta phone_number_id"
                        value={phoneNumberId}
                        onChange={(e) => {
                          setPhoneNumberId(e.target.value);
                          setVerifyResult(null);
                          setVerifyError("");
                        }}
                      />
                    </div>
                    <div>
                      <Label>Business WA ID</Label>
                      <Input
                        className="mt-1.5 font-mono text-xs"
                        value={businessWaId}
                        onChange={(e) => setBusinessWaId(e.target.value)}
                      />
                    </div>
                    <div>
                      <Label>Owner WhatsApp</Label>
                      <Input
                        className="mt-1.5 font-mono text-xs"
                        placeholder="923001234567"
                        value={ownerWhatsapp}
                        onChange={(e) => setOwnerWhatsapp(e.target.value)}
                      />
                    </div>
                    <Button
                      type="button"
                      variant="outline"
                      className="w-full"
                      disabled={verifying || !phoneNumberId.trim()}
                      onClick={verifyConnection}
                    >
                      {verifying ? (
                        <Loader2 className="h-4 w-4 animate-spin" />
                      ) : (
                        "Verify connection"
                      )}
                    </Button>
                    {verifyResult && (
                      <div className="rounded-lg bg-emerald-500/10 px-3 py-2 text-sm text-emerald-400">
                        {verifyResult.verified_name && (
                          <p>{verifyResult.verified_name}</p>
                        )}
                        {verifyResult.display_phone_number && (
                          <p className="text-xs opacity-80">
                            {verifyResult.display_phone_number}
                          </p>
                        )}
                      </div>
                    )}
                    {verifyError && (
                      <p className="text-sm text-destructive">{verifyError}</p>
                    )}
                  </div>
                )}

                {step === 4 && (
                  <div>
                    <Label>Default language</Label>
                    <select
                      className="mt-1.5 h-10 w-full rounded-lg border border-input bg-background px-3 text-sm focus-ring"
                      value={language}
                      onChange={(e) => setLanguage(e.target.value)}
                    >
                      <option value="roman_urdu">Roman Urdu</option>
                      <option value="english">English</option>
                    </select>
                    <p className="mt-3 text-xs text-muted-foreground">
                      Business will be created as a draft. You can publish after reviewing
                      settings.
                    </p>
                  </div>
                )}
              </>
            )}
          </div>

          {!created && (
            <div className="flex items-center justify-between border-t border-border px-5 py-4">
              <Button
                variant="ghost"
                size="sm"
                disabled={step === 1}
                onClick={() => setStep((s) => (s > 1 ? ((s - 1) as WizardStep) : s))}
              >
                <ChevronLeft className="h-4 w-4" />
                Back
              </Button>
              {step < 4 ? (
                <Button
                  size="sm"
                  disabled={!canAdvance()}
                  onClick={() => setStep((s) => (s < 4 ? ((s + 1) as WizardStep) : s))}
                >
                  Next
                  <ChevronRight className="h-4 w-4" />
                </Button>
              ) : (
                <Button size="sm" disabled={creating} onClick={createBusiness}>
                  {creating ? (
                    <Loader2 className="h-4 w-4 animate-spin" />
                  ) : (
                    "Create"
                  )}
                </Button>
              )}
            </div>
          )}
        </DialogContent>
      </Dialog>
    </div>
  );
}
