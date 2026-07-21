import { useMemo } from "react";
import { MenuV2 } from "../../api";
import { FieldError, LIMITS } from "../../lib/menu-v2";
import { Button } from "../ui/button";
import { cn } from "../../lib/utils";

type StepPayload = {
  type?: string;
  text?: { body: string };
  interactive?: {
    type: string;
    body: { text: string };
    action: {
      button?: string;
      buttons?: { reply: { id: string; title: string } }[];
      sections?: { rows: { id: string; title: string; description?: string }[] }[];
    };
  };
};

/** Client-side mirror of runtime pagination for live preview (same rules as menu_v2.py). */
function buildPreviewSteps(menu: MenuV2): { label: string; payload: StepPayload }[] {
  const steps: { label: string; payload: StepPayload }[] = [];
  const greeting = menu.settings.greeting_text || "…";
  steps.push({
    label: "Greeting",
    payload: { type: "text", text: { body: greeting } },
  });

  const roots = menu.categories.filter((c) => c.visible && !c.parent_id);
  const childrenOf = (pid: string) =>
    menu.categories.filter((c) => c.visible && (c.parent_id || "") === pid);
  const button = menu.settings.menu_button_label.slice(0, LIMITS.buttonLabel) || "Menu";

  const itemRows = (catId: string | null, page: number) => {
    const items = menu.items
      .filter((i) => i.available && (catId == null || i.category_id === catId))
      .sort((a, b) => a.sort - b.sort);
    const pageSize = LIMITS.rowsMax - 1;
    const start = page * pageSize;
    const remaining = items.slice(start);
    const needsMore = remaining.length > LIMITS.rowsMax;
    const slice = needsMore ? remaining.slice(0, pageSize) : remaining.slice(0, LIMITS.rowsMax);
    const rows = slice.map((it) => ({
      id: `item:${it.id}`,
      title: it.name.slice(0, LIMITS.itemName),
      description: `PKR ${it.price}${it.description ? ` · ${it.description}` : ""}`.slice(
        0,
        LIMITS.itemDesc
      ),
    }));
    if (needsMore) {
      rows.push({
        id: `menu:more:${catId || "all"}:${page + 1}`,
        title: "Aur dekhein →",
        description: "Agli list",
      });
    }
    return rows;
  };

  const catRows = (list: typeof roots) =>
    list.slice(0, LIMITS.rowsMax).map((c) => {
      const kids = childrenOf(c.id);
      return {
        id: `cat:${c.id}`,
        title: c.name.slice(0, LIMITS.categoryName),
        description: kids.length
          ? `${kids.length} groups`
          : `${menu.items.filter((i) => i.category_id === c.id && i.available).length} items`,
      };
    });

  if (roots.length > 1) {
    steps.push({
      label: "Categories",
      payload: {
        type: "interactive",
        interactive: {
          type: "list",
          body: { text: "Category choose karein:" },
          action: { button, sections: [{ rows: catRows(roots) }] },
        },
      },
    });
  }

  let leafId: string | null = roots[0]?.id ?? null;
  if (roots[0]) {
    const kids = childrenOf(roots[0].id);
    if (kids.length) {
      steps.push({
        label: "Sub-categories",
        payload: {
          type: "interactive",
          interactive: {
            type: "list",
            body: { text: `${roots[0].name} — choose karein:` },
            action: { button, sections: [{ rows: catRows(kids) }] },
          },
        },
      });
      leafId = kids[0].id;
    }
    steps.push({
      label: "Items",
      payload: {
        type: "interactive",
        interactive: {
          type: "list",
          body: {
            text: leafId
              ? `${menu.categories.find((c) => c.id === leafId)?.name || ""} — item choose karein:`
              : "Item choose karein:",
          },
          action: { button, sections: [{ rows: itemRows(leafId, 0) }] },
        },
      },
    });
  } else {
    steps.push({
      label: "Items",
      payload: {
        type: "interactive",
        interactive: {
          type: "list",
          body: { text: "Item choose karein:" },
          action: { button, sections: [{ rows: itemRows(null, 0) }] },
        },
      },
    });
  }

  const firstItem = menu.items
    .filter((i) => i.available && (!leafId || i.category_id === leafId))
    .sort((a, b) => a.sort - b.sort)[0];

  if (firstItem?.modifiers?.[0]?.options?.length) {
    const mod = firstItem.modifiers[0];
    steps.push({
      label: "Modifier",
      payload: {
        type: "interactive",
        interactive: {
          type: "button",
          body: { text: `${firstItem.name} — ${mod.name} choose karein:` },
          action: {
            buttons: mod.options.slice(0, LIMITS.buttonsMax).map((o) => ({
              reply: {
                id: o.id,
                title: (
                  o.price_delta
                    ? `${o.label.slice(0, 12)} +${o.price_delta}`
                    : o.label
                ).slice(0, LIMITS.optionLabel),
              },
            })),
          },
        },
      },
    });
  }

  if (firstItem) {
    steps.push({
      label: "Quantity",
      payload: {
        type: "text",
        text: { body: `${firstItem.name} — kitni quantity? (1-9)` },
      },
    });
    const unit = firstItem.price + (firstItem.modifiers?.[0]?.options?.[0]?.price_delta || 0);
    const delivery = menu.settings.delivery.enabled ? menu.settings.delivery.charge : 0;
    steps.push({
      label: "Add more?",
      payload: {
        type: "interactive",
        interactive: {
          type: "button",
          body: { text: "Aur kuch add karein?" },
          action: {
            buttons: [
              { reply: { id: "more", title: "Haan" } },
              { reply: { id: "done", title: "Nahi, bas" } },
            ],
          },
        },
      },
    });
    steps.push({
      label: "Confirm",
      payload: {
        type: "interactive",
        interactive: {
          type: "button",
          body: {
            text: `Aapka order:\n• 1x ${firstItem.name} — PKR ${unit}\nDelivery: PKR ${delivery}\nTotal: PKR ${unit + delivery}\n\n${menu.settings.order_confirm_note}`,
          },
          action: {
            buttons: [
              { reply: { id: "confirm", title: "Confirm" } },
              { reply: { id: "cancel", title: "Cancel" } },
            ],
          },
        },
      },
    });
  }

  return steps;
}

export function WhatsAppMenuPreview({
  menu,
  errors,
  step,
  onStepChange,
}: {
  menu: MenuV2;
  errors: FieldError[];
  step: number;
  onStepChange: (n: number) => void;
}) {
  const steps = useMemo(() => buildPreviewSteps(menu), [menu]);
  const current = steps[Math.min(step, steps.length - 1)] || steps[0];
  const hardErrors = errors.filter((e) => !e.path.endsWith(":rows"));
  const warnErrors = errors.filter((e) => e.path.endsWith(":rows"));

  return (
    <div className="flex flex-col rounded-2xl border border-border bg-card p-4">
      <div className="mb-3 flex items-center justify-between">
        <p className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
          Live WhatsApp preview
        </p>
        <div className="flex gap-1">
          <Button
            size="sm"
            variant="ghost"
            disabled={step <= 0}
            onClick={() => onStepChange(Math.max(0, step - 1))}
          >
            ←
          </Button>
          <span className="px-2 text-[11px] tabular text-muted-foreground">
            {Math.min(step + 1, steps.length)}/{steps.length} · {current?.label}
          </span>
          <Button
            size="sm"
            variant="ghost"
            disabled={step >= steps.length - 1}
            onClick={() => onStepChange(Math.min(steps.length - 1, step + 1))}
          >
            →
          </Button>
        </div>
      </div>

      {(hardErrors.length > 0 || warnErrors.length > 0) && (
        <div className="mb-3 space-y-1">
          {hardErrors.slice(0, 3).map((e) => (
            <p key={e.path} className="text-[11px] text-destructive">
              {e.message}
            </p>
          ))}
          {warnErrors.slice(0, 2).map((e) => (
            <p key={e.path} className="text-[11px] text-warning">
              {e.message}
            </p>
          ))}
        </div>
      )}

      <div
        className="flex-1 overflow-hidden rounded-xl p-3"
        style={{
          backgroundColor: "var(--wa-bg)",
          minHeight: 360,
          backgroundImage: `url("data:image/svg+xml,%3Csvg width='60' height='60' viewBox='0 0 60 60' xmlns='http://www.w3.org/2000/svg'%3E%3Cg fill='%23ffffff' fill-opacity='0.03'%3E%3Cpath d='M36 34v-4h-2v4h-4v2h4v4h2v-4h4v-2h-4zm0-30V0h-2v4h-4v2h4v4h2V6h4V4h-4zM6 34v-4H4v4H0v2h4v4h2v-4h4v-2H6zM6 4V0H4v4H0v2h4v4h2V6h4V4H6z'/%3E%3C/g%3E%3C/svg%3E")`,
        }}
      >
        {current && <PreviewBubble payload={current.payload} onTapRow={() => onStepChange(Math.min(step + 1, steps.length - 1))} />}
      </div>
      <p className="mt-2 text-[10px] text-muted-foreground">
        Tap a list row or button in the preview to advance the simulated flow.
      </p>
    </div>
  );
}

function PreviewBubble({
  payload,
  onTapRow,
}: {
  payload: StepPayload;
  onTapRow: () => void;
}) {
  if (payload.type === "text" || payload.text) {
    return (
      <div className="flex justify-start">
        <div className="max-w-[90%] rounded-2xl rounded-bl-sm bg-[var(--wa-in)] px-3 py-2 text-[13px] text-zinc-100">
          <p className="transcript-text whitespace-pre-wrap">{payload.text?.body}</p>
        </div>
      </div>
    );
  }

  const interactive = payload.interactive;
  if (!interactive) return null;

  if (interactive.type === "list") {
    const rows = interactive.action.sections?.[0]?.rows || [];
    return (
      <div className="space-y-2">
        <div className="flex justify-start">
          <div className="max-w-[90%] rounded-2xl rounded-bl-sm bg-[var(--wa-in)] px-3 py-2 text-[13px] text-zinc-100">
            <p className="transcript-text">{interactive.body.text}</p>
            <button
              type="button"
              className="mt-2 w-full rounded-lg border border-white/15 bg-white/10 py-1.5 text-center text-xs font-semibold text-emerald-300"
              onClick={onTapRow}
            >
              {interactive.action.button || "Menu"}
            </button>
          </div>
        </div>
        <div className="rounded-xl border border-white/10 bg-black/40 p-2">
          <p className="mb-1 text-[10px] uppercase tracking-wider text-zinc-500">List rows</p>
          {rows.map((r) => (
            <button
              key={r.id}
              type="button"
              onClick={onTapRow}
              className={cn(
                "mb-1 w-full rounded-lg px-2 py-2 text-left transition hover:bg-white/10",
                r.title === "Aur dekhein →" && "text-emerald-300"
              )}
            >
              <p className="text-[13px] font-medium text-zinc-100">{r.title}</p>
              {r.description && (
                <p className="text-[11px] text-zinc-400">{r.description}</p>
              )}
            </button>
          ))}
        </div>
      </div>
    );
  }

  if (interactive.type === "button") {
    return (
      <div className="flex justify-start">
        <div className="max-w-[90%] rounded-2xl rounded-bl-sm bg-[var(--wa-in)] px-3 py-2 text-[13px] text-zinc-100">
          <p className="transcript-text whitespace-pre-wrap">{interactive.body.text}</p>
          <div className="mt-2 space-y-1.5">
            {(interactive.action.buttons || []).map((b) => (
              <button
                key={b.reply.id}
                type="button"
                onClick={onTapRow}
                className="w-full rounded-lg border border-emerald-500/30 bg-emerald-500/10 py-1.5 text-center text-xs font-semibold text-emerald-300"
              >
                {b.reply.title}
              </button>
            ))}
          </div>
        </div>
      </div>
    );
  }

  return null;
}
