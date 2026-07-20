import { useCallback, useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import {
  Archive,
  Building2,
  Check,
  CheckCircle2,
  ChevronLeft,
  ChevronRight,
  Eye,
  Loader2,
  Pause,
  Play,
  Plus,
  RotateCcw,
  Search,
  Settings,
  ShieldAlert,
  Trash2,
} from "lucide-react";
import { toast } from "sonner";
import {
  api,
  enterViewAs,
  fetchTenants,
  getRole,
  OnboardingChecklist,
  Overview as OverviewData,
  setTenantFilter,
  Tenant,
  TenantStatusCounts,
} from "../api";
import { Badge } from "../components/ui/badge";
import { Button } from "../components/ui/button";
import { Dialog, DialogContent } from "../components/ui/dialog";
import { Input, Label } from "../components/ui/input";
import { Skeleton } from "../components/ui/avatar";
import { TemplatePicker } from "../components/TemplatePicker";
import { cn } from "../lib/utils";

type WizardStep = 1 | 2 | 3 | 4 | 5;

type VerifyResult = {
  ok: boolean;
  verified_name?: string;
  display_phone_number?: string;
  subscribed_apps?: boolean | null;
  subscribed_apps_fixed?: boolean;
};

type DraftResult = {
  id: number;
  phone_number_id: string;
  name: string;
  flow_mode: string;
  status: string;
  template_id?: string;
  checklist?: OnboardingChecklist;
};

const STEPS: { id: WizardStep; label: string }[] = [
  { id: 1, label: "Basics" },
  { id: 2, label: "WhatsApp" },
  { id: 3, label: "Content" },
  { id: 4, label: "Sheet" },
  { id: 5, label: "Go live" },
];

const STATUS_BADGE: Record<string, string> = {
  draft: "bg-amber-500/15 text-amber-400 ring-1 ring-amber-500/25",
  live: "bg-emerald-500/15 text-emerald-400 ring-1 ring-emerald-500/25",
  paused: "bg-orange-500/15 text-orange-400 ring-1 ring-orange-500/25",
  archived: "bg-zinc-500/15 text-zinc-400 ring-1 ring-zinc-500/25",
};

const FILTER_TABS: { id: "all" | "live" | "paused" | "archived"; label: string }[] = [
  { id: "all", label: "All" },
  { id: "live", label: "Live" },
  { id: "paused", label: "Paused" },
  { id: "archived", label: "Archived" },
];

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

function ChecklistView({ checklist }: { checklist?: OnboardingChecklist | null }) {
  if (!checklist?.items?.length) return null;
  return (
    <ul className="mt-3 space-y-1.5">
      {checklist.items.map((item) => (
        <li key={item.id} className="flex items-center gap-2 text-xs">
          <span
            className={cn(
              "flex h-4 w-4 items-center justify-center rounded-full",
              item.done
                ? "bg-emerald-500/20 text-emerald-400"
                : "bg-muted text-muted-foreground"
            )}
          >
            {item.done ? <Check className="h-2.5 w-2.5" /> : null}
          </span>
          <span className={item.done ? "text-foreground" : "text-muted-foreground"}>
            {item.label}
          </span>
        </li>
      ))}
    </ul>
  );
}

export default function BusinessesPage() {
  const navigate = useNavigate();
  const isAdmin = getRole() === "admin";

  const [tenants, setTenants] = useState<Tenant[]>([]);
  const [counts, setCounts] = useState<TenantStatusCounts>({
    all: 0,
    live: 0,
    paused: 0,
    archived: 0,
    draft: 0,
  });
  const [filter, setFilter] = useState<"all" | "live" | "paused" | "archived">("live");
  const [search, setSearch] = useState("");
  const [loading, setLoading] = useState(true);
  const [busyId, setBusyId] = useState<number | null>(null);
  const [archiveTarget, setArchiveTarget] = useState<Tenant | null>(null);
  const [deleteTarget, setDeleteTarget] = useState<Tenant | null>(null);
  const [deleteConfirmName, setDeleteConfirmName] = useState("");
  const [overview, setOverview] = useState<OverviewData | null>(null);
  const [viewBusyId, setViewBusyId] = useState<number | null>(null);

  const [wizardOpen, setWizardOpen] = useState(false);
  const [step, setStep] = useState<WizardStep>(1);

  // Step 1
  const [name, setName] = useState("");
  const [flowMode, setFlowMode] = useState<"lead" | "order">("lead");
  const [language, setLanguage] = useState("roman_urdu");
  const [ownerWhatsapp, setOwnerWhatsapp] = useState("");

  // Step 2
  const [phoneNumberId, setPhoneNumberId] = useState("");
  const [wabaId, setWabaId] = useState("");
  const [businessWaId, setBusinessWaId] = useState("");
  const [verifying, setVerifying] = useState(false);
  const [verifyResult, setVerifyResult] = useState<VerifyResult | null>(null);
  const [verifyError, setVerifyError] = useState("");

  // Step 3
  const [templateId, setTemplateId] = useState("pos_lead");

  // Step 4
  const [sheetUrl, setSheetUrl] = useState("");
  const [sheetTesting, setSheetTesting] = useState(false);
  const [sheetOk, setSheetOk] = useState(false);
  const [sheetMsg, setSheetMsg] = useState("");

  // Draft / activate
  const [draftId, setDraftId] = useState<number | null>(null);
  const [saving, setSaving] = useState(false);
  const [activating, setActivating] = useState(false);
  const [created, setCreated] = useState<DraftResult | null>(null);

  const load = useCallback(() => {
    setLoading(true);
    Promise.all([
      fetchTenants(),
      api<OverviewData>("/api/dashboard/overview", { tenant: false }).catch(() => null),
    ])
      .then(([list, ov]) => {
        setTenants(list.items);
        setCounts(list.counts);
        setOverview(ov);
      })
      .catch(() => {
        setTenants([]);
        setCounts({ all: 0, live: 0, paused: 0, archived: 0, draft: 0 });
        setOverview(null);
      })
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => {
    if (isAdmin) load();
  }, [isAdmin, load]);

  const visible = useMemo(() => {
    const q = search.trim().toLowerCase();
    return tenants.filter((t) => {
      const st = (t.status || "live").toLowerCase();
      if (filter === "archived") {
        if (st !== "archived") return false;
      } else if (filter === "live") {
        if (st !== "live") return false;
      } else if (filter === "paused") {
        if (st !== "paused") return false;
      } else if (st === "archived") {
        return false; // All tab excludes archived
      }
      if (q && !(t.name || "").toLowerCase().includes(q)) return false;
      return true;
    });
  }, [tenants, filter, search]);

  function resetWizard() {
    setStep(1);
    setName("");
    setFlowMode("lead");
    setLanguage("roman_urdu");
    setOwnerWhatsapp("");
    setPhoneNumberId("");
    setWabaId("");
    setBusinessWaId("");
    setVerifyResult(null);
    setVerifyError("");
    setTemplateId("pos_lead");
    setSheetUrl("");
    setSheetOk(false);
    setSheetMsg("");
    setDraftId(null);
    setCreated(null);
  }

  function openWizard() {
    resetWizard();
    setWizardOpen(true);
  }

  function closeWizard() {
    setWizardOpen(false);
    if (created || draftId) load();
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

  async function confirmArchive() {
    if (!archiveTarget) return;
    const id = archiveTarget.id;
    setArchiveTarget(null);
    await setStatus(id, "archived");
  }

  async function confirmDelete() {
    if (!deleteTarget) return;
    setBusyId(deleteTarget.id);
    try {
      await api(`/api/dashboard/tenants/${deleteTarget.id}`, {
        method: "DELETE",
        body: JSON.stringify({ confirm_name: deleteConfirmName }),
        tenant: false,
      });
      toast.success("Business permanently deleted");
      setDeleteTarget(null);
      setDeleteConfirmName("");
      load();
    } catch (e: unknown) {
      toast.error(e instanceof Error ? e.message : "Delete failed");
    } finally {
      setBusyId(null);
    }
  }

  function openSettings(t: Tenant) {
    setTenantFilter(t.phone_number_id);
    window.dispatchEvent(new Event("tenant-change"));
    navigate("/settings");
  }

  async function viewAsTenant(t: Tenant) {
    setViewBusyId(t.id);
    try {
      await enterViewAs(t.id);
      navigate("/", { replace: true });
      window.location.reload();
    } catch (e: unknown) {
      toast.error(e instanceof Error ? e.message : "View as failed");
      setViewBusyId(null);
    }
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
        body: JSON.stringify({
          phone_number_id: phoneNumberId.trim(),
          waba_id: wabaId.trim() || undefined,
        }),
        tenant: false,
      });
      setVerifyResult(res);
      if (!businessWaId.trim() && res.display_phone_number) {
        setBusinessWaId(res.display_phone_number.replace(/\D/g, ""));
      }
      const bits = [res.verified_name || "Connected"];
      if (res.subscribed_apps_fixed) bits.push("subscribed_apps fixed");
      else if (res.subscribed_apps) bits.push("webhooks subscribed");
      toast.success(bits.join(" · "));
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : "Verification failed";
      setVerifyError(msg);
      toast.error(msg);
    } finally {
      setVerifying(false);
    }
  }

  async function testSheet() {
    if (!sheetUrl.trim()) {
      toast.error("Paste a Google Sheet URL first");
      return;
    }
    setSheetTesting(true);
    setSheetOk(false);
    setSheetMsg("");
    try {
      const res = await api<{ ok: boolean; title?: string; write_access?: boolean }>(
        "/api/dashboard/sheet/test",
        {
          method: "POST",
          body: JSON.stringify({ sheet_url: sheetUrl.trim() }),
          tenant: false,
        }
      );
      setSheetOk(true);
      setSheetMsg(
        res.title
          ? `Write OK — “${res.title}”`
          : "Write access confirmed"
      );
      toast.success("Sheet access OK");
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : "Sheet test failed";
      setSheetOk(false);
      setSheetMsg(msg);
      toast.error(msg);
    } finally {
      setSheetTesting(false);
    }
  }

  function draftPayload() {
    return {
      tenant_id: draftId || undefined,
      name: name.trim(),
      flow_mode: flowMode,
      phone_number_id: phoneNumberId.trim(),
      business_wa_id: businessWaId.trim(),
      owner_whatsapp: ownerWhatsapp.trim(),
      greeting_language: language,
      template_id: templateId,
      waba_id: wabaId.trim(),
      sheet_url: sheetUrl.trim(),
      connection_verified: Boolean(verifyResult?.ok),
      subscribed_apps: verifyResult?.subscribed_apps ?? null,
      sheet_tested: sheetOk,
      verified_name: verifyResult?.verified_name || "",
    };
  }

  async function saveDraft(silent = false): Promise<DraftResult | null> {
    setSaving(true);
    try {
      const res = await api<DraftResult>("/api/dashboard/onboarding/draft", {
        method: "POST",
        body: JSON.stringify(draftPayload()),
        tenant: false,
      });
      setDraftId(res.id);
      setCreated(res);
      if (!silent) toast.success("Draft saved");
      return res;
    } catch (e: unknown) {
      toast.error(e instanceof Error ? e.message : "Save failed");
      return null;
    } finally {
      setSaving(false);
    }
  }

  async function activate() {
    setActivating(true);
    try {
      let id = draftId;
      if (!id) {
        const draft = await saveDraft(true);
        if (!draft) return;
        id = draft.id;
      } else {
        const draft = await saveDraft(true);
        if (!draft) return;
        id = draft.id;
      }
      const res = await api<{
        status: string;
        test_message_sent: boolean;
        test_error?: string | null;
        checklist?: OnboardingChecklist;
      }>(`/api/dashboard/onboarding/${id}/activate`, {
        method: "POST",
        body: JSON.stringify({ send_test: true }),
        tenant: false,
      });
      setCreated((prev) =>
        prev
          ? { ...prev, status: "live", checklist: res.checklist }
          : prev
      );
      if (res.test_message_sent) {
        toast.success("Live — test message sent to owner");
      } else if (res.test_error) {
        toast.success("Live — but test message failed");
        toast.error(res.test_error);
      } else {
        toast.success("Business is live");
      }
      load();
    } catch (e: unknown) {
      toast.error(e instanceof Error ? e.message : "Activate failed");
    } finally {
      setActivating(false);
    }
  }

  function canAdvance(): boolean {
    if (step === 1) {
      return name.trim().length > 0 && ownerWhatsapp.trim().length >= 8;
    }
    if (step === 2) {
      return (
        phoneNumberId.trim().length > 0 &&
        ownerWhatsapp.trim().length >= 8 &&
        Boolean(verifyResult?.ok)
      );
    }
    if (step === 3) return Boolean(templateId);
    if (step === 4) return true; // sheet optional
    return true;
  }

  async function goNext() {
    if (!canAdvance()) {
      if (step === 2 && !verifyResult?.ok) {
        toast.error("Test connection before continuing");
      }
      return;
    }
    if (step < 5) setStep((step + 1) as WizardStep);
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
            Platform console — onboard, monitor health, and open support view-as
          </p>
        </div>
        <Button onClick={openWizard}>
          <Plus className="h-4 w-4" />
          New Business
        </Button>
      </div>

      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <div className="rounded-2xl border border-border bg-card px-4 py-3">
          <p className="text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">
            Leads today
          </p>
          <p className="mt-1 text-2xl font-bold tabular-nums">{overview?.leads_today ?? 0}</p>
        </div>
        <div className="rounded-2xl border border-border bg-card px-4 py-3">
          <p className="text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">
            Orders today
          </p>
          <p className="mt-1 text-2xl font-bold tabular-nums">{overview?.orders_today ?? 0}</p>
        </div>
        <div className="rounded-2xl border border-border bg-card px-4 py-3">
          <p className="text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">
            Live businesses
          </p>
          <p className="mt-1 text-2xl font-bold tabular-nums">{counts.live}</p>
        </div>
        <div className="rounded-2xl border border-border bg-card px-4 py-3">
          <p className="text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">
            Active conversations
          </p>
          <p className="mt-1 text-2xl font-bold tabular-nums">
            {overview?.active_conversations ?? 0}
          </p>
        </div>
      </div>

      <div className="flex flex-wrap items-center gap-2">
        {FILTER_TABS.map((tab) => {
          const n =
            tab.id === "all"
              ? counts.all - counts.archived
              : counts[tab.id] ?? 0;
          return (
            <button
              key={tab.id}
              type="button"
              onClick={() => setFilter(tab.id)}
              className={cn(
                "rounded-full px-3 py-1.5 text-xs font-semibold transition",
                filter === tab.id
                  ? "bg-primary text-primary-foreground"
                  : "bg-muted/50 text-muted-foreground hover:bg-muted"
              )}
            >
              {tab.label}
              <span className="ml-1.5 tabular-nums opacity-80">{n}</span>
            </button>
          );
        })}
        <div className="relative ml-auto min-w-[200px] flex-1 sm:max-w-xs">
          <Search className="absolute left-2.5 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-muted-foreground" />
          <Input
            className="h-9 pl-8"
            placeholder="Search by name…"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
        </div>
      </div>

      {loading ? (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {[1, 2, 3].map((i) => (
            <Skeleton key={i} className="h-52 w-full rounded-2xl" />
          ))}
        </div>
      ) : visible.length === 0 ? (
        <div className="rounded-2xl border border-dashed border-border bg-card/50 p-12 text-center">
          <Building2 className="mx-auto h-10 w-10 text-muted-foreground" />
          <p className="mt-3 text-sm text-muted-foreground">
            {tenants.length === 0 ? "No businesses yet" : "No businesses in this filter"}
          </p>
          {tenants.length === 0 && (
            <Button className="mt-4" onClick={openWizard}>
              <Plus className="h-4 w-4" />
              Create your first business
            </Button>
          )}
        </div>
      ) : (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {visible.map((t) => {
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
                      {t.template_id ? ` · ${t.template_id}` : ""}
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

                {st !== "archived" && (
                  <div className="mt-2 rounded-xl border border-border/60 bg-muted/20 px-3 py-2">
                    <p className="text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">
                      Onboarding
                      {t.checklist
                        ? ` · ${t.checklist.done_count}/${t.checklist.total_count}`
                        : ""}
                    </p>
                    <ChecklistView checklist={t.checklist} />
                  </div>
                )}

                <div className="mt-4 flex flex-wrap gap-1.5 border-t border-border pt-4">
                  {(st === "live" || st === "paused") && (
                    <Button
                      variant="soft"
                      size="sm"
                      disabled={viewBusyId === t.id}
                      onClick={() => void viewAsTenant(t)}
                    >
                      {viewBusyId === t.id ? (
                        <Loader2 className="h-3.5 w-3.5 animate-spin" />
                      ) : (
                        <Eye className="h-3.5 w-3.5" />
                      )}
                      View as
                    </Button>
                  )}
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
                  {st === "archived" && (
                    <Button
                      variant="outline"
                      size="sm"
                      disabled={busyId === t.id}
                      onClick={() => setStatus(t.id, "paused")}
                    >
                      {busyId === t.id ? (
                        <Loader2 className="h-3.5 w-3.5 animate-spin" />
                      ) : (
                        <RotateCcw className="h-3.5 w-3.5" />
                      )}
                      Restore
                    </Button>
                  )}
                  {st !== "archived" && (
                    <Button
                      variant="outline"
                      size="sm"
                      disabled={busyId === t.id}
                      onClick={() => setArchiveTarget(t)}
                    >
                      <Archive className="h-3.5 w-3.5" />
                      Archive
                    </Button>
                  )}
                  {st === "archived" && (
                    <Button
                      variant="outline"
                      size="sm"
                      className="text-destructive"
                      disabled={busyId === t.id}
                      onClick={() => {
                        setDeleteConfirmName("");
                        setDeleteTarget(t);
                      }}
                    >
                      <Trash2 className="h-3.5 w-3.5" />
                      Delete
                    </Button>
                  )}
                  {(st === "live" || st === "draft") && (
                    <Button variant="outline" size="sm" onClick={() => openSettings(t)}>
                      <Settings className="h-3.5 w-3.5" />
                      Wiring
                    </Button>
                  )}
                </div>
              </article>
            );
          })}
        </div>
      )}

      <Dialog open={!!archiveTarget} onOpenChange={(o) => !o && setArchiveTarget(null)}>
        <DialogContent className="max-w-md p-0">
          <div className="border-b border-border px-5 py-4">
            <h2 className="text-lg font-semibold">Archive business?</h2>
          </div>
          <div className="space-y-3 px-5 py-4 text-sm text-muted-foreground">
            <p>
              This stops the bot and hides{" "}
              <span className="font-medium text-foreground">{archiveTarget?.name}</span>.
              Data is kept and can be restored.
            </p>
          </div>
          <div className="flex justify-end gap-2 border-t border-border px-5 py-3">
            <Button variant="ghost" onClick={() => setArchiveTarget(null)}>
              Cancel
            </Button>
            <Button onClick={() => void confirmArchive()}>Archive</Button>
          </div>
        </DialogContent>
      </Dialog>

      <Dialog
        open={!!deleteTarget}
        onOpenChange={(o) => {
          if (!o) {
            setDeleteTarget(null);
            setDeleteConfirmName("");
          }
        }}
      >
        <DialogContent className="max-w-md p-0">
          <div className="border-b border-border px-5 py-4">
            <h2 className="text-lg font-semibold text-destructive">Delete permanently</h2>
          </div>
          <div className="space-y-3 px-5 py-4 text-sm">
            <p className="text-muted-foreground">
              This irreversibly removes all leads, orders, conversations, and config for{" "}
              <span className="font-medium text-foreground">{deleteTarget?.name}</span>.
            </p>
            <div>
              <Label>Type the business name to confirm</Label>
              <Input
                className="mt-1.5"
                value={deleteConfirmName}
                onChange={(e) => setDeleteConfirmName(e.target.value)}
                placeholder={deleteTarget?.name}
                autoComplete="off"
              />
            </div>
          </div>
          <div className="flex justify-end gap-2 border-t border-border px-5 py-3">
            <Button
              variant="ghost"
              onClick={() => {
                setDeleteTarget(null);
                setDeleteConfirmName("");
              }}
            >
              Cancel
            </Button>
            <Button
              variant="destructive"
              disabled={
                !deleteTarget ||
                deleteConfirmName.trim() !== (deleteTarget.name || "").trim() ||
                busyId === deleteTarget.id
              }
              onClick={() => void confirmDelete()}
            >
              {busyId === deleteTarget?.id ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : (
                <Trash2 className="h-4 w-4" />
              )}
              Delete forever
            </Button>
          </div>
        </DialogContent>
      </Dialog>

      <Dialog open={wizardOpen} onOpenChange={(o) => !o && closeWizard()}>
        <DialogContent className="max-h-[90vh] overflow-y-auto p-0 sm:max-w-lg">
          <div className="border-b border-border px-5 py-4">
            <h2 className="text-lg font-semibold">Onboard business</h2>
            <p className="mt-0.5 text-xs text-muted-foreground">
              Zero to live bot — step {step} of {STEPS.length}
            </p>
            <div className="mt-4 flex gap-1">
              {STEPS.map((s) => (
                <button
                  key={s.id}
                  type="button"
                  onClick={() => s.id < step && setStep(s.id)}
                  className={cn(
                    "flex-1 rounded-full px-1 py-1.5 text-[10px] font-semibold uppercase tracking-wide transition-colors",
                    s.id === step
                      ? "bg-primary text-primary-foreground"
                      : s.id < step
                        ? "bg-primary/20 text-primary"
                        : "bg-muted text-muted-foreground"
                  )}
                >
                  {s.label}
                </button>
              ))}
            </div>
          </div>

          <div className="space-y-4 px-5 py-4">
            {step === 1 && (
              <>
                <div>
                  <Label htmlFor="biz-name">Business name</Label>
                  <Input
                    id="biz-name"
                    value={name}
                    onChange={(e) => setName(e.target.value)}
                    placeholder="e.g. Ali Grocery"
                    className="mt-1.5"
                  />
                </div>
                <div>
                  <Label>Flow type</Label>
                  <div className="mt-1.5 grid grid-cols-2 gap-2">
                    {(["lead", "order"] as const).map((m) => (
                      <button
                        key={m}
                        type="button"
                        onClick={() => {
                          setFlowMode(m);
                          setTemplateId(m === "order" ? "restaurant" : "pos_lead");
                        }}
                        className={cn(
                          "rounded-xl border px-3 py-3 text-left text-sm transition-colors",
                          flowMode === m
                            ? "border-primary bg-primary/10"
                            : "border-border hover:bg-muted/40"
                        )}
                      >
                        <p className="font-semibold">
                          {m === "lead" ? "Lead" : "Order"}
                        </p>
                        <p className="mt-0.5 text-xs text-muted-foreground">
                          {m === "lead"
                            ? "Qualify & book demos"
                            : "Menu + cart on WhatsApp"}
                        </p>
                      </button>
                    ))}
                  </div>
                </div>
                <div>
                  <Label htmlFor="lang">Language</Label>
                  <select
                    id="lang"
                    value={language}
                    onChange={(e) => setLanguage(e.target.value)}
                    className="mt-1.5 flex h-10 w-full rounded-lg border border-input bg-background px-3 text-sm"
                  >
                    <option value="roman_urdu">Roman Urdu</option>
                    <option value="english">English</option>
                  </select>
                </div>
                <div>
                  <Label htmlFor="owner-wa">Owner WhatsApp</Label>
                  <Input
                    id="owner-wa"
                    value={ownerWhatsapp}
                    onChange={(e) => setOwnerWhatsapp(e.target.value)}
                    placeholder="92300…"
                    className="mt-1.5"
                  />
                  <p className="mt-1 text-[11px] text-muted-foreground">
                    Receives lead cards / order slips and the go-live test message
                  </p>
                </div>
              </>
            )}

            {step === 2 && (
              <>
                <div>
                  <Label htmlFor="phone-id">Phone number ID</Label>
                  <Input
                    id="phone-id"
                    value={phoneNumberId}
                    onChange={(e) => {
                      setPhoneNumberId(e.target.value);
                      setVerifyResult(null);
                    }}
                    placeholder="Meta phone_number_id"
                    className="mt-1.5 font-mono text-sm"
                  />
                </div>
                <div>
                  <Label htmlFor="waba">WABA ID</Label>
                  <Input
                    id="waba"
                    value={wabaId}
                    onChange={(e) => {
                      setWabaId(e.target.value);
                      setVerifyResult(null);
                    }}
                    placeholder="WhatsApp Business Account ID"
                    className="mt-1.5 font-mono text-sm"
                  />
                  <p className="mt-1 text-[11px] text-muted-foreground">
                    Used to auto-check and fix subscribed_apps
                  </p>
                </div>
                <div>
                  <Label htmlFor="biz-wa">Business WA ID (digits)</Label>
                  <Input
                    id="biz-wa"
                    value={businessWaId}
                    onChange={(e) => setBusinessWaId(e.target.value)}
                    placeholder="Auto-filled after verify when possible"
                    className="mt-1.5 font-mono text-sm"
                  />
                </div>
                <div>
                  <Label htmlFor="owner-wa-2">Owner WhatsApp</Label>
                  <Input
                    id="owner-wa-2"
                    value={ownerWhatsapp}
                    onChange={(e) => setOwnerWhatsapp(e.target.value)}
                    className="mt-1.5"
                  />
                </div>
                <Button
                  variant="outline"
                  className="w-full"
                  disabled={verifying || !phoneNumberId.trim()}
                  onClick={() => void verifyConnection()}
                >
                  {verifying ? (
                    <Loader2 className="h-4 w-4 animate-spin" />
                  ) : (
                    <CheckCircle2 className="h-4 w-4" />
                  )}
                  Test connection
                </Button>
                {verifyResult?.ok && (
                  <div className="rounded-xl border border-emerald-500/30 bg-emerald-500/10 px-3 py-2 text-sm">
                    <p className="font-medium text-emerald-400">
                      {verifyResult.verified_name || "Verified"}
                    </p>
                    {verifyResult.display_phone_number && (
                      <p className="text-xs text-muted-foreground">
                        {verifyResult.display_phone_number}
                      </p>
                    )}
                    <p className="mt-1 text-xs text-muted-foreground">
                      Webhooks:{" "}
                      {verifyResult.subscribed_apps
                        ? verifyResult.subscribed_apps_fixed
                          ? "subscribed (auto-fixed)"
                          : "subscribed ✓"
                        : wabaId
                          ? "unknown / failed"
                          : "skipped (add WABA ID)"}
                    </p>
                  </div>
                )}
                {verifyError && (
                  <p className="text-sm text-destructive">{verifyError}</p>
                )}
              </>
            )}

            {step === 3 && (
              <>
                <p className="text-sm text-muted-foreground">
                  Pick a starter template. You can edit copy, options, and menu later in
                  Settings.
                </p>
                <TemplatePicker
                  selectedId={templateId}
                  flowMode={flowMode}
                  onSelect={(id, tmpl) => {
                    setTemplateId(id);
                    if (tmpl?.flow_mode === "lead" || tmpl?.flow_mode === "order") {
                      setFlowMode(tmpl.flow_mode);
                    }
                  }}
                />
              </>
            )}

            {step === 4 && (
              <>
                <p className="text-sm text-muted-foreground">
                  Optional — paste a Google Sheet URL shared with the service account.
                </p>
                <div>
                  <Label htmlFor="sheet">Google Sheet URL</Label>
                  <Input
                    id="sheet"
                    value={sheetUrl}
                    onChange={(e) => {
                      setSheetUrl(e.target.value);
                      setSheetOk(false);
                      setSheetMsg("");
                    }}
                    placeholder="https://docs.google.com/spreadsheets/d/…"
                    className="mt-1.5"
                  />
                </div>
                <Button
                  variant="outline"
                  className="w-full"
                  disabled={sheetTesting || !sheetUrl.trim()}
                  onClick={() => void testSheet()}
                >
                  {sheetTesting ? (
                    <Loader2 className="h-4 w-4 animate-spin" />
                  ) : (
                    <CheckCircle2 className="h-4 w-4" />
                  )}
                  Test write access
                </Button>
                {sheetMsg && (
                  <p
                    className={cn(
                      "text-sm",
                      sheetOk ? "text-emerald-400" : "text-destructive"
                    )}
                  >
                    {sheetMsg}
                  </p>
                )}
                <p className="text-[11px] text-muted-foreground">
                  Skip this step if the client has no sheet yet.
                </p>
              </>
            )}

            {step === 5 && (
              <>
                {created?.status === "live" ? (
                  <div className="rounded-xl border border-emerald-500/30 bg-emerald-500/10 p-4 text-center">
                    <CheckCircle2 className="mx-auto h-8 w-8 text-emerald-400" />
                    <p className="mt-2 font-semibold">You’re live</p>
                    <p className="mt-1 text-sm text-muted-foreground">
                      {created.name} is routable now — no redeploy needed.
                    </p>
                    {created.checklist && (
                      <div className="mt-3 text-left">
                        <ChecklistView checklist={created.checklist} />
                      </div>
                    )}
                    <Button
                      className="mt-4"
                      onClick={() => {
                        closeWizard();
                        if (created) {
                          openSettings({
                            id: created.id,
                            phone_number_id: created.phone_number_id,
                            name: created.name,
                            flow_mode: created.flow_mode,
                          });
                        }
                      }}
                    >
                      Open Settings
                    </Button>
                  </div>
                ) : (
                  <>
                    <div className="space-y-2 rounded-xl border border-border bg-muted/20 p-4 text-sm">
                      <p>
                        <span className="text-muted-foreground">Name · </span>
                        {name || "—"}
                      </p>
                      <p>
                        <span className="text-muted-foreground">Flow · </span>
                        {flowLabel(flowMode)}
                      </p>
                      <p>
                        <span className="text-muted-foreground">Template · </span>
                        {templateId}
                      </p>
                      <p>
                        <span className="text-muted-foreground">Phone ID · </span>
                        <span className="font-mono text-xs">{phoneNumberId || "—"}</span>
                      </p>
                      <p>
                        <span className="text-muted-foreground">Owner · </span>
                        {ownerWhatsapp || "—"}
                      </p>
                      <p>
                        <span className="text-muted-foreground">Connection · </span>
                        {verifyResult?.ok
                          ? verifyResult.verified_name || "Verified"
                          : "Not verified"}
                      </p>
                      <p>
                        <span className="text-muted-foreground">Sheet · </span>
                        {sheetUrl
                          ? sheetOk
                            ? "Tested ✓"
                            : "Provided (not tested)"
                          : "Skipped"}
                      </p>
                    </div>
                    <p className="text-xs text-muted-foreground">
                      Activate creates the tenant as Live, seeds the template, and sends a
                      test WhatsApp to the owner.
                    </p>
                  </>
                )}
              </>
            )}
          </div>

          {!(step === 5 && created?.status === "live") && (
            <div className="flex flex-wrap items-center justify-between gap-2 border-t border-border px-5 py-3">
              <Button
                variant="ghost"
                size="sm"
                disabled={step === 1 || saving || activating}
                onClick={() => setStep((step - 1) as WizardStep)}
              >
                <ChevronLeft className="h-4 w-4" />
                Back
              </Button>
              <div className="flex gap-2">
                <Button
                  variant="outline"
                  size="sm"
                  disabled={saving || activating || !name.trim() || !phoneNumberId.trim()}
                  onClick={() => void saveDraft()}
                >
                  {saving ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : null}
                  Save draft
                </Button>
                {step < 5 ? (
                  <Button size="sm" disabled={!canAdvance()} onClick={() => void goNext()}>
                    Next
                    <ChevronRight className="h-4 w-4" />
                  </Button>
                ) : (
                  <Button
                    size="sm"
                    disabled={activating || !canAdvance() || !verifyResult?.ok}
                    onClick={() => void activate()}
                  >
                    {activating ? (
                      <Loader2 className="h-3.5 w-3.5 animate-spin" />
                    ) : null}
                    Activate
                  </Button>
                )}
              </div>
            </div>
          )}
        </DialogContent>
      </Dialog>
    </div>
  );
}
