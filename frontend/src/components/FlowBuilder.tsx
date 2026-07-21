import { useCallback, useEffect, useMemo, useState } from "react";
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
import {
  ChevronDown,
  ChevronRight,
  GripVertical,
  Lock,
  Plus,
  Trash2,
} from "lucide-react";
import { toast } from "sonner";
import { api, FlowStep, FlowStepOption } from "../api";
import {
  OptionListEditor,
  OptionListItem,
  stripEmptyOptionRows,
} from "./OptionListEditor";
import { Button } from "./ui/button";
import { Input, Label, Textarea } from "./ui/input";
import { cn } from "../lib/utils";

const STEP_TYPES = [
  { id: "text_question", label: "Text question" },
  { id: "button_options", label: "Buttons (≤3)" },
  { id: "list_options", label: "List (≤10)" },
  { id: "free_text_capture", label: "Free-text capture" },
] as const;

const CAPTURE_FIELDS = [
  "business_name",
  "business_type",
  "locations",
  "current_system",
  "demo_slot",
  "city",
  "custom_1",
  "custom_2",
  "custom_3",
  "custom_4",
  "custom_5",
] as const;

const FLOW_MAX = 20;

function nid(prefix: string) {
  return `${prefix}_${Math.random().toString(36).slice(2, 10)}`;
}

function keyFromLabel(label: string): string {
  return label
    .trim()
    .toUpperCase()
    .replace(/[^A-Z0-9]+/g, "_")
    .replace(/^_|_$/g, "")
    .slice(0, 32) || "STEP";
}

type PreviewStep = {
  key: string;
  type: string;
  kind: string;
  body: string;
  options?: FlowStepOption[];
  capture_field?: string | null;
  reserved?: boolean;
};

type Props = {
  tenantDbId: number;
  initial: FlowStep[];
  demoSlots: string[];
  onChange: (flow: FlowStep[]) => void;
  readonly?: boolean;
};

export function FlowBuilder({
  tenantDbId,
  initial,
  demoSlots,
  onChange,
  readonly = false,
}: Props) {
  const [steps, setSteps] = useState<FlowStep[]>(initial);
  const [openId, setOpenId] = useState<string | null>(null);
  const [preview, setPreview] = useState<PreviewStep[]>([]);
  const [previewErr, setPreviewErr] = useState("");

  useEffect(() => {
    setSteps(initial);
  }, [initial]);

  const sensors = useSensors(
    useSensor(PointerSensor, { activationConstraint: { distance: 6 } })
  );

  const update = useCallback(
    (next: FlowStep[]) => {
      setSteps(next);
      onChange(next);
    },
    [onChange]
  );

  const refreshPreview = useCallback(async () => {
    setPreviewErr("");
    try {
      const res = await api<{ steps: PreviewStep[] }>(
        `/api/dashboard/tenants/${tenantDbId}/flow/preview`,
        {
          method: "POST",
          body: JSON.stringify({ flow: steps }),
          tenant: false,
        }
      );
      setPreview(res.steps || []);
    } catch (e: unknown) {
      setPreview([]);
      setPreviewErr(e instanceof Error ? e.message : "Preview failed");
    }
  }, [steps, tenantDbId]);

  useEffect(() => {
    const t = setTimeout(() => void refreshPreview(), 400);
    return () => clearTimeout(t);
  }, [refreshPreview]);

  function onDragEnd(e: DragEndEvent) {
    if (readonly) return;
    const { active, over } = e;
    if (!over || active.id === over.id) return;
    const oldIndex = steps.findIndex((s) => s.id === active.id);
    const newIndex = steps.findIndex((s) => s.id === over.id);
    if (oldIndex < 0 || newIndex < 0) return;
    update(arrayMove(steps, oldIndex, newIndex));
  }

  function addStep(type: FlowStep["type"]) {
    if (readonly) return;
    if (steps.length >= FLOW_MAX) {
      toast.error(`Max ${FLOW_MAX} steps`);
      return;
    }
    const id = nid("step");
    const key = keyFromLabel(`CUSTOM_${steps.length}`);
    const step: FlowStep = {
      id,
      key,
      type,
      question_text: type === "text_question" ? "Aapka sawaal yahan…" : "Neeche se muntakhib karein.",
      options: type === "button_options" || type === "list_options" ? [
        { id: nid("opt"), title: "Option 1", value: "Option 1" },
        { id: nid("opt"), title: "Option 2", value: "Option 2" },
      ] : [],
      capture_field: "custom_1",
      required: true,
      skip_if_declined: false,
      reserved: false,
      system: false,
    };
    update([...steps, step]);
    setOpenId(id);
  }

  function removeStep(id: string) {
    if (readonly) return;
    const step = steps.find((s) => s.id === id);
    if (step?.reserved) {
      toast.error("Reserved steps cannot be deleted");
      return;
    }
    update(steps.filter((s) => s.id !== id));
  }

  function patchStep(id: string, patch: Partial<FlowStep>) {
    if (readonly) return;
    update(steps.map((s) => (s.id === id ? { ...s, ...patch } : s)));
  }

  const ids = useMemo(() => steps.map((s) => s.id), [steps]);

  return (
    <div className="grid gap-6 lg:grid-cols-[1fr_320px]">
      <div className="space-y-4">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <div>
            <h2 className="text-sm font-semibold">Conversation steps</h2>
            <p className="text-xs text-muted-foreground">
              Drag to reorder. Reserved steps (greeting + confirm) stay; scheduling and questions can be removed.
            </p>
          </div>
          {!readonly && (
            <div className="flex flex-wrap gap-1">
              {STEP_TYPES.map((t) => (
                <Button
                  key={t.id}
                  type="button"
                  size="sm"
                  variant="outline"
                  disabled={steps.length >= FLOW_MAX}
                  onClick={() => addStep(t.id)}
                >
                  <Plus className="h-3.5 w-3.5" />
                  {t.label}
                </Button>
              ))}
            </div>
          )}
        </div>

        <DndContext sensors={sensors} collisionDetection={closestCenter} onDragEnd={onDragEnd}>
          <SortableContext items={ids} strategy={verticalListSortingStrategy}>
            <div className="space-y-2">
              {steps.map((step) => (
                <SortableStep
                  key={step.id}
                  step={step}
                  open={openId === step.id}
                  onToggle={() => setOpenId(openId === step.id ? null : step.id)}
                  onPatch={(p) => patchStep(step.id, p)}
                  onDelete={() => removeStep(step.id)}
                  readonly={readonly}
                />
              ))}
            </div>
          </SortableContext>
        </DndContext>
      </div>

      <aside className="space-y-3 lg:sticky lg:top-20 lg:self-start">
        <h2 className="text-sm font-semibold">WhatsApp preview</h2>
        <p className="text-xs text-muted-foreground">
          Live walkthrough — same builders as the bot
        </p>
        {previewErr && (
          <p className="rounded-lg bg-destructive/10 px-3 py-2 text-xs text-destructive">
            {previewErr}
          </p>
        )}
        <div className="max-h-[70vh] space-y-3 overflow-y-auto rounded-2xl bg-[var(--wa-bg)] p-3">
          {preview.map((p, i) => (
            <div key={`${p.key}-${i}`} className="space-y-1">
              <p className="text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">
                {p.key}
                {p.capture_field ? ` · ${p.capture_field}` : ""}
              </p>
              <div className="ml-auto max-w-[92%] rounded-2xl rounded-br-sm bg-[var(--wa-out)] px-3 py-2 text-[13px] text-white">
                <p className="transcript-text whitespace-pre-wrap">{p.body || "—"}</p>
              </div>
              {(p.options || []).length > 0 && (
                <div className="ml-auto flex max-w-[92%] flex-wrap gap-1">
                  {p.options!.map((o) => (
                    <span
                      key={o.id}
                      className="rounded-full border border-white/20 bg-black/20 px-2 py-0.5 text-[11px] text-white/90"
                    >
                      {o.title}
                    </span>
                  ))}
                </div>
              )}
              {p.key === "SCHEDULING" && (
                <div className="ml-auto flex max-w-[92%] flex-wrap gap-1">
                  {(demoSlots || []).slice(0, 2).map((s, si) => (
                    <span
                      key={si}
                      className="rounded-full border border-white/20 bg-black/20 px-2 py-0.5 text-[11px] text-white/90"
                    >
                      {s}
                    </span>
                  ))}
                  <span className="rounded-full border border-white/20 bg-black/20 px-2 py-0.5 text-[11px] text-white/90">
                    Another time
                  </span>
                </div>
              )}
            </div>
          ))}
          {!preview.length && !previewErr && (
            <p className="py-8 text-center text-xs text-muted-foreground">Building preview…</p>
          )}
        </div>
      </aside>
    </div>
  );
}

function SortableStep({
  step,
  open,
  onToggle,
  onPatch,
  onDelete,
  readonly,
}: {
  step: FlowStep;
  open: boolean;
  onToggle: () => void;
  onPatch: (p: Partial<FlowStep>) => void;
  onDelete: () => void;
  readonly: boolean;
}) {
  const { attributes, listeners, setNodeRef, transform, transition, isDragging } = useSortable({
    id: step.id,
  });
  const style = {
    transform: CSS.Transform.toString(transform),
    transition,
  };

  const optionItems: OptionListItem[] = (step.options || []).map((o) => ({
    id: o.id,
    label: o.title,
    value: o.value || o.sheet_value || "",
    description: o.description || "",
  }));

  const isButtons = step.type === "button_options";
  const isList = step.type === "list_options";
  const showOptions = isButtons || isList;
  const maxItems = 10;
  const maxLabel = 50;

  return (
    <div
      ref={setNodeRef}
      style={style}
      className={cn(
        "rounded-2xl border border-border bg-card",
        isDragging && "opacity-80 shadow-elevated",
        step.reserved && "border-dashed"
      )}
    >
      <div className="flex items-center gap-2 px-3 py-2.5">
        <button
          type="button"
          className="cursor-grab touch-none text-muted-foreground active:cursor-grabbing"
          {...attributes}
          {...listeners}
          aria-label="Drag to reorder"
        >
          <GripVertical className="h-4 w-4" />
        </button>
        <button
          type="button"
          className="flex min-w-0 flex-1 items-center gap-2 text-left"
          onClick={onToggle}
        >
          {open ? <ChevronDown className="h-4 w-4 shrink-0" /> : <ChevronRight className="h-4 w-4 shrink-0" />}
          <div className="min-w-0">
            <p className="truncate text-sm font-medium">
              {step.key}
              {step.reserved && (
                <Lock className="ml-1 inline h-3 w-3 text-muted-foreground" />
              )}
            </p>
            <p className="truncate text-[11px] text-muted-foreground">
              {step.type}
              {step.capture_field ? ` · ${step.capture_field}` : ""}
            </p>
          </div>
        </button>
        {!readonly && !step.reserved && (
          <Button type="button" size="icon" variant="ghost" onClick={onDelete} aria-label="Delete">
            <Trash2 className="h-4 w-4 text-destructive" />
          </Button>
        )}
      </div>

      {open && (
        <div className="space-y-3 border-t border-border px-4 py-3">
          <div className="grid gap-3 sm:grid-cols-2">
            <div>
              <Label>Key</Label>
              <Input
                className="mt-1.5 font-mono text-xs"
                value={step.key}
                disabled={readonly || step.reserved}
                onChange={(e) => onPatch({ key: keyFromLabel(e.target.value) })}
              />
            </div>
            <div>
              <Label>Type</Label>
              <select
                className="mt-1.5 flex h-10 w-full rounded-lg border border-input bg-background px-3 text-sm"
                value={step.type}
                disabled={readonly || step.reserved}
                onChange={(e) =>
                  onPatch({ type: e.target.value as FlowStep["type"] })
                }
              >
                {STEP_TYPES.map((t) => (
                  <option key={t.id} value={t.id}>
                    {t.label}
                  </option>
                ))}
              </select>
            </div>
            <div>
              <Label>Capture field</Label>
              <select
                className="mt-1.5 flex h-10 w-full rounded-lg border border-input bg-background px-3 text-sm"
                value={step.capture_field || ""}
                disabled={readonly || step.key === "GREETING" || step.key === "CONFIRMED"}
                onChange={(e) =>
                  onPatch({ capture_field: e.target.value || null })
                }
              >
                <option value="">— none —</option>
                {CAPTURE_FIELDS.map((f) => (
                  <option key={f} value={f}>
                    {f}
                  </option>
                ))}
              </select>
            </div>
            <div className="flex items-end gap-4 pb-1">
              <label className="flex items-center gap-2 text-xs">
                <input
                  type="checkbox"
                  checked={!!step.required}
                  disabled={readonly}
                  onChange={(e) => onPatch({ required: e.target.checked })}
                />
                Required
              </label>
              <label className="flex items-center gap-2 text-xs">
                <input
                  type="checkbox"
                  checked={!!step.skip_if_declined}
                  disabled={readonly}
                  onChange={(e) => onPatch({ skip_if_declined: e.target.checked })}
                />
                Skip if declined
              </label>
            </div>
          </div>
          <div>
            <Label>Question text</Label>
            <Textarea
              className="mt-1.5"
              rows={3}
              value={step.question_text || ""}
              disabled={readonly || step.key === "GREETING" || step.key === "CONFIRMED"}
              placeholder={
                step.options_key
                  ? "Leave empty to use catalog message"
                  : "Shown above buttons / list"
              }
              onChange={(e) => onPatch({ question_text: e.target.value })}
            />
            {step.options_key && (
              <p className="mt-1 text-[11px] text-muted-foreground">
                Linked to messages.interactive.{step.options_key} when options empty
              </p>
            )}
          </div>
          {showOptions && step.key !== "SCHEDULING" && (
            <OptionListEditor
              title="Options"
              items={optionItems}
              constraints={{
                maxItems,
                maxLabelChars: maxLabel,
                maxValueChars: 64,
                maxDescriptionChars: isList ? 72 : undefined,
              }}
              features={{
                reorder: !readonly,
                valueField: true,
                valueLabel: "Sheet value",
                descriptionField: isList,
              }}
              onChange={(items) => {
                if (readonly) return;
                const cleaned = stripEmptyOptionRows(items).map((r) => ({
                  id: r.id,
                  title: r.label.trim(),
                  value: (r.value || r.label).trim(),
                  description: r.description || "",
                }));
                onPatch({ options: cleaned, options_key: undefined });
              }}
            />
          )}
          {step.key === "SCHEDULING" && (
            <p className="rounded-lg bg-muted/40 px-3 py-2 text-xs text-muted-foreground">
              Scheduling buttons come from demo slots + “Another time”. Edit slots under Lead options.
            </p>
          )}
        </div>
      )}
    </div>
  );
}
