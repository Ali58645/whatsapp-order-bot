import {
  DndContext,
  DragEndEvent,
  PointerSensor,
  closestCenter,
  useSensor,
  useSensors,
} from "@dnd-kit/core";
import {
  SortableContext,
  arrayMove,
  useSortable,
  verticalListSortingStrategy,
} from "@dnd-kit/sortable";
import { CSS } from "@dnd-kit/utilities";
import { GripVertical, Plus, Trash2 } from "lucide-react";
import { type ReactNode } from "react";
import { toast } from "sonner";
import { FlowStep, FlowStepOption } from "../api";
import { cn } from "../lib/utils";
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
    next_key?: string;
  }>;
  locations?: Array<{ id: string; title: string; value?: string; next_key?: string }>;
  current_system?: Array<{
    id: string;
    title: string;
    sheet_value?: string;
    next_key?: string;
  }>;
};

type LeadDraft = {
  q_business_type?: string;
  q_locations?: string;
  q_current_system?: string;
  q_scheduling?: string;
  [key: string]: string | undefined;
};

/** Built-in lead steps owners can remove / restore / rename. */
export type RemovableLeadStep =
  | "BUSINESS_TYPE"
  | "LOCATIONS"
  | "CURRENT_SYSTEM"
  | "SCHEDULING";

const REMOVABLE: RemovableLeadStep[] = [
  "BUSINESS_TYPE",
  "LOCATIONS",
  "CURRENT_SYSTEM",
  "SCHEDULING",
];

const REMOVABLE_SET = new Set<string>(REMOVABLE);

/** Always first / last — not shown in the arrangeable Questions list. */
const ANCHOR_KEYS = new Set(["GREETING", "BUSINESS_NAME", "CONFIRMED", "STALLED"]);

const FLOW_MAX = 20;
const CUSTOM_FIELDS = ["custom_1", "custom_2", "custom_3", "custom_4", "custom_5"] as const;

const STEP_META: Record<RemovableLeadStep, { title: string; restoreLabel: string }> = {
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
    label: "Business type",
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
    type: "list_options",
    label: "Locations",
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
    type: "list_options",
    label: "Current system",
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
  SCHEDULING: {
    id: "step_scheduling",
    key: "SCHEDULING",
    type: "button_options",
    label: "Demo scheduling",
    question_text: "",
    question_key: "q_scheduling",
    options: [],
    capture_field: "demo_slot",
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
  DEFAULT_BUILTIN.SCHEDULING,
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

function nid(prefix: string) {
  return `${prefix}_${Math.random().toString(36).slice(2, 10)}`;
}

function resolveFlow(flow: FlowStep[] | undefined): FlowStep[] {
  return flow && flow.length ? flow : DEFAULT_LEAD_FLOW;
}

function cloneFlow(flow: FlowStep[]): FlowStep[] {
  return flow.map((s) => ({ ...s, options: [...(s.options || [])] }));
}

/**
 * Ensure a full lead flow exists before mutating (e.g. adding Extra questions).
 * Salvages orphan extras if greeting/confirm were never seeded.
 */
export function ensureLeadFlow(flow: FlowStep[] | undefined): FlowStep[] {
  if (!flow || !flow.length) return cloneFlow(DEFAULT_LEAD_FLOW);
  const keys = new Set(flow.map((s) => (s.key || "").toUpperCase()));
  if (keys.has("GREETING") && keys.has("CONFIRMED")) return cloneFlow(flow);

  const reserved = new Set([
    "GREETING",
    "BUSINESS_NAME",
    "BUSINESS_TYPE",
    "LOCATIONS",
    "CURRENT_SYSTEM",
    "SCHEDULING",
    "CONFIRMED",
    "STALLED",
  ]);
  const extras = flow.filter((s) => !reserved.has((s.key || "").toUpperCase()));
  const base = cloneFlow(DEFAULT_LEAD_FLOW);
  const insertAt = (() => {
    const sched = base.findIndex((s) => (s.key || "").toUpperCase() === "SCHEDULING");
    if (sched >= 0) return sched;
    const conf = base.findIndex((s) => (s.key || "").toUpperCase() === "CONFIRMED");
    return conf >= 0 ? conf : base.length;
  })();
  return [...base.slice(0, insertAt), ...extras.map((s) => ({ ...s })), ...base.slice(insertAt)];
}

function isRemovableKey(key: string | undefined): key is RemovableLeadStep {
  return Boolean(key && REMOVABLE_SET.has(key.toUpperCase()));
}

function isExtraStep(step: FlowStep): boolean {
  const key = (step.key || "").toUpperCase();
  if (ANCHOR_KEYS.has(key) || REMOVABLE_SET.has(key)) return false;
  if (step.reserved || step.system) return false;
  return true;
}

/** Built-ins + extras owners can drag (excludes greeting / business name / confirm). */
function arrangableSteps(flow: FlowStep[] | undefined): FlowStep[] {
  return ensureLeadFlow(flow).filter((s) => {
    const key = (s.key || "").toUpperCase();
    return !ANCHOR_KEYS.has(key);
  });
}

type Props = {
  lead: LeadDraft;
  interactive: Interactive;
  demoSlots: string[];
  onLeadChange: (lead: LeadDraft) => void;
  onInteractiveChange: (interactive: Interactive) => void;
  onDemoSlotsChange: (slots: string[]) => void;
  /** When set with onFlowChange, owners can remove/restore/rename/reorder steps */
  flow?: FlowStep[];
  onFlowChange?: (flow: FlowStep[]) => void;
  allowRemove?: boolean;
  /** Show + Text / + Buttons to add custom steps into the same list */
  allowExtras?: boolean;
  readonly?: boolean;
};

function btToItems(rows: Interactive["business_types"] = []): OptionListItem[] {
  return rows.map((r) => ({
    id: r.id,
    label: r.title || "",
    value: r.value || r.title || "",
    description: r.description || "",
    next_key: r.next_key || "",
  }));
}

function locToItems(rows: Interactive["locations"] = []): OptionListItem[] {
  return rows.map((r) => ({
    id: r.id,
    label: r.title || "",
    value: r.value || r.title || "",
    next_key: r.next_key || "",
  }));
}

function sysToItems(rows: Interactive["current_system"] = []): OptionListItem[] {
  return rows.map((r) => ({
    id: r.id,
    label: r.title || "",
    value: r.sheet_value || r.title || "",
    next_key: r.next_key || "",
  }));
}

function branchTargets(
  flow: FlowStep[] | undefined,
  excludeKey?: string
): { value: string; label: string }[] {
  const exclude = (excludeKey || "").toUpperCase();
  return ensureLeadFlow(flow)
    .filter((s) => {
      const k = (s.key || "").toUpperCase();
      if (k === "GREETING" || k === exclude) return false;
      return true;
    })
    .map((s) => {
      const k = (s.key || "").toUpperCase();
      const label =
        (s.label || "").trim() ||
        (isRemovableKey(k) ? STEP_META[k].title : k);
      return { value: k, label: `${label} (${k})` };
    });
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

function stepTitle(flow: FlowStep[] | undefined, key: RemovableLeadStep): string {
  const s = resolveFlow(flow).find((x) => (x.key || "").toUpperCase() === key);
  const custom = (s?.label || "").trim();
  return custom || STEP_META[key].title;
}

function insertBuiltin(flow: FlowStep[], key: RemovableLeadStep): FlowStep[] {
  const base = resolveFlow(flow);
  if (base.some((s) => (s.key || "").toUpperCase() === key)) return base;
  const step = { ...DEFAULT_BUILTIN[key] };
  const order = ["BUSINESS_NAME", "BUSINESS_TYPE", "LOCATIONS", "CURRENT_SYSTEM", "SCHEDULING"];
  const targetIdx = order.indexOf(key);
  const next = [...base];
  let insertAt = next.findIndex((s) => (s.key || "").toUpperCase() === "CONFIRMED");
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

function nextCustomField(flow: FlowStep[]): (typeof CUSTOM_FIELDS)[number] | null {
  const used = new Set(
    flow.map((s) => s.capture_field).filter((f): f is string => Boolean(f))
  );
  return CUSTOM_FIELDS.find((f) => !used.has(f)) ?? null;
}

function insertBeforeScheduling(flow: FlowStep[], step: FlowStep): FlowStep[] {
  const idx = flow.findIndex((s) => (s.key || "").toUpperCase() === "SCHEDULING");
  if (idx < 0) {
    const confirmIdx = flow.findIndex((s) => (s.key || "").toUpperCase() === "CONFIRMED");
    if (confirmIdx >= 0) {
      const next = [...flow];
      next.splice(confirmIdx, 0, step);
      return next;
    }
    return [...flow, step];
  }
  const next = [...flow];
  next.splice(idx, 0, step);
  return next;
}

function SortableStepShell({
  id,
  canDrag,
  children,
}: {
  id: string;
  canDrag: boolean;
  children: (leading: ReactNode | undefined) => ReactNode;
}) {
  const { attributes, listeners, setNodeRef, transform, transition, isDragging } = useSortable({
    id,
    disabled: !canDrag,
  });
  const style = {
    transform: CSS.Transform.toString(transform),
    transition,
  };
  const leading = canDrag ? (
    <button
      type="button"
      className="flex cursor-grab items-center px-3 text-muted-foreground touch-none active:cursor-grabbing"
      {...attributes}
      {...listeners}
      aria-label="Drag to reorder"
      onClick={(e) => e.stopPropagation()}
    >
      <GripVertical className="h-4 w-4" />
    </button>
  ) : undefined;

  return (
    <div
      ref={setNodeRef}
      style={style}
      className={cn(isDragging && "relative z-10 opacity-90 shadow-elevated")}
    >
      {children(leading)}
    </div>
  );
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
  allowExtras = true,
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

  const sensors = useSensors(
    useSensor(PointerSensor, { activationConstraint: { distance: 6 } })
  );

  const steps = arrangableSteps(flow);
  const sortableIds = steps.map((s) => s.id);
  const canReorder = Boolean(onFlowChange) && !readonly && steps.length > 1;
  const showExtras = Boolean(onFlowChange) && allowExtras;

  function setLeadQ(key: keyof LeadDraft, value: string) {
    onLeadChange({ ...lead, [key]: value });
  }

  function setStepNextKey(stepKey: string, nextKey: string) {
    if (!onFlowChange) return;
    const nk = nextKey.trim().toUpperCase();
    onFlowChange(
      ensureLeadFlow(flow).map((s) =>
        (s.key || "").toUpperCase() === stepKey.toUpperCase()
          ? { ...s, next_key: nk || null }
          : s
      )
    );
  }

  function StepNextKeyField({
    stepKey,
    current,
  }: {
    stepKey: string;
    current?: string | null;
  }) {
    if (!onFlowChange || readonly) return null;
    const targets = branchTargets(flow, stepKey);
    if (!targets.length) return null;
    return (
      <div>
        <Label>After answer, go to</Label>
        <select
          className="mt-1.5 flex h-9 w-full rounded-md border border-border bg-background px-3 text-sm"
          value={(current || "").toUpperCase()}
          onChange={(e) => setStepNextKey(stepKey, e.target.value)}
        >
          <option value="">Next in list (default)</option>
          {targets.map((t) => (
            <option key={t.value} value={t.value}>
              {t.label}
            </option>
          ))}
        </select>
        <p className="mt-1 text-[11px] text-muted-foreground">
          Use this for niche paths — e.g. after Assisted Living questions jump to Demo scheduling.
        </p>
      </div>
    );
  }

  const gotoTargets = branchTargets(flow);

  function removeStep(key: RemovableLeadStep) {
    if (!onFlowChange) return;
    onFlowChange(ensureLeadFlow(flow).filter((s) => (s.key || "").toUpperCase() !== key));
  }

  function restoreStep(key: RemovableLeadStep) {
    if (!onFlowChange) return;
    onFlowChange(insertBuiltin(ensureLeadFlow(flow), key));
  }

  function renameStep(key: RemovableLeadStep, label: string) {
    if (!onFlowChange) return;
    const nextLabel = label.slice(0, 40);
    const base = ensureLeadFlow(flow);
    if (!base.some((s) => (s.key || "").toUpperCase() === key)) {
      onFlowChange(
        insertBuiltin(base, key).map((s) =>
          (s.key || "").toUpperCase() === key ? { ...s, label: nextLabel } : s
        )
      );
      return;
    }
    onFlowChange(
      base.map((s) =>
        (s.key || "").toUpperCase() === key ? { ...s, label: nextLabel } : s
      )
    );
  }

  function patchExtra(id: string, patch: Partial<FlowStep>) {
    if (!onFlowChange) return;
    onFlowChange(ensureLeadFlow(flow).map((s) => (s.id === id ? { ...s, ...patch } : s)));
  }

  function removeExtra(id: string) {
    if (!onFlowChange) return;
    onFlowChange(ensureLeadFlow(flow).filter((s) => s.id !== id));
  }

  function addExtra(kind: "text" | "buttons") {
    if (!onFlowChange || readonly) return;
    const current = ensureLeadFlow(flow);
    if (current.length >= FLOW_MAX) {
      toast.error(`Max ${FLOW_MAX} steps in the conversation`);
      return;
    }
    const field = nextCustomField(current);
    if (!field) {
      toast.error("You can add up to 5 extra questions");
      return;
    }
    const n = current.filter(isExtraStep).length + 1;
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
      type: kind === "buttons" ? "list_options" : "free_text_capture",
      label: kind === "buttons" ? "Buttons question" : "Text question",
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
    onFlowChange(insertBeforeScheduling(current, step));
  }

  function onDragEnd(event: DragEndEvent) {
    if (!onFlowChange || !canReorder) return;
    const { active, over } = event;
    if (!over || active.id === over.id) return;
    const base = ensureLeadFlow(flow);
    const oldIndex = base.findIndex((s) => s.id === active.id);
    const newIndex = base.findIndex((s) => s.id === over.id);
    if (oldIndex < 0 || newIndex < 0 || oldIndex === newIndex) return;
    onFlowChange(arrayMove(base, oldIndex, newIndex));
  }

  const missing = REMOVABLE.filter((k) => !hasStep(flow, k));

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

  function SectionNameField({ stepKey }: { stepKey: RemovableLeadStep }) {
    if (!onFlowChange || readonly) return null;
    const value = stepTitle(flow, stepKey);
    return (
      <div>
        <div className="mb-1 flex items-center justify-between">
          <Label>Section name</Label>
          <CharHint len={value.length} max={40} />
        </div>
        <Input
          className="mt-1"
          maxLength={40}
          value={value}
          onChange={(e) => renameStep(stepKey, e.target.value)}
          placeholder={STEP_META[stepKey].title}
        />
        <p className="mt-1 text-[11px] text-muted-foreground">
          Shown in My Bot / Settings only — WhatsApp uses the question text below.
        </p>
      </div>
    );
  }

  function renderBuiltin(stepKey: RemovableLeadStep, index: number, leading?: ReactNode) {
    const title = `${index + 1}. ${stepTitle(flow, stepKey)}`;

    if (stepKey === "BUSINESS_TYPE") {
      return (
        <AccordionSection
          title={title}
          count={btItems.length}
          countLabel={btItems.length === 1 ? "row" : "rows"}
          defaultOpen={index === 0}
          leading={leading}
        >
          <SectionNameField stepKey="BUSINESS_TYPE" />
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
            constraints={{ maxItems: 10, maxLabelChars: 50, maxValueChars: 64, maxDescriptionChars: 72 }}
            features={{
              reorder: true,
              valueField: true,
              valueLabel: "Saved as",
              descriptionField: true,
              nextKeyField: Boolean(onFlowChange) && !readonly,
              nextKeyOptions: gotoTargets.filter((t) => t.value !== "BUSINESS_TYPE"),
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
                  ...(it.next_key ? { next_key: it.next_key } : {}),
                })),
              });
            }}
          />
          <StepNextKeyField
            stepKey="BUSINESS_TYPE"
            current={
              ensureLeadFlow(flow).find((s) => (s.key || "").toUpperCase() === "BUSINESS_TYPE")
                ?.next_key
            }
          />
          <RemoveBtn stepKey="BUSINESS_TYPE" />
        </AccordionSection>
      );
    }

    if (stepKey === "LOCATIONS") {
      return (
        <AccordionSection
          title={title}
          count={locItems.length}
          countLabel={locItems.length === 1 ? "row" : "rows"}
          leading={leading}
        >
          <SectionNameField stepKey="LOCATIONS" />
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
            title="Rows"
            items={locItems}
            constraints={{ maxItems: 10, maxLabelChars: 50, maxValueChars: 64 }}
            features={{
              reorder: true,
              valueField: true,
              valueLabel: "Saved as",
              nextKeyField: Boolean(onFlowChange) && !readonly,
              nextKeyOptions: gotoTargets.filter((t) => t.value !== "LOCATIONS"),
            }}
            addDisabledHint="WhatsApp list limit: 10 rows"
            onChange={(items) => {
              onInteractiveChange({
                ...interactive,
                locations: items.slice(0, 10).map((it) => ({
                  id: it.id,
                  title: it.label.slice(0, 50),
                  value: (it.value || it.label).trim() || it.label,
                  ...(it.next_key ? { next_key: it.next_key } : {}),
                })),
              });
            }}
          />
          <StepNextKeyField
            stepKey="LOCATIONS"
            current={
              ensureLeadFlow(flow).find((s) => (s.key || "").toUpperCase() === "LOCATIONS")?.next_key
            }
          />
          <RemoveBtn stepKey="LOCATIONS" />
        </AccordionSection>
      );
    }

    if (stepKey === "CURRENT_SYSTEM") {
      return (
        <AccordionSection
          title={title}
          count={sysItems.length}
          countLabel={sysItems.length === 1 ? "row" : "rows"}
          leading={leading}
        >
          <SectionNameField stepKey="CURRENT_SYSTEM" />
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
            title="Rows"
            items={sysItems}
            constraints={{ maxItems: 10, maxLabelChars: 50, maxValueChars: 64 }}
            features={{
              reorder: true,
              valueField: true,
              valueLabel: "Value for sheet",
              nextKeyField: Boolean(onFlowChange) && !readonly,
              nextKeyOptions: gotoTargets.filter((t) => t.value !== "CURRENT_SYSTEM"),
            }}
            addDisabledHint="WhatsApp list limit: 10 rows"
            onChange={(items) => {
              onInteractiveChange({
                ...interactive,
                current_system: items.slice(0, 10).map((it) => ({
                  id: it.id,
                  title: it.label.slice(0, 50),
                  sheet_value: (it.value || it.label).trim() || it.label,
                  ...(it.next_key ? { next_key: it.next_key } : {}),
                })),
              });
            }}
          />
          <StepNextKeyField
            stepKey="CURRENT_SYSTEM"
            current={
              ensureLeadFlow(flow).find((s) => (s.key || "").toUpperCase() === "CURRENT_SYSTEM")
                ?.next_key
            }
          />
          <RemoveBtn stepKey="CURRENT_SYSTEM" />
        </AccordionSection>
      );
    }

    return (
      <AccordionSection
        title={title}
        count={schedulingItems.length}
        countLabel="slot buttons"
        leading={leading}
      >
        <SectionNameField stepKey="SCHEDULING" />
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
          addDisabledHint="WhatsApp reply-button limit: 3 (2 slots + other)"
          disabled={readonly}
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
          WhatsApp allows 3 reply buttons max — 2 time slots + “another time”. You can remove this
          whole step if you don’t book demos.
        </p>
        <RemoveBtn stepKey="SCHEDULING" />
      </AccordionSection>
    );
  }

  function renderExtra(step: FlowStep, index: number, leading?: ReactNode) {
    const isButtons =
      step.type === "button_options" || step.type === "list_options";
    const items: OptionListItem[] = (step.options || []).map((o) => ({
      id: o.id,
      label: o.title,
      value: o.value || o.sheet_value || o.title,
      next_key: o.next_key || "",
    }));
    const label =
      (step.label || "").trim() ||
      (isButtons ? "Buttons question" : "Text question");
    const stepKey = (step.key || "").toUpperCase();

    return (
      <AccordionSection
        title={`${index + 1}. ${label}`}
        count={isButtons ? items.length : undefined}
        countLabel={isButtons ? (items.length === 1 ? "button" : "buttons") : undefined}
        defaultOpen
        leading={leading}
        className="border-dashed"
      >
        <div className="space-y-3">
          <div>
            <div className="mb-1 flex items-center justify-between">
              <Label>Section name</Label>
              <CharHint len={label.length} max={40} />
            </div>
            <Input
              className="mt-1"
              maxLength={40}
              value={label}
              disabled={readonly}
              onChange={(e) => patchExtra(step.id, { label: e.target.value.slice(0, 40) })}
            />
          </div>
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
              features={{
                reorder: true,
                valueField: true,
                valueLabel: "Saved as",
                nextKeyField: !readonly,
                nextKeyOptions: gotoTargets.filter((t) => t.value !== stepKey),
              }}
              addDisabledHint="WhatsApp list limit: 10 rows"
              onChange={(next) =>
                patchExtra(step.id, {
                  type: "list_options",
                  options: next.slice(0, 10).map((it) => ({
                    id: it.id,
                    title: it.label.slice(0, 50),
                    value: (it.value || it.label).trim() || it.label,
                    ...(it.next_key ? { next_key: it.next_key } : {}),
                  })),
                })
              }
            />
          )}
          <StepNextKeyField stepKey={stepKey} current={step.next_key} />
          {!readonly && onFlowChange && (
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

      {showExtras && !readonly && (
        <div className="flex flex-wrap items-center justify-between gap-2">
          <p className="text-xs text-muted-foreground">
            Drag to set order. On each option, use <strong>Then go to</strong> for niche branches
            (e.g. Assisted living → its questions → Demo).
          </p>
          <div className="flex flex-wrap gap-2">
            <Button type="button" size="sm" variant="outline" onClick={() => addExtra("text")}>
              <Plus className="h-3.5 w-3.5" />
              Text question
            </Button>
            <Button type="button" size="sm" variant="outline" onClick={() => addExtra("buttons")}>
              <Plus className="h-3.5 w-3.5" />
              Buttons question
            </Button>
          </div>
        </div>
      )}

      {!showExtras && canReorder && (
        <p className="text-xs text-muted-foreground">
          Drag the handle to change the order WhatsApp asks these questions.
        </p>
      )}

      <DndContext sensors={sensors} collisionDetection={closestCenter} onDragEnd={onDragEnd}>
        <SortableContext items={sortableIds} strategy={verticalListSortingStrategy}>
          <div className="space-y-3">
            {steps.map((step, index) => {
              const key = (step.key || "").toUpperCase();
              return (
                <SortableStepShell key={step.id} id={step.id} canDrag={canReorder}>
                  {(leading) =>
                    isRemovableKey(key)
                      ? renderBuiltin(key, index, leading)
                      : renderExtra(step, index, leading)
                  }
                </SortableStepShell>
              );
            })}
          </div>
        </SortableContext>
      </DndContext>
    </div>
  );
}
