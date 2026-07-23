import { useCallback, useEffect, useMemo, useState } from "react";
import { Link, Navigate, useNavigate, useSearchParams } from "react-router-dom";
import { ArrowLeft, ArrowRight, Check, Loader2, Sparkles } from "lucide-react";
import { toast } from "sonner";
import {
  api,
  clearMeCache,
  fetchMe,
  isOwner,
  isReadonlySession,
  isSupportSession,
  OnboardingTemplate,
} from "../../api";
import {
  BusinessHoursEditor,
  defaultAwayMessage,
  defaultBusinessHoursForLang,
  type BusinessHoursConfig,
} from "../../components/BusinessHoursEditor";
import { TemplatePicker } from "../../components/TemplatePicker";
import { Button } from "../../components/ui/button";
import { Input, Label, Textarea } from "../../components/ui/input";
import { useI18n } from "../../i18n";
import { cn } from "../../lib/utils";

type SetupStatus = {
  needed: boolean;
  tenant_id: number;
  tenant_name: string;
  flow_mode: string;
  owner_setup_complete?: boolean;
  content_set?: boolean;
  templates: { lead: OnboardingTemplate[]; order: OnboardingTemplate[] };
};

type Preview = {
  template_id: string;
  template_name: string;
  flow_mode: string;
  blurb: string;
  greetings: { id: string; text: string }[];
  questions: { key: string; label: string; text: string }[];
  more_replies: { key: string; text: string }[];
};

const QUESTION_EDIT_KEYS = [
  "q_business_name",
  "q_business_type",
  "q_locations",
  "q_current_system",
  "q_scheduling",
] as const;

const MORE_EDIT_KEYS = ["confirm_slot", "handoff", "ack_business_name"] as const;

function botLangToUi(lang: "roman_urdu" | "en"): "en" | "ur" {
  return lang === "en" ? "en" : "ur";
}

export default function OwnerSetup() {
  const navigate = useNavigate();
  const [params] = useSearchParams();
  const force = params.get("force") === "1" || params.get("rerun") === "1";
  const readonly = isReadonlySession();
  const { t, setLang: setUiLang } = useI18n();

  const STEPS = [
    t("setupStepBusiness"),
    t("setupStepCategory"),
    t("setupStepHours"),
    t("setupStepAbout"),
    t("setupStepReview"),
  ] as const;

  const [boot, setBoot] = useState(true);
  const [status, setStatus] = useState<SetupStatus | null>(null);
  const [step, setStep] = useState(0);
  const [busy, setBusy] = useState(false);
  const [previewBusy, setPreviewBusy] = useState(false);

  const [name, setName] = useState("");
  const [flowMode, setFlowMode] = useState<"lead" | "order">("lead");
  const [lang, setLang] = useState<"roman_urdu" | "en">("roman_urdu");
  const [templateId, setTemplateId] = useState("");
  const [hours, setHours] = useState<BusinessHoursConfig>({
    ...defaultBusinessHoursForLang("roman_urdu"),
    enabled: true,
  });
  const [overview, setOverview] = useState("");
  const [offer, setOffer] = useState("");
  const [location, setLocation] = useState("");
  const [contact, setContact] = useState("");
  const [preview, setPreview] = useState<Preview | null>(null);
  const [greetingId, setGreetingId] = useState("");
  const [greetingText, setGreetingText] = useState("");
  const [questionEdits, setQuestionEdits] = useState<Record<string, string>>({});
  const [moreEdits, setMoreEdits] = useState<Record<string, string>>({});
  const [buttonTypesText, setButtonTypesText] = useState("");

  function changeBotLang(next: "roman_urdu" | "en") {
    setLang(next);
    setUiLang(botLangToUi(next));
    setHours((prev) => {
      const urDefault = defaultAwayMessage("roman_urdu");
      const enDefault = defaultAwayMessage("en");
      const current = (prev.away_message || "").trim();
      const stillDefault = !current || current === urDefault || current === enDefault;
      if (!stillDefault) return prev;
      return { ...prev, away_message: defaultAwayMessage(next) };
    });
  }

  const canAccess = isOwner() || isSupportSession();

  const load = useCallback(async () => {
    setBoot(true);
    try {
      const [st, me] = await Promise.all([
        api<SetupStatus>("/api/dashboard/owner/setup", { tenant: false }),
        fetchMe({ force: true }),
      ]);
      setStatus(st);
      setName(me.tenant?.name || st.tenant_name || "");
      if (me.tenant?.flow_mode === "order" || me.tenant?.flow_mode === "lead") {
        setFlowMode(me.tenant.flow_mode);
      }
    } catch (e: unknown) {
      toast.error(e instanceof Error ? e.message : "Failed to load setup");
    } finally {
      setBoot(false);
    }
  }, []);

  useEffect(() => {
    if (canAccess) void load();
  }, [canAccess, load]);

  const loadPreview = useCallback(async () => {
    if (!templateId || !name.trim()) return;
    setPreviewBusy(true);
    try {
      const q = new URLSearchParams({
        template_id: templateId,
        business_name: name.trim(),
        greeting_language: lang,
        flow_mode: flowMode,
        overview: overview.trim(),
        offer: offer.trim(),
        location: location.trim(),
      });
      const p = await api<Preview>(`/api/dashboard/owner/setup/preview?${q}`, {
        tenant: false,
      });
      setPreview(p);
      const first = p.greetings[0];
      if (first) {
        setGreetingId(first.id);
        setGreetingText(first.text);
      }
      const qNext: Record<string, string> = {};
      for (const qq of p.questions) {
        if ((QUESTION_EDIT_KEYS as readonly string[]).includes(qq.key)) {
          qNext[qq.key] = qq.text;
        }
      }
      setQuestionEdits(qNext);
      const mNext: Record<string, string> = {};
      for (const mm of p.more_replies) {
        if ((MORE_EDIT_KEYS as readonly string[]).includes(mm.key)) {
          mNext[mm.key] = mm.text;
        }
      }
      setMoreEdits(mNext);
      const buttons = p.questions.find((qq) => qq.key === "buttons_business_types");
      setButtonTypesText(buttons?.text || "");
    } catch (e: unknown) {
      toast.error(e instanceof Error ? e.message : "Preview failed");
    } finally {
      setPreviewBusy(false);
    }
  }, [templateId, name, lang, flowMode, overview, offer, location]);

  useEffect(() => {
    if (step === 4) void loadPreview();
  }, [step, loadPreview]);

  const templatesForMode = useMemo(() => {
    const lead = status?.templates.lead || [];
    const order = status?.templates.order || [];
    return [...lead, ...order];
  }, [status]);

  const preferredTemplates = useMemo(
    () => (flowMode === "order" ? status?.templates.order : status?.templates.lead) || [],
    [flowMode, status]
  );

  if (!canAccess) return <Navigate to="/" replace />;

  if (boot) {
    return (
      <div className="flex min-h-[50vh] items-center justify-center">
        <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
      </div>
    );
  }

  if (status && !status.needed && !force) {
    return <Navigate to="/" replace />;
  }

  function canNext(): boolean {
    if (step === 0) return name.trim().length >= 2;
    if (step === 1) return Boolean(templateId);
    if (step === 2) return true;
    if (step === 3) return overview.trim().length >= 8 || offer.trim().length >= 8;
    if (step === 4) return Boolean(greetingText.trim());
    return false;
  }

  async function finish() {
    if (readonly) {
      toast.error("Read-only session");
      return;
    }
    if (!templateId || !greetingText.trim()) {
      toast.error("Pick a greeting to continue");
      return;
    }
    setBusy(true);
    try {
      await api("/api/dashboard/owner/setup", {
        method: "POST",
        tenant: false,
        body: JSON.stringify({
          business_name: name.trim(),
          flow_mode: flowMode,
          template_id: templateId,
          greeting_language: lang,
          greeting_text: greetingText.trim(),
          business_hours: hours,
          overview: overview.trim(),
          offer: offer.trim(),
          location: location.trim(),
          contact: contact.trim(),
          extra: "",
          message_overrides: {
            lead: {
              ...questionEdits,
              ...moreEdits,
            },
            interactive: {
              business_types_text: buttonTypesText,
            },
          },
        }),
      });
      clearMeCache();
      window.dispatchEvent(new Event("tenant-change"));
      try {
        sessionStorage.removeItem("bahi_setup_skipped");
      } catch {
        /* ignore */
      }
      toast.success("You're live — tweak Questions anytime in My Bot");
      navigate("/my-bot", { replace: true });
    } catch (e: unknown) {
      toast.error(e instanceof Error ? e.message : "Setup failed");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="mx-auto max-w-2xl space-y-8 pb-16">
      <div>
        <p className="page-kicker">Get started</p>
        <h1 className="page-title mt-1">{t("setupTitle")}</h1>
        <p className="page-subtitle">{t("setupSubtitle")}</p>
      </div>

      <ol className="flex flex-wrap gap-2">
        {STEPS.map((label, i) => (
          <li
            key={label}
            className={cn(
              "rounded-full px-3 py-1 text-xs font-semibold",
              i === step
                ? "bg-primary text-primary-foreground"
                : i < step
                  ? "bg-emerald-500/15 text-emerald-400"
                  : "bg-muted text-muted-foreground"
            )}
          >
            {i < step ? <Check className="mr-1 inline h-3 w-3" /> : null}
            {label}
          </li>
        ))}
      </ol>

      <div className="space-y-5 rounded-2xl border border-border/80 bg-card/40 p-5 sm:p-6">
        {step === 0 && (
          <div className="space-y-4">
            <div>
              <Label htmlFor="biz-name">{t("setupBusinessName")}</Label>
              <Input
                id="biz-name"
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder="e.g. Al-Noor Salon"
                disabled={readonly}
                className="mt-1.5"
              />
            </div>
            <div>
              <Label>{t("setupBotJob")}</Label>
              <p className="mt-1 text-xs text-muted-foreground">{t("setupBotJobHint")}</p>
              <div className="mt-2 grid gap-2 sm:grid-cols-2">
                {(
                  [
                    {
                      id: "lead" as const,
                      title: t("setupLeadMode"),
                      blurb: t("setupLeadModeBlurb"),
                    },
                    {
                      id: "order" as const,
                      title: t("setupOrderMode"),
                      blurb: t("setupOrderModeBlurb"),
                    },
                  ] as const
                ).map((opt) => (
                  <button
                    key={opt.id}
                    type="button"
                    disabled={readonly}
                    onClick={() => {
                      setFlowMode(opt.id);
                      setTemplateId("");
                    }}
                    className={cn(
                      "rounded-xl border px-4 py-3 text-left transition",
                      flowMode === opt.id
                        ? "border-primary bg-primary/10"
                        : "border-border hover:bg-muted/40"
                    )}
                  >
                    <p className="text-sm font-semibold">{opt.title}</p>
                    <p className="mt-1 text-xs text-muted-foreground">{opt.blurb}</p>
                  </button>
                ))}
              </div>
            </div>
            <div>
              <Label>{t("setupGreetingLang")}</Label>
              <p className="mt-1 text-xs text-muted-foreground">{t("setupGreetingLangHint")}</p>
              <div className="mt-2 flex flex-wrap gap-2">
                {(
                  [
                    { id: "roman_urdu" as const, label: t("romanUrdu") },
                    { id: "en" as const, label: t("english") },
                  ] as const
                ).map((opt) => (
                  <button
                    key={opt.id}
                    type="button"
                    disabled={readonly}
                    onClick={() => changeBotLang(opt.id)}
                    className={cn(
                      "rounded-full px-3 py-1.5 text-xs font-semibold",
                      lang === opt.id
                        ? "bg-primary text-primary-foreground"
                        : "bg-muted text-muted-foreground"
                    )}
                  >
                    {opt.label}
                  </button>
                ))}
              </div>
            </div>
          </div>
        )}

        {step === 1 && (
          <div className="space-y-3">
            <Label>{t("setupCategory")}</Label>
            <p className="text-xs text-muted-foreground">
              All {templatesForMode.length} starter packs — food, retail, services, and more.
              {preferredTemplates.length
                ? ` Suggested for ${flowMode === "order" ? "orders" : "leads"}: ${preferredTemplates.length}.`
                : ""}{" "}
              Choosing a category sets lead vs order for you.
            </p>
            <TemplatePicker
              selectedId={templateId}
              className="max-h-[min(70vh,560px)]"
              onSelect={(id, tmpl) => {
                setTemplateId(id);
                if (tmpl?.flow_mode === "lead" || tmpl?.flow_mode === "order") {
                  setFlowMode(tmpl.flow_mode);
                }
              }}
            />
          </div>
        )}

        {step === 2 && (
          <div className="space-y-3">
            <Label>{t("setupHours")}</Label>
            <p className="mt-0.5 text-xs text-muted-foreground">{t("setupHoursHint")}</p>
            <BusinessHoursEditor value={hours} onChange={setHours} disabled={readonly} />
          </div>
        )}

        {step === 3 && (
          <div className="space-y-4">
            <div>
                  <Label htmlFor="overview">{t("setupOverview")}</Label>
              <Textarea
                id="overview"
                value={overview}
                onChange={(e) => setOverview(e.target.value)}
                rows={3}
                placeholder="We are a salon in DHA offering hair, bridal, and facials…"
                disabled={readonly}
                className="mt-1.5"
              />
            </div>
            <div>
                  <Label htmlFor="offer">
                    {flowMode === "order" ? t("setupOfferOrder") : t("setupOffer")}
                  </Label>
              <Textarea
                id="offer"
                value={offer}
                onChange={(e) => setOffer(e.target.value)}
                rows={3}
                placeholder="Haircut, facial, bridal packages…"
                disabled={readonly}
                className="mt-1.5"
              />
            </div>
            <div>
                  <Label htmlFor="location">{t("setupLocation")}</Label>
              <Input
                id="location"
                value={location}
                onChange={(e) => setLocation(e.target.value)}
                placeholder="DHA Phase 5, Lahore"
                disabled={readonly}
                className="mt-1.5"
              />
            </div>
            <div>
                  <Label htmlFor="contact">{t("setupContact")}</Label>
              <Input
                id="contact"
                value={contact}
                onChange={(e) => setContact(e.target.value)}
                placeholder="0300 1234567"
                disabled={readonly}
                className="mt-1.5"
              />
            </div>
          </div>
        )}

        {step === 4 && (
          <div className="space-y-8">
            {previewBusy && (
              <div className="flex items-center gap-2 text-sm text-muted-foreground">
                <Loader2 className="h-4 w-4 animate-spin" /> Loading preview…
              </div>
            )}
            {preview && (
              <>
                <div>
                  <Label>{t("setupGreetingLang")}</Label>
                  <p className="mt-1 text-xs text-muted-foreground">{t("setupGreetingLangHint")}</p>
                  <div className="mt-2 flex flex-wrap gap-2">
                    {(
                      [
                        { id: "roman_urdu" as const, label: t("romanUrdu") },
                        { id: "en" as const, label: t("english") },
                      ] as const
                    ).map((opt) => (
                      <button
                        key={opt.id}
                        type="button"
                        disabled={readonly || previewBusy}
                        onClick={() => changeBotLang(opt.id)}
                        className={cn(
                          "rounded-full px-3 py-1.5 text-xs font-semibold",
                          lang === opt.id
                            ? "bg-primary text-primary-foreground"
                            : "bg-muted text-muted-foreground"
                        )}
                      >
                        {opt.label}
                      </button>
                    ))}
                  </div>
                </div>

                {preview.template_name && (
                  <p className="text-xs text-muted-foreground">
                    Based on <span className="font-semibold text-foreground">{preview.template_name}</span>
                    {preview.blurb ? ` — ${preview.blurb}` : ""}.
                  </p>
                )}

                {/* 1. Greeting */}
                <section className="space-y-3">
                  <div>
                    <h2 className="text-sm font-semibold tracking-tight">{t("setupGreetingSection")}</h2>
                    <p className="mt-0.5 text-xs text-muted-foreground">{t("setupGreetingHint")}</p>
                  </div>
                  <div className="space-y-2">
                    {preview.greetings.map((g) => (
                      <button
                        key={g.id}
                        type="button"
                        disabled={readonly}
                        onClick={() => {
                          setGreetingId(g.id);
                          setGreetingText(g.text);
                        }}
                        className={cn(
                          "w-full rounded-xl border px-4 py-3 text-left text-sm transition",
                          greetingId === g.id
                            ? "border-primary bg-primary/10"
                            : "border-border hover:bg-muted/40"
                        )}
                      >
                        {g.text}
                      </button>
                    ))}
                  </div>
                  <div>
                    <Label htmlFor="greet-edit">{t("setupEditGreeting")}</Label>
                    <Textarea
                      id="greet-edit"
                      value={greetingText}
                      onChange={(e) => {
                        setGreetingText(e.target.value);
                        setGreetingId("custom");
                      }}
                      rows={3}
                      disabled={readonly}
                      className="mt-1.5"
                    />
                  </div>
                </section>

                {/* 2. Questions preview */}
                <section className="space-y-3">
                  <div>
                    <h2 className="text-sm font-semibold tracking-tight">{t("setupQuestionsSection")}</h2>
                    <p className="mt-0.5 text-xs text-muted-foreground">{t("setupQuestionsHint")}</p>
                  </div>
                  <div className="space-y-3">
                    {(
                      [
                        ["q_business_name", t("setupQName")],
                        ["q_business_type", t("setupQType")],
                        ["q_locations", t("setupQLocation")],
                        ["q_current_system", t("setupQFollowup")],
                        ["q_scheduling", t("setupQScheduling")],
                      ] as const
                    ).map(([key, label]) =>
                      questionEdits[key] !== undefined ? (
                        <div key={key} className="space-y-2">
                          <div>
                            <Label htmlFor={`q-${key}`}>{label}</Label>
                            <Textarea
                              id={`q-${key}`}
                              value={questionEdits[key] || ""}
                              onChange={(e) =>
                                setQuestionEdits((prev) => ({ ...prev, [key]: e.target.value }))
                              }
                              rows={key === "q_scheduling" ? 3 : 2}
                              disabled={readonly}
                              className="mt-1.5"
                            />
                          </div>
                          {key === "q_business_type" && (
                            <div className="rounded-xl border border-border/70 bg-muted/20 p-3">
                              <Label htmlFor="btn-types">{t("setupOptions")}</Label>
                              <Textarea
                                id="btn-types"
                                value={buttonTypesText}
                                onChange={(e) => setButtonTypesText(e.target.value)}
                                rows={3}
                                disabled={readonly}
                                className="mt-1.5"
                                placeholder="Automation, Integrations, AI agents, Other"
                              />
                              <p className="mt-1.5 text-[11px] text-muted-foreground">
                                {t("setupOptionsHint")}
                              </p>
                              {buttonTypesText.trim() && (
                                <div className="mt-2 flex flex-wrap gap-1.5">
                                  {buttonTypesText
                                    .split(/[,;\n|]+/)
                                    .map((s) => s.trim())
                                    .filter(Boolean)
                                    .slice(0, 10)
                                    .map((opt) => (
                                      <span
                                        key={opt}
                                        className="rounded-full border border-border bg-background px-2.5 py-0.5 text-[11px] font-medium"
                                      >
                                        {opt}
                                      </span>
                                    ))}
                                </div>
                              )}
                            </div>
                          )}
                        </div>
                      ) : null
                    )}
                  </div>
                </section>

                {/* 3. More replies */}
                <section className="space-y-3">
                  <div>
                    <h2 className="text-sm font-semibold tracking-tight">{t("setupMoreSection")}</h2>
                    <p className="mt-0.5 text-xs text-muted-foreground">{t("setupMoreHint")}</p>
                  </div>
                  <div className="space-y-3">
                    {(
                      [
                        ["confirm_slot", t("setupMConfirm")],
                        ["handoff", t("setupMHandoff")],
                        ["ack_business_name", t("setupMAck")],
                      ] as const
                    ).map(([key, label]) =>
                      moreEdits[key] !== undefined ? (
                        <div key={key}>
                          <Label htmlFor={`m-${key}`}>{label}</Label>
                          <Textarea
                            id={`m-${key}`}
                            value={moreEdits[key] || ""}
                            onChange={(e) =>
                              setMoreEdits((prev) => ({ ...prev, [key]: e.target.value }))
                            }
                            rows={2}
                            disabled={readonly}
                            className="mt-1.5"
                          />
                          {key === "confirm_slot" && (
                            <p className="mt-1 text-[11px] text-muted-foreground">
                              Keep {"{{slot}}"} so the chosen time is filled in automatically.
                            </p>
                          )}
                        </div>
                      ) : null
                    )}
                  </div>
                </section>
              </>
            )}
          </div>
        )}
      </div>

      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex gap-2">
          {step > 0 ? (
            <Button
              type="button"
              variant="outline"
              onClick={() => setStep((s) => Math.max(0, s - 1))}
              disabled={busy}
            >
              <ArrowLeft className="h-4 w-4" />
              {t("setupBack")}
            </Button>
          ) : (
            <Button type="button" variant="ghost" asChild>
              <Link
                to="/"
                onClick={() => {
                  try {
                    sessionStorage.setItem("bahi_setup_skipped", "1");
                  } catch {
                    /* ignore */
                  }
                }}
              >
                {t("setupSkip")}
              </Link>
            </Button>
          )}
        </div>
        {step < STEPS.length - 1 ? (
          <Button
            type="button"
            disabled={!canNext() || readonly}
            onClick={() => setStep((s) => s + 1)}
          >
            {t("setupContinue")}
            <ArrowRight className="h-4 w-4" />
          </Button>
        ) : (
          <Button type="button" disabled={!canNext() || busy || readonly} onClick={() => void finish()}>
            {busy ? <Loader2 className="h-4 w-4 animate-spin" /> : <Sparkles className="h-4 w-4" />}
            {t("setupApply")}
          </Button>
        )}
      </div>
    </div>
  );
}
