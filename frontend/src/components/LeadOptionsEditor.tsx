import {
  DndContext,
  DragEndEvent,
  DragOverEvent,
  PointerSensor,
  closestCenter,
  useSensor,
  useSensors,
} from "@dnd-kit/core";
import {
  SortableContext,
  useSortable,
  verticalListSortingStrategy,
} from "@dnd-kit/sortable";
import { CSS } from "@dnd-kit/utilities";
import { ChevronDown, GripVertical, Plus, Trash2 } from "lucide-react";
import { useMemo, useState, type ReactNode } from "react";
import { toast } from "sonner";
import { FlowStep, FlowStepOption } from "../api";
import { cn } from "../lib/utils";
import { Input, Label, Textarea } from "./ui/input";
import { OptionListEditor } from "./OptionListEditor";
import { Button } from "./ui/button";
import {
  type InteractiveOpts,
  type TreeQuestionNode,
  childForOption,
  childTriggerId,
  flattenTree,
  flowToTree,
  nestQuestionUnder,
  parentOptionsForChild,
  questionTitle,
  reorderRoots,
  setChildTrigger,
  treeToFlow,
  unnestToRoot,
  normKey,
  isTextLike,
} from "./flowTree";

type Interactive = InteractiveOpts & {
  select_button_label?: string;
  slot_other_label?: string;
};

type LeadDraft = {
  q_business_type?: string;
  q_locations?: string;
  q_current_system?: string;
  q_scheduling?: string;
  [key: string]: string | undefined;
};

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

function isExtraStep(step: FlowStep): boolean {
  const key = (step.key || "").toUpperCase();
  if (ANCHOR_KEYS.has(key) || REMOVABLE_SET.has(key)) return false;
  if (step.reserved || step.system) return false;
  return true;
}

type Props = {
  lead: LeadDraft;
  interactive: Interactive;
  demoSlots: string[];
  onLeadChange: (lead: LeadDraft) => void;
  onInteractiveChange: (interactive: Interactive) => void;
  onDemoSlotsChange: (slots: string[]) => void;
  flow?: FlowStep[];
  onFlowChange?: (flow: FlowStep[]) => void;
  allowRemove?: boolean;
  allowExtras?: boolean;
  readonly?: boolean;
};

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

function preserveNextKeys<T extends { id: string; next_key?: string }>(
  prev: T[] | undefined,
  id: string
): { next_key?: string } {
  const nk = prev?.find((r) => r.id === id)?.next_key;
  return nk ? { next_key: nk } : {};
}

function SortableRow({
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
      className="flex cursor-grab items-center px-2 text-muted-foreground touch-none active:cursor-grabbing"
      {...attributes}
      {...listeners}
      aria-label="Drag to reorder or nest"
      onClick={(e) => e.stopPropagation()}
    >
      <GripVertical className="h-4 w-4" />
    </button>
  ) : (
    <span className="w-8" />
  );

  return (
    <div
      ref={setNodeRef}
      style={style}
      className={cn(isDragging && "relative z-10 opacity-90")}
    >
      {children(leading)}
    </div>
  );
}

function TreeRowShell({
  depth,
  leading,
  title,
  typeLabel,
  isSub,
  open,
  onToggle,
  nestHighlight,
  children,
}: {
  depth: number;
  leading?: ReactNode;
  title: string;
  typeLabel: string;
  isSub: boolean;
  open: boolean;
  onToggle: () => void;
  nestHighlight?: boolean;
  children: ReactNode;
}) {
  return (
    <div style={{ marginLeft: depth * 24 }} className="mb-1.5">
      <div
        className={cn(
          "overflow-hidden rounded-md border bg-card",
          nestHighlight ? "border-primary ring-1 ring-primary/40" : "border-border"
        )}
      >
        <div className="flex items-stretch">
          {leading}
          <button
            type="button"
            onClick={onToggle}
            aria-expanded={open}
            className="flex min-w-0 flex-1 items-center gap-2 px-3 py-2.5 text-left hover:bg-muted/30 focus-ring"
          >
            <div className="min-w-0 flex-1">
              <div className="flex flex-wrap items-baseline gap-2">
                <span className="text-sm font-medium text-foreground">{title}</span>
                {isSub && (
                  <span className="text-[11px] italic text-muted-foreground">sub item</span>
                )}
              </div>
            </div>
            <span className="shrink-0 text-[11px] text-muted-foreground">{typeLabel}</span>
            <ChevronDown
              className={cn(
                "h-4 w-4 shrink-0 text-muted-foreground transition-transform",
                open && "rotate-180"
              )}
            />
          </button>
        </div>
        {open && (
          <div className="space-y-3 border-t border-border px-3 py-3">{children}</div>
        )}
      </div>
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

  const [openIds, setOpenIds] = useState<Record<string, boolean>>({});
  const [nestOverId, setNestOverId] = useState<string | null>(null);

  const baseFlow = ensureLeadFlow(flow);
  const tree = useMemo(
    () => flowToTree(baseFlow, interactive),
    // eslint-disable-next-line react-hooks/exhaustive-deps -- recompute when flow/interactive content changes
    [flow, interactive]
  );
  const rows = useMemo(() => flattenTree(tree), [tree]);
  const sortableIds = rows.map((r) => r.id);

  const sensors = useSensors(
    useSensor(PointerSensor, { activationConstraint: { distance: 6 } })
  );

  const canEditFlow = Boolean(onFlowChange) && !readonly;
  const showExtras = Boolean(onFlowChange) && allowExtras;

  function toggleOpen(id: string) {
    setOpenIds((prev) => ({ ...prev, [id]: !prev[id] }));
  }

  function applyTree(nextTree: TreeQuestionNode[]) {
    if (!onFlowChange) return;
    const { flow: nextFlow, interactive: nextIx } = treeToFlow(
      nextTree,
      ensureLeadFlow(flow),
      interactive
    );
    onFlowChange(nextFlow);
    onInteractiveChange({ ...interactive, ...nextIx });
  }

  function setLeadQ(key: keyof LeadDraft, value: string) {
    onLeadChange({ ...lead, [key]: value });
  }

  function removeStep(key: RemovableLeadStep) {
    if (!onFlowChange) return;
    onFlowChange(ensureLeadFlow(flow).filter((s) => (s.key || "").toUpperCase() !== key));
  }

  function restoreStep(key: RemovableLeadStep) {
    if (!onFlowChange) return;
    onFlowChange(insertBuiltin(ensureLeadFlow(flow), key));
  }

  function renameStep(stepId: string, label: string) {
    if (!onFlowChange) return;
    onFlowChange(
      ensureLeadFlow(flow).map((s) =>
        s.id === stepId ? { ...s, label: label.slice(0, 40) } : s
      )
    );
  }

  function patchStep(stepId: string, patch: Partial<FlowStep>) {
    if (!onFlowChange) return;
    onFlowChange(ensureLeadFlow(flow).map((s) => (s.id === stepId ? { ...s, ...patch } : s)));
  }

  function removeExtra(id: string) {
    if (!onFlowChange) return;
    // Also clear option next_keys pointing at this step via recompile after filter
    const next = ensureLeadFlow(flow).filter((s) => s.id !== id);
    onFlowChange(next);
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
    setOpenIds((prev) => ({ ...prev, [`q:${step.id}`]: true }));
  }

  /** Create a new follow-up question and attach it to one answer button. */
  function addBranchForOption(
    parent: TreeQuestionNode,
    optionId: string,
    kind: "text" | "buttons"
  ) {
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
    const btn = parent.options.find((o) => o.id === optionId);
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
      label: btn?.title ? `${btn.title.slice(0, 28)} path` : kind === "buttons" ? "Branch buttons" : "Branch question",
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
    // Existing child for this button → unnest first so we replace the path
    const existing = childForOption(parent, optionId);
    let nextFlow = insertBeforeScheduling(current, step);
    let nextTree = flowToTree(nextFlow, interactive);
    if (existing) {
      nextTree = unnestToRoot(nextTree, existing.step.id);
    }
    nextTree = nestQuestionUnder(nextTree, step.id, parent.step.id, optionId);
    applyTree(nextTree);
    setOpenIds((prev) => ({
      ...prev,
      [`q:${parent.step.id}`]: true,
      [`q:${step.id}`]: true,
    }));
    toast.success(
      `Follow-up added for “${btn?.title || "this button"}” — edit the sub item below`
    );
  }

  function setBranchForOption(
    parent: TreeQuestionNode,
    optionId: string,
    followUpStepId: string
  ) {
    if (!canEditFlow) return;
    const existing = childForOption(parent, optionId);
    let next = tree;
    if (existing && existing.step.id !== followUpStepId) {
      next = unnestToRoot(next, existing.step.id);
    }
    if (!followUpStepId) {
      if (existing) next = unnestToRoot(next, existing.step.id);
      applyTree(next);
      return;
    }
    next = nestQuestionUnder(next, followUpStepId, parent.step.id, optionId);
    applyTree(next);
    setOpenIds((prev) => ({ ...prev, [`q:${followUpStepId}`]: true }));
  }

  function renderBranchPanel(parent: TreeQuestionNode) {
    if (!canEditFlow || parent.options.length === 0) return null;
    const attachable = rows
      .map((r) => r.node)
      .filter((n) => n.step.id !== parent.step.id);

    return (
      <div className="space-y-3 rounded-xl border border-primary/25 bg-primary/5 p-3">
        <div>
          <p className="text-xs font-semibold text-foreground">Different path per button</p>
          <p className="mt-0.5 text-[11px] text-muted-foreground">
            Example: “Build New Automation” asks one set of questions; “Technical Support” asks
            another. Each button can open its own follow-up.
          </p>
        </div>
        <div className="space-y-2">
          {parent.options.map((opt) => {
            const linked = childForOption(parent, opt.id);
            return (
              <div
                key={opt.id}
                className="space-y-2 rounded-lg border border-border bg-card/80 p-2.5 sm:space-y-0 sm:flex sm:flex-wrap sm:items-end sm:gap-2"
              >
                <div className="min-w-[8rem] flex-1">
                  <p className="text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">
                    If they choose
                  </p>
                  <p className="truncate text-sm font-medium">{opt.title || "Button"}</p>
                </div>
                <div className="min-w-[12rem] flex-[2]">
                  <Label className="text-[11px]">Then ask</Label>
                  <select
                    className="mt-1 flex h-9 w-full rounded-md border border-border bg-background px-2 text-sm"
                    value={linked?.step.id || ""}
                    disabled={readonly}
                    onChange={(e) => setBranchForOption(parent, opt.id, e.target.value)}
                  >
                    <option value="">Next main question (no branch)</option>
                    {attachable.map((n) => (
                      <option key={n.step.id} value={n.step.id}>
                        {questionTitle(n.step)}
                      </option>
                    ))}
                  </select>
                </div>
                <div className="flex flex-wrap gap-1.5">
                  <Button
                    type="button"
                    size="sm"
                    variant="outline"
                    disabled={readonly}
                    onClick={() => addBranchForOption(parent, opt.id, "text")}
                  >
                    <Plus className="h-3.5 w-3.5" />
                    New text path
                  </Button>
                  <Button
                    type="button"
                    size="sm"
                    variant="outline"
                    disabled={readonly}
                    onClick={() => addBranchForOption(parent, opt.id, "buttons")}
                  >
                    <Plus className="h-3.5 w-3.5" />
                    New buttons path
                  </Button>
                </div>
              </div>
            );
          })}
        </div>
      </div>
    );
  }

  function onDragOver(event: DragOverEvent) {
    const overId = event.over?.id ? String(event.over.id) : null;
    if (overId?.startsWith("q:")) {
      const overRow = rows.find((r) => r.id === overId);
      if (overRow && overRow.node.step.key?.toUpperCase() !== "SCHEDULING") {
        setNestOverId(overId);
        return;
      }
    }
    setNestOverId(null);
  }

  function onDragEnd(event: DragEndEvent) {
    setNestOverId(null);
    if (!onFlowChange || readonly) return;
    const { active, over } = event;
    if (!over || active.id === over.id) return;
    const activeId = String(active.id);
    const overId = String(over.id);
    if (!activeId.startsWith("q:") || !overId.startsWith("q:")) return;

    const activeStepId = activeId.slice(2);
    const overStepId = overId.slice(2);
    const activeRow = rows.find((r) => r.id === activeId);
    const overRow = rows.find((r) => r.id === overId);
    if (!activeRow || !overRow) return;
    if (overRow.node.step.key?.toUpperCase() === "SCHEDULING") {
      if (activeRow.depth === 0 && overRow.depth === 0) {
        applyTree(reorderRoots(tree, activeStepId, overStepId));
      }
      return;
    }

    // Nest follow-ups under a parent question; reorder only when both are top-level
    // and the active item is not an extra being attached to a buttons question.
    const nestUnderParent =
      activeRow.depth > 0 ||
      overRow.depth > 0 ||
      overRow.node.children.length > 0 ||
      (isExtraStep(activeRow.node.step) &&
        (overRow.node.options.length > 0 || isTextLike(overRow.node.step)));

    if (nestUnderParent) {
      applyTree(nestQuestionUnder(tree, activeStepId, overStepId));
      return;
    }

    if (activeRow.depth === 0 && overRow.depth === 0) {
      applyTree(reorderRoots(tree, activeStepId, overStepId));
    }
  }

  const missing = REMOVABLE.filter((k) => !hasStep(flow, k));

  function renderQuestionEditor(node: TreeQuestionNode, isSub: boolean) {
    const step = node.step;
    const key = normKey(step.key);
    const title = questionTitle(step);
    const isButtons =
      step.type === "button_options" ||
      step.type === "list_options" ||
      Boolean(step.options_key);

    const parentOpts = isSub ? parentOptionsForChild(tree, step.id) : [];
    const triggerId = isSub ? childTriggerId(tree, step.id) : null;

    return (
      <>
        {isSub && parentOpts.length > 0 && canEditFlow && (
          <div>
            <Label>When they choose</Label>
            <select
              className="mt-1.5 flex h-9 w-full rounded-md border border-border bg-background px-3 text-sm"
              value={triggerId || ""}
              disabled={readonly}
              onChange={(e) =>
                applyTree(setChildTrigger(tree, step.id, e.target.value || null))
              }
            >
              <option value="">— Pick a button on the parent —</option>
              {parentOpts.map((o) => (
                <option key={o.id} value={o.id}>
                  {o.title || o.id}
                </option>
              ))}
            </select>
            <p className="mt-1 text-[11px] text-muted-foreground">
              This follow-up is asked after that answer button.
            </p>
          </div>
        )}

        <div>
          <div className="mb-1 flex items-center justify-between">
            <Label>Section name</Label>
            <CharHint len={title.length} max={40} />
          </div>
          <Input
            maxLength={40}
            value={title}
            disabled={readonly || !onFlowChange}
            onChange={(e) => renameStep(step.id, e.target.value)}
          />
        </div>

        {key === "BUSINESS_TYPE" && (
          <>
            <div>
              <Label>Question text</Label>
              <Textarea
                rows={2}
                className="mt-1.5"
                value={lead.q_business_type || ""}
                disabled={readonly}
                onChange={(e) => setLeadQ("q_business_type", e.target.value)}
              />
            </div>
            <div>
              <Label>List button label</Label>
              <Input
                className="mt-1.5"
                maxLength={20}
                value={interactive.select_button_label || ""}
                disabled={readonly}
                onChange={(e) =>
                  onInteractiveChange({
                    ...interactive,
                    select_button_label: e.target.value.slice(0, 20),
                  })
                }
              />
            </div>
            <OptionListEditor
              title="Answer buttons"
              items={(interactive.business_types || []).map((r) => ({
                id: r.id,
                label: r.title || "",
                value: r.value || r.title || "",
                description: r.description || "",
              }))}
              constraints={{
                maxItems: 10,
                maxLabelChars: 50,
                maxValueChars: 64,
                maxDescriptionChars: 72,
              }}
              features={{
                reorder: true,
                valueField: true,
                valueLabel: "Saved as",
                descriptionField: true,
              }}
              disabled={readonly}
              onChange={(next) => {
                const prev = interactive.business_types || [];
                onInteractiveChange({
                  ...interactive,
                  business_types: next.map((it) => ({
                    id: it.id,
                    title: it.label,
                    value: (it.value || it.label).trim() || it.label,
                    description: it.description || "",
                    ...preserveNextKeys(prev, it.id),
                  })),
                });
              }}
            />
            {renderBranchPanel(node)}
            {allowRemove && canEditFlow && (
              <RemoveBuiltinBtn onClick={() => removeStep("BUSINESS_TYPE")} />
            )}
          </>
        )}

        {key === "LOCATIONS" && (
          <>
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
              title="Answer buttons"
              items={(interactive.locations || []).map((r) => ({
                id: r.id,
                label: r.title || "",
                value: r.value || r.title || "",
              }))}
              constraints={{ maxItems: 10, maxLabelChars: 50, maxValueChars: 64 }}
              features={{ reorder: true, valueField: true, valueLabel: "Saved as" }}
              disabled={readonly}
              onChange={(next) => {
                const prev = interactive.locations || [];
                onInteractiveChange({
                  ...interactive,
                  locations: next.slice(0, 10).map((it) => ({
                    id: it.id,
                    title: it.label.slice(0, 50),
                    value: (it.value || it.label).trim() || it.label,
                    ...preserveNextKeys(prev, it.id),
                  })),
                });
              }}
            />
            {renderBranchPanel(node)}
            {allowRemove && canEditFlow && (
              <RemoveBuiltinBtn onClick={() => removeStep("LOCATIONS")} />
            )}
          </>
        )}

        {key === "CURRENT_SYSTEM" && (
          <>
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
              title="Answer buttons"
              items={(interactive.current_system || []).map((r) => ({
                id: r.id,
                label: r.title || "",
                value: r.sheet_value || r.title || "",
              }))}
              constraints={{ maxItems: 10, maxLabelChars: 50, maxValueChars: 64 }}
              features={{ reorder: true, valueField: true, valueLabel: "Value for sheet" }}
              disabled={readonly}
              onChange={(next) => {
                const prev = interactive.current_system || [];
                onInteractiveChange({
                  ...interactive,
                  current_system: next.slice(0, 10).map((it) => ({
                    id: it.id,
                    title: it.label.slice(0, 50),
                    sheet_value: (it.value || it.label).trim() || it.label,
                    ...preserveNextKeys(prev, it.id),
                  })),
                });
              }}
            />
            {renderBranchPanel(node)}
            {allowRemove && canEditFlow && (
              <RemoveBuiltinBtn onClick={() => removeStep("CURRENT_SYSTEM")} />
            )}
          </>
        )}

        {key === "SCHEDULING" && (
          <>
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
              items={[
                { id: "slot_1", label: (slots[0] || "").slice(0, 20), locked: true },
                { id: "slot_2", label: (slots[1] || "").slice(0, 20), locked: true },
                { id: "slot_other", label: slotOther.slice(0, 20), locked: true },
              ]}
              constraints={{ maxItems: 3, maxLabelChars: 20 }}
              features={{ reorder: false }}
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
            {allowRemove && canEditFlow && (
              <RemoveBuiltinBtn onClick={() => removeStep("SCHEDULING")} />
            )}
          </>
        )}

        {!REMOVABLE_SET.has(key) && (
          <>
            <div>
              <Label>Question text</Label>
              <Textarea
                className="mt-1.5"
                rows={2}
                value={step.question_text || ""}
                disabled={readonly}
                onChange={(e) =>
                  patchStep(step.id, { question_text: e.target.value.slice(0, 1024) })
                }
              />
            </div>
            {isButtons && (
              <OptionListEditor
                title="Answer buttons"
                items={(step.options || []).map((o) => ({
                  id: o.id,
                  label: o.title,
                  value: o.value || o.sheet_value || o.title,
                }))}
                constraints={{ maxItems: 10, maxLabelChars: 50, maxValueChars: 64 }}
                features={{ reorder: true, valueField: true, valueLabel: "Saved as" }}
                disabled={readonly}
                onChange={(next) => {
                  const prev = step.options || [];
                  patchStep(step.id, {
                    type: "list_options",
                    options: next.slice(0, 10).map((it) => ({
                      id: it.id,
                      title: it.label.slice(0, 50),
                      value: (it.value || it.label).trim() || it.label,
                      ...preserveNextKeys(prev, it.id),
                    })),
                  });
                }}
              />
            )}
            {isButtons && renderBranchPanel(node)}
            {isTextLike(step) && (
              <p className="text-[11px] text-muted-foreground">
                Drag another question under this one to ask it next.
              </p>
            )}
            {canEditFlow && isExtraStep(step) && (
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
          </>
        )}
      </>
    );
  }

  if (!onFlowChange) {
    return (
      <div className="rounded-xl border border-border bg-muted/20 px-3 py-3 text-sm text-muted-foreground">
        Flow editor requires flow editing to be enabled.
      </div>
    );
  }

  return (
    <div className="space-y-3">
      {allowRemove && missing.length > 0 && !readonly && (
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
            Expand a question to edit its answer list. Drag a follow-up question under it as a sub
            item.
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

      <div>
        <p className="mb-2 text-sm font-semibold text-foreground">Menu structure</p>
        <p className="mb-3 text-xs text-muted-foreground">
          Expand a question → add answer buttons → use{" "}
          <span className="font-medium text-foreground">Different path per button</span> so each
          choice (e.g. Build New Automation vs Technical Support) opens its own follow-up questions.
        </p>

        <DndContext
          sensors={sensors}
          collisionDetection={closestCenter}
          onDragOver={onDragOver}
          onDragEnd={onDragEnd}
        >
          <SortableContext items={sortableIds} strategy={verticalListSortingStrategy}>
            <div>
              {rows.map((row) => {
                const title = questionTitle(row.node.step);
                const typeLabel =
                  isTextLike(row.node.step) &&
                  !row.node.step.options_key &&
                  !(row.node.step.options || []).length
                    ? "Text"
                    : "Question";
                return (
                  <SortableRow key={row.id} id={row.id} canDrag={canEditFlow}>
                    {(leading) => (
                      <TreeRowShell
                        depth={row.depth}
                        leading={leading}
                        title={title}
                        typeLabel={typeLabel}
                        isSub={row.depth > 0}
                        open={Boolean(openIds[row.id])}
                        onToggle={() => toggleOpen(row.id)}
                        nestHighlight={nestOverId === row.id}
                      >
                        {renderQuestionEditor(row.node, row.depth > 0)}
                      </TreeRowShell>
                    )}
                  </SortableRow>
                );
              })}
            </div>
          </SortableContext>
        </DndContext>
      </div>
    </div>
  );
}

function RemoveBuiltinBtn({ onClick }: { onClick: () => void }) {
  return (
    <Button type="button" size="sm" variant="ghost" className="text-destructive" onClick={onClick}>
      <Trash2 className="h-3.5 w-3.5" />
      Remove this question
    </Button>
  );
}
