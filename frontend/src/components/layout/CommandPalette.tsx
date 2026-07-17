import { useEffect, useState } from "react";
import { Command } from "cmdk";
import { useNavigate } from "react-router-dom";
import {
  LayoutDashboard,
  Users,
  Package,
  MessagesSquare,
  Activity,
  Settings,
  Search,
  VolumeX,
} from "lucide-react";
import { api, Lead, setTenantFilter, Tenant } from "../../api";
import { Dialog, DialogContent } from "../ui/dialog";

const PAGES = [
  { to: "/", label: "Overview", icon: LayoutDashboard },
  { to: "/leads", label: "Leads", icon: Users },
  { to: "/orders", label: "Orders", icon: Package },
  { to: "/conversations", label: "Conversations", icon: MessagesSquare },
  { to: "/activity", label: "Activity", icon: Activity },
  { to: "/settings", label: "Settings", icon: Settings },
];

export function CommandPalette({
  open,
  onOpenChange,
  tenants,
}: {
  open: boolean;
  onOpenChange: (v: boolean) => void;
  tenants: Tenant[];
}) {
  const navigate = useNavigate();
  const [query, setQuery] = useState("");
  const [leads, setLeads] = useState<Lead[]>([]);

  useEffect(() => {
    if (!open) return;
    const t = setTimeout(() => {
      const q = query.trim();
      api<{ items: Lead[] }>(
        `/api/dashboard/leads?search=${encodeURIComponent(q)}&status=`
      )
        .then((r) => setLeads(r.items.slice(0, 8)))
        .catch(() => setLeads([]));
    }, 200);
    return () => clearTimeout(t);
  }, [query, open]);

  useEffect(() => {
    if (!open) setQuery("");
  }, [open]);

  function go(path: string) {
    onOpenChange(false);
    navigate(path);
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="overflow-hidden p-0 sm:max-w-lg">
        <Command className="bg-popover text-popover-foreground" shouldFilter={false}>
          <div className="flex items-center gap-2 border-b border-border px-3">
            <Search className="h-4 w-4 shrink-0 text-muted-foreground" />
            <Command.Input
              value={query}
              onValueChange={setQuery}
              placeholder="Jump to lead, page, or action…"
              className="h-12 w-full bg-transparent text-sm outline-none placeholder:text-muted-foreground"
            />
            <kbd className="hidden rounded border border-border px-1.5 py-0.5 text-[10px] text-muted-foreground sm:inline">
              ESC
            </kbd>
          </div>
          <Command.List className="max-h-80 overflow-y-auto p-2">
            <Command.Empty className="py-8 text-center text-sm text-muted-foreground">
              No results
            </Command.Empty>

            <Command.Group heading="Navigate" className="text-xs text-muted-foreground [&_[cmdk-group-heading]]:px-2 [&_[cmdk-group-heading]]:py-1.5">
              {PAGES.map((p) => (
                <Command.Item
                  key={p.to}
                  value={p.label}
                  onSelect={() => go(p.to)}
                  className="flex cursor-pointer items-center gap-2 rounded-lg px-2 py-2 text-sm text-foreground aria-selected:bg-accent"
                >
                  <p.icon className="h-4 w-4 text-muted-foreground" />
                  {p.label}
                </Command.Item>
              ))}
            </Command.Group>

            {leads.length > 0 && (
              <Command.Group heading="Leads" className="text-xs text-muted-foreground [&_[cmdk-group-heading]]:px-2 [&_[cmdk-group-heading]]:py-1.5">
                {leads.map((l) => (
                  <Command.Item
                    key={l.id}
                    value={`${l.business_name} ${l.contact.wa_id}`}
                    onSelect={() => go(`/leads?open=${l.id}`)}
                    className="flex cursor-pointer flex-col rounded-lg px-2 py-2 text-sm aria-selected:bg-accent"
                  >
                    <span className="font-medium">
                      {l.business_name || l.contact.profile_name || l.contact.wa_id}
                    </span>
                    <span className="text-xs text-muted-foreground">{l.contact.wa_id}</span>
                  </Command.Item>
                ))}
              </Command.Group>
            )}

            {tenants.length > 0 && (
              <Command.Group heading="Switch tenant" className="text-xs text-muted-foreground [&_[cmdk-group-heading]]:px-2 [&_[cmdk-group-heading]]:py-1.5">
                <Command.Item
                  value="All tenants"
                  onSelect={() => {
                    setTenantFilter("all");
                    window.dispatchEvent(new Event("tenant-change"));
                    onOpenChange(false);
                  }}
                  className="cursor-pointer rounded-lg px-2 py-2 text-sm aria-selected:bg-accent"
                >
                  All tenants
                </Command.Item>
                {tenants.map((t) => (
                  <Command.Item
                    key={t.id}
                    value={t.name}
                    onSelect={() => {
                      setTenantFilter(t.phone_number_id);
                      window.dispatchEvent(new Event("tenant-change"));
                      onOpenChange(false);
                    }}
                    className="cursor-pointer rounded-lg px-2 py-2 text-sm aria-selected:bg-accent"
                  >
                    {t.name}
                  </Command.Item>
                ))}
              </Command.Group>
            )}

            <Command.Group heading="Actions" className="text-xs text-muted-foreground [&_[cmdk-group-heading]]:px-2 [&_[cmdk-group-heading]]:py-1.5">
              <Command.Item
                value="Mute from leads"
                onSelect={() => go("/leads")}
                className="flex cursor-pointer items-center gap-2 rounded-lg px-2 py-2 text-sm aria-selected:bg-accent"
              >
                <VolumeX className="h-4 w-4 text-muted-foreground" />
                Mute contact (open a lead)
              </Command.Item>
            </Command.Group>
          </Command.List>
        </Command>
      </DialogContent>
    </Dialog>
  );
}
