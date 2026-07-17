import { FormEvent, useCallback, useEffect, useState } from "react";
import { Loader2, Plus, Save, Trash2 } from "lucide-react";
import { toast } from "sonner";
import { api, getTenantFilter, Tenant, TenantConfigResponse } from "../api";
import { Button } from "../components/ui/button";
import { Input, Label, Textarea } from "../components/ui/input";
import { Skeleton } from "../components/ui/avatar";
import { MenuBuilder } from "../components/MenuBuilder";
import { cn } from "../lib/utils";

type FaqRow = { question: string; answer: string };
type Tab = "general" | "menu" | "faq";

export default function SettingsPage() {
  const [tenants, setTenants] = useState<Tenant[]>([]);
  const [selectedDbId, setSelectedDbId] = useState<number | null>(null);
  const [cfg, setCfg] = useState<TenantConfigResponse | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [loading, setLoading] = useState(true);
  const [tab, setTab] = useState<Tab>("general");

  const loadTenants = useCallback(() => {
    api<Tenant[]>("/api/dashboard/tenants", { tenant: false })
      .then(setTenants)
      .catch(() => setTenants([]));
  }, []);

  useEffect(() => {
    loadTenants();
    const onTenant = () => loadTenants();
    window.addEventListener("tenant-change", onTenant);
    return () => window.removeEventListener("tenant-change", onTenant);
  }, [loadTenants]);

  useEffect(() => {
    if (!tenants.length) return;
    const filter = getTenantFilter();
    const match = tenants.find((t) => t.phone_number_id === filter) || tenants[0];
    setSelectedDbId(match.id);
  }, [tenants]);

  useEffect(() => {
    if (selectedDbId == null) return;
    setError("");
    setLoading(true);
    api<TenantConfigResponse>(`/api/dashboard/tenants/${selectedDbId}/config`, {
      tenant: false,
    })
      .then(setCfg)
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, [selectedDbId]);

  async function onSave(e: FormEvent) {
    e.preventDefault();
    if (!cfg || selectedDbId == null) return;
    setBusy(true);
    setError("");
    try {
      const body: Record<string, unknown> = {
        name: cfg.name,
        greeting_text: cfg.config.greeting_text,
        greeting_language: cfg.config.greeting_language,
        campaign_phrase: cfg.config.campaign_phrase,
        demo_slots: cfg.config.demo_slots,
        facts_features: cfg.config.facts_features,
        facts_pricing_note: cfg.config.facts_pricing_note,
        facts_claims_note: cfg.config.facts_claims_note,
        faq: cfg.config.faq,
        business_wa_id: cfg.config.business_wa_id,
        owner_whatsapp: cfg.config.owner_whatsapp,
      };
      if (cfg.flow_mode === "order" && cfg.config.menu) {
        body.menu = cfg.config.menu;
      }
      const updated = await api<TenantConfigResponse>(
        `/api/dashboard/tenants/${selectedDbId}/config`,
        { method: "POST", body: JSON.stringify(body), tenant: false }
      );
      setCfg(updated);
      toast.success("Settings saved — live within ~60s");
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Save failed";
      setError(msg);
      toast.error(msg);
    } finally {
      setBusy(false);
    }
  }

  function updateFaq(i: number, field: keyof FaqRow, value: string) {
    if (!cfg) return;
    const faq = [...(cfg.config.faq || [])];
    faq[i] = { ...faq[i], [field]: value };
    setCfg({ ...cfg, config: { ...cfg.config, faq } });
  }

  function addFaq() {
    if (!cfg || (cfg.config.faq?.length || 0) >= 30) return;
    setCfg({
      ...cfg,
      config: {
        ...cfg.config,
        faq: [...(cfg.config.faq || []), { question: "", answer: "" }],
      },
    });
  }

  function removeFaq(i: number) {
    if (!cfg) return;
    const faq = (cfg.config.faq || []).filter((_, idx) => idx !== i);
    setCfg({ ...cfg, config: { ...cfg.config, faq } });
  }

  if (loading || !cfg) {
    return (
      <div className="space-y-4">
        <Skeleton className="h-10 w-48" />
        <Skeleton className="h-40 w-full rounded-2xl" />
        <Skeleton className="h-40 w-full rounded-2xl" />
      </div>
    );
  }

  const slots = cfg.config.demo_slots?.length
    ? cfg.config.demo_slots
    : ["", ""];

  const tabs: { id: Tab; label: string; show?: boolean }[] = [
    { id: "general", label: "General" },
    { id: "menu", label: "Menu", show: cfg.flow_mode === "order" },
    { id: "faq", label: "FAQ" },
  ];

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">Settings</h1>
          <p className="mt-1 text-sm text-muted-foreground">
            Changes go live within ~60 seconds
          </p>
        </div>
        {tab !== "menu" && (
          <Button type="button" disabled={busy} onClick={(e) => onSave(e as unknown as FormEvent)}>
            {busy ? <Loader2 className="h-4 w-4 animate-spin" /> : <Save className="h-4 w-4" />}
            Save
          </Button>
        )}
      </div>

      {error && (
        <p className="rounded-lg bg-destructive/10 px-3 py-2 text-sm text-destructive">{error}</p>
      )}

      {tenants.length > 1 && (
        <div className="rounded-2xl border border-border bg-card p-5">
          <Label>Tenant</Label>
          <select
            className="mt-1.5 h-10 w-full rounded-lg border border-input bg-background px-3 text-sm focus-ring"
            value={selectedDbId ?? ""}
            onChange={(e) => setSelectedDbId(Number(e.target.value))}
          >
            {tenants.map((t) => (
              <option key={t.id} value={t.id}>
                {t.name} ({t.flow_mode})
              </option>
            ))}
          </select>
        </div>
      )}

      <div className="flex gap-1 rounded-xl border border-border bg-muted/30 p-1">
        {tabs
          .filter((t) => t.show !== false)
          .map((t) => (
            <button
              key={t.id}
              type="button"
              onClick={() => setTab(t.id)}
              className={cn(
                "flex-1 rounded-lg px-3 py-2 text-sm font-medium transition",
                tab === t.id
                  ? "bg-card text-foreground shadow-sm"
                  : "text-muted-foreground hover:text-foreground"
              )}
            >
              {t.label}
            </button>
          ))}
      </div>

      {tab === "menu" && cfg.flow_mode === "order" && selectedDbId != null && (
        <MenuBuilder
          tenantDbId={selectedDbId}
          initial={cfg.config.menu_v2_draft || cfg.config.menu_v2}
          published={cfg.config.menu_v2}
          onSaved={(draft, published) =>
            setCfg({
              ...cfg,
              config: {
                ...cfg.config,
                menu_v2_draft: draft,
                menu_v2: published ?? cfg.config.menu_v2,
              },
            })
          }
        />
      )}

      {tab === "general" && (
    <form onSubmit={onSave} className="space-y-6">
      {/* Profile */}
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
      </section>

      {cfg.flow_mode === "lead" && (
        <section className="space-y-4 rounded-2xl border border-border bg-card p-5">
          <h2 className="text-sm font-semibold">Lead settings</h2>
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
          <div className="grid gap-4 sm:grid-cols-2">
            {[0, 1].map((i) => (
              <div key={i}>
                <Label>Demo slot {i + 1}</Label>
                <Input
                  className="mt-1.5"
                  value={slots[i] || ""}
                  onChange={(e) => {
                    const next = [...slots];
                    next[i] = e.target.value;
                    setCfg({
                      ...cfg,
                      config: { ...cfg.config, demo_slots: next },
                    });
                  }}
                />
              </div>
            ))}
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
        </section>
      )}
    </form>
      )}

      {tab === "faq" && (
      <section className="space-y-4 rounded-2xl border border-border bg-card p-5">
        <div className="flex items-center justify-between">
          <h2 className="text-sm font-semibold">FAQ</h2>
          <Button type="button" variant="outline" size="sm" onClick={addFaq}>
            <Plus className="h-3.5 w-3.5" /> Add
          </Button>
        </div>
        {(cfg.config.faq || []).map((row, i) => (
          <div key={i} className="space-y-2 rounded-xl border border-border p-3">
            <div className="flex items-start gap-2">
              <Input
                placeholder="Question"
                value={row.question}
                onChange={(e) => updateFaq(i, "question", e.target.value)}
              />
              <Button
                type="button"
                variant="ghost"
                size="icon"
                onClick={() => removeFaq(i)}
                aria-label="Remove FAQ"
              >
                <Trash2 className="h-4 w-4 text-destructive" />
              </Button>
            </div>
            <Textarea
              placeholder="Answer (max 500)"
              maxLength={500}
              rows={2}
              value={row.answer}
              onChange={(e) => updateFaq(i, "answer", e.target.value)}
            />
          </div>
        ))}
        <Button type="button" disabled={busy} onClick={(e) => onSave(e as unknown as FormEvent)}>
          {busy ? <Loader2 className="h-4 w-4 animate-spin" /> : <Save className="h-4 w-4" />}
          Save FAQ
        </Button>
      </section>
      )}
    </div>
  );
}
