import { FormEvent, useCallback, useEffect, useState } from "react";
import { Loader2, Plus, Save, Trash2 } from "lucide-react";
import { api, getTenantFilter, Tenant, TenantConfigResponse } from "../api";
import PageHeader from "../components/ui/PageHeader";
import { useToast } from "../components/ui/Toast";

type FaqRow = { question: string; answer: string };

const inputCls =
  "mt-1.5 w-full rounded-xl border border-canvas-200 bg-canvas-50 px-3.5 py-2.5 text-sm outline-none transition-ui focus:border-bahi-400 focus:bg-white focus:ring-2 focus:ring-bahi-500/15";

const sectionCls = "rounded-2xl border border-canvas-200 bg-white p-5 shadow-card space-y-4";

export default function SettingsPage() {
  const { toast } = useToast();
  const [tenants, setTenants] = useState<Tenant[]>([]);
  const [selectedDbId, setSelectedDbId] = useState<number | null>(null);
  const [cfg, setCfg] = useState<TenantConfigResponse | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [loading, setLoading] = useState(true);

  const loadTenants = useCallback(() => {
    api<Tenant[]>("/api/dashboard/tenants", { tenant: false }).then(setTenants).catch(() => setTenants([]));
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
    api<TenantConfigResponse>(`/api/dashboard/tenants/${selectedDbId}/config`, { tenant: false })
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
        { method: "POST", body: JSON.stringify(body), tenant: false },
      );
      setCfg(updated);
      toast("Settings saved — live within ~60s", "success");
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Save failed";
      setError(msg);
      toast(msg, "error");
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
      config: { ...cfg.config, faq: [...(cfg.config.faq || []), { question: "", answer: "" }] },
    });
  }

  function removeFaq(i: number) {
    if (!cfg) return;
    const faq = (cfg.config.faq || []).filter((_, idx) => idx !== i);
    setCfg({ ...cfg, config: { ...cfg.config, faq } });
  }

  if (loading || !cfg) {
    return (
      <div>
        <PageHeader title="Settings" subtitle="Changes go live within ~60 seconds" />
        <div className="space-y-4">
          <div className="h-40 animate-shimmer rounded-2xl bg-canvas-200" />
          <div className="h-40 animate-shimmer rounded-2xl bg-canvas-200" />
        </div>
      </div>
    );
  }

  const isLead = cfg.flow_mode === "lead";
  const isOrder = cfg.flow_mode === "order";

  return (
    <div>
      <PageHeader
        title="Settings"
        subtitle="Changes go live within ~60 seconds (config cache)"
        action={
          <button
            type="submit"
            form="settings-form"
            disabled={busy}
            className="inline-flex items-center gap-2 rounded-xl bg-bahi-600 px-4 py-2.5 text-sm font-bold text-white transition-ui hover:bg-bahi-700 disabled:opacity-60"
          >
            {busy ? <Loader2 className="h-4 w-4 animate-spin" /> : <Save className="h-4 w-4" />}
            {busy ? "Saving…" : "Save settings"}
          </button>
        }
      />

      {tenants.length > 1 && (
        <label className="mb-5 block max-w-md text-sm font-semibold text-ink-800">
          Editing tenant
          <select
            className={inputCls}
            value={selectedDbId ?? ""}
            onChange={(e) => setSelectedDbId(Number(e.target.value))}
          >
            {tenants.map((t) => (
              <option key={t.id} value={t.id}>
                {t.name}
              </option>
            ))}
          </select>
        </label>
      )}

      <form id="settings-form" onSubmit={onSave} className="space-y-5">
        <section className={sectionCls}>
          <h2 className="text-sm font-bold text-ink-900">Profile</h2>
          <label className="block text-sm font-semibold text-ink-700">
            Business name
            <input className={inputCls} value={cfg.name} onChange={(e) => setCfg({ ...cfg, name: e.target.value })} />
          </label>
          <label className="block text-sm font-semibold text-ink-700">
            Greeting text
            <textarea
              className={inputCls}
              rows={3}
              value={cfg.config.greeting_text || ""}
              onChange={(e) => setCfg({ ...cfg, config: { ...cfg.config, greeting_text: e.target.value } })}
            />
          </label>
          {cfg.config.greeting_text && (
            <div className="rounded-xl bg-[#e5ddd5] p-3 max-w-sm">
              <div className="transcript-text rounded-2xl rounded-bl-md bg-white px-3 py-2 text-sm shadow-sm">
                {cfg.config.greeting_text}
              </div>
            </div>
          )}
          <label className="block text-sm font-semibold text-ink-700">
            Language
            <select
              className={inputCls}
              value={cfg.config.greeting_language || "roman_urdu"}
              onChange={(e) => setCfg({ ...cfg, config: { ...cfg.config, greeting_language: e.target.value } })}
            >
              <option value="roman_urdu">Roman Urdu</option>
              <option value="en">English</option>
            </select>
          </label>
        </section>

        {isLead && (
          <section className={sectionCls}>
            <h2 className="text-sm font-bold text-ink-900">Lead settings</h2>
            <label className="block text-sm font-semibold text-ink-700">
              Campaign phrase
              <input
                className={inputCls}
                value={cfg.config.campaign_phrase || ""}
                onChange={(e) => setCfg({ ...cfg, config: { ...cfg.config, campaign_phrase: e.target.value } })}
              />
            </label>
            <div className="grid gap-4 sm:grid-cols-2">
              <label className="block text-sm font-semibold text-ink-700">
                Demo slot 1
                <input
                  className={inputCls}
                  value={cfg.config.demo_slots?.[0] || ""}
                  onChange={(e) => {
                    const slots = [...(cfg.config.demo_slots || ["", ""])];
                    slots[0] = e.target.value;
                    setCfg({ ...cfg, config: { ...cfg.config, demo_slots: slots } });
                  }}
                />
              </label>
              <label className="block text-sm font-semibold text-ink-700">
                Demo slot 2
                <input
                  className={inputCls}
                  value={cfg.config.demo_slots?.[1] || ""}
                  onChange={(e) => {
                    const slots = [...(cfg.config.demo_slots || ["", ""])];
                    slots[1] = e.target.value;
                    setCfg({ ...cfg, config: { ...cfg.config, demo_slots: slots } });
                  }}
                />
              </label>
            </div>
            <label className="block text-sm font-semibold text-ink-700">
              Features
              <textarea
                className={inputCls}
                rows={3}
                maxLength={2000}
                value={cfg.config.facts_features || ""}
                onChange={(e) => setCfg({ ...cfg, config: { ...cfg.config, facts_features: e.target.value } })}
              />
            </label>
            <label className="block text-sm font-semibold text-ink-700">
              Pricing note
              <textarea
                className={inputCls}
                rows={2}
                maxLength={2000}
                value={cfg.config.facts_pricing_note || ""}
                onChange={(e) => setCfg({ ...cfg, config: { ...cfg.config, facts_pricing_note: e.target.value } })}
              />
            </label>
            <label className="block text-sm font-semibold text-ink-700">
              Claims note
              <textarea
                className={inputCls}
                rows={2}
                maxLength={2000}
                value={cfg.config.facts_claims_note || ""}
                onChange={(e) => setCfg({ ...cfg, config: { ...cfg.config, facts_claims_note: e.target.value } })}
              />
            </label>
          </section>
        )}

        {isOrder && cfg.config.menu && (
          <section className={sectionCls}>
            <h2 className="text-sm font-bold text-ink-900">Menu</h2>
            <label className="block text-sm font-semibold text-ink-700">
              Shop name
              <input
                className={inputCls}
                value={cfg.config.menu.shop_name || ""}
                onChange={(e) =>
                  setCfg({
                    ...cfg,
                    config: { ...cfg.config, menu: { ...cfg.config.menu!, shop_name: e.target.value } },
                  })
                }
              />
            </label>
            {(cfg.config.menu.categories || []).map((cat, ci) => (
              <div key={ci} className="border-t border-canvas-100 pt-4">
                <p className="mb-2 text-xs font-bold uppercase tracking-wide text-ink-500">{cat.name}</p>
                {(cat.items || []).map((it, ii) => (
                  <div key={ii} className="mb-2 flex flex-wrap items-center gap-2">
                    <input
                      className="min-w-[8rem] flex-1 rounded-lg border border-canvas-200 px-2.5 py-1.5 text-sm"
                      value={it.name}
                      placeholder="Item name"
                      onChange={(e) => {
                        const menu = structuredClone(cfg.config.menu!);
                        menu.categories[ci].items[ii].name = e.target.value;
                        setCfg({ ...cfg, config: { ...cfg.config, menu } });
                      }}
                    />
                    <input
                      type="number"
                      className="w-24 rounded-lg border border-canvas-200 px-2.5 py-1.5 text-sm"
                      value={it.price}
                      min={1}
                      onChange={(e) => {
                        const menu = structuredClone(cfg.config.menu!);
                        menu.categories[ci].items[ii].price = Number(e.target.value);
                        setCfg({ ...cfg, config: { ...cfg.config, menu } });
                      }}
                    />
                    <label className="flex items-center gap-1.5 text-xs font-medium text-ink-600">
                      <input
                        type="checkbox"
                        checked={it.available !== false}
                        onChange={(e) => {
                          const menu = structuredClone(cfg.config.menu!);
                          menu.categories[ci].items[ii].available = e.target.checked;
                          setCfg({ ...cfg, config: { ...cfg.config, menu } });
                        }}
                      />
                      Available
                    </label>
                  </div>
                ))}
              </div>
            ))}
          </section>
        )}

        <section className={sectionCls}>
          <div className="flex items-center justify-between">
            <h2 className="text-sm font-bold text-ink-900">FAQ</h2>
            <button
              type="button"
              onClick={addFaq}
              className="inline-flex items-center gap-1 text-sm font-semibold text-bahi-600 transition-ui hover:text-bahi-700"
            >
              <Plus className="h-4 w-4" /> Add
            </button>
          </div>
          {(cfg.config.faq || []).map((row, i) => (
            <div key={i} className="rounded-xl border border-canvas-100 bg-canvas-50 p-4 space-y-2">
              <input
                className="w-full rounded-lg border border-canvas-200 px-3 py-2 text-sm"
                placeholder="Question"
                value={row.question}
                onChange={(e) => updateFaq(i, "question", e.target.value)}
              />
              <textarea
                className="w-full rounded-lg border border-canvas-200 px-3 py-2 text-sm"
                rows={2}
                maxLength={500}
                placeholder="Answer"
                value={row.answer}
                onChange={(e) => updateFaq(i, "answer", e.target.value)}
              />
              <button
                type="button"
                className="inline-flex items-center gap-1 text-xs font-semibold text-red-600 hover:text-red-700"
                onClick={() => removeFaq(i)}
              >
                <Trash2 className="h-3.5 w-3.5" /> Remove
              </button>
            </div>
          ))}
        </section>

        {error && (
          <p className="rounded-xl border border-red-200 bg-red-50 px-4 py-2 text-sm text-red-700">{error}</p>
        )}
      </form>
    </div>
  );
}
