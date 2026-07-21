import { useRef } from "react";
import { Loader2, RotateCcw, Save, Upload } from "lucide-react";
import { Button } from "./ui/button";
import { Label, Textarea } from "./ui/input";
import { cn } from "../lib/utils";

const ALLOWED_VARS: Record<string, string[]> = {
  "lead.confirm_slot": ["slot"],
  "lead.price_deflect_mid": ["current_question"],
  "lead.reprompt": ["current_question"],
  "lead.ack_business_name": ["name"],
  "lead.owner_card_body": [
    "business_name",
    "business_type",
    "locations",
    "current_system",
    "slot",
    "source",
    "referral_headline",
    "sender",
  ],
  "order.item_choose": ["category"],
  "order.modifier_prompt": ["item", "modifier"],
  "order.quantity_ask": ["item"],
  "order.delivery_line": ["amount"],
  "order.total_line": ["total"],
  "order.owner_slip_body": ["items", "total", "address", "customer"],
};

function humanizeKey(key: string): string {
  return key
    .replace(/_/g, " ")
    .replace(/\b\w/g, (c) => c.toUpperCase());
}

function previewText(template: string): string {
  return template.replace(/\{\{\s*([a-zA-Z0-9_]+)\s*\}\}/g, (_, v: string) => `[${v}]`);
}

type Props = {
  tenantDbId: number;
  flowMode: "lead" | "order";
  draft: Record<string, unknown> | null | undefined;
  defaults: Record<string, unknown> | null | undefined;
  onChange: (next: Record<string, unknown>) => void;
  onSave: () => void;
  onPublish: () => void;
  onResetField: (key: string) => void;
  busy: boolean;
  publishing: boolean;
  /** Owner My Bot — parent owns Save & go live */
  hideActions?: boolean;
};

export function MessagesEditor({
  flowMode,
  draft,
  defaults,
  onChange,
  onSave,
  onPublish,
  onResetField,
  busy,
  publishing,
  hideActions = false,
}: Props) {
  const section = flowMode === "order" ? "order" : "lead";
  const sectionDraft = (draft?.[section] as Record<string, string>) || {};
  const sectionDefaults = (defaults?.[section] as Record<string, string>) || {};

  const stringKeys = Object.keys({ ...sectionDefaults, ...sectionDraft }).filter(
    (k) => typeof (sectionDraft[k] ?? sectionDefaults[k]) === "string"
  );

  function updateField(key: string, value: string) {
    onChange({
      ...(draft || {}),
      [section]: { ...sectionDraft, [key]: value },
    });
  }

  return (
    <div className="space-y-6">
      {!hideActions && (
        <div className="flex flex-wrap items-center justify-between gap-3">
          <p className="text-sm text-muted-foreground">
            Edit bot message templates — use {"{{variable}}"} for dynamic text
          </p>
          <div className="flex gap-2">
            <Button type="button" variant="outline" size="sm" disabled={busy} onClick={onSave}>
              {busy ? <Loader2 className="h-4 w-4 animate-spin" /> : <Save className="h-4 w-4" />}
              Save draft
            </Button>
            <Button type="button" size="sm" disabled={publishing} onClick={onPublish}>
              {publishing ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : (
                <Upload className="h-4 w-4" />
              )}
              Publish messages
            </Button>
          </div>
        </div>
      )}

      <section className="space-y-4 rounded-2xl border border-border bg-card p-5">
        <h2 className="text-sm font-semibold capitalize">
          {hideActions ? "Reply templates" : `${section} messages`}
        </h2>
        {stringKeys.map((key) => (
          <MessageField
            key={key}
            fieldKey={key}
            dottedKey={`${section}.${key}`}
            value={sectionDraft[key] ?? sectionDefaults[key] ?? ""}
            onChange={(v) => updateField(key, v)}
            onReset={() => onResetField(`${section}.${key}`)}
          />
        ))}
      </section>

      {flowMode === "lead" && !hideActions && (
        <p className="rounded-xl border border-border bg-muted/20 px-4 py-3 text-sm text-muted-foreground">
          Interactive option sets (business type, locations, system, scheduling) are edited under{" "}
          <span className="text-foreground">Lead options</span>.
        </p>
      )}
    </div>
  );
}

function MessageField({
  fieldKey,
  dottedKey,
  value,
  onChange,
  onReset,
}: {
  fieldKey: string;
  dottedKey: string;
  value: string;
  onChange: (v: string) => void;
  onReset: () => void;
}) {
  const ref = useRef<HTMLTextAreaElement>(null);
  const vars = ALLOWED_VARS[dottedKey] || [];

  function insertVar(v: string) {
    const el = ref.current;
    if (!el) {
      onChange(value + `{{${v}}}`);
      return;
    }
    const start = el.selectionStart ?? value.length;
    const end = el.selectionEnd ?? value.length;
    const token = `{{${v}}}`;
    const next = value.slice(0, start) + token + value.slice(end);
    onChange(next);
    requestAnimationFrame(() => {
      el.focus();
      const pos = start + token.length;
      el.setSelectionRange(pos, pos);
    });
  }

  return (
    <div className="space-y-2 rounded-xl border border-border p-4">
      <div className="flex items-center justify-between gap-2">
        <Label>{humanizeKey(fieldKey)}</Label>
        <Button type="button" variant="ghost" size="sm" onClick={onReset}>
          <RotateCcw className="h-3.5 w-3.5" />
          Reset
        </Button>
      </div>
      <Textarea
        ref={ref}
        rows={3}
        value={value}
        onChange={(e) => onChange(e.target.value)}
      />
      {vars.length > 0 && (
        <div className="flex flex-wrap gap-1.5">
          {vars.map((v) => (
            <button
              key={v}
              type="button"
              onClick={() => insertVar(v)}
              className={cn(
                "rounded-md border border-border bg-muted/40 px-2 py-0.5 font-mono text-[11px]",
                "text-muted-foreground transition hover:bg-primary/15 hover:text-primary"
              )}
            >
              {`{{${v}}}`}
            </button>
          ))}
        </div>
      )}
      <div className="rounded-xl bg-[var(--wa-bg)] p-3">
        <div className="ml-auto max-w-[85%] rounded-2xl rounded-br-sm bg-[var(--wa-out)] px-3 py-2 text-[13px] text-white">
          <p className="transcript-text whitespace-pre-wrap">{previewText(value) || "…"}</p>
        </div>
      </div>
    </div>
  );
}
