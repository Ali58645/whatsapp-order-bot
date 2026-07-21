/** Client-side WhatsApp limit checks (server also enforces). */
export const LIMITS = {
  categoryName: 24,
  itemName: 24,
  itemDesc: 72,
  optionLabel: 20,
  buttonLabel: 20,
  rowsMax: 10,
  buttonsMax: 3,
  modifierGroupsMax: 1,
  modifierOptionsMax: 3,
} as const;

export function nid(prefix: string) {
  return `${prefix}_${Math.random().toString(36).slice(2, 10)}`;
}

export function emptyMenuV2() {
  return {
    categories: [] as import("../api").MenuV2Category[],
    items: [] as import("../api").MenuV2Item[],
    settings: {
      greeting_text: "Assalam o Alaikum! Menu dekhne ke liye neeche tap karein.",
      menu_button_label: "Menu dekhein",
      delivery: { enabled: true, charge: 100, free_above: 0, area_note: "" },
      order_confirm_note: "Confirm karein?",
      currency: "PKR",
    },
  };
}

export type FieldError = { path: string; message: string };

export function rootCategories(menu: ReturnType<typeof emptyMenuV2>) {
  return menu.categories.filter((c) => !c.parent_id).sort((a, b) => a.sort - b.sort);
}

export function childCategories(menu: ReturnType<typeof emptyMenuV2>, parentId: string) {
  return menu.categories
    .filter((c) => (c.parent_id || "") === parentId)
    .sort((a, b) => a.sort - b.sort);
}

export function isLeafCategory(menu: ReturnType<typeof emptyMenuV2>, catId: string) {
  return childCategories(menu, catId).length === 0;
}

export function validateMenuClient(menu: ReturnType<typeof emptyMenuV2>): FieldError[] {
  const errs: FieldError[] = [];
  if (menu.settings.menu_button_label.length > LIMITS.buttonLabel) {
    errs.push({
      path: "settings.menu_button_label",
      message: `Button label max ${LIMITS.buttonLabel} chars`,
    });
  }
  const byId = new Map(menu.categories.map((c) => [c.id, c]));
  for (const c of menu.categories) {
    if (c.name.length > LIMITS.categoryName) {
      errs.push({ path: `cat:${c.id}`, message: `Category name max ${LIMITS.categoryName}` });
    }
    if (!c.name.trim()) {
      errs.push({ path: `cat:${c.id}`, message: "Category name required" });
    }
    if (c.parent_id) {
      if (c.parent_id === c.id) {
        errs.push({ path: `cat:${c.id}`, message: "Sub-category cannot parent itself" });
      } else if (!byId.has(c.parent_id)) {
        errs.push({ path: `cat:${c.id}`, message: "Unknown parent category" });
      } else if (byId.get(c.parent_id)?.parent_id) {
        errs.push({
          path: `cat:${c.id}`,
          message: "Max depth 2 — cannot nest under a sub-category",
        });
      }
    }
    const kids = childCategories(menu, c.id);
    if (kids.length > LIMITS.rowsMax) {
      errs.push({
        path: `cat:${c.id}:rows`,
        message: `${kids.length} sub-categories — WhatsApp list max ${LIMITS.rowsMax}`,
      });
    }
    if (kids.length === 0) {
      const avail = menu.items.filter(
        (i) => i.category_id === c.id && i.available && c.visible
      );
      if (avail.length > LIMITS.rowsMax) {
        errs.push({
          path: `cat:${c.id}:rows`,
          message: `${avail.length} items — runtime will paginate (row 10 = Aur dekhein →)`,
        });
      }
    }
  }
  const roots = rootCategories(menu).filter((c) => c.visible);
  if (roots.length > LIMITS.rowsMax) {
    errs.push({
      path: "cats:roots",
      message: `${roots.length} root categories — WhatsApp list max ${LIMITS.rowsMax}`,
    });
  }
  for (const it of menu.items) {
    if (it.name.length > LIMITS.itemName) {
      errs.push({ path: `item:${it.id}:name`, message: `Name max ${LIMITS.itemName}` });
    }
    if ((it.description || "").length > LIMITS.itemDesc) {
      errs.push({ path: `item:${it.id}:desc`, message: `Description max ${LIMITS.itemDesc}` });
    }
    if (it.price <= 0) {
      errs.push({ path: `item:${it.id}:price`, message: "Price must be > 0" });
    }
    if ((it.modifiers || []).length > LIMITS.modifierGroupsMax) {
      errs.push({ path: `item:${it.id}:mods`, message: "Max 1 modifier group" });
    }
    for (const mod of it.modifiers || []) {
      if ((mod.options || []).length > LIMITS.modifierOptionsMax) {
        errs.push({
          path: `item:${it.id}:mods`,
          message: `Max ${LIMITS.modifierOptionsMax} options (reply buttons)`,
        });
      }
      for (const opt of mod.options || []) {
        if (opt.label.length > LIMITS.optionLabel) {
          errs.push({
            path: `item:${it.id}:mods`,
            message: `Option label max ${LIMITS.optionLabel}`,
          });
        }
      }
    }
  }
  return errs;
}
