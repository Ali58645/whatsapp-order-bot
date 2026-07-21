import { FormEvent, useCallback, useEffect, useMemo, useState } from "react";
import { Loader2, Save, LayoutTemplate } from "lucide-react";
import { toast } from "sonner";
import {
  api,
  filterPickerTenants,
  getTenantFilter,
  isReadonlySession,
  setTenantFilter,
  Tenant,
  TenantConfigResponse,
} from "../api";
import { useI18n } from "../i18n";
import { Button } from "../components/ui/button";
import { Input, Label, Textarea } from "../components/ui/input";
import { Skeleton } from "../components/ui/avatar";
import { InlineError, PageHeader } from "../components/ui/page-header";
import { Dialog, DialogContent, DialogSrTitle } from "../components/ui/dialog";
import { MenuBuilder } from "../components/MenuBuilder";
import { MessagesEditor } from "../components/MessagesEditor";
import { LeadOptionsEditor } from "../components/LeadOptionsEditor";
import { OptionListEditor, OptionListItem, stripEmptyOptionRows } from "../components/OptionListEditor";
import { TemplatePicker } from "../components/TemplatePicker";
import { FlowBuilder } from "../components/FlowBuilder";
import { cn } from "../lib/utils";
import type { FlowStep } from "../api";

type Tab = "general" | "lead" | "menu" | "faq" | "messages" | "flow";

type MessagesDraft = {
  lead?: Record<string, string>;
  order?: Record<string, string>;
  interactive?: Record<string, unknown>;
  lang_hint?: string;
  [key: string]: unknown;
};

type Props = {
  /** Owner "My Bot" — content only; wiring read-only */
  ownerMode?: boolean;
  /** Owner Menu page — jump straight to menu builder */
  menuOnly?: boolean;
};

export default function SettingsPage({ ownerMode = false, menuOnly = false }: Props) {
  const { t } = useI18n();
  const [tenants, setTenants] = useState<Tenant[]>([]);
  const [selectedDbId, setSelectedDbId] = useState<number | null>(null);
  const [cfg, setCfg] = useState<TenantConfigResponse | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [messagesBusy, setMessagesBusy] = useState(false);
  const [messagesPublishing, setMessagesPublishing] = useState(false);
  const [loading, setLoading] = useState(true);
  const [tab, setTab] = useState<Tab>(menuOnly ? "menu" : "general");
  const [faqRows, setFaqRows] = useState<OptionListItem[]>([]);
  const [templateOpen, setTemplateOpen] = useState(false);
  const [pickTemplateId, setPickTemplateId] = useState("pos_lead");
  const [templateConfirm, setTemplateConfirm] = useState(false);
  const [templateBusy, setTemplateBusy] = useState(false);
  const readonly = isReadonlySession();

  /** Live + draft only — paused/archived stay on the Businesses lifecycle UI. */
  const pickerTenants = useMemo(() => filterPickerTenants(tenants), [tenants]);

  const loadTenants = useCallback(() => {
    api<{ items?: Tenant[] } | Tenant[]>("/api/dashboard/tenants", { tenant: false })
      .then((raw) => setTenants(Array.isArray(raw) ? raw : raw.items || []))
      .catch(() => setTenants([]));
  }, []);

  useEffect(() => {
    loadTenants();
    const onTenant = () => loadTenants();
    window.addEventListener("tenant-change", onTenant);
    return () => window.removeEventListener("tenant-change", onTenant);
  }, [loadTenants]);

  useEffect(() => {
    if (!pickerTenants.length) {
      setSelectedDbId(null);
      return;
    }
    const filter = getTenantFilter();
    const match =
      filter === "all"
        ? pickerTenants[0]
        : pickerTenants.find((t) => t.phone_number_id === filter) || pickerTenants[0];
    setSelectedDbId(match?.id ?? null);
    if (match && filter !== match.phone_number_id) {
      setTenantFilter(match.phone_number_id);
    }
  }, [pickerTenants]);

  useEffect(() => {
    const onFilterChange = () => {
      if (!pickerTenants.length) return;
      const filter = getTenantFilter();
      const match =
        filter === "all"
          ? pickerTenants[0]
          : pickerTenants.find((t) => t.phone_number_id === filter);
      if (match) setSelectedDbId(match.id);
      else if (pickerTenants[0]) setSelectedDbId(pickerTenants[0].id);
    };
    window.addEventListener("tenant-change", onFilterChange);
    return () => window.removeEventListener("tenant-change", onFilterChange);
  }, [pickerTenants]);

  useEffect(() => {
    if (selectedDbId == null) return;
    setError("");
    setLoading(true);
    api<TenantConfigResponse>(`/api/dashboard/tenants/${selectedDbId}/config`, {
      tenant: false,
    })
      .then((data) => {
        setCfg(data);
        setFaqRows(
          (data.config.faq || []).map((f, i) => ({
            id: `faq_${Date.now()}_${i}`,
            label: f.question,
            answer: f.answer,
          }))
        );
      })
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, [selectedDbId]);

  function messagesDraft(): MessagesDraft {
    return (cfg?.config.messages_draft || cfg?.config.messages || {}) as MessagesDraft;
  }

  function patchMessagesDraft(patch: Partial<MessagesDraft>) {
    if (!cfg) return;
    const current = messagesDraft();
    setCfg({
      ...cfg,
      config: {
        ...cfg.config,
        messages_draft: { ...current, ...patch },
      },
    });
  }

  function prepareMessagesForSave(draft: MessagesDraft): MessagesDraft {
    const interactive = { ...(draft.interactive || {}) } as Record<string, unknown>;
    const bt = (interactive.business_types as Array<{ title?: string }> | undefined) || [];
    const locs = (interactive.locations as Array<{ title?: string }> | undefined) || [];
    const sys = (interactive.current_system as Array<{ title?: string }> | undefined) || [];
    interactive.business_types = bt.filter((r) => (r.title || "").trim());
    interactive.locations = locs.filter((r) => (r.title || "").trim());
    interactive.current_system = sys.filter((r) => (r.title || "").trim());
    return { ...draft, interactive };
  }

  async function onSave(e?: FormEvent) {
    e?.preventDefault();
    if (!cfg || selectedDbId == null) return;

    const faqClean = stripEmptyOptionRows(faqRows).map((r) => ({
      question: r.label.trim(),
      answer: (r.answer || "").trim(),
    }));

    const labels = faqClean.map((f) => f.question.toLowerCase());
    const dups = labels.filter((l, i) => labels.indexOf(l) !== i);
    if (dups.length) {
      const msg = "Duplicate FAQ questions are not allowed";
      setError(msg);
      toast.error(msg);
      return;
    }

    setBusy(true);
    setError("");
    try {
      const draft = prepareMessagesForSave(messagesDraft());
      // Duplicate option labels
      for (const [key, field] of [
        ["business_types", "title"],
        ["locations", "title"],
        ["current_system", "title"],
      ] as const) {
        const rows = ((draft.interactive as Record<string, unknown>)?.[key] as Array<Record<string, string>>) || [];
        const titles = rows.map((r) => (r[field] || "").trim().toLowerCase()).filter(Boolean);
        if (titles.some((t, i) => titles.indexOf(t) !== i)) {
          throw new Error(`Duplicate labels in ${key.replace("_", " ")}`);
        }
      }

      const body: Record<string, unknown> = {
        name: cfg.name,
        greeting_text: cfg.config.greeting_text,
        greeting_language: cfg.config.greeting_language,
        campaign_phrase: cfg.config.campaign_phrase,
        demo_slots: cfg.config.demo_slots,
        facts_features: cfg.config.facts_features,
        facts_pricing_note: cfg.config.facts_pricing_note,
        facts_claims_note: cfg.config.facts_claims_note,
        faq: faqClean,
        messages_draft: draft,
      };
      // Owners must never send wiring fields (server also rejects)
      if (!ownerMode) {
        body.business_wa_id = cfg.config.business_wa_id;
        body.owner_whatsapp = cfg.config.owner_whatsapp;
      }
      if (cfg.flow_mode === "order" && cfg.config.menu) {
        body.menu = cfg.config.menu;
      }
      if (cfg.flow_mode === "lead" && cfg.config.flow) {
        body.flow = cfg.config.flow;
      }
      const updated = await api<TenantConfigResponse>(
        `/api/dashboard/tenants/${selectedDbId}/config`,
        { method: "POST", body: JSON.stringify(body), tenant: false }
      );
      setCfg(updated);
      setFaqRows(
        (updated.config.faq || []).map((f, i) => ({
          id: `faq_${Date.now()}_${i}`,
          label: f.question,
          answer: f.answer,
        }))
      );
      toast.success("Settings saved — live within ~60s");
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Save failed";
      setError(msg);
      toast.error(msg);
    } finally {
      setBusy(false);
    }
  }

  async function onSaveMessages() {
    if (!cfg || selectedDbId == null) return;
    setMessagesBusy(true);
    setError("");
    try {
      const draft = prepareMessagesForSave(messagesDraft());
      const updated = await api<TenantConfigResponse>(
        `/api/dashboard/tenants/${selectedDbId}/config`,
        {
          method: "POST",
          body: JSON.stringify({ messages_draft: draft }),
          tenant: false,
        }
      );
      setCfg(updated);
      toast.success("Message draft saved");
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Save failed";
      setError(msg);
      toast.error(msg);
    } finally {
      setMessagesBusy(false);
    }
  }

  async function onPublishMessages() {
    if (selectedDbId == null) return;
    setMessagesPublishing(true);
    setError("");
    try {
      // Save draft first so publish picks up latest
      await onSaveMessages();
      const updated = await api<TenantConfigResponse>(
        `/api/dashboard/tenants/${selectedDbId}/messages/publish`,
        { method: "POST", tenant: false }
      );
      setCfg(updated);
      toast.success("Messages published — live within ~60s");
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Publish failed";
      setError(msg);
      toast.error(msg);
    } finally {
      setMessagesPublishing(false);
    }
  }

  function resetMessageField(dottedKey: string) {
    if (!cfg?.config.messages) return;
    const parts = dottedKey.split(".");
    const [section, key] = parts;
    const published = cfg.config.messages as Record<string, Record<string, string>>;
    const defaultVal = published?.[section]?.[key];
    if (defaultVal === undefined) return;

    const draft = { ...messagesDraft() } as MessagesDraft;
    const sec = { ...((draft[section] as Record<string, string>) || {}), [key]: defaultVal };
    draft[section] = sec;
    setCfg({
      ...cfg,
      config: { ...cfg.config, messages_draft: draft },
    });
    toast.message("Field reset to published value");
  }

  function updateMessagesDraft(next: Record<string, unknown>) {
    if (!cfg) return;
    setCfg({
      ...cfg,
      config: { ...cfg.config, messages_draft: next },
    });
  }

  function setFaqItems(items: OptionListItem[]) {
    setFaqRows(items);
  }

  async function applyStarterTemplate() {
    if (!selectedDbId || !pickTemplateId) return;
    if (!templateConfirm) {
      toast.error("Confirm that you want to overwrite draft config");
      return;
    }
    setTemplateBusy(true);
    try {
      await api(`/api/dashboard/tenants/${selectedDbId}/apply-template`, {
        method: "POST",
        body: JSON.stringify({
          template_id: pickTemplateId,
          confirm: true,
          greeting_language: cfg?.config.greeting_language || "roman_urdu",
        }),
        tenant: false,
      });
      toast.success("Starter template loaded into draft — review & publish");
      setTemplateOpen(false);
      setTemplateConfirm(false);
      // Reload config
      const data = await api<TenantConfigResponse>(
        `/api/dashboard/tenants/${selectedDbId}/config`,
        { tenant: false }
      );
      setCfg(data);
      setFaqRows(
        (data.config.faq || []).map((f, i) => ({
          id: `faq_${Date.now()}_${i}`,
          label: f.question,
          answer: f.answer,
        }))
      );
      loadTenants();
    } catch (e: unknown) {
      toast.error(e instanceof Error ? e.message : "Failed to apply template");
    } finally {
      setTemplateBusy(false);
    }
  }

  if (selectedDbId == null && !loading) {
    return (
      <div className="space-y-6">
        <PageHeader
          kicker={ownerMode ? "Workspace" : "Wiring"}
          title={ownerMode ? (menuOnly ? t("menu") : t("myBot")) : "Settings"}
          description="Select a live business to edit configuration"
        />
        <InlineError message="No active business available for settings." />
      </div>
    );
  }

  if (loading) {
    return (
      <div className="space-y-4">
        <Skeleton className="h-10 w-48" />
        <Skeleton className="h-40 w-full rounded-2xl" />
        <Skeleton className="h-40 w-full rounded-2xl" />
      </div>
    );
  }

  if (!cfg) {
    return (
      <div className="space-y-6">
        <PageHeader
          kicker={ownerMode ? "Workspace" : "Wiring"}
          title={ownerMode ? (menuOnly ? t("menu") : t("myBot")) : "Settings"}
        />
        <InlineError
          message={error || "Failed to load configuration"}
          onRetry={() => {
            if (selectedDbId == null) return;
            setError("");
            setLoading(true);
            api<TenantConfigResponse>(`/api/dashboard/tenants/${selectedDbId}/config`, {
              tenant: false,
            })
              .then((data) => {
                setCfg(data);
                setFaqRows(
                  (data.config.faq || []).map((f, i) => ({
                    id: `faq_${Date.now()}_${i}`,
                    label: f.question,
                    answer: f.answer,
                  }))
                );
              })
              .catch((e) => setError(e.message))
              .finally(() => setLoading(false));
          }}
        />
      </div>
    );
  }

  const slots = cfg.config.demo_slots?.length
    ? cfg.config.demo_slots
    : ["", ""];

  const draft = messagesDraft();
  const leadMsgs = (draft.lead || {}) as Record<string, string>;
  const interactive = (draft.interactive || {}) as Record<string, unknown>;

  const tabs: { id: Tab; label: string; show?: boolean }[] = menuOnly
    ? [{ id: "menu", label: t("menu"), show: cfg.flow_mode === "order" }]
    : [
        { id: "general", label: "General" },
        { id: "lead", label: "Lead options", show: cfg.flow_mode === "lead" },
        {
          id: "flow",
          label: "Flow",
          show: cfg.flow_mode === "lead" && !ownerMode,
        },
        { id: "messages", label: "Messages" },
        {
          id: "menu",
          label: t("menu"),
          show: cfg.flow_mode === "order" && !ownerMode,
        },
        { id: "faq", label: "FAQ" },
      ];

  return (
    <div className="space-y-7">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <p className="page-kicker">{ownerMode ? "Workspace" : "Wiring"}</p>
          <h1 className="page-title mt-1">
            {ownerMode ? (menuOnly ? t("menu") : t("myBot")) : "Settings"}
          </h1>
          <p className="page-subtitle">Changes go live within ~60 seconds</p>
        </div>
        <div className="flex flex-wrap gap-2">
          {!ownerMode && (
            <Button
              type="button"
              variant="outline"
              onClick={() => {
                setPickTemplateId(
                  cfg.flow_mode === "order" ? "restaurant" : "pos_lead"
                );
                setTemplateConfirm(false);
                setTemplateOpen(true);
              }}
            >
              <LayoutTemplate className="h-4 w-4" />
              Load starter template
            </Button>
          )}
          {tab !== "menu" && tab !== "messages" && (
            <Button type="button" disabled={busy || readonly} onClick={() => onSave()}>
              {busy ? <Loader2 className="h-4 w-4 animate-spin" /> : <Save className="h-4 w-4" />}
              {t("save")}
            </Button>
          )}
        </div>
      </div>

      <Dialog open={templateOpen} onOpenChange={(o) => !o && setTemplateOpen(false)}>
        <DialogContent className="max-h-[90vh] overflow-y-auto p-0 sm:max-w-2xl">
          <DialogSrTitle>Load starter template</DialogSrTitle>
          <div className="border-b border-border px-5 py-4">
            <h2 className="text-lg font-semibold">Load starter template</h2>
            <p className="mt-0.5 text-xs text-muted-foreground">
              Applies to draft config only. Published messages/menu stay until you publish.
            </p>
          </div>
          <div className="space-y-4 px-5 py-4">
            <TemplatePicker
              selectedId={pickTemplateId}
              onSelect={(id) => {
                setPickTemplateId(id);
                setTemplateConfirm(false);
              }}
            />
            <label className="flex items-start gap-2 rounded-xl border border-warning/30 bg-warning/10 px-3 py-3 text-sm">
              <input
                type="checkbox"
                className="mt-1"
                checked={templateConfirm}
                onChange={(e) => setTemplateConfirm(e.target.checked)}
              />
              <span>
                I understand this will overwrite the current <strong>draft</strong>{" "}
                messages / menu for this business.
              </span>
            </label>
          </div>
          <div className="flex justify-end gap-2 border-t border-border px-5 py-3">
            <Button variant="ghost" onClick={() => setTemplateOpen(false)} disabled={templateBusy}>
              Cancel
            </Button>
            <Button
              disabled={!templateConfirm || templateBusy || !pickTemplateId}
              onClick={() => void applyStarterTemplate()}
            >
              {templateBusy ? <Loader2 className="h-4 w-4 animate-spin" /> : null}
              Apply to draft
            </Button>
          </div>
        </DialogContent>
      </Dialog>

      {error && (
        <p className="rounded-lg bg-destructive/10 px-3 py-2 text-sm text-destructive">{error}</p>
      )}

      {!ownerMode && pickerTenants.length > 1 && (
        <div className="surface p-5">
          <Label>Tenant</Label>
          <select
            className="field-select"
            value={selectedDbId ?? ""}
            onChange={(e) => {
              const id = Number(e.target.value);
              setSelectedDbId(id);
              const tn = pickerTenants.find((x) => x.id === id);
              if (tn) {
                setTenantFilter(tn.phone_number_id);
                window.dispatchEvent(new Event("tenant-change"));
              }
            }}
          >
            {pickerTenants.map((tn) => (
              <option key={tn.id} value={tn.id}>
                {tn.name} ({tn.flow_mode})
              </option>
            ))}
          </select>
        </div>
      )}

      {!menuOnly && (
        <div className="flex flex-wrap gap-1 rounded-xl border border-border bg-muted/30 p-1">
          {tabs
            .filter((tabItem) => tabItem.show !== false)
            .map((tabItem) => (
              <button
                key={tabItem.id}
                type="button"
                onClick={() => setTab(tabItem.id)}
                className={cn(
                  "flex-1 rounded-lg px-3 py-2 text-sm font-medium transition min-w-[5.5rem]",
                  tab === tabItem.id
                    ? "bg-card text-foreground shadow-sm"
                    : "text-muted-foreground hover:text-foreground"
                )}
              >
                {tabItem.label}
              </button>
            ))}
        </div>
      )}

      {tab === "menu" && cfg.flow_mode === "order" && selectedDbId != null && (
        <MenuBuilder
          tenantDbId={selectedDbId}
          initial={cfg.config.menu_v2_draft || cfg.config.menu_v2}
          published={cfg.config.menu_v2}
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
      )}

      {tab === "messages" && selectedDbId != null && (
        <MessagesEditor
          tenantDbId={selectedDbId}
          flowMode={cfg.flow_mode === "order" ? "order" : "lead"}
          draft={cfg.config.messages_draft || cfg.config.messages}
          defaults={cfg.config.messages}
          onChange={updateMessagesDraft}
          onSave={onSaveMessages}
          onPublish={onPublishMessages}
          onResetField={resetMessageField}
          busy={messagesBusy}
          publishing={messagesPublishing}
        />
      )}

      {tab === "lead" && cfg.flow_mode === "lead" && (
        <LeadOptionsEditor
          lead={leadMsgs}
          interactive={interactive as Parameters<typeof LeadOptionsEditor>[0]["interactive"]}
          demoSlots={slots}
          onLeadChange={(lead) =>
            patchMessagesDraft({ lead: { ...leadMsgs, ...lead } })
          }
          onInteractiveChange={(next) =>
            patchMessagesDraft({ interactive: next as Record<string, unknown> })
          }
          onDemoSlotsChange={(nextSlots) =>
            setCfg({
              ...cfg,
              config: { ...cfg.config, demo_slots: nextSlots },
            })
          }
        />
      )}

      {tab === "flow" && cfg.flow_mode === "lead" && selectedDbId != null && (
        <FlowBuilder
          tenantDbId={selectedDbId}
          initial={(cfg.config.flow || []) as FlowStep[]}
          demoSlots={slots}
          readonly={readonly}
          onChange={(flow) =>
            setCfg({
              ...cfg,
              config: { ...cfg.config, flow },
            })
          }
        />
      )}

      {tab === "general" && (
        <form onSubmit={onSave} className="space-y-6">
          <section className="space-y-4 rounded-2xl border border-border bg-card p-5">
            <h2 className="text-sm font-semibold">Profile</h2>
            <div>
              <Label>Display name</Label>
              <Input
                className="mt-1.5"
                value={cfg.name}
                onChange={(e) => setCfg({ ...cfg, name: e.target.value })}
              />
            </div>
            <div>
              <Label>Greeting</Label>
              <Textarea
                className="mt-1.5"
                rows={3}
                value={cfg.config.greeting_text}
                onChange={(e) =>
                  setCfg({
                    ...cfg,
                    config: { ...cfg.config, greeting_text: e.target.value },
                  })
                }
              />
              <div className="mt-3 rounded-xl bg-[var(--wa-bg)] p-3">
                <div className="ml-auto max-w-[85%] rounded-2xl rounded-br-sm bg-[var(--wa-out)] px-3 py-2 text-[13px] text-white">
                  <p className="transcript-text whitespace-pre-wrap">
                    {cfg.config.greeting_text || "…"}
                  </p>
                </div>
              </div>
            </div>
            <div>
              <Label>Greeting language</Label>
              <select
                className="mt-1.5 h-10 w-full rounded-lg border border-input bg-background px-3 text-sm focus-ring"
                value={cfg.config.greeting_language}
                onChange={(e) =>
                  setCfg({
                    ...cfg,
                    config: { ...cfg.config, greeting_language: e.target.value },
                  })
                }
              >
                <option value="roman_urdu">Roman Urdu</option>
                <option value="en">English</option>
              </select>
            </div>
            {ownerMode ? (
              <section className="rounded-xl border border-dashed border-border bg-muted/20 p-4">
                <p className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
                  Connection
                </p>
                <p className="mt-1 text-xs text-muted-foreground">{t("wiringNote")}</p>
                <div className="mt-3 grid gap-3 sm:grid-cols-3">
                  <div>
                    <Label className="text-muted-foreground">Phone number ID</Label>
                    <Input
                      className="mt-1.5 opacity-60"
                      value={cfg.wiring?.phone_number_id || cfg.phone_number_id}
                      readOnly
                      disabled
                    />
                  </div>
                  <div>
                    <Label className="text-muted-foreground">WABA ID</Label>
                    <Input
                      className="mt-1.5 opacity-60"
                      value={cfg.wiring?.waba_id || ""}
                      readOnly
                      disabled
                    />
                  </div>
                  <div>
                    <Label className="text-muted-foreground">Flow mode</Label>
                    <Input
                      className="mt-1.5 opacity-60"
                      value={cfg.wiring?.flow_mode || cfg.flow_mode}
                      readOnly
                      disabled
                    />
                  </div>
                </div>
              </section>
            ) : (
              <div className="grid gap-4 sm:grid-cols-2">
                <div>
                  <Label>Business WA ID</Label>
                  <Input
                    className="mt-1.5"
                    value={cfg.config.business_wa_id}
                    onChange={(e) =>
                      setCfg({
                        ...cfg,
                        config: { ...cfg.config, business_wa_id: e.target.value },
                      })
                    }
                  />
                </div>
                <div>
                  <Label>Owner WhatsApp</Label>
                  <Input
                    className="mt-1.5"
                    value={cfg.config.owner_whatsapp}
                    onChange={(e) =>
                      setCfg({
                        ...cfg,
                        config: { ...cfg.config, owner_whatsapp: e.target.value },
                      })
                    }
                  />
                </div>
              </div>
            )}
          </section>

          {cfg.flow_mode === "lead" && (
            <section className="space-y-4 rounded-2xl border border-border bg-card p-5">
              <h2 className="text-sm font-semibold">Lead campaign</h2>
              <div>
                <Label>Campaign phrase</Label>
                <Input
                  className="mt-1.5"
                  value={cfg.config.campaign_phrase}
                  onChange={(e) =>
                    setCfg({
                      ...cfg,
                      config: { ...cfg.config, campaign_phrase: e.target.value },
                    })
                  }
                />
              </div>
              <div>
                <Label>Features copy</Label>
                <Textarea
                  className="mt-1.5"
                  rows={3}
                  value={cfg.config.facts_features}
                  onChange={(e) =>
                    setCfg({
                      ...cfg,
                      config: { ...cfg.config, facts_features: e.target.value },
                    })
                  }
                />
              </div>
              <div>
                <Label>Pricing note</Label>
                <Textarea
                  className="mt-1.5"
                  rows={2}
                  value={cfg.config.facts_pricing_note}
                  onChange={(e) =>
                    setCfg({
                      ...cfg,
                      config: { ...cfg.config, facts_pricing_note: e.target.value },
                    })
                  }
                />
              </div>
              <div>
                <Label>Claims note</Label>
                <Textarea
                  className="mt-1.5"
                  rows={2}
                  value={cfg.config.facts_claims_note}
                  onChange={(e) =>
                    setCfg({
                      ...cfg,
                      config: { ...cfg.config, facts_claims_note: e.target.value },
                    })
                  }
                />
              </div>
              <p className="text-xs text-muted-foreground">
                Interactive option lists (business type, locations, system, scheduling) live under{" "}
                <button
                  type="button"
                  className="text-primary underline-offset-2 hover:underline"
                  onClick={() => setTab("lead")}
                >
                  Lead options
                </button>
                .
              </p>
            </section>
          )}
        </form>
      )}

      {tab === "faq" && (
        <section className="space-y-4 rounded-2xl border border-border bg-card p-5">
          <OptionListEditor
            title="FAQ pairs"
            items={faqRows}
            constraints={{
              maxItems: 30,
              maxLabelChars: 200,
              maxAnswerChars: 500,
            }}
            features={{ reorder: true, answerField: true }}
            addDisabledHint="FAQ limit: 30 pairs"
            emptyHint="Add common questions customers ask."
            onChange={setFaqItems}
          />
          <Button type="button" disabled={busy} onClick={() => onSave()}>
            {busy ? <Loader2 className="h-4 w-4 animate-spin" /> : <Save className="h-4 w-4" />}
            Save FAQ
          </Button>
        </section>
      )}
    </div>
  );
}
