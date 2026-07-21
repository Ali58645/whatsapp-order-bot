import { Trash2 } from "lucide-react";
import { FlowStep } from "../api";
import { Input, Label, Textarea } from "./ui/input";
import { AccordionSection } from "./ui/accordion-section";
import { OptionListEditor, OptionListItem } from "./OptionListEditor";
import { Button } from "./ui/button";

type Interactive = {
  select_button_label?: string;
  slot_other_label?: string;
  business_types?: Array<{
    id: string;
    title: string;
    description?: string;
    value?: string;
  }>;
  locations?: Array<{ id: string; title: string; value?: string }>;
  current_system?: Array<{ id: string; title: string; sheet_value?: string }>;
};

type LeadDraft = {
  q_business_type?: string;
  q_locations?: string;
  q_current_system?: string;
  q_scheduling?: string;
  [key: string]: string | undefined;
};

/** Built-in lead steps owners can remove (scheduling is required). */
export type RemovableLeadStep = "BUSINESS_TYPE" | "LOCATIONS" | "CURRENT_SYSTEM";

const REMOVABLE: RemovableLeadStep[] = ["BUSINESS_TYPE", "LOCATIONS", "CURRENT_SYSTEM"];

const STEP_META: Record<
  RemovableLeadStep | "SCHEDULING",
  { title: string; restoreLabel: string }
> = {
  BUSINESS_TYPE: { title: "Business type", restoreLabel: "Business type" },
  LOCATIONS: { title: "Locations", restoreLabel: "Locations" },
  CURRENT_SYSTEM: { title: "Current system", restoreLabel: "Current system" },
  SCHEDULING: { title: "Demo scheduling", restoreLabel: "Demo scheduling" },
};

const DEFAULT_BUILTIN: Record<RemovableLeadStep, FlowStep> = {
  BUSINESS_TYPE: {
    id: "step_business_type",
    key: "BUSINESS_TYPE",
    type: "list_options",
    question_text: "",
    question_key: "q_business_type",
    options_key: "business_types",
    options: [],
    capture_field: "business_type",
    required: true,
    skip_if_declined: false,
    reserved: false,
    system: false,
  },
  LOCATIONS: {
    id: "step_locations",
    key: "LOCATIONS",
    type: "button_options",
    question_text: "",
    question_key: "q_locations",
    options_key: "locations",
    options: [],
    capture_field: "locations",
    required: true,
    skip_if_declined: false,
    reserved: false,
    system: false,
  },
  CURRENT_SYSTEM: {
    id: "step_current_system",
    key: "CURRENT_SYSTEM",
    type: "button_options",
    question_text: "",
    question_key: "q_current_system",
    options_key: "current_system",
    options: [],
    capture_field: "current_system",
    required: true,
    skip_if_declined: false,
    reserved: false,
    system: false,
  },
};

/** Minimal default lead flow so remove works before first custom save. */
const DEFAULT_LEAD_FLOW: FlowStep[] = [
  {
    id: "step_greeting",
    key: "GREETING",
    type: "text_question",
    question_text: "",
    options: [],
    capture_field: null,
    required: true,
    reserved: true,
    system: true,
  },
  {
    id: "step_business_name",
    key: "BUSINESS_NAME",
    type: "text_question",
    question_text: "",
    question_key: "q_business_name",
    options: [],
    capture_field: "business_name",
    required: true,
    reserved: false,
    system: false,
  },
  DEFAULT_BUILTIN.BUSINESS_TYPE,
  DEFAULT_BUILTIN.LOCATIONS,
  DEFAULT_BUILTIN.CURRENT_SYSTEM,
  {
    id: "step_scheduling",
    key: "SCHEDULING",
    type: "button_options",
    question_text: "",
    question_key: "q_scheduling",
    options: [],
    capture_field: "demo_slot",
    required: true,
    reserved: true,
    system: true,
  },
  {
    id: "step_confirmed",
    key: "CONFIRMED",
    type: "text_question",
    question_text: "",
    options: [],
    capture_field: null,
    required: true,
    reserved: true,
    system: true,
  },
];

function resolveFlow(flow: FlowStep[] | undefined): FlowStep[] {
  return flow && flow.length ? flow : DEFAULT_LEAD_FLOW;
}

type Props = {
  lead: LeadDraft;
  interactive: Interactive;
  demoSlots: string[];
  onLeadChange: (lead: LeadDraft) => void;
  onInteractiveChange: (interactive: Interactive) => void;
  onDemoSlotsChange: (slots: string[]) => void;
  /** When set with onFlowChange, owners can remove/restore built-in steps */
  flow?: FlowStep[];
  onFlowChange?: (flow: FlowStep[]) => void;
  allowRemove?: boolean;
  readonly?: boolean;
};

function btToItems(rows: Interactive["business_types"] = []): OptionListItem[] {
  return rows.map((r) => ({
    id: r.id,
    label: r.title || "",
    value: r.value || r.title || "",
    description: r.description || "",
  }));
}

function locToItems(rows: Interactive["locations"] = []): OptionListItem[] {
  return rows.map((r) => ({
    id: r.id,
    label: r.title || "",
    value: r.value || r.title || "",
  }));
}

function sysToItems(rows: Interactive["current_system"] = []): OptionListItem[] {
  return rows.map((r) => ({
    id: r.id,
    label: r.title || "",
    value: r.sheet_value || r.title || "",
  }));
}

function CharHint({ len, max }: { len: number; max: number }) {
  const cls =
    len > max
      ? "text-destructive"
      : len >= max - 3
        ? "text-amber-400"
        : "text-muted-foreground";
  return <span className={`text-[11px] tabular-nums ${cls}`}>{len}/{max}</span>;
}

function hasStep(flow: FlowStep[] | undefined, key: string): boolean {
  return resolveFlow(flow).some((s) => (s.key || "").toUpperCase() === key);
}

function insertBuiltin(flow: FlowStep[], key: RemovableLeadStep): FlowStep[] {
  const base = resolveFlow(flow);
  if (base.some((s) => (s.key || "").toUpperCase() === key)) return base;
  const step = { ...DEFAULT_BUILTIN[key] };
  const order = ["BUSINESS_NAME", "BUSINESS_TYPE", "LOCATIONS", "CURRENT_SYSTEM", "SCHEDULING"];
  const targetIdx = order.indexOf(key);
  const next = [...base];
  let insertAt = next.findIndex((s) => (s.key || "").toUpperCase() === "SCHEDULING");
  if (insertAt < 0) insertAt = next.length;
  for (let i = targetIdx - 1; i >= 0; i--) {
    const earlier = next.findIndex((s) => (s.key || "").toUpperCase() === order[i]);
    if (earlier >= 0) {
      insertAt = earlier + 1;
      break;
    }
  }
  next.splice(insertAt, 0, step);
  return next;
}

export function LeadOptionsEditor({
  lead,
  interactive,
  demoSlots,
  onLeadChange,
  onInteractiveChange,
  onDemoSlotsChange,
  flow,
  onFlowChange,
  allowRemove = false,
  readonly = false,
}: Props) {
  const slots = demoSlots.length >= 2 ? demoSlots : [demoSlots[0] || "", demoSlots[0] || ""];
  const slotOther = interactive.slot_other_label || "Koi aur time";

  const btItems = btToItems(interactive.business_types);
  const locItems = locToItems(interactive.locations);
  const sysItems = sysToItems(interactive.current_system);

  const schedulingItems: OptionListItem[] = [
    { id: "slot_1", label: (slots[0] || "").slice(0, 20), locked: true },
    { id: "slot_2", label: (slots[1] || "").slice(0, 20), locked: true },
    { id: "slot_other", label: slotOther.slice(0, 20), locked: true },
  ];

  function setLeadQ(key: keyof LeadDraft, value: string) {
    onLeadChange({ ...lead, [key]: value });
  }

  function removeStep(key: RemovableLeadStep) {
    if (!onFlowChange) return;
    onFlowChange(resolveFlow(flow).filter((s) => (s.key || "").toUpperCase() !== key));
  }

  function restoreStep(key: RemovableLeadStep) {
    if (!onFlowChange) return;
    onFlowChange(insertBuiltin(flow, key));
  }

  const showBt = hasStep(flow, "BUSINESS_TYPE");
  const showLoc = hasStep(flow, "LOCATIONS");
  const showSys = hasStep(flow, "CURRENT_SYSTEM");
  const showSched = hasStep(flow, "SCHEDULING");

  const missing = REMOVABLE.filter((k) => !hasStep(flow, k));
  let n = 0;
  const num = () => {
    n += 1;
    return n;
  };

  function RemoveBtn({ stepKey }: { stepKey: RemovableLeadStep }) {
    if (!allowRemove || readonly || !onFlowChange) return null;
    return (
      <Button
        type="button"
        size="sm"
        variant="ghost"
        className="text-destructive"
        onClick={() => removeStep(stepKey)}
      >
        <Trash2 className="h-3.5 w-3.5" />
        Remove this question
      </Button>
    );
  }

  return (
    <div className="space-y-3">
      {allowRemove && missing.length > 0 && onFlowChange && !readonly && (
        <div className="rounded-xl border border-dashed border-border bg-muted/20 px-3 py-3">
          <p className="text-xs font-medium text-muted-foreground">Removed — tap to restore</p>
          <div className="mt-2 flex flex-wrap gap-2">
            {missing.map((k) => (
              <Button
                key={k}
                type="button"
                size="sm"
                variant="outline"
                onClick={() => restoreStep(k)}
              >
                + {STEP_META[k].restoreLabel}
              </Button>
            ))}
          </div>
        </div>
      )}

      {showBt && (
        <AccordionSection
          title={`${num()}. ${STEP_META.BUSINESS_TYPE.title}`}
          count={btItems.length}
          countLabel={btItems.length === 1 ? "row" : "rows"}
          defaultOpen
        >
          <div>
            <div className="mb-1 flex items-center justify-between">
              <Label>Question text</Label>
              <CharHint len={(lead.q_business_type || "").length} max={1024} />
            </div>
            <Textarea
              rows={2}
              className="mt-1"
              value={lead.q_business_type || ""}
              onChange={(e) => setLeadQ("q_business_type", e.target.value)}
              disabled={readonly}
            />
          </div>
          <div>
            <div className="mb-1 flex items-center justify-between">
              <Label>List button label</Label>
              <CharHint len={(interactive.select_button_label || "").length} max={20} />
            </div>
            <Input
              className="mt-1"
              maxLength={24}
              value={interactive.select_button_label || ""}
              disabled={readonly}
              onChange={(e) =>
                onInteractiveChange({
                  ...interactive,
                  select_button_label: e.target.value.slice(0, 20),
                })
              }
              placeholder="Muntakhib karein"
            />
          </div>
          <OptionListEditor
            title="Rows"
            items={btItems}
            constraints={{ maxItems: 10, maxLabelChars: 24, maxValueChars: 64, maxDescriptionChars: 72 }}
            features={{
              reorder: true,
              valueField: true,
              valueLabel: "Saved as",
              descriptionField: true,
            }}
            addDisabledHint="WhatsApp list limit: 10 rows"
            onChange={(items) => {
              onInteractiveChange({
                ...interactive,
                business_types: items.map((it) => ({
                  id: it.id,
                  title: it.label,
                  value: (it.value || it.label).trim() || it.label,
                  description: it.description || "",
                })),
              });
            }}
          />
          <RemoveBtn stepKey="BUSINESS_TYPE" />
        </AccordionSection>
      )}

      {showLoc && (
        <AccordionSection
          title={`${num()}. ${STEP_META.LOCATIONS.title}`}
          count={locItems.length}
          countLabel={locItems.length === 1 ? "button" : "buttons"}
        >
          <div>
            <Label>Question text</Label>
            <Textarea
              rows={2}
              className="mt-1.5"
              value={lead.q_locations || ""}
              disabled={readonly}
              onChange={(e) => setLeadQ("q_locations", e.target.value)}
            />
          </div>
          <OptionListEditor
            title="Buttons"
            items={locItems}
            constraints={{ maxItems: 3, maxLabelChars: 20, maxValueChars: 64 }}
            features={{ reorder: true, valueField: true, valueLabel: "Value" }}
            addDisabledHint="Button limit: 3"
            onChange={(items) => {
              onInteractiveChange({
                ...interactive,
                locations: items.slice(0, 3).map((it) => ({
                  id: it.id,
                  title: it.label,
                  value: (it.value || it.label).trim() || it.label,
                })),
              });
            }}
          />
          <RemoveBtn stepKey="LOCATIONS" />
        </AccordionSection>
      )}

      {showSys && (
        <AccordionSection
          title={`${num()}. ${STEP_META.CURRENT_SYSTEM.title}`}
          count={sysItems.length}
          countLabel={sysItems.length === 1 ? "button" : "buttons"}
        >
          <div>
            <Label>Question text</Label>
            <Textarea
              rows={2}
              className="mt-1.5"
              value={lead.q_current_system || ""}
              disabled={readonly}
              onChange={(e) => setLeadQ("q_current_system", e.target.value)}
            />
          </div>
          <OptionListEditor
            title="Buttons"
            items={sysItems}
            constraints={{ maxItems: 3, maxLabelChars: 20, maxValueChars: 64 }}
            features={{ reorder: true, valueField: true, valueLabel: "Value for sheet" }}
            addDisabledHint="Button limit: 3"
            onChange={(items) => {
              onInteractiveChange({
                ...interactive,
                current_system: items.slice(0, 3).map((it) => ({
                  id: it.id,
                  title: it.label,
                  sheet_value: (it.value || it.label).trim() || it.label,
                })),
              });
            }}
          />
          <RemoveBtn stepKey="CURRENT_SYSTEM" />
        </AccordionSection>
      )}

      {showSched && (
        <AccordionSection
          title={`${num()}. ${STEP_META.SCHEDULING.title}`}
          count={schedulingItems.length}
          countLabel="slot buttons"
        >
          <div>
            <Label>Question text</Label>
            <Textarea
              rows={3}
              className="mt-1.5"
              value={lead.q_scheduling || ""}
              disabled={readonly}
              onChange={(e) => setLeadQ("q_scheduling", e.target.value)}
            />
          </div>
          <OptionListEditor
            title="Slot buttons"
            items={schedulingItems}
            constraints={{ maxItems: 3, maxLabelChars: 20 }}
            features={{ reorder: false }}
            addDisabledHint="Scheduling uses 2 slots + other"
            onChange={(items) => {
              const s1 = items.find((i) => i.id === "slot_1")?.label || slots[0];
              const s2 = items.find((i) => i.id === "slot_2")?.label || slots[1];
              const other = items.find((i) => i.id === "slot_other")?.label || slotOther;
              onDemoSlotsChange([s1.slice(0, 64), s2.slice(0, 64)]);
              onInteractiveChange({
                ...interactive,
                slot_other_label: other.slice(0, 20),
              });
            }}
          />
          <p className="text-[11px] text-muted-foreground">
            Required for demo booking — can’t be removed. The third button (“another time”) always stays.
          </p>
        </AccordionSection>
      )}
    </div>
  );
}
