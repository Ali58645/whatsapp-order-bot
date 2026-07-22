import { useEffect, useState } from "react";
import { Command } from "cmdk";
import { useNavigate } from "react-router-dom";
import {
  Building2,
  CreditCard,
  LayoutDashboard,
  ScrollText,
  Search,
  Settings,
  Users,
} from "lucide-react";
import { filterPickerTenants, getRole, isOwner, isSupportSession, setTenantFilter, Tenant } from "../../api";
import { Dialog, DialogContent } from "../ui/dialog";

const ADMIN_PAGES = [
  { to: "/", label: "Businesses", icon: Building2 },
  { to: "/team", label: "Team", icon: Users },
  { to: "/access-log", label: "Access Log", icon: ScrollText },
  { to: "/billing", label: "Billing", icon: CreditCard },
  { to: "/settings", label: "Wiring", icon: Settings },
];

const OWNER_PAGES = [
  { to: "/", label: "Home", icon: LayoutDashboard },
  { to: "/conversations", label: "Inbox", icon: Users },
  { to: "/customers", label: "Customers", icon: Users },
  { to: "/my-bot/greeting", label: "My Bot", icon: Settings },
  { to: "/account", label: "Account", icon: Settings },
  { to: "/billing", label: "Billing", icon: CreditCard },
  { to: "/team", label: "Team", icon: Users },
];

export function CommandPalette({
  open,
  onOpenChange,
  tenants,
  isAdmin,
}: {
  open: boolean;
  onOpenChange: (v: boolean) => void;
  tenants: Tenant[];
  isAdmin?: boolean;
}) {
  const navigate = useNavigate();
  const [query, setQuery] = useState("");
  const admin = isAdmin ?? (getRole() === "admin" && !isSupportSession());
  const ownerShell = isOwner() || isSupportSession();
  const pages = admin && !ownerShell ? ADMIN_PAGES : OWNER_PAGES;

  useEffect(() => {
    if (!open) setQuery("");
  }, [open]);

  function go(path: string) {
    onOpenChange(false);
    navigate(path);
  }

  const q = query.trim().toLowerCase();
  const filteredTenants =
    admin && !ownerShell && q
      ? filterPickerTenants(tenants).filter((t) => (t.name || "").toLowerCase().includes(q))
      : [];

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="overflow-hidden p-0 sm:max-w-lg">
        <Command className="bg-popover text-popover-foreground" shouldFilter={false}>
          <div className="flex items-center gap-2 border-b border-border px-3">
            <Search className="h-4 w-4 shrink-0 text-muted-foreground" />
            <Command.Input
              value={query}
              onValueChange={setQuery}
              placeholder={
                admin && !ownerShell
                  ? "Jump to page or business…"
                  : "Jump to page…"
              }
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

            <Command.Group
              heading="Navigate"
              className="text-xs text-muted-foreground [&_[cmdk-group-heading]]:px-2 [&_[cmdk-group-heading]]:py-1.5"
            >
              {pages
                .filter((p) => !q || p.label.toLowerCase().includes(q))
                .map((p) => (
                  <Command.Item
                    key={p.to}
                    value={p.label}
                    onSelect={() => go(p.to)}
                    className="flex cursor-pointer items-center gap-2 rounded-lg px-2 py-2 text-sm aria-selected:bg-accent"
                  >
                    <p.icon className="h-4 w-4 text-muted-foreground" />
                    {p.label}
                  </Command.Item>
                ))}
            </Command.Group>

            {filteredTenants.length > 0 && (
              <Command.Group
                heading="Businesses"
                className="text-xs text-muted-foreground [&_[cmdk-group-heading]]:px-2 [&_[cmdk-group-heading]]:py-1.5"
              >
                {filteredTenants.slice(0, 8).map((tn) => (
                  <Command.Item
                    key={tn.id}
                    value={tn.name}
                    onSelect={() => {
                      setTenantFilter(tn.phone_number_id);
                      onOpenChange(false);
                      navigate("/");
                    }}
                    className="flex cursor-pointer items-center gap-2 rounded-lg px-2 py-2 text-sm aria-selected:bg-accent"
                  >
                    <Building2 className="h-4 w-4 text-muted-foreground" />
                    {tn.name}
                  </Command.Item>
                ))}
              </Command.Group>
            )}
          </Command.List>
        </Command>
      </DialogContent>
    </Dialog>
  );
}
