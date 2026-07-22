import { useRef, useState } from "react";
import { ChevronDown, Loader2, RotateCcw, Save, Upload } from "lucide-react";
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

/** Plain-English labels for owners. Keys not listed fall back to humanized name. */
const FIELD_META: Record<string, { title: string; when: string }> = {
  // Lead — essentials
  confirm_slot: {
    title: "Demo booked confirmation",
    when: "Sent to the customer after they pick a demo time.",
  },
  handoff: {
    title: "Closing thank-you",
    when: "Sent when the lead is finished and your team will follow up.",
  },
  owner_card_title: {
    title: "Your alert — title",
    when: "WhatsApp notification you receive when a lead books.",
  },
  owner_card_body: {
    title: "Your alert — details",
    when: "Body of the lead alert (business name, slot, phone, etc.).",
  },
  ack_business_name: {
    title: "After business name",
    when: "Short thank-you right after they share their shop/business name.",
  },
  // Lead — advanced
  pricing_text: {
    title: "Pricing explanation",
    when: "Longer pricing reply (FAQ can also cover this).",
  },
  info_text: {
    title: "Product info blurb",
    when: "General “what is this product” reply.",
  },
  price_deflect_mid: {
    title: "Price asked mid-flow",
    when: "When they ask price while still answering questions — then re-asks the current question.",
  },
  reprompt: {
    title: "Didn’t understand",
    when: "When their reply isn’t clear — then shows the current question again.",
  },
  unsupported_media: {
    title: "Image / voice / sticker",
    when: "When they send a photo or voice note instead of text.",
  },
  media_redirect_suffix: {
    title: "Ask for text (after media)",
    when: "Extra line asking them to type a text answer.",
  },
  error_fallback: {
    title: "Something went wrong",
    when: "Rare system error message.",
  },
  entry_demo_suffix: {
    title: "Demo entry hint",
    when: "Extra line when they arrive wanting a demo.",
  },
  // Order essentials / common
  greeting: {
    title: "Order greeting",
    when: "First message when someone opens the order bot.",
  },
  menu_button_label: {
    title: "Menu button label",
    when: "Text on the button that opens the menu.",
  },
  order_received: {
    title: "Order confirmed",
    when: "Sent to the customer after they confirm the order.",
  },
  order_cancel: {
    title: "Order cancelled",
    when: "Sent if they cancel.",
  },
  owner_slip_title: {
    title: "Your order alert — title",
    when: "Notification you get for a new order.",
  },
  owner_slip_body: {
    title: "Your order alert — details",
    when: "Items, total, address, customer phone.",
  },
};

/** Shown first in My Bot “More replies”. Everything else behind Show advanced. */
const LEAD_ESSENTIALS = [
  "confirm_slot",
  "handoff",
  "ack_business_name",
  "owner_card_title",
  "owner_card_body",
] as const;

/** Keys already edited under Greeting / Questions — hide from this screen for owners. */
const LEAD_HIDDEN_FOR_OWNERS = new Set([
  "greeting_line",
  "value_line",
  "q_business_name",
  "q_business_type",
  "q_locations",
  "q_current_system",
  "q_scheduling",
  "q_custom_slot",
]);

const ORDER_ESSENTIALS = [
  "greeting",
  "menu_button_label",
  "order_received",
  "order_cancel",
  "owner_slip_title",
  "owner_slip_body",
] as const;

function humanizeKey(key: string): string {
  return key
    .replace(/_/g, " ")
    .replace(/\b\w/g, (c) => c.toUpperCase());
}

function previewText(template: string): string {
  return template.replace(/\{\{\s*([a-zA-Z0-9_]+)\s*\}\}/g, (_, v: string) => `[${v}]`);
}

function fieldTitle(key: string): string {
  return FIELD_META[key]?.title || humanizeKey(key);
}

function fieldWhen(key: string): string | undefined {
  return FIELD_META[key]?.when;
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
  /** Owner My Bot — parent owns Save & go live; simplify the list */
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
  const [showAdvanced, setShowAdvanced] = useState(!hideActions);
  const section = flowMode === "order" ? "order" : "lead";
  const sectionDraft = (draft?.[section] as Record<string, string>) || {};
  const sectionDefaults = (defaults?.[section] as Record<string, string>) || {};

  const allKeys = Object.keys({ ...sectionDefaults, ...sectionDraft }).filter(
    (k) => typeof (sectionDraft[k] ?? sectionDefaults[k]) === "string"
  );

  const visibleKeys = hideActions
    ? allKeys.filter((k) => !(section === "lead" && LEAD_HIDDEN_FOR_OWNERS.has(k)))
    : allKeys;

  const essentialSet = new Set<string>(
    section === "lead" ? LEAD_ESSENTIALS : ORDER_ESSENTIALS
  );

  const essentialKeys = visibleKeys.filter((k) => essentialSet.has(k));
  // Keep known essentials in preferred order, then any other essentials present
  const orderedEssentials = [
    ...(section === "lead" ? LEAD_ESSENTIALS : ORDER_ESSENTIALS),
  ].filter((k) => visibleKeys.includes(k));
  const extraEssentials = essentialKeys.filter((k) => !orderedEssentials.includes(k));
  const primaryKeys = [...orderedEssentials, ...extraEssentials];

  const advancedKeys = visibleKeys.filter((k) => !essentialSet.has(k));

  function updateField(key: string, value: string) {
    onChange({
      ...(draft || {}),
      [section]: { ...sectionDraft, [key]: value },
    });
  }

  const keysToShow = hideActions
    ? showAdvanced
      ? [...primaryKeys, ...advancedKeys]
      : primaryKeys
    : visibleKeys;

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
        <div>
          <h2 className="text-sm font-semibold">
            {hideActions ? "Common replies" : `${section} messages`}
          </h2>
          {hideActions && (
            <p className="mt-1 text-xs text-muted-foreground">
              Optional. Greeting, questions, and FAQ are enough for most businesses — only change
              these if you want different confirmation or owner-alert wording.
            </p>
          )}
        </div>

        {keysToShow.length === 0 && (
          <p className="text-sm text-muted-foreground">No templates to edit.</p>
        )}

        {keysToShow.map((key) => (
          <MessageField
            key={key}
            fieldKey={key}
            dottedKey={`${section}.${key}`}
            value={sectionDraft[key] ?? sectionDefaults[key] ?? ""}
            onChange={(v) => updateField(key, v)}
            onReset={() => onResetField(`${section}.${key}`)}
          />
        ))}

        {hideActions && advancedKeys.length > 0 && (
          <Button
            type="button"
            variant="outline"
            size="sm"
            className="w-full sm:w-auto"
            onClick={() => setShowAdvanced((v) => !v)}
          >
            <ChevronDown
              className={cn("h-4 w-4 transition-transform", showAdvanced && "rotate-180")}
            />
            {showAdvanced ? "Hide advanced replies" : `Show ${advancedKeys.length} more replies`}
          </Button>
        )}
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
  const when = fieldWhen(fieldKey);

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
      <div className="flex items-start justify-between gap-2">
        <div className="min-w-0">
          <Label className="normal-case tracking-normal text-sm font-semibold text-foreground">
            {fieldTitle(fieldKey)}
          </Label>
          {when && <p className="mt-0.5 text-[11px] text-muted-foreground">{when}</p>}
        </div>
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
          <span className="w-full text-[11px] text-muted-foreground">
            Tap to insert a live value:
          </span>
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
        <p className="mb-1.5 text-[10px] uppercase tracking-wide text-muted-foreground">
          WhatsApp preview
        </p>
        <div className="ml-auto max-w-[85%] rounded-2xl rounded-br-sm bg-[var(--wa-out)] px-3 py-2 text-[13px] text-white">
          <p className="transcript-text whitespace-pre-wrap">{previewText(value) || "…"}</p>
        </div>
      </div>
    </div>
  );
}
