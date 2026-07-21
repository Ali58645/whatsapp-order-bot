import { Input, Label, Textarea } from "./ui/input";
import { AccordionSection } from "./ui/accordion-section";
import { OptionListEditor, OptionListItem } from "./OptionListEditor";

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

type Props = {
  lead: LeadDraft;
  interactive: Interactive;
  demoSlots: string[];
  onLeadChange: (lead: LeadDraft) => void;
  onInteractiveChange: (interactive: Interactive) => void;
  onDemoSlotsChange: (slots: string[]) => void;
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

export function LeadOptionsEditor({
  lead,
  interactive,
  demoSlots,
  onLeadChange,
  onInteractiveChange,
  onDemoSlotsChange,
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

  return (
    <div className="space-y-3">
      <AccordionSection
        title="1. Business type"
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
      </AccordionSection>

      <AccordionSection
        title="2. Locations"
        count={locItems.length}
        countLabel={locItems.length === 1 ? "button" : "buttons"}
      >
        <div>
          <Label>Question text</Label>
          <Textarea
            rows={2}
            className="mt-1.5"
            value={lead.q_locations || ""}
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
      </AccordionSection>

      <AccordionSection
        title="3. Current system"
        count={sysItems.length}
        countLabel={sysItems.length === 1 ? "button" : "buttons"}
      >
        <div>
          <Label>Question text</Label>
          <Textarea
            rows={2}
            className="mt-1.5"
            value={lead.q_current_system || ""}
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
      </AccordionSection>

      <AccordionSection
        title="4. Demo scheduling"
        count={schedulingItems.length}
        countLabel="slot buttons"
      >
        <div>
          <Label>Question text</Label>
          <Textarea
            rows={3}
            className="mt-1.5"
            value={lead.q_scheduling || ""}
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
          The third button is always shown and cannot be removed. Slot labels are also the booked demo values.
        </p>
      </AccordionSection>
    </div>
  );
}
