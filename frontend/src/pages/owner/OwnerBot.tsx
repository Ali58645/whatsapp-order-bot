import { FormEvent, useCallback, useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { Check, LayoutTemplate, Loader2, Plus, Save, Trash2 } from "lucide-react";
import { toast } from "sonner";
import {
  api,
  fetchMe,
  FlowStep,
  isReadonlySession,
  MeResponse,
  TenantConfigResponse,
} from "../../api";
import { LeadOptionsEditor, ensureLeadFlow } from "../../components/LeadOptionsEditor";
import { BusinessHoursEditor } from "../../components/BusinessHoursEditor";
import {
  KnowledgeBaseEditor,
  KnowledgeBase,
  faqRowsFromKb,
  kbWithFaqRows,
  normalizeKnowledgeBase,
} from "../../components/KnowledgeBaseEditor";
import { MessagesEditor } from "../../components/MessagesEditor";
import { OptionListItem } from "../../components/OptionListEditor";
import { TemplatePicker } from "../../components/TemplatePicker";
import { Button } from "../../components/ui/button";
import { Dialog, DialogContent, DialogSrTitle } from "../../components/ui/dialog";
import { Input, Label, Textarea } from "../../components/ui/input";
import { Skeleton } from "../../components/ui/avatar";

type Step = "greeting" | "questions" | "faq" | "more";

const VALID_STEPS = new Set<Step>(["greeting", "questions", "faq", "more"]);

function parseStep(raw: string | undefined): Step | null {
  if (!raw) return null;
  return VALID_STEPS.has(raw as Step) ? (raw as Step) : null;
}

type GreetingBlock = { text: string; image_url: string };

function readGreetingBlocks(config: TenantConfigResponse["config"]): GreetingBlock[] {
  const blocks = config.greeting_blocks;
  if (Array.isArray(blocks) && blocks.length) {
    return blocks.map((b) => ({
      text: (b?.text || "").toString(),
      image_url: (b?.image_url || "").toString(),
    }));
  }
  const texts = [config.greeting_text || "", ...(config.greeting_variants || [])];
  const firstImg = config.greeting_image_url || "";
  const mapped = texts.map((text, i) => ({
    text,
    image_url: i === 0 ? firstImg : "",
  }));
  return mapped.length ? mapped : [{ text: "", image_url: "" }];
}

function writeGreetingBlocks(
  config: TenantConfigResponse["config"],
  blocks: GreetingBlock[]
): TenantConfigResponse["config"] {
  const next = blocks.length ? blocks : [{ text: "", image_url: "" }];
  return {
    ...config,
    greeting_blocks: next,
    greeting_text: next[0]?.text || "",
    greeting_image_url: next[0]?.image_url || "",
    greeting_variants: next.slice(1).map((b) => b.text),
  };
}

type MessagesDraft = {
  lead?: Record<string, string>;
  order?: Record<string, string>;
  interactive?: Record<string, unknown>;
  lang_hint?: string;
  [key: string]: unknown;
};

/**
 * Owner-only My Bot — sections via sidebar under My Bot.
 * Admin wiring stays on /settings.
 */
export default function OwnerBot() {
  const navigate = useNavigate();
  const { section: sectionParam } = useParams<{ section?: string }>();
  const [me, setMe] = useState<MeResponse | null>(null);
  const [cfg, setCfg] = useState<TenantConfigResponse | null>(null);
  const [faqRows, setFaqRows] = useState<OptionListItem[]>([]);
  const [knowledge, setKnowledge] = useState<KnowledgeBase>(() => normalizeKnowledgeBase(null));
  const [flow, setFlow] = useState<FlowStep[]>([]);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [templateOpen, setTemplateOpen] = useState(false);
  const [pickTemplateId, setPickTemplateId] = useState("pos_lead");
  const [templateConfirm, setTemplateConfirm] = useState(false);
  const [templateBusy, setTemplateBusy] = useState(false);
  const readonly = isReadonlySession();

  const tenantId = me?.tenant?.id ?? me?.tenant_id ?? null;
  const isLead = (cfg?.flow_mode || me?.tenant?.flow_mode || "lead") === "lead";

  const step: Step = (() => {
    const parsed = parseStep(sectionParam);
    if (parsed === "questions" && !isLead) return "greeting";
    if (parsed) return parsed;
    return "greeting";
  })();

  function goToStep(next: Step) {
    const target = next === "questions" && !isLead ? "faq" : next;
    navigate(`/my-bot/${target}`);
  }

  useEffect(() => {
    const parsed = parseStep(sectionParam);
    if (!sectionParam || !parsed) {
      navigate("/my-bot/greeting", { replace: true });
      return;
    }
    if (parsed === "questions" && cfg && !isLead) {
      navigate("/my-bot/faq", { replace: true });
    }
  }, [sectionParam, cfg, isLead, navigate]);

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const profile = await fetchMe();
      setMe(profile);
      const tid = profile.tenant?.id ?? profile.tenant_id;
      if (!tid) {
        setError("No business linked to this account");
        setCfg(null);
        return;
      }
      const data = await api<TenantConfigResponse>(`/api/dashboard/tenants/${tid}/config`, {
        tenant: false,
      });
      setCfg(data);
      const kb = normalizeKnowledgeBase(data.config.knowledge_base, data.config.faq);
      setKnowledge(kb);
      setFaqRows(faqRowsFromKb(kb));
      setFlow((data.config.flow as FlowStep[] | undefined) || []);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Failed to load");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  function messagesDraft(): MessagesDraft {
    return (cfg?.config.messages_draft || cfg?.config.messages || {}) as MessagesDraft;
  }

  function patchMessagesDraft(patch: Partial<MessagesDraft>) {
    setCfg((prev) => {
      if (!prev) return prev;
      const current = (prev.config.messages_draft ||
        prev.config.messages ||
        {}) as MessagesDraft;
      return {
        ...prev,
        config: {
          ...prev.config,
          messages_draft: { ...current, ...patch },
        },
      };
    });
  }

  function prepareMessagesForSave(draft: MessagesDraft): MessagesDraft {
    const interactive = { ...(draft.interactive || {}) } as Record<string, unknown>;
    for (const key of ["business_types", "locations", "current_system"] as const) {
      const rows = (interactive[key] as Array<{ title?: string }> | undefined) || [];
      interactive[key] = rows.filter((r) => (r.title || "").trim());
    }
    return { ...draft, interactive };
  }

  async function saveAndGoLive(e?: FormEvent) {
    e?.preventDefault();
    if (!cfg || tenantId == null) return;

    const kbPayload = kbWithFaqRows(knowledge, faqRows);
    const labels = kbPayload.faq.map((f) => f.question.toLowerCase());
    if (labels.some((l, i) => labels.indexOf(l) !== i)) {
      toast.error("Duplicate FAQ questions are not allowed");
      return;
    }

    setBusy(true);
    setError("");
    try {
      const draft = prepareMessagesForSave(messagesDraft());
      for (const [key, field] of [
        ["business_types", "title"],
        ["locations", "title"],
        ["current_system", "title"],
      ] as const) {
        const rows =
          ((draft.interactive as Record<string, unknown>)?.[key] as Array<Record<string, string>>) ||
          [];
        const titles = rows.map((r) => (r[field] || "").trim().toLowerCase()).filter(Boolean);
        if (titles.some((t, i) => titles.indexOf(t) !== i)) {
          throw new Error(`Duplicate button labels in ${key.replace(/_/g, " ")}`);
        }
      }

      const greetingBlocks = readGreetingBlocks(cfg.config)
        .map((b) => ({
          text: b.text.trim(),
          image_url: b.image_url.trim(),
        }))
        .filter((b) => b.text || b.image_url);

      const updated = await api<TenantConfigResponse>(
        `/api/dashboard/tenants/${tenantId}/config`,
        {
          method: "POST",
          body: JSON.stringify({
            name: cfg.name,
            greeting_blocks: greetingBlocks,
            greeting_text: greetingBlocks[0]?.text || "",
            greeting_language: cfg.config.greeting_language,
            greeting_image_url: greetingBlocks[0]?.image_url || "",
            greeting_variants: greetingBlocks.slice(1).map((b) => b.text).filter(Boolean),
            business_hours: cfg.config.business_hours || { enabled: false },
            owner_whatsapp: cfg.config.owner_whatsapp || "",
            campaign_phrase: cfg.config.campaign_phrase,
            demo_slots: cfg.config.demo_slots,
            facts_features: cfg.config.facts_features,
            facts_pricing_note: cfg.config.facts_pricing_note,
            facts_claims_note: cfg.config.facts_claims_note,
            knowledge_base: kbPayload,
            messages_draft: draft,
            ...(isLead ? { flow: ensureLeadFlow(flow) } : {}),
          }),
          tenant: false,
        }
      );
      setCfg(updated);
      const nextKb = normalizeKnowledgeBase(updated.config.knowledge_base, updated.config.faq);
      setKnowledge(nextKb);
      setFaqRows(faqRowsFromKb(nextKb));

      // Publish message drafts so owners don't juggle Save draft / Publish
      try {
        const published = await api<TenantConfigResponse>(
          `/api/dashboard/tenants/${tenantId}/messages/publish`,
          { method: "POST", tenant: false }
        );
        setCfg(published);
      } catch {
        /* config already saved; publish may fail if nothing to publish */
      }

      toast.success("Saved — live within about a minute");
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Save failed";
      setError(msg);
      toast.error(msg);
    } finally {
      setBusy(false);
    }
  }

  async function applyTemplate() {
    if (!tenantId || !pickTemplateId || !templateConfirm) {
      toast.error("Confirm that you want to replace your bot content");
      return;
    }
    setTemplateBusy(true);
    try {
      const res = await api<{
        message?: string;
        config?: TenantConfigResponse;
        template_id?: string;
      }>(`/api/dashboard/tenants/${tenantId}/apply-template`, {
        method: "POST",
        body: JSON.stringify({
          template_id: pickTemplateId,
          confirm: true,
          go_live: true,
          greeting_language: cfg?.config.greeting_language || "roman_urdu",
        }),
        tenant: false,
      });
      const data =
        res.config ||
        (await api<TenantConfigResponse>(`/api/dashboard/tenants/${tenantId}/config`, {
          tenant: false,
        }));
      setCfg(data);
      setFlow((data.config.flow as FlowStep[] | undefined) || []);
      const kb = normalizeKnowledgeBase(data.config.knowledge_base, data.config.faq);
      setKnowledge(kb);
      setFaqRows(faqRowsFromKb(kb));
      navigate("/my-bot/greeting");
      setTemplateOpen(false);
      setTemplateConfirm(false);
      toast.success(
        res.message ||
          "Template applied — greeting, questions, and knowledge base replaced. Edit anything below."
      );
    } catch (err: unknown) {
      toast.error(err instanceof Error ? err.message : "Failed to apply template");
    } finally {
      setTemplateBusy(false);
    }
  }

  if (loading) {
    return (
      <div className="space-y-4">
        <Skeleton className="h-10 w-48" />
        <Skeleton className="h-12 w-full rounded-xl" />
        <Skeleton className="h-64 w-full rounded-2xl" />
      </div>
    );
  }

  if (!cfg || tenantId == null) {
    return (
      <div className="space-y-4">
        <h1 className="page-title">My Bot</h1>
        <p className="rounded-lg bg-destructive/10 px-3 py-2 text-sm text-destructive">
          {error || "No business available"}
        </p>
      </div>
    );
  }

  const slots = cfg.config.demo_slots?.length ? cfg.config.demo_slots : ["", ""];
  const draft = messagesDraft();
  const leadMsgs = (draft.lead || {}) as Record<string, string>;
  const interactive = (draft.interactive || {}) as Record<string, unknown>;

  const sectionMeta: Record<Step, { title: string; subtitle: string }> = {
    greeting: {
      title: "Greeting",
      subtitle: "First WhatsApp message customers see — greeting plus opening question.",
    },
    questions: {
      title: "Questions",
      subtitle: "Build the question flow, answer buttons, and niche follow-ups.",
    },
    faq: {
      title: "Knowledge Base",
      subtitle:
        "Company information the WhatsApp bot uses to answer questions that aren’t part of the flow.",
    },
    more: {
      title: "More replies",
      subtitle: "Optional confirmation texts and owner alerts. Most owners can skip this.",
    },
  };
  const { title: pageTitle, subtitle: pageSubtitle } = sectionMeta[step];

  return (
    <div className="w-full space-y-6 pb-24">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div className="min-w-0 flex-1">
          <p className="page-kicker">{cfg.name}</p>
          <h1 className="page-title mt-1">{pageTitle}</h1>
          <p className="page-subtitle">{pageSubtitle}</p>
        </div>
        <Button
          type="button"
          variant="outline"
          size="sm"
          disabled={readonly}
          onClick={() => {
            setPickTemplateId(isLead ? "pos_lead" : "restaurant");
            setTemplateConfirm(false);
            setTemplateOpen(true);
          }}
        >
          <LayoutTemplate className="h-4 w-4" />
          Load template
        </Button>
      </div>

      <Dialog open={templateOpen} onOpenChange={(o) => !o && setTemplateOpen(false)}>
        <DialogContent className="max-h-[90vh] overflow-y-auto p-0 sm:max-w-2xl">
          <DialogSrTitle>Load starter template</DialogSrTitle>
          <div className="border-b border-border px-5 py-4">
            <h2 className="text-lg font-semibold">Load starter template</h2>
            <p className="mt-0.5 text-xs text-muted-foreground">
              Replaces greeting, questions &amp; buttons, knowledge base, and reply texts for this business.
              You can edit everything afterward.
            </p>
          </div>
          <div className="space-y-4 px-5 py-4">
            <TemplatePicker
              selectedId={pickTemplateId}
              flowMode={isLead ? "lead" : "order"}
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
                I understand this will <strong>replace</strong> my current greeting, questions,
                knowledge base, and related bot copy (goes live immediately).
              </span>
            </label>
          </div>
          <div className="flex justify-end gap-2 border-t border-border px-5 py-3">
            <Button
              variant="ghost"
              onClick={() => setTemplateOpen(false)}
              disabled={templateBusy}
            >
              Cancel
            </Button>
            <Button
              disabled={!templateConfirm || templateBusy || !pickTemplateId}
              onClick={() => void applyTemplate()}
            >
              {templateBusy ? <Loader2 className="h-4 w-4 animate-spin" /> : null}
              Apply template
            </Button>
          </div>
        </DialogContent>
      </Dialog>

      {error && (
        <p className="rounded-lg bg-destructive/10 px-3 py-2 text-sm text-destructive">{error}</p>
      )}

      {step === "greeting" && (
        <div className="grid gap-6 xl:grid-cols-[minmax(0,1fr)_minmax(280px,380px)]">
          <section className="space-y-5 rounded-2xl border border-border bg-card p-5 sm:p-6 lg:p-7">
          <div>
            <Label>Business display name</Label>
            <Input
              className="mt-1.5"
              value={cfg.name}
              onChange={(e) => setCfg({ ...cfg, name: e.target.value })}
              disabled={readonly}
            />
          </div>
          <div className="space-y-3">
            <div className="flex items-center justify-between gap-3">
              <div>
                <Label>Greeting messages</Label>
                <p className="mt-0.5 text-xs text-muted-foreground">
                  Each box is its own WhatsApp bubble. Optional image URL on every box.
                </p>
              </div>
              {!readonly && (
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  onClick={() =>
                    setCfg({
                      ...cfg,
                      config: writeGreetingBlocks(cfg.config, [
                        ...readGreetingBlocks(cfg.config),
                        { text: "", image_url: "" },
                      ]),
                    })
                  }
                >
                  <Plus className="h-3.5 w-3.5" />
                  Add greeting
                </Button>
              )}
            </div>
            {readGreetingBlocks(cfg.config).map((block, idx, boxes) => (
              <div
                key={`greet-${idx}`}
                className="space-y-2 rounded-xl border border-border bg-muted/15 p-3 sm:p-4"
              >
                <div className="flex items-center justify-between gap-2">
                  <p className="text-xs font-semibold text-muted-foreground">
                    Message {idx + 1}
                    {idx === 0 ? " · first" : ""}
                  </p>
                  {!readonly && boxes.length > 1 && (
                    <button
                      type="button"
                      className="inline-flex items-center gap-1 text-xs text-destructive hover:underline"
                      onClick={() =>
                        setCfg({
                          ...cfg,
                          config: writeGreetingBlocks(
                            cfg.config,
                            boxes.filter((_, i) => i !== idx)
                          ),
                        })
                      }
                    >
                      <Trash2 className="h-3.5 w-3.5" />
                      Remove
                    </button>
                  )}
                </div>
                <Textarea
                  rows={3}
                  value={block.text}
                  onChange={(e) => {
                    const next = boxes.map((b, i) =>
                      i === idx ? { ...b, text: e.target.value } : b
                    );
                    setCfg({
                      ...cfg,
                      config: writeGreetingBlocks(cfg.config, next),
                    });
                  }}
                  disabled={readonly}
                  placeholder={
                    idx === 0
                      ? "e.g. Assalam o Alaikum — thanks for messaging us."
                      : "Next greeting message…"
                  }
                />
                <div>
                  <Label className="text-xs">Image URL (optional)</Label>
                  <Input
                    className="mt-1.5"
                    placeholder="https://…"
                    value={block.image_url}
                    onChange={(e) => {
                      const next = boxes.map((b, i) =>
                        i === idx ? { ...b, image_url: e.target.value } : b
                      );
                      setCfg({
                        ...cfg,
                        config: writeGreetingBlocks(cfg.config, next),
                      });
                    }}
                    disabled={readonly}
                    inputMode="url"
                  />
                  <p className="mt-1 text-[11px] text-muted-foreground">
                    Public https image sent with this message.
                  </p>
                </div>
              </div>
            ))}
          </div>
          {isLead && (
            <div>
              <Label>Opening question (asks for business name)</Label>
              <Textarea
                className="mt-1.5"
                rows={2}
                value={
                  leadMsgs.q_business_name ||
                  "Barah-e-karam apne business ya shop ka naam farmaayein."
                }
                onChange={(e) =>
                  patchMessagesDraft({
                    lead: { ...leadMsgs, q_business_name: e.target.value },
                  })
                }
                disabled={readonly}
              />
              <p className="mt-1 text-xs text-muted-foreground">
                Sent after all greeting messages.
              </p>
            </div>
          )}
          <div>
            <Label>Language</Label>
            <select
              className="mt-1.5 h-10 w-full rounded-lg border border-input bg-background px-3 text-sm"
              value={cfg.config.greeting_language}
              onChange={(e) =>
                setCfg({
                  ...cfg,
                  config: { ...cfg.config, greeting_language: e.target.value },
                })
              }
              disabled={readonly}
            >
              <option value="roman_urdu">Roman Urdu</option>
              <option value="en">English</option>
            </select>
          </div>
          {isLead && (
            <div>
              <Label>Your alert WhatsApp (demos / handoffs)</Label>
              <Input
                className="mt-1.5"
                placeholder="92xxxxxxxxxx"
                value={cfg.config.owner_whatsapp || ""}
                onChange={(e) =>
                  setCfg({
                    ...cfg,
                    config: { ...cfg.config, owner_whatsapp: e.target.value },
                  })
                }
                disabled={readonly}
              />
              <p className="mt-1 text-xs text-muted-foreground">
                Number that receives demo confirmations (with country code).
              </p>
            </div>
          )}
          {isLead && (
            <div className="rounded-xl border border-border bg-muted/20 p-4">
              <BusinessHoursEditor
                value={cfg.config.business_hours}
                disabled={readonly}
                onChange={(business_hours) =>
                  setCfg({
                    ...cfg,
                    config: { ...cfg.config, business_hours },
                  })
                }
              />
            </div>
          )}
          {isLead && (
            <div>
              <Label>Campaign keyword (optional)</Label>
              <Input
                className="mt-1.5"
                placeholder="e.g. Bahi POS"
                value={cfg.config.campaign_phrase || ""}
                onChange={(e) =>
                  setCfg({
                    ...cfg,
                    config: { ...cfg.config, campaign_phrase: e.target.value },
                  })
                }
                disabled={readonly}
              />
              <p className="mt-1 text-xs text-muted-foreground">
                Phrase from ads that starts a new lead chat.
              </p>
            </div>
          )}
          <Button type="button" variant="outline" onClick={() => goToStep(isLead ? "questions" : "faq")}>
            Next: {isLead ? "Questions" : "Knowledge Base"}
          </Button>
          </section>

          <aside className="xl:sticky xl:top-20 xl:self-start">
            <div className="rounded-2xl border border-border bg-card p-4 sm:p-5">
              <p className="mb-3 text-xs font-semibold uppercase tracking-wider text-muted-foreground">
                Preview — what WhatsApp sends
              </p>
              <div className="space-y-2 rounded-xl bg-[var(--wa-bg)] p-3 min-h-[220px]">
                {[
                  ...readGreetingBlocks(cfg.config)
                    .filter((b) => b.text.trim() || b.image_url.trim())
                    .map((b) => ({
                      text: b.text.trim() || (b.image_url ? "[image]" : ""),
                      image: b.image_url.trim(),
                    })),
                  ...(isLead
                    ? [
                        {
                          text: (
                            leadMsgs.q_business_name ||
                            "Barah-e-karam apne business ya shop ka naam farmaayein."
                          ).trim(),
                          image: "",
                        },
                      ]
                    : []),
                ]
                  .filter((b) => b.text)
                  .map((bubble, i) => (
                    <div
                      key={`${i}-${bubble.text.slice(0, 24)}`}
                      className="mr-auto max-w-[92%] overflow-hidden rounded-2xl rounded-bl-sm bg-[var(--wa-in)] text-[13px] text-zinc-100"
                    >
                      {bubble.image ? (
                        <img
                          src={bubble.image}
                          alt=""
                          className="max-h-40 w-full object-cover"
                          onError={(e) => {
                            (e.target as HTMLImageElement).style.display = "none";
                          }}
                        />
                      ) : null}
                      <p className="transcript-text whitespace-pre-wrap px-3 py-2">{bubble.text}</p>
                    </div>
                  ))}
                {!readGreetingBlocks(cfg.config).some(
                  (b) => b.text.trim() || b.image_url.trim()
                ) && (
                  <div className="mr-auto max-w-[92%] rounded-2xl rounded-bl-sm bg-[var(--wa-in)] px-3 py-2 text-[13px] text-zinc-100">
                    …
                  </div>
                )}
              </div>
            </div>
          </aside>
        </div>
      )}

      {step === "questions" && isLead && (
        <section className="space-y-4 rounded-2xl border border-border bg-card p-5 sm:p-6 lg:p-7">
          <LeadOptionsEditor
            lead={leadMsgs}
            interactive={interactive as Parameters<typeof LeadOptionsEditor>[0]["interactive"]}
            demoSlots={slots}
            onLeadChange={(lead) => patchMessagesDraft({ lead: { ...leadMsgs, ...lead } })}
            onInteractiveChange={(next) =>
              patchMessagesDraft({ interactive: next as Record<string, unknown> })
            }
            onDemoSlotsChange={(nextSlots) =>
              setCfg((prev) =>
                prev
                  ? { ...prev, config: { ...prev.config, demo_slots: nextSlots } }
                  : prev
              )
            }
            flow={flow}
            onFlowChange={setFlow}
            allowRemove
            allowExtras
            readonly={readonly}
          />
          <Button type="button" variant="outline" onClick={() => goToStep("faq")}>
            Next: Knowledge Base
          </Button>
        </section>
      )}

      {step === "faq" && (
        <section className="space-y-4 rounded-2xl border border-border bg-card p-5 sm:p-6 lg:p-7">
          <KnowledgeBaseEditor
            tenantDbId={tenantId}
            value={knowledge}
            faqRows={faqRows}
            onChange={setKnowledge}
            onFaqRowsChange={setFaqRows}
            disabled={readonly || busy}
          />
          <Button type="button" variant="outline" onClick={() => goToStep("more")}>
            Optional: More replies
          </Button>
        </section>
      )}

      {step === "more" && (
        <section className="space-y-4">
          <MessagesEditor
            tenantDbId={tenantId}
            flowMode={isLead ? "lead" : "order"}
            draft={cfg.config.messages_draft || cfg.config.messages}
            defaults={cfg.config.messages}
            onChange={(next) =>
              setCfg({ ...cfg, config: { ...cfg.config, messages_draft: next } })
            }
            onSave={() => void saveAndGoLive()}
            onPublish={() => void saveAndGoLive()}
            onResetField={() => toast.message("Use Save & go live after editing")}
            busy={busy}
            publishing={busy}
            hideActions
          />
        </section>
      )}

      {/* Sticky primary action */}
      <div className="fixed bottom-0 left-0 right-0 z-30 border-t border-border bg-card/95 p-4 backdrop-blur md:static md:border-0 md:bg-transparent md:p-0 md:backdrop-blur-none">
        <div className="mx-auto flex w-full max-w-[1600px] flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
          <p className="text-xs text-muted-foreground">
            One button saves greeting, questions, knowledge base, and messages.
          </p>
          <Button
            type="button"
            size="lg"
            disabled={busy || readonly}
            onClick={() => void saveAndGoLive()}
            className="w-full sm:w-auto"
          >
            {busy ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              <Save className="h-4 w-4" />
            )}
            Save & go live
            {!busy && <Check className="h-4 w-4 opacity-70" />}
          </Button>
        </div>
      </div>
    </div>
  );
}
