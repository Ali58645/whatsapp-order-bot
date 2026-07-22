import { useMemo, useState } from "react";
import { Loader2, Search, Sparkles } from "lucide-react";
import { toast } from "sonner";
import { api } from "../api";
import { OptionListEditor, OptionListItem, stripEmptyOptionRows } from "./OptionListEditor";
import { Button } from "./ui/button";
import { Input, Label, Textarea } from "./ui/input";

export const KB_SECTION_KEYS = [
  "overview",
  "products_services",
  "pricing",
  "business_hours",
  "locations",
  "contact",
  "payment_methods",
  "delivery_booking",
  "policies",
  "additional",
] as const;

export type KbSectionKey = (typeof KB_SECTION_KEYS)[number];

export const KB_SECTION_LABELS: Record<KbSectionKey, string> = {
  overview: "Company overview",
  products_services: "Products and services",
  pricing: "Pricing information",
  business_hours: "Business hours",
  locations: "Locations and service areas",
  contact: "Contact information",
  payment_methods: "Payment methods",
  delivery_booking: "Delivery or booking process",
  policies: "Policies",
  additional: "Additional company information",
};

const SECTION_MAX = 4000;
const COMPLETE_MAX = 20000;

export type KnowledgeBase = {
  enabled: boolean;
  status: "draft" | "published";
  updated_at?: string | null;
  sections: Record<string, string>;
  complete_knowledge: string;
  faq: { question: string; answer: string }[];
};

export function emptyKnowledgeBase(): KnowledgeBase {
  return {
    enabled: true,
    status: "draft",
    updated_at: null,
    sections: Object.fromEntries(KB_SECTION_KEYS.map((k) => [k, ""])),
    complete_knowledge: "",
    faq: [],
  };
}

export function normalizeKnowledgeBase(
  raw: Partial<KnowledgeBase> | null | undefined,
  legacyFaq?: { question: string; answer: string }[]
): KnowledgeBase {
  const base = emptyKnowledgeBase();
  if (!raw || typeof raw !== "object") {
    return {
      ...base,
      faq: (legacyFaq || []).map((f) => ({
        question: f.question || "",
        answer: f.answer || "",
      })),
    };
  }
  const sections = { ...base.sections };
  for (const key of KB_SECTION_KEYS) {
    sections[key] = String((raw.sections && raw.sections[key]) || "");
  }
  const faq =
    Array.isArray(raw.faq) && raw.faq.length
      ? raw.faq.map((f) => ({
          question: f.question || "",
          answer: f.answer || "",
        }))
      : (legacyFaq || []).map((f) => ({
          question: f.question || "",
          answer: f.answer || "",
        }));
  return {
    enabled: raw.enabled !== false,
    status: raw.status === "published" ? "published" : "draft",
    updated_at: raw.updated_at || null,
    sections,
    complete_knowledge: String(raw.complete_knowledge || ""),
    faq,
  };
}

export function knowledgeCharCount(kb: KnowledgeBase): number {
  let n = (kb.complete_knowledge || "").length;
  for (const v of Object.values(kb.sections || {})) n += (v || "").length;
  for (const item of kb.faq || []) {
    n += (item.question || "").length + (item.answer || "").length;
  }
  return n;
}

export function faqRowsFromKb(kb: KnowledgeBase): OptionListItem[] {
  return (kb.faq || []).map((f, i) => ({
    id: `faq_${Date.now()}_${i}`,
    label: f.question,
    answer: f.answer,
  }));
}

export function kbWithFaqRows(kb: KnowledgeBase, rows: OptionListItem[]): KnowledgeBase {
  return {
    ...kb,
    faq: stripEmptyOptionRows(rows).map((r) => ({
      question: r.label.trim(),
      answer: (r.answer || "").trim(),
    })),
  };
}

type Props = {
  tenantDbId: number;
  value: KnowledgeBase;
  faqRows: OptionListItem[];
  onChange: (next: KnowledgeBase) => void;
  onFaqRowsChange: (rows: OptionListItem[]) => void;
  disabled?: boolean;
};

export function KnowledgeBaseEditor({
  tenantDbId,
  value,
  faqRows,
  onChange,
  onFaqRowsChange,
  disabled,
}: Props) {
  const [search, setSearch] = useState("");
  const [previewQ, setPreviewQ] = useState("");
  const [previewAnswer, setPreviewAnswer] = useState("");
  const [previewDetail, setPreviewDetail] = useState("");
  const [previewBusy, setPreviewBusy] = useState(false);

  const charCount = knowledgeCharCount(kbWithFaqRows(value, faqRows));
  const q = search.trim().toLowerCase();

  const visibleSections = useMemo(() => {
    if (!q) return [...KB_SECTION_KEYS];
    return KB_SECTION_KEYS.filter((key) => {
      const label = KB_SECTION_LABELS[key].toLowerCase();
      const text = (value.sections[key] || "").toLowerCase();
      return label.includes(q) || text.includes(q);
    });
  }, [q, value.sections]);

  const showComplete =
    !q ||
    "complete company knowledge".includes(q) ||
    (value.complete_knowledge || "").toLowerCase().includes(q);

  const showFaq =
    !q ||
    "faq".includes(q) ||
    "frequently".includes(q) ||
    faqRows.some(
      (r) =>
        r.label.toLowerCase().includes(q) || (r.answer || "").toLowerCase().includes(q)
    );

  function patch(partial: Partial<KnowledgeBase>) {
    onChange({ ...value, ...partial });
  }

  function setSection(key: KbSectionKey, text: string) {
    onChange({
      ...value,
      sections: { ...value.sections, [key]: text.slice(0, SECTION_MAX) },
    });
  }

  async function runPreview() {
    const question = previewQ.trim();
    if (!question) {
      toast.error("Enter a test question");
      return;
    }
    setPreviewBusy(true);
    setPreviewAnswer("");
    setPreviewDetail("");
    try {
      const kb = kbWithFaqRows(value, faqRows);
      const res = await api<{
        answer: string;
        matched: boolean;
        used_ai?: boolean;
        detail?: string | null;
        model?: string;
      }>(`/api/dashboard/tenants/${tenantDbId}/knowledge/preview`, {
        method: "POST",
        body: JSON.stringify({ question, knowledge_base: kb, lang: "en" }),
        tenant: false,
      });
      setPreviewAnswer(res.answer || "");
      if (res.detail) setPreviewDetail(res.detail);
      if (res.matched) {
        toast.success(res.used_ai ? "Answered from your knowledge (AI)" : "Answer ready");
      } else {
        toast.message(res.detail || "No confirmed match — bot would offer human support");
      }
    } catch (e: unknown) {
      toast.error(e instanceof Error ? e.message : "Preview failed");
    } finally {
      setPreviewBusy(false);
    }
  }

  const empty =
    charCount === 0 &&
    !faqRows.some((r) => r.label.trim() || (r.answer || "").trim());

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-border bg-muted/30 px-4 py-3">
        <div className="space-y-1">
          <p className="text-sm font-medium text-foreground">
            Status:{" "}
            <span className={value.status === "published" ? "text-emerald-700" : "text-amber-700"}>
              {value.status === "published" ? "Published" : "Draft"}
            </span>
          </p>
          <p className="text-xs text-muted-foreground">
            {value.updated_at
              ? `Last updated ${new Date(value.updated_at).toLocaleString()}`
              : "Not saved yet"}
            {" · "}
            {charCount.toLocaleString()} characters
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-3">
          <label className="flex items-center gap-2 text-sm">
            <input
              type="checkbox"
              className="h-4 w-4 rounded border-border"
              checked={value.enabled}
              disabled={disabled}
              onChange={(e) => patch({ enabled: e.target.checked })}
            />
            Enable knowledge answers
          </label>
          <div className="flex rounded-lg border border-border p-0.5 text-sm">
            <button
              type="button"
              disabled={disabled}
              className={`rounded-md px-3 py-1 ${
                value.status === "draft" ? "bg-background shadow-sm" : "text-muted-foreground"
              }`}
              onClick={() => patch({ status: "draft" })}
            >
              Draft
            </button>
            <button
              type="button"
              disabled={disabled}
              className={`rounded-md px-3 py-1 ${
                value.status === "published" ? "bg-background shadow-sm" : "text-muted-foreground"
              }`}
              onClick={() => patch({ status: "published" })}
            >
              Published
            </button>
          </div>
        </div>
      </div>

      <div className="relative">
        <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
        <Input
          className="pl-9"
          placeholder="Search within knowledge…"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
        />
      </div>

      {empty && (
        <div className="rounded-xl border border-dashed border-border bg-muted/20 px-4 py-8 text-center">
          <p className="text-sm font-medium text-foreground">No company knowledge yet</p>
          <p className="mt-1 text-sm text-muted-foreground">
            Paste a full company summary below, or fill the sections. Existing FAQ pairs still work.
          </p>
        </div>
      )}

      {showComplete && (
        <div className="space-y-2">
          <Label htmlFor="kb-complete">Complete Company Knowledge</Label>
          <p className="text-xs text-muted-foreground">
            Paste a full company summary, services, policies, pricing, and anything useful for the
            bot. Plain text preferred (HTML is stripped on save).
          </p>
          <Textarea
            id="kb-complete"
            rows={10}
            disabled={disabled}
            value={value.complete_knowledge}
            maxLength={COMPLETE_MAX}
            onChange={(e) =>
              patch({ complete_knowledge: e.target.value.slice(0, COMPLETE_MAX) })
            }
            placeholder="Example: We are … We offer … Hours … Pricing … Policies …"
          />
          <p className="text-xs text-muted-foreground text-right">
            {(value.complete_knowledge || "").length.toLocaleString()} /{" "}
            {COMPLETE_MAX.toLocaleString()}
          </p>
        </div>
      )}

      <div className="space-y-4">
        <h3 className="text-sm font-semibold text-foreground">Structured sections</h3>
        {visibleSections.length === 0 && (
          <p className="text-sm text-muted-foreground">No sections match your search.</p>
        )}
        {visibleSections.map((key) => (
          <div key={key} className="space-y-1.5">
            <Label htmlFor={`kb-${key}`}>{KB_SECTION_LABELS[key]}</Label>
            <Textarea
              id={`kb-${key}`}
              rows={3}
              disabled={disabled}
              value={value.sections[key] || ""}
              maxLength={SECTION_MAX}
              onChange={(e) => setSection(key, e.target.value)}
              placeholder={`Details about ${KB_SECTION_LABELS[key].toLowerCase()}…`}
            />
          </div>
        ))}
      </div>

      {showFaq && (
        <OptionListEditor
          title="Frequently asked questions"
          items={faqRows}
          onChange={onFaqRowsChange}
          constraints={{
            maxItems: 30,
            maxLabelChars: 200,
            maxAnswerChars: 500,
          }}
          features={{ answerField: true, reorder: true }}
          addDisabledHint="FAQ limit: 30 pairs"
          emptyHint="Exact Q&A still matched first; knowledge fills gaps."
        />
      )}

      <div className="space-y-3 rounded-xl border border-border bg-card p-4">
        <div className="flex items-center gap-2">
          <Sparkles className="h-4 w-4 text-muted-foreground" />
          <h3 className="text-sm font-semibold">Preview test question</h3>
        </div>
        <p className="text-xs text-muted-foreground">
          Uses AI (Anthropic) with only the company knowledge above — including drafts. Save &amp;
          publish for WhatsApp customers.
        </p>
        <Textarea
          rows={2}
          value={previewQ}
          disabled={disabled || previewBusy}
          onChange={(e) => setPreviewQ(e.target.value)}
          placeholder="e.g. Do you deliver on Sundays?"
        />
        <Button
          type="button"
          variant="outline"
          disabled={disabled || previewBusy}
          onClick={() => void runPreview()}
        >
          {previewBusy ? <Loader2 className="h-4 w-4 animate-spin" /> : <Sparkles className="h-4 w-4" />}
          Test answer
        </Button>
        {previewAnswer && (
          <div className="space-y-1">
            <div className="rounded-lg border border-border bg-muted/40 px-3 py-2 text-sm whitespace-pre-wrap">
              {previewAnswer}
            </div>
            {previewDetail && (
              <p className="text-xs text-muted-foreground">{previewDetail}</p>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
