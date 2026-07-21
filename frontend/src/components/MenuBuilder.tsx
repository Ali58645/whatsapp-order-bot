import { useEffect, useMemo, useState } from "react";
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
  Copy,
  Eye,
  EyeOff,
  GripVertical,
  Loader2,
  Plus,
  Send,
  Trash2,
  Upload,
} from "lucide-react";
import { toast } from "sonner";
import { api, MenuV2, MenuV2Item } from "../api";
import { emptyMenuV2, nid, validateMenuClient, LIMITS } from "../lib/menu-v2";
import { Button } from "./ui/button";
import { Input, Label, Textarea } from "./ui/input";
import { Switch } from "./ui/switch";
import { cn } from "../lib/utils";
import { WhatsAppMenuPreview } from "./menu/WhatsAppMenuPreview";

type Props = {
  tenantDbId: number;
  initial: MenuV2 | null | undefined;
  published: MenuV2 | null | undefined;
  onSaved: (draft: MenuV2, published?: MenuV2 | null) => void;
  /** Owner Order Menu — plainer labels, less builder jargon */
  simple?: boolean;
};

export function MenuBuilder({ tenantDbId, initial, published, onSaved, simple = false }: Props) {
  const [menu, setMenu] = useState<MenuV2>(() => initial || emptyMenuV2());
  const [openCats, setOpenCats] = useState<Record<string, boolean>>({});
  const [editingItem, setEditingItem] = useState<MenuV2Item | null>(null);
  const [busy, setBusy] = useState<"draft" | "publish" | "test" | null>(null);
  const [previewStep, setPreviewStep] = useState(0);

  useEffect(() => {
    setMenu(initial || emptyMenuV2());
  }, [initial]);

  const errors = useMemo(() => validateMenuClient(menu), [menu]);
  const errorMap = useMemo(() => {
    const m: Record<string, string> = {};
    for (const e of errors) m[e.path] = e.message;
    return m;
  }, [errors]);

  const sensors = useSensors(useSensor(PointerSensor, { activationConstraint: { distance: 6 } }));

  const sortedCats = useMemo(
    () => [...menu.categories].sort((a, b) => a.sort - b.sort),
    [menu.categories]
  );

  function updateMenu(next: MenuV2) {
    setMenu(next);
  }

  function addCategory() {
    const cat = { id: nid("cat"), name: "New category", sort: menu.categories.length, visible: true };
    updateMenu({ ...menu, categories: [...menu.categories, cat] });
    setOpenCats((o) => ({ ...o, [cat.id]: true }));
  }

  function addItem(categoryId: string) {
    const item: MenuV2Item = {
      id: nid("item"),
      category_id: categoryId,
      name: "New item",
      description: "",
      price: 100,
      available: true,
      sort: menu.items.filter((i) => i.category_id === categoryId).length,
      modifiers: [],
    };
    updateMenu({ ...menu, items: [...menu.items, item] });
    setEditingItem(item);
  }

  function duplicateItem(item: MenuV2Item) {
    const copy = { ...item, id: nid("item"), name: `${item.name} copy`.slice(0, LIMITS.itemName) };
    updateMenu({ ...menu, items: [...menu.items, copy] });
  }

  function markCategoryUnavailable(catId: string) {
    updateMenu({
      ...menu,
      items: menu.items.map((i) =>
        i.category_id === catId ? { ...i, available: false } : i
      ),
    });
    toast.message("Category marked unavailable for today");
  }

  function onDragEnd(e: DragEndEvent) {
    const { active, over } = e;
    if (!over || active.id === over.id) return;
    const activeId = String(active.id);
    const overId = String(over.id);

    if (activeId.startsWith("cat:") && overId.startsWith("cat:")) {
      const oldIndex = sortedCats.findIndex((c) => `cat:${c.id}` === activeId);
      const newIndex = sortedCats.findIndex((c) => `cat:${c.id}` === overId);
      const moved = arrayMove(sortedCats, oldIndex, newIndex).map((c, i) => ({ ...c, sort: i }));
      updateMenu({ ...menu, categories: moved });
      return;
    }

    if (activeId.startsWith("item:") && overId.startsWith("item:")) {
      const a = menu.items.find((i) => `item:${i.id}` === activeId);
      const b = menu.items.find((i) => `item:${i.id}` === overId);
      if (!a || !b) return;
      const sameCat = menu.items.filter((i) => i.category_id === a.category_id);
      const oldIndex = sameCat.findIndex((i) => i.id === a.id);
      const newIndex = sameCat.findIndex((i) => i.id === b.id);
      if (a.category_id !== b.category_id) {
        // Move across categories
        const updated = menu.items.map((i) =>
          i.id === a.id ? { ...i, category_id: b.category_id } : i
        );
        updateMenu({ ...menu, items: updated });
        return;
      }
      const reordered = arrayMove(sameCat, oldIndex, newIndex).map((it, i) => ({ ...it, sort: i }));
      const others = menu.items.filter((i) => i.category_id !== a.category_id);
      updateMenu({ ...menu, items: [...others, ...reordered] });
    }
  }

  async function saveDraft() {
    if (errors.some((e) => !e.path.includes(":rows"))) {
      // Allow pagination warnings; block hard errors
      const hard = errors.filter((e) => !e.path.endsWith(":rows"));
      if (hard.length) {
        toast.error(hard[0].message);
        return;
      }
    }
    setBusy("draft");
    try {
      const updated = await api<{ config: { menu_v2_draft: MenuV2 } }>(
        `/api/dashboard/tenants/${tenantDbId}/config`,
        { method: "POST", body: JSON.stringify({ menu_v2_draft: menu }), tenant: false }
      );
      onSaved(updated.config.menu_v2_draft || menu, published);
      toast.success("Draft saved");
    } catch (e: unknown) {
      toast.error(e instanceof Error ? e.message : "Save failed");
    } finally {
      setBusy(null);
    }
  }

  async function publish() {
    setBusy("publish");
    try {
      // Persist draft first
      await api(`/api/dashboard/tenants/${tenantDbId}/config`, {
        method: "POST",
        body: JSON.stringify({ menu_v2_draft: menu }),
        tenant: false,
      });
      const updated = await api<{ config: { menu_v2: MenuV2; menu_v2_draft: MenuV2 } }>(
        `/api/dashboard/tenants/${tenantDbId}/menu/publish`,
        { method: "POST", tenant: false }
      );
      onSaved(updated.config.menu_v2_draft, updated.config.menu_v2);
      toast.success("Published — live within ~60s");
    } catch (e: unknown) {
      toast.error(e instanceof Error ? e.message : "Publish failed");
    } finally {
      setBusy(null);
    }
  }

  async function testSend() {
    setBusy("test");
    try {
      await api(`/api/dashboard/tenants/${tenantDbId}/config`, {
        method: "POST",
        body: JSON.stringify({ menu_v2_draft: menu }),
        tenant: false,
      });
      const res = await api<{ sent: number; to: string }>(
        `/api/dashboard/tenants/${tenantDbId}/menu/test-send`,
        { method: "POST", tenant: false }
      );
      toast.success(`Draft sent to ${res.to} (${res.sent} messages)`);
    } catch (e: unknown) {
      toast.error(e instanceof Error ? e.message : "Test send failed");
    } finally {
      setBusy(null);
    }
  }

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h2 className="text-sm font-semibold">
            {simple ? "Your menu" : "Menu Builder"}
          </h2>
          <p className="text-xs text-muted-foreground">
            {simple
              ? "Add categories → items → prices · Save, then Go live"
              : "Design the WhatsApp lists customers tap through · Draft vs Publish"}
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          <Button variant="outline" size="sm" onClick={testSend} disabled={!!busy}>
            {busy === "test" ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Send className="h-3.5 w-3.5" />}
            Test on my phone
          </Button>
          <Button variant="secondary" size="sm" onClick={saveDraft} disabled={!!busy}>
            {busy === "draft" ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : null}
            {simple ? "Save" : "Save Draft"}
          </Button>
          <Button size="sm" onClick={publish} disabled={!!busy}>
            {busy === "publish" ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Upload className="h-3.5 w-3.5" />}
            {simple ? "Go live" : "Publish"}
          </Button>
        </div>
      </div>

      {/* Settings strip */}
      <div className="grid gap-3 rounded-2xl border border-border bg-card p-4 sm:grid-cols-2">
        <div>
          <Label>{simple ? "First WhatsApp message" : "Greeting text"}</Label>
          <Textarea
            className="mt-1.5"
            rows={2}
            value={menu.settings.greeting_text}
            onChange={(e) =>
              updateMenu({
                ...menu,
                settings: { ...menu.settings, greeting_text: e.target.value },
              })
            }
          />
        </div>
        <div className="space-y-3">
          <div>
            <Label>
              {simple ? "Menu button text" : `Menu button label (≤${LIMITS.buttonLabel})`}
            </Label>
            <Input
              className={cn(
                "mt-1.5",
                errorMap["settings.menu_button_label"] && "border-destructive"
              )}
              value={menu.settings.menu_button_label}
              maxLength={LIMITS.buttonLabel + 5}
              onChange={(e) =>
                updateMenu({
                  ...menu,
                  settings: { ...menu.settings, menu_button_label: e.target.value },
                })
              }
            />
            {errorMap["settings.menu_button_label"] && (
              <p className="mt-1 text-[11px] text-destructive">{errorMap["settings.menu_button_label"]}</p>
            )}
          </div>
          <div className="grid grid-cols-2 gap-2">
            <div>
              <Label>Delivery charge</Label>
              <Input
                type="number"
                className="mt-1.5"
                value={menu.settings.delivery.charge}
                onChange={(e) =>
                  updateMenu({
                    ...menu,
                    settings: {
                      ...menu.settings,
                      delivery: {
                        ...menu.settings.delivery,
                        charge: Number(e.target.value),
                      },
                    },
                  })
                }
              />
            </div>
            <div>
              <Label>Free above</Label>
              <Input
                type="number"
                className="mt-1.5"
                value={menu.settings.delivery.free_above}
                onChange={(e) =>
                  updateMenu({
                    ...menu,
                    settings: {
                      ...menu.settings,
                      delivery: {
                        ...menu.settings.delivery,
                        free_above: Number(e.target.value),
                      },
                    },
                  })
                }
              />
            </div>
          </div>
        </div>
      </div>

      <div className="grid gap-4 lg:grid-cols-2">
        {/* LEFT — structure */}
        <div className="space-y-3 rounded-2xl border border-border bg-card p-4">
          <div className="flex items-center justify-between">
            <p className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
              Structure
            </p>
            <Button type="button" size="sm" variant="outline" onClick={addCategory}>
              <Plus className="h-3.5 w-3.5" /> Category
            </Button>
          </div>

          <DndContext sensors={sensors} collisionDetection={closestCenter} onDragEnd={onDragEnd}>
            <SortableContext
              items={sortedCats.map((c) => `cat:${c.id}`)}
              strategy={verticalListSortingStrategy}
            >
              {sortedCats.map((cat) => {
                const items = menu.items
                  .filter((i) => i.category_id === cat.id)
                  .sort((a, b) => a.sort - b.sort);
                const open = openCats[cat.id] ?? true;
                return (
                  <SortableCat key={cat.id} id={`cat:${cat.id}`}>
                    <div
                      className={cn(
                        "rounded-xl border border-border bg-muted/20",
                        errorMap[`cat:${cat.id}`] && "border-destructive/60"
                      )}
                    >
                      <div className="flex items-center gap-2 px-3 py-2">
                        <button
                          type="button"
                          onClick={() => setOpenCats((o) => ({ ...o, [cat.id]: !open }))}
                          className="text-muted-foreground"
                        >
                          {open ? <ChevronDown className="h-4 w-4" /> : <ChevronRight className="h-4 w-4" />}
                        </button>
                        <Input
                          value={cat.name}
                          className="h-8 border-0 bg-transparent px-1 font-medium shadow-none focus-visible:ring-0"
                          maxLength={LIMITS.categoryName + 5}
                          onChange={(e) =>
                            updateMenu({
                              ...menu,
                              categories: menu.categories.map((c) =>
                                c.id === cat.id ? { ...c, name: e.target.value } : c
                              ),
                            })
                          }
                        />
                        <span className="text-[10px] tabular text-muted-foreground">
                          {cat.name.length}/{LIMITS.categoryName}
                        </span>
                        <button
                          type="button"
                          title={cat.visible ? "Hide category" : "Show category"}
                          onClick={() =>
                            updateMenu({
                              ...menu,
                              categories: menu.categories.map((c) =>
                                c.id === cat.id ? { ...c, visible: !c.visible } : c
                              ),
                            })
                          }
                        >
                          {cat.visible ? (
                            <Eye className="h-4 w-4 text-primary" />
                          ) : (
                            <EyeOff className="h-4 w-4 text-muted-foreground" />
                          )}
                        </button>
                        <Button
                          type="button"
                          size="sm"
                          variant="ghost"
                          title="Mark all unavailable (aaj deals band)"
                          onClick={() => markCategoryUnavailable(cat.id)}
                        >
                          Off
                        </Button>
                        <Button
                          type="button"
                          size="icon"
                          variant="ghost"
                          onClick={() =>
                            updateMenu({
                              ...menu,
                              categories: menu.categories.filter((c) => c.id !== cat.id),
                              items: menu.items.filter((i) => i.category_id !== cat.id),
                            })
                          }
                        >
                          <Trash2 className="h-3.5 w-3.5 text-destructive" />
                        </Button>
                      </div>
                      {(errorMap[`cat:${cat.id}`] || errorMap[`cat:${cat.id}:rows`]) && (
                        <p className="px-3 pb-2 text-[11px] text-destructive">
                          {errorMap[`cat:${cat.id}`] || errorMap[`cat:${cat.id}:rows`]}
                        </p>
                      )}
                      {open && (
                        <div className="space-y-1.5 border-t border-border px-2 py-2">
                          <SortableContext
                            items={items.map((i) => `item:${i.id}`)}
                            strategy={verticalListSortingStrategy}
                          >
                            {items.map((item) => (
                              <SortableItem key={item.id} id={`item:${item.id}`}>
                                <button
                                  type="button"
                                  onClick={() => setEditingItem(item)}
                                  className={cn(
                                    "flex w-full items-center gap-2 rounded-lg border border-transparent bg-card px-2 py-2 text-left text-sm transition hover:border-primary/30",
                                    (errorMap[`item:${item.id}:name`] ||
                                      errorMap[`item:${item.id}:desc`]) &&
                                      "border-destructive/50"
                                  )}
                                >
                                  <div className="min-w-0 flex-1">
                                    <p className="truncate font-medium">{item.name}</p>
                                    <p className="truncate text-[11px] text-muted-foreground">
                                      {item.description || "No description"} · Rs {item.price}
                                      {!item.available && " · unavailable"}
                                    </p>
                                  </div>
                                  <Button
                                    type="button"
                                    size="icon"
                                    variant="ghost"
                                    onClick={(e) => {
                                      e.stopPropagation();
                                      duplicateItem(item);
                                    }}
                                  >
                                    <Copy className="h-3.5 w-3.5" />
                                  </Button>
                                </button>
                              </SortableItem>
                            ))}
                          </SortableContext>
                          <Button
                            type="button"
                            size="sm"
                            variant="ghost"
                            className="w-full"
                            onClick={() => addItem(cat.id)}
                          >
                            <Plus className="h-3.5 w-3.5" /> Add item
                          </Button>
                        </div>
                      )}
                    </div>
                  </SortableCat>
                );
              })}
            </SortableContext>
          </DndContext>
          {!sortedCats.length && (
            <p className="py-8 text-center text-sm text-muted-foreground">
              Add a category to start building your WhatsApp menu.
            </p>
          )}
        </div>

        {/* RIGHT — live preview */}
        <WhatsAppMenuPreview
          menu={menu}
          errors={errors}
          step={previewStep}
          onStepChange={setPreviewStep}
        />
      </div>

      {editingItem && (
        <ItemEditorDrawer
          item={editingItem}
          errorMap={errorMap}
          onClose={() => setEditingItem(null)}
          onChange={(next) => {
            setEditingItem(next);
            updateMenu({
              ...menu,
              items: menu.items.map((i) => (i.id === next.id ? next : i)),
            });
          }}
          onDelete={() => {
            updateMenu({ ...menu, items: menu.items.filter((i) => i.id !== editingItem.id) });
            setEditingItem(null);
          }}
        />
      )}
    </div>
  );
}

function SortableCat({ id, children }: { id: string; children: React.ReactNode }) {
  const { attributes, listeners, setNodeRef, transform, transition } = useSortable({ id });
  return (
    <div
      ref={setNodeRef}
      style={{ transform: CSS.Transform.toString(transform), transition }}
      className="mb-2"
    >
      <div className="flex gap-1">
        <button
          type="button"
          className="mt-3 touch-none text-muted-foreground"
          {...attributes}
          {...listeners}
        >
          <GripVertical className="h-4 w-4" />
        </button>
        <div className="min-w-0 flex-1">{children}</div>
      </div>
    </div>
  );
}

function SortableItem({ id, children }: { id: string; children: React.ReactNode }) {
  const { attributes, listeners, setNodeRef, transform, transition } = useSortable({ id });
  return (
    <div
      ref={setNodeRef}
      style={{ transform: CSS.Transform.toString(transform), transition }}
      className="flex items-center gap-1"
    >
      <button type="button" className="touch-none text-muted-foreground" {...attributes} {...listeners}>
        <GripVertical className="h-3.5 w-3.5" />
      </button>
      <div className="min-w-0 flex-1">{children}</div>
    </div>
  );
}

function ItemEditorDrawer({
  item,
  onChange,
  onClose,
  onDelete,
  errorMap,
}: {
  item: MenuV2Item;
  onChange: (i: MenuV2Item) => void;
  onClose: () => void;
  onDelete: () => void;
  errorMap: Record<string, string>;
}) {
  const mod = item.modifiers[0];
  return (
    <div className="fixed inset-0 z-50 flex justify-end bg-black/50" onClick={onClose}>
      <div
        className="h-full w-full max-w-md overflow-y-auto border-l border-border bg-card p-5 shadow-drawer"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between">
          <h3 className="font-semibold">Edit item</h3>
          <Button variant="ghost" size="sm" onClick={onClose}>
            Close
          </Button>
        </div>
        <div className="mt-4 space-y-3">
          <div>
            <Label>Name (≤{LIMITS.itemName})</Label>
            <Input
              className={cn("mt-1.5", errorMap[`item:${item.id}:name`] && "border-destructive")}
              value={item.name}
              onChange={(e) => onChange({ ...item, name: e.target.value })}
            />
            {errorMap[`item:${item.id}:name`] && (
              <p className="mt-1 text-[11px] text-destructive">{errorMap[`item:${item.id}:name`]}</p>
            )}
          </div>
          <div>
            <Label>Description (≤{LIMITS.itemDesc})</Label>
            <Textarea
              className={cn("mt-1.5", errorMap[`item:${item.id}:desc`] && "border-destructive")}
              rows={2}
              value={item.description}
              onChange={(e) => onChange({ ...item, description: e.target.value })}
            />
          </div>
          <div className="flex items-center justify-between gap-3">
            <div className="flex-1">
              <Label>Price (PKR)</Label>
              <Input
                type="number"
                className="mt-1.5"
                value={item.price}
                onChange={(e) => onChange({ ...item, price: Number(e.target.value) })}
              />
            </div>
            <div className="pt-5">
              <div className="flex items-center gap-2">
                <Switch
                  checked={item.available}
                  onCheckedChange={(v) => onChange({ ...item, available: v })}
                />
                <span className="text-xs text-muted-foreground">Available</span>
              </div>
            </div>
          </div>

          <div className="rounded-xl border border-border p-3">
            <div className="flex items-center justify-between">
              <p className="text-sm font-medium">Modifier group</p>
              {!mod ? (
                <Button
                  size="sm"
                  variant="outline"
                  onClick={() =>
                    onChange({
                      ...item,
                      modifiers: [
                        {
                          id: nid("mod"),
                          name: "Size",
                          options: [
                            { id: nid("opt"), label: "Regular", price_delta: 0 },
                            { id: nid("opt"), label: "Large", price_delta: 100 },
                          ],
                        },
                      ],
                    })
                  }
                >
                  Add
                </Button>
              ) : (
                <Button
                  size="sm"
                  variant="ghost"
                  onClick={() => onChange({ ...item, modifiers: [] })}
                >
                  Remove
                </Button>
              )}
            </div>
            {mod && (
              <div className="mt-3 space-y-2">
                <Input
                  value={mod.name}
                  onChange={(e) =>
                    onChange({
                      ...item,
                      modifiers: [{ ...mod, name: e.target.value }],
                    })
                  }
                  placeholder="Group name (e.g. Size)"
                />
                {mod.options.map((opt, oi) => (
                  <div key={opt.id} className="flex gap-2">
                    <Input
                      value={opt.label}
                      maxLength={LIMITS.optionLabel + 5}
                      onChange={(e) => {
                        const options = mod.options.map((o, i) =>
                          i === oi ? { ...o, label: e.target.value } : o
                        );
                        onChange({ ...item, modifiers: [{ ...mod, options }] });
                      }}
                      placeholder="Label"
                    />
                    <Input
                      type="number"
                      className="w-24"
                      value={opt.price_delta}
                      onChange={(e) => {
                        const options = mod.options.map((o, i) =>
                          i === oi ? { ...o, price_delta: Number(e.target.value) } : o
                        );
                        onChange({ ...item, modifiers: [{ ...mod, options }] });
                      }}
                    />
                    <Button
                      size="icon"
                      variant="ghost"
                      disabled={mod.options.length <= 1}
                      onClick={() => {
                        const options = mod.options.filter((_, i) => i !== oi);
                        onChange({ ...item, modifiers: [{ ...mod, options }] });
                      }}
                    >
                      <Trash2 className="h-3.5 w-3.5" />
                    </Button>
                  </div>
                ))}
                {mod.options.length < LIMITS.modifierOptionsMax && (
                  <Button
                    size="sm"
                    variant="ghost"
                    onClick={() =>
                      onChange({
                        ...item,
                        modifiers: [
                          {
                            ...mod,
                            options: [
                              ...mod.options,
                              { id: nid("opt"), label: "Option", price_delta: 0 },
                            ],
                          },
                        ],
                      })
                    }
                  >
                    <Plus className="h-3.5 w-3.5" /> Option
                  </Button>
                )}
                {errorMap[`item:${item.id}:mods`] && (
                  <p className="text-[11px] text-destructive">{errorMap[`item:${item.id}:mods`]}</p>
                )}
              </div>
            )}
          </div>

          <Button variant="destructive" onClick={onDelete}>
            Delete item
          </Button>
        </div>
      </div>
    </div>
  );
}
