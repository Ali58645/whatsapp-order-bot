import { NavLink, Outlet, useLocation, useNavigate } from "react-router-dom";
import { useEffect, useMemo, useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import {
  Activity,
  Bell,
  ChevronsUpDown,
  LayoutDashboard,
  LogOut,
  Menu,
  MessagesSquare,
  Moon,
  Package,
  PanelLeftClose,
  PanelLeft,
  Search,
  Settings,
  Sun,
  Users,
  X,
} from "lucide-react";
import {
  api,
  getTenantFilter,
  setTenantFilter,
  setToken,
  Tenant,
} from "../../api";
import { useSidebarCollapsed } from "../../hooks/use-sidebar";
import { useTheme } from "../../hooks/use-theme";
import { Avatar } from "../ui/avatar";
import { Button } from "../ui/button";
import { cn } from "../../lib/utils";
import { CommandPalette } from "./CommandPalette";
import * as Dropdown from "@radix-ui/react-dropdown-menu";

const NAV = [
  { to: "/", label: "Overview", icon: LayoutDashboard, end: true },
  { to: "/leads", label: "Leads", icon: Users },
  { to: "/orders", label: "Orders", icon: Package },
  { to: "/conversations", label: "Conversations", icon: MessagesSquare },
  { to: "/activity", label: "Activity", icon: Activity },
  { to: "/settings", label: "Settings", icon: Settings },
];

const CRUMBS: Record<string, string> = {
  "/": "Overview",
  "/leads": "Leads",
  "/orders": "Orders",
  "/conversations": "Conversations",
  "/activity": "Activity",
  "/settings": "Settings",
};

export default function Layout() {
  const { collapsed, toggle } = useSidebarCollapsed();
  const { theme, toggle: toggleTheme } = useTheme();
  const navigate = useNavigate();
  const location = useLocation();
  const [tenants, setTenants] = useState<Tenant[]>([]);
  const [tenantId, setTenantId] = useState(getTenantFilter());
  const [cmdOpen, setCmdOpen] = useState(false);
  const [mobileOpen, setMobileOpen] = useState(false);

  useEffect(() => {
    api<Tenant[]>("/api/dashboard/tenants", { tenant: false })
      .then(setTenants)
      .catch(() => setTenants([]));
  }, []);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        setCmdOpen(true);
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  useEffect(() => setMobileOpen(false), [location.pathname]);

  const activeTenant = useMemo(
    () => tenants.find((t) => t.phone_number_id === tenantId),
    [tenants, tenantId]
  );

  function selectTenant(id: string) {
    setTenantId(id);
    setTenantFilter(id);
    window.dispatchEvent(new Event("tenant-change"));
  }

  function logout() {
    setToken(null);
    navigate("/login");
  }

  const crumb = CRUMBS[location.pathname] || "BahiDesk";

  const sidebarInner = (
    <>
      <div className={cn("flex h-14 items-center gap-2 px-3", collapsed && "justify-center")}>
        <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-gradient-to-br from-bahi-400 to-bahi-700 text-sm font-bold text-white shadow-glow-sm">
          B
        </div>
        {!collapsed && (
          <div className="min-w-0">
            <p className="truncate text-sm font-bold tracking-tight">BahiDesk</p>
            <p className="truncate text-[10px] text-muted-foreground">Console</p>
          </div>
        )}
      </div>

      {/* Tenant switcher */}
      <div className="px-2 pb-3">
        <Dropdown.Root>
          <Dropdown.Trigger asChild>
            <button
              className={cn(
                "flex w-full items-center gap-2 rounded-xl border border-sidebar-border bg-sidebar-accent/40 px-2 py-2 text-left transition hover:bg-sidebar-accent focus-ring",
                collapsed && "justify-center px-0"
              )}
            >
              <Avatar
                name={activeTenant?.name || "All"}
                seed={activeTenant?.phone_number_id || "all"}
                size="sm"
              />
              {!collapsed && (
                <>
                  <span className="min-w-0 flex-1 truncate text-xs font-medium">
                    {activeTenant?.name || "All tenants"}
                  </span>
                  <ChevronsUpDown className="h-3.5 w-3.5 shrink-0 text-muted-foreground" />
                </>
              )}
            </button>
          </Dropdown.Trigger>
          <Dropdown.Portal>
            <Dropdown.Content
              side="right"
              align="start"
              sideOffset={8}
              className="z-50 min-w-[220px] overflow-hidden rounded-xl border border-border bg-popover p-1 shadow-elevated"
            >
              <Dropdown.Item
                className="cursor-pointer rounded-lg px-3 py-2 text-sm outline-none data-[highlighted]:bg-accent"
                onSelect={() => selectTenant("all")}
              >
                All tenants
              </Dropdown.Item>
              {tenants.map((t) => (
                <Dropdown.Item
                  key={t.id}
                  className="flex cursor-pointer items-center gap-2 rounded-lg px-3 py-2 text-sm outline-none data-[highlighted]:bg-accent"
                  onSelect={() => selectTenant(t.phone_number_id)}
                >
                  <Avatar name={t.name} seed={t.phone_number_id} size="sm" />
                  <span className="truncate">{t.name}</span>
                </Dropdown.Item>
              ))}
            </Dropdown.Content>
          </Dropdown.Portal>
        </Dropdown.Root>
      </div>

      <nav className="flex-1 space-y-0.5 px-2">
        {NAV.map((item) => (
          <NavLink
            key={item.to}
            to={item.to}
            end={item.end}
            title={item.label}
            className={({ isActive }) =>
              cn(
                "flex items-center gap-3 rounded-xl px-2.5 py-2 text-sm font-medium transition-colors",
                collapsed && "justify-center px-0",
                isActive
                  ? "bg-sidebar-accent text-primary"
                  : "text-sidebar-foreground/70 hover:bg-sidebar-accent/60 hover:text-sidebar-foreground"
              )
            }
          >
            <item.icon className="h-4.5 w-4.5 h-[18px] w-[18px] shrink-0" />
            {!collapsed && <span>{item.label}</span>}
          </NavLink>
        ))}
      </nav>

      <div className="space-y-1 border-t border-sidebar-border p-2">
        <Button
          variant="ghost"
          size={collapsed ? "icon" : "sm"}
          className={cn("w-full", !collapsed && "justify-start")}
          onClick={toggle}
          aria-label={collapsed ? "Expand sidebar" : "Collapse sidebar"}
        >
          {collapsed ? <PanelLeft className="h-4 w-4" /> : <PanelLeftClose className="h-4 w-4" />}
          {!collapsed && <span>Collapse</span>}
        </Button>
        <Button
          variant="ghost"
          size={collapsed ? "icon" : "sm"}
          className={cn("w-full text-muted-foreground", !collapsed && "justify-start")}
          onClick={logout}
        >
          <LogOut className="h-4 w-4" />
          {!collapsed && <span>Log out</span>}
        </Button>
      </div>
    </>
  );

  return (
    <div className="flex min-h-screen bg-background">
      {/* Desktop sidebar */}
      <aside
        className={cn(
          "fixed inset-y-0 left-0 z-40 hidden flex-col border-r border-sidebar-border glass transition-[width] duration-200 md:flex",
          collapsed ? "w-16" : "w-60"
        )}
      >
        {sidebarInner}
      </aside>

      {/* Mobile drawer */}
      <AnimatePresence>
        {mobileOpen && (
          <motion.div
            className="fixed inset-0 z-50 md:hidden"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
          >
            <div className="absolute inset-0 bg-black/60" onClick={() => setMobileOpen(false)} />
            <motion.aside
              initial={{ x: -280 }}
              animate={{ x: 0 }}
              exit={{ x: -280 }}
              transition={{ type: "spring", stiffness: 380, damping: 36 }}
              className="absolute inset-y-0 left-0 flex w-60 flex-col border-r border-sidebar-border bg-sidebar"
            >
              <div className="flex justify-end p-2">
                <Button variant="ghost" size="icon" onClick={() => setMobileOpen(false)}>
                  <X className="h-4 w-4" />
                </Button>
              </div>
              {sidebarInner}
            </motion.aside>
          </motion.div>
        )}
      </AnimatePresence>

      <div
        className={cn(
          "flex min-h-screen flex-1 flex-col transition-[padding] duration-200",
          collapsed ? "md:pl-16" : "md:pl-60"
        )}
      >
        {/* Topbar */}
        <header className="sticky top-0 z-30 flex h-14 items-center gap-3 border-b border-border bg-background/80 px-4 backdrop-blur-xl">
          <Button
            variant="ghost"
            size="icon"
            className="md:hidden"
            onClick={() => setMobileOpen(true)}
            aria-label="Open menu"
          >
            <Menu className="h-5 w-5" />
          </Button>

          <div className="min-w-0 flex-1">
            <p className="truncate text-xs text-muted-foreground">
              BahiDesk <span className="mx-1 opacity-40">/</span>
              <span className="text-foreground">{crumb}</span>
            </p>
          </div>

          <button
            onClick={() => setCmdOpen(true)}
            className="hidden items-center gap-2 rounded-lg border border-border bg-muted/40 px-3 py-1.5 text-xs text-muted-foreground transition hover:bg-muted sm:flex focus-ring"
          >
            <Search className="h-3.5 w-3.5" />
            Search…
            <kbd className="rounded border border-border bg-background px-1.5 py-0.5 text-[10px]">
              ⌘K
            </kbd>
          </button>

          <Button
            variant="ghost"
            size="icon"
            className="sm:hidden"
            onClick={() => setCmdOpen(true)}
            aria-label="Search"
          >
            <Search className="h-4 w-4" />
          </Button>

          <div className="flex items-center gap-1.5 rounded-full border border-border bg-muted/30 px-2.5 py-1">
            <span className="relative flex h-2 w-2">
              <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-primary opacity-40" />
              <span className="relative inline-flex h-2 w-2 rounded-full bg-primary" />
            </span>
            <span className="hidden text-[11px] font-medium text-muted-foreground sm:inline">
              Bot online
            </span>
          </div>

          <Button variant="ghost" size="icon" aria-label="Notifications">
            <Bell className="h-4 w-4" />
          </Button>

          <Button
            variant="ghost"
            size="icon"
            onClick={toggleTheme}
            aria-label="Toggle theme"
          >
            {theme === "dark" ? <Sun className="h-4 w-4" /> : <Moon className="h-4 w-4" />}
          </Button>
        </header>

        <main className="flex-1 px-4 py-6 pb-24 md:px-8 md:pb-8">
          <div className="mx-auto max-w-6xl">
            <AnimatePresence mode="wait">
              <motion.div
                key={location.pathname}
                initial={{ opacity: 0, y: 4 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -2 }}
                transition={{ duration: 0.18 }}
              >
                <Outlet />
              </motion.div>
            </AnimatePresence>
          </div>
        </main>

        {/* Mobile bottom nav */}
        <nav className="fixed inset-x-0 bottom-0 z-30 flex border-t border-border bg-background/90 backdrop-blur-xl md:hidden">
          {NAV.slice(0, 5).map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              end={item.end}
              className={({ isActive }) =>
                cn(
                  "flex flex-1 flex-col items-center gap-0.5 py-2 text-[10px] font-medium",
                  isActive ? "text-primary" : "text-muted-foreground"
                )
              }
            >
              <item.icon className="h-5 w-5" />
              {item.label.split(" ")[0]}
            </NavLink>
          ))}
        </nav>
      </div>

      <CommandPalette open={cmdOpen} onOpenChange={setCmdOpen} tenants={tenants} />
    </div>
  );
}
