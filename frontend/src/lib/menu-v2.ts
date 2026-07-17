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

export function validateMenuClient(menu: ReturnType<typeof emptyMenuV2>): FieldError[] {
  const errs: FieldError[] = [];
  if (menu.settings.menu_button_label.length > LIMITS.buttonLabel) {
    errs.push({
      path: "settings.menu_button_label",
      message: `Button label max ${LIMITS.buttonLabel} chars`,
    });
  }
  for (const c of menu.categories) {
    if (c.name.length > LIMITS.categoryName) {
      errs.push({ path: `cat:${c.id}`, message: `Category name max ${LIMITS.categoryName}` });
    }
    if (!c.name.trim()) {
      errs.push({ path: `cat:${c.id}`, message: "Category name required" });
    }
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
            path: `item:${it.id}:opt:${opt.id}`,
            message: `Option label max ${LIMITS.optionLabel}`,
          });
        }
      }
    }
  }
  return errs;
}
