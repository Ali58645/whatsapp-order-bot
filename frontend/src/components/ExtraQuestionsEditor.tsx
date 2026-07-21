import { Plus, Trash2 } from "lucide-react";
import { toast } from "sonner";
import { FlowStep, FlowStepOption } from "../api";
import { OptionListEditor, OptionListItem } from "./OptionListEditor";
import { AccordionSection } from "./ui/accordion-section";
import { Button } from "./ui/button";
import { Label, Textarea } from "./ui/input";

const BUILTIN_KEYS = new Set([
  "GREETING",
  "BUSINESS_NAME",
  "BUSINESS_TYPE",
  "LOCATIONS",
  "CURRENT_SYSTEM",
  "SCHEDULING",
  "CONFIRMED",
  "STALLED",
]);

const FLOW_MAX = 12;
const CUSTOM_FIELDS = ["custom_1", "custom_2", "custom_3", "custom_4", "custom_5"] as const;

function nid(prefix: string) {
  return `${prefix}_${Math.random().toString(36).slice(2, 10)}`;
}

function isExtraStep(step: FlowStep): boolean {
  const key = (step.key || "").toUpperCase();
  if (BUILTIN_KEYS.has(key)) return false;
  if (step.reserved || step.system) return false;
  return true;
}

function nextCustomField(flow: FlowStep[]): (typeof CUSTOM_FIELDS)[number] | null {
  const used = new Set(
    flow.map((s) => s.capture_field).filter((f): f is string => Boolean(f))
  );
  return CUSTOM_FIELDS.find((f) => !used.has(f)) ?? null;
}

function insertBeforeScheduling(flow: FlowStep[], step: FlowStep): FlowStep[] {
  const idx = flow.findIndex((s) => (s.key || "").toUpperCase() === "SCHEDULING");
  if (idx < 0) return [...flow, step];
  const next = [...flow];
  next.splice(idx, 0, step);
  return next;
}

type Props = {
  flow: FlowStep[];
  onChange: (flow: FlowStep[]) => void;
  readonly?: boolean;
};

/**
 * Owner-friendly extras on top of the fixed 4 lead questions.
 * Adds text or button questions stored in config.flow (custom_1..5).
 */
export function ExtraQuestionsEditor({ flow, onChange, readonly = false }: Props) {
  const extras = flow.filter(isExtraStep);

  function addQuestion(kind: "text" | "buttons") {
    if (readonly) return;
    if (flow.length >= FLOW_MAX) {
      toast.error(`Max ${FLOW_MAX} steps in the conversation`);
      return;
    }
    const field = nextCustomField(flow);
    if (!field) {
      toast.error("You can add up to 5 extra questions");
      return;
    }
    const n = extras.length + 1;
    const options: FlowStepOption[] =
      kind === "buttons"
        ? [
            { id: nid("opt"), title: "Option 1", value: "Option 1" },
            { id: nid("opt"), title: "Option 2", value: "Option 2" },
          ]
        : [];
    const step: FlowStep = {
      id: nid("step"),
      key: `EXTRA_${n}_${Date.now().toString(36).toUpperCase()}`.slice(0, 32),
      type: kind === "buttons" ? "list_options" : "text_question",
      question_text:
        kind === "buttons"
          ? "Neeche se muntakhib karein."
          : "Aapka sawaal yahan likhein…",
      options,
      capture_field: field,
      required: true,
      skip_if_declined: false,
      reserved: false,
      system: false,
    };
    onChange(insertBeforeScheduling(flow, step));
  }

  function patchExtra(id: string, patch: Partial<FlowStep>) {
    onChange(flow.map((s) => (s.id === id ? { ...s, ...patch } : s)));
  }

  function removeExtra(id: string) {
    onChange(flow.filter((s) => s.id !== id));
  }

  return (
    <div className="space-y-3 rounded-2xl border border-dashed border-border bg-card/60 p-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h3 className="text-sm font-semibold">Extra questions</h3>
          <p className="mt-0.5 text-xs text-muted-foreground">
            Add your own steps after the built-in ones (before demo booking). Up to 5.
          </p>
        </div>
        {!readonly && (
          <div className="flex flex-wrap gap-2">
            <Button
              type="button"
              size="sm"
              variant="outline"
              onClick={() => addQuestion("text")}
            >
              <Plus className="h-3.5 w-3.5" />
              Text question
            </Button>
            <Button
              type="button"
              size="sm"
              variant="outline"
              onClick={() => addQuestion("buttons")}
            >
              <Plus className="h-3.5 w-3.5" />
              Buttons question
            </Button>
          </div>
        )}
      </div>

      {!extras.length && (
        <p className="rounded-xl bg-muted/40 px-3 py-4 text-center text-xs text-muted-foreground">
          No extra questions yet. Tap <strong>Text question</strong> (customer types an answer) or{" "}
          <strong>Buttons question</strong> (customer taps a choice).
        </p>
      )}

      {extras.map((step, i) => {
        const isButtons =
          step.type === "button_options" || step.type === "list_options";
        const items: OptionListItem[] = (step.options || []).map((o) => ({
          id: o.id,
          label: o.title,
          value: o.value || o.sheet_value || o.title,
        }));
        return (
          <AccordionSection
            key={step.id}
            title={`${i + 1}. ${isButtons ? "Buttons" : "Text"} question`}
            count={isButtons ? items.length : undefined}
            countLabel={isButtons ? (items.length === 1 ? "button" : "buttons") : undefined}
            defaultOpen
          >
            <div className="space-y-3">
              <div>
                <Label>Question text</Label>
                <Textarea
                  className="mt-1.5"
                  rows={2}
                  value={step.question_text || ""}
                  disabled={readonly}
                  onChange={(e) =>
                    patchExtra(step.id, { question_text: e.target.value.slice(0, 1024) })
                  }
                />
              </div>
              {isButtons && (
                <OptionListEditor
                  title="Buttons"
                  items={items}
                  constraints={{ maxItems: 10, maxLabelChars: 50, maxValueChars: 64 }}
                  features={{ reorder: true, valueField: true, valueLabel: "Saved as" }}
                  addDisabledHint="WhatsApp list limit: 10 rows"
                  onChange={(next) =>
                    patchExtra(step.id, {
                      type: "list_options",
                      options: next.slice(0, 10).map((it) => ({
                        id: it.id,
                        title: it.label.slice(0, 50),
                        value: (it.value || it.label).trim() || it.label,
                      })),
                    })
                  }
                />
              )}
              {!readonly && (
                <Button
                  type="button"
                  size="sm"
                  variant="ghost"
                  className="text-destructive"
                  onClick={() => removeExtra(step.id)}
                >
                  <Trash2 className="h-3.5 w-3.5" />
                  Remove this question
                </Button>
              )}
            </div>
          </AccordionSection>
        );
      })}
    </div>
  );
}
