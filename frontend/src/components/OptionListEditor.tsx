import { useEffect, useRef, useState } from "react";
import {
  DndContext,
  DragEndEvent,
  KeyboardSensor,
  PointerSensor,
  closestCenter,
  useSensor,
  useSensors,
} from "@dnd-kit/core";
import {
  SortableContext,
  arrayMove,
  sortableKeyboardCoordinates,
  useSortable,
  verticalListSortingStrategy,
} from "@dnd-kit/sortable";
import { CSS } from "@dnd-kit/utilities";
import { GripVertical, Plus, Trash2 } from "lucide-react";
import { Button } from "./ui/button";
import { Input, Label, Textarea } from "./ui/input";
import { cn } from "../lib/utils";

export type OptionListItem = {
  id: string;
  label: string;
  value?: string;
  description?: string;
  answer?: string;
  locked?: boolean;
};

type Constraints = {
  maxItems: number;
  maxLabelChars: number;
  maxValueChars?: number;
  maxAnswerChars?: number;
  maxDescriptionChars?: number;
};

type Features = {
  reorder?: boolean;
  valueField?: boolean;
  valueLabel?: string;
  descriptionField?: boolean;
  answerField?: boolean;
};

type Props = {
  title: string;
  items: OptionListItem[];
  onChange: (items: OptionListItem[]) => void;
  constraints: Constraints;
  features?: Features;
  addDisabledHint?: string;
  emptyHint?: string;
  className?: string;
};

function newId(prefix = "opt"): string {
  return `${prefix}_${Math.random().toString(36).slice(2, 10)}`;
}

function CharCount({ len, max }: { len: number; max: number }) {
  const tone =
    len > max ? "text-destructive" : len >= max - 3 ? "text-amber-400" : "text-muted-foreground";
  return (
    <span className={cn("tabular-nums text-[11px]", tone)}>
      {len}/{max}
    </span>
  );
}

export function OptionListEditor({
  title,
  items,
  onChange,
  constraints,
  features = {},
  addDisabledHint,
  emptyHint,
  className,
}: Props) {
  const {
    reorder = true,
    valueField = false,
    valueLabel = "Value",
    descriptionField = false,
    answerField = false,
  } = features;
  const { maxItems, maxLabelChars } = constraints;
  const maxValueChars = constraints.maxValueChars ?? 64;
  const maxAnswerChars = constraints.maxAnswerChars ?? 500;
  const maxDescriptionChars = constraints.maxDescriptionChars ?? 72;

  const [focusId, setFocusId] = useState<string | null>(null);
  const sensors = useSensors(
    useSensor(PointerSensor, { activationConstraint: { distance: 6 } }),
    useSensor(KeyboardSensor, { coordinateGetter: sortableKeyboardCoordinates })
  );

  const atMax = items.length >= maxItems;
  const labels = items.map((i) => i.label.trim().toLowerCase()).filter(Boolean);
  const dupSet = new Set(
    labels.filter((l, idx) => labels.indexOf(l) !== idx)
  );

  function updateItem(id: string, patch: Partial<OptionListItem>) {
    onChange(items.map((it) => (it.id === id ? { ...it, ...patch } : it)));
  }

  function removeItem(id: string) {
    const row = items.find((i) => i.id === id);
    if (row?.locked) return;
    onChange(items.filter((i) => i.id !== id));
  }

  function addItem(afterId?: string) {
    if (atMax) return;
    const row: OptionListItem = {
      id: newId(),
      label: "",
      ...(valueField ? { value: "" } : {}),
      ...(descriptionField ? { description: "" } : {}),
      ...(answerField ? { answer: "" } : {}),
    };
    if (afterId) {
      const idx = items.findIndex((i) => i.id === afterId);
      const next = [...items];
      next.splice(idx + 1, 0, row);
      onChange(next);
    } else {
      onChange([...items, row]);
    }
    setFocusId(row.id);
  }

  function onDragEnd(e: DragEndEvent) {
    const { active, over } = e;
    if (!over || active.id === over.id) return;
    const oldIndex = items.findIndex((i) => i.id === active.id);
    const newIndex = items.findIndex((i) => i.id === over.id);
    if (oldIndex < 0 || newIndex < 0) return;
    onChange(arrayMove(items, oldIndex, newIndex));
  }

  const hint =
    addDisabledHint ||
    (maxItems >= 10
      ? `WhatsApp list limit: ${maxItems} rows`
      : `Button limit: ${maxItems}`);

  return (
    <div className={cn("space-y-3", className)}>
      <div className="flex items-center justify-between gap-2">
        <h3 className="text-sm font-semibold">{title}</h3>
        <span className="text-[11px] text-muted-foreground">
          {items.length}/{maxItems}
        </span>
      </div>

      {items.length === 0 && emptyHint && (
        <p className="text-xs text-muted-foreground">{emptyHint}</p>
      )}

      <DndContext sensors={sensors} collisionDetection={closestCenter} onDragEnd={onDragEnd}>
        <SortableContext
          items={items.map((i) => i.id)}
          strategy={verticalListSortingStrategy}
          disabled={!reorder}
        >
          <div className="space-y-2">
            {items.map((item) => (
              <SortableRow
                key={item.id}
                item={item}
                reorder={reorder}
                valueField={valueField}
                valueLabel={valueLabel}
                descriptionField={descriptionField}
                answerField={answerField}
                maxLabelChars={maxLabelChars}
                maxValueChars={maxValueChars}
                maxAnswerChars={maxAnswerChars}
                maxDescriptionChars={maxDescriptionChars}
                isDuplicate={
                  !!item.label.trim() && dupSet.has(item.label.trim().toLowerCase())
                }
                autofocus={focusId === item.id}
                onFocused={() => setFocusId(null)}
                onChange={(patch) => updateItem(item.id, patch)}
                onRemove={() => removeItem(item.id)}
                onEnterAdd={() => addItem(item.id)}
              />
            ))}
          </div>
        </SortableContext>
      </DndContext>

      <Button
        type="button"
        variant="ghost"
        size="sm"
        disabled={atMax}
        title={atMax ? hint : undefined}
        onClick={() => addItem()}
        className="w-full justify-start text-muted-foreground"
      >
        <Plus className="h-3.5 w-3.5" />
        Add item
        {atMax && <span className="ml-2 text-[11px] opacity-70">({hint})</span>}
      </Button>
    </div>
  );
}

/** Drop blank rows before persisting. */
export function stripEmptyOptionRows(items: OptionListItem[]): OptionListItem[] {
  return items.filter((i) => i.label.trim() || (i.answer || "").trim());
}

function SortableRow({
  item,
  reorder,
  valueField,
  valueLabel,
  descriptionField,
  answerField,
  maxLabelChars,
  maxValueChars,
  maxAnswerChars,
  maxDescriptionChars,
  isDuplicate,
  autofocus,
  onFocused,
  onChange,
  onRemove,
  onEnterAdd,
}: {
  item: OptionListItem;
  reorder: boolean;
  valueField: boolean;
  valueLabel: string;
  descriptionField: boolean;
  answerField: boolean;
  maxLabelChars: number;
  maxValueChars: number;
  maxAnswerChars: number;
  maxDescriptionChars: number;
  isDuplicate: boolean;
  autofocus: boolean;
  onFocused: () => void;
  onChange: (patch: Partial<OptionListItem>) => void;
  onRemove: () => void;
  onEnterAdd: () => void;
}) {
  const { attributes, listeners, setNodeRef, transform, transition, isDragging } = useSortable({
    id: item.id,
    disabled: !reorder,
  });
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (autofocus && inputRef.current) {
      inputRef.current.focus();
      onFocused();
    }
  }, [autofocus, onFocused]);

  return (
    <div
      ref={setNodeRef}
      style={{ transform: CSS.Transform.toString(transform), transition }}
      className={cn(
        "group rounded-xl border border-border bg-background/60 p-3 transition",
        isDragging && "z-10 opacity-90 shadow-lg",
        isDuplicate && "border-amber-500/60"
      )}
    >
      <div className="flex items-start gap-2">
        {reorder && (
          <button
            type="button"
            className="mt-2.5 touch-none text-muted-foreground hover:text-foreground"
            aria-label="Drag to reorder"
            {...attributes}
            {...listeners}
          >
            <GripVertical className="h-4 w-4" />
          </button>
        )}
        <div className="min-w-0 flex-1 space-y-2">
          <div>
            <div className="mb-1 flex items-center justify-between gap-2">
              <Label className="text-[11px] text-muted-foreground">
                {answerField ? "Question" : "Label"}
              </Label>
              <CharCount len={item.label.length} max={maxLabelChars} />
            </div>
            <Input
              ref={inputRef}
              value={item.label}
              maxLength={maxLabelChars + 20}
              className={cn(
                item.label.length > maxLabelChars && "border-destructive",
                item.label.length >= maxLabelChars - 3 &&
                  item.label.length <= maxLabelChars &&
                  "border-amber-500/70"
              )}
              onChange={(e) => onChange({ label: e.target.value })}
              onKeyDown={(e) => {
                if (e.key === "Enter" && !e.shiftKey && !answerField) {
                  e.preventDefault();
                  onEnterAdd();
                }
              }}
              placeholder={answerField ? "FAQ question" : "Option label"}
            />
            {isDuplicate && (
              <p className="mt-1 text-[11px] text-amber-400">Duplicate label in this set</p>
            )}
          </div>

          {valueField && (
            <div>
              <div className="mb-1 flex items-center justify-between">
                <Label className="text-[11px] text-muted-foreground">{valueLabel}</Label>
                <CharCount len={(item.value || "").length} max={maxValueChars} />
              </div>
              <Input
                value={item.value || ""}
                maxLength={maxValueChars + 10}
                className="h-8 text-xs text-muted-foreground"
                placeholder="Sheet / mapped value"
                onChange={(e) => onChange({ value: e.target.value })}
              />
            </div>
          )}

          {descriptionField && (
            <div>
              <div className="mb-1 flex items-center justify-between">
                <Label className="text-[11px] text-muted-foreground">Description</Label>
                <CharCount len={(item.description || "").length} max={maxDescriptionChars} />
              </div>
              <Input
                value={item.description || ""}
                maxLength={maxDescriptionChars + 10}
                className="h-8 text-xs"
                placeholder="List row description (optional)"
                onChange={(e) => onChange({ description: e.target.value })}
              />
            </div>
          )}

          {answerField && (
            <div>
              <div className="mb-1 flex items-center justify-between">
                <Label className="text-[11px] text-muted-foreground">Answer</Label>
                <CharCount len={(item.answer || "").length} max={maxAnswerChars} />
              </div>
              <Textarea
                rows={2}
                value={item.answer || ""}
                maxLength={maxAnswerChars + 20}
                placeholder="Answer"
                onChange={(e) => onChange({ answer: e.target.value })}
              />
            </div>
          )}
        </div>

        {!item.locked && (
          <Button
            type="button"
            variant="ghost"
            size="icon"
            className="mt-1 opacity-0 transition group-hover:opacity-100 focus:opacity-100"
            onClick={onRemove}
            aria-label="Remove"
          >
            <Trash2 className="h-4 w-4 text-destructive" />
          </Button>
        )}
      </div>
    </div>
  );
}
