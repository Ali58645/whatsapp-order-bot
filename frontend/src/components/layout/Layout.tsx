import { NavLink, Outlet, useLocation, useNavigate } from "react-router-dom";
import { useEffect, useMemo, useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import {
  Activity,
  Bell,
  Bot,
  Building2,
  ChevronsUpDown,
  CreditCard,
  Home,
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
  clearSession,
  exitViewAs,
  getImpersonatedBy,
  getRole,
  getTenantFilter,
  isOwner,
  isReadonlySession,
  MeResponse,
  setTenantFilter,
  Tenant,
} from "../../api";
import { useI18n } from "../../i18n";
import { useSidebarCollapsed } from "../../hooks/use-sidebar";
import { useTheme } from "../../hooks/use-theme";
import { Avatar } from "../ui/avatar";
import { Button } from "../ui/button";
import { cn } from "../../lib/utils";
import { CommandPalette } from "./CommandPalette";
import * as Dropdown from "@radix-ui/react-dropdown-menu";

type NavItem = {
  to: string;
  labelKey: "home" | "customers" | "myBot" | "menu" | "billing" | "overview" | "leads" | "orders" | "conversations" | "activity" | "settings" | "businesses" | "team";
  icon: typeof Home;
  end?: boolean;
  orderOnly?: boolean;
  leadOnly?: boolean;
};

const OWNER_NAV: NavItem[] = [
  { to: "/", labelKey: "home", icon: Home, end: true },
  { to: "/customers", labelKey: "customers", icon: Users },
  { to: "/my-bot", labelKey: "myBot", icon: Bot },
  { to: "/menu", labelKey: "menu", icon: Package, orderOnly: true },
  { to: "/billing", labelKey: "billing", icon: CreditCard },
];

const ADMIN_NAV: NavItem[] = [
  { to: "/", labelKey: "overview", icon: LayoutDashboard, end: true },
  { to: "/leads", labelKey: "leads", icon: Users },
  { to: "/orders", labelKey: "orders", icon: Package },
  { to: "/conversations", labelKey: "conversations", icon: MessagesSquare },
  { to: "/activity", labelKey: "activity", icon: Activity },
  { to: "/businesses", labelKey: "businesses", icon: Building2 },
  { to: "/team", labelKey: "team", icon: Users },
  { to: "/settings", labelKey: "settings", icon: Settings },
];

export default function Layout() {
  const { collapsed, toggle } = useSidebarCollapsed();
  const { theme, toggle: toggleTheme } = useTheme();
  const { t, lang, setLang } = useI18n();
  const navigate = useNavigate();
  const location = useLocation();
  const [tenants, setTenants] = useState<Tenant[]>([]);
  const [tenantId, setTenantId] = useState(getTenantFilter());
  const [flowMode, setFlowMode] = useState<string>("lead");
  const [cmdOpen, setCmdOpen] = useState(false);
  const [mobileOpen, setMobileOpen] = useState(false);
  const ownerShell = isOwner() || isReadonlySession();
  const isAdmin = getRole() === "admin" && !isReadonlySession();
  const readonly = isReadonlySession();
  const impersonator = getImpersonatedBy();

  const nav = useMemo(() => {
    const base = ownerShell ? OWNER_NAV : ADMIN_NAV;
    return base.filter((item) => {
      if (item.orderOnly && flowMode !== "order") return false;
      if (item.leadOnly && flowMode === "order") return false;
      return true;
    });
  }, [ownerShell, flowMode]);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const me = await api<MeResponse>("/api/dashboard/me", { tenant: false });
        if (cancelled) return;
        if (me.tenant?.phone_number_id && (me.role === "owner" || me.readonly)) {
          setTenantFilter(me.tenant.phone_number_id);
          setTenantId(me.tenant.phone_number_id);
          setFlowMode(me.tenant.flow_mode || "lead");
          window.dispatchEvent(new Event("tenant-change"));
        }
      } catch {
        /* ignore bootstrap errors */
      }
      try {
        const list = await api<Tenant[]>("/api/dashboard/tenants", { tenant: false });
        if (!cancelled) setTenants(list);
        if (!cancelled && list[0] && !ownerShell && getTenantFilter() === "all") {
          // admin may keep "all"
        } else if (!cancelled && list[0]?.flow_mode && ownerShell) {
          setFlowMode(list[0].flow_mode);
        }
      } catch {
        if (!cancelled) setTenants([]);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [ownerShell]);

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
    if (ownerShell) return;
    setTenantId(id);
    setTenantFilter(id);
    window.dispatchEvent(new Event("tenant-change"));
  }

  function logout() {
    clearSession();
    localStorage.removeItem("dash_admin_token_backup");
    navigate("/login");
  }

  function onExitViewAs() {
    if (exitViewAs()) {
      navigate("/team", { replace: true });
      window.location.reload();
    }
  }

  const crumb = t(
    (nav.find((n) =>
      n.end ? location.pathname === n.to : location.pathname.startsWith(n.to) && n.to !== "/"
    )?.labelKey as Parameters<typeof t>[0]) || (ownerShell ? "home" : "overview")
  );

  const sidebarInner = (
    <>
      <div className={cn("flex h-14 items-center gap-2 px-3", collapsed && "justify-center")}>
        <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-gradient-to-br from-bahi-400 to-bahi-700 text-sm font-bold text-white shadow-glow-sm">
          B
        </div>
        {!collapsed && (
          <div className="min-w-0">
            <p className="truncate text-sm font-bold tracking-tight">BahiDesk</p>
            <p className="truncate text-[10px] text-muted-foreground">
              {ownerShell ? activeTenant?.name || "Your business" : "Console"}
            </p>
          </div>
        )}
      </div>

      {/* Tenant switcher — admin only */}
      {isAdmin && (
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
                {tenants.map((tn) => (
                  <Dropdown.Item
                    key={tn.id}
                    className="flex cursor-pointer items-center gap-2 rounded-lg px-3 py-2 text-sm outline-none data-[highlighted]:bg-accent"
                    onSelect={() => selectTenant(tn.phone_number_id)}
                  >
                    <Avatar name={tn.name} seed={tn.phone_number_id} size="sm" />
                    <span className="truncate">{tn.name}</span>
                  </Dropdown.Item>
                ))}
              </Dropdown.Content>
            </Dropdown.Portal>
          </Dropdown.Root>
        </div>
      )}

      {/* Owner: fixed tenant chip (no switcher) */}
      {ownerShell && !collapsed && (
        <div className="px-3 pb-3">
          <div className="rounded-xl border border-sidebar-border bg-sidebar-accent/30 px-3 py-2">
            <p className="truncate text-xs font-medium">{activeTenant?.name || "…"}</p>
            <p className="text-[10px] text-muted-foreground">Your business</p>
          </div>
        </div>
      )}

      <nav className="flex-1 space-y-0.5 px-2">
        {nav.map((item) => (
          <NavLink
            key={item.to}
            to={item.to}
            end={item.end}
            title={t(item.labelKey)}
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
            {!collapsed && <span>{t(item.labelKey)}</span>}
          </NavLink>
        ))}
      </nav>

      <div className="space-y-1 border-t border-sidebar-border p-2">
        {!collapsed && (
          <div className="mb-1 flex gap-1 rounded-lg border border-sidebar-border p-0.5">
            <button
              type="button"
              className={cn(
                "flex-1 rounded-md px-2 py-1 text-[10px] font-semibold",
                lang === "en" ? "bg-sidebar-accent text-primary" : "text-muted-foreground"
              )}
              onClick={() => setLang("en")}
            >
              EN
            </button>
            <button
              type="button"
              className={cn(
                "flex-1 rounded-md px-2 py-1 text-[10px] font-semibold",
                lang === "ur" ? "bg-sidebar-accent text-primary" : "text-muted-foreground"
              )}
              onClick={() => setLang("ur")}
            >
              UR
            </button>
          </div>
        )}
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
          {!collapsed && <span>{t("logout")}</span>}
        </Button>
      </div>
    </>
  );

  return (
    <div className="flex min-h-screen bg-background">
      <aside
        className={cn(
          "fixed inset-y-0 left-0 z-40 hidden flex-col border-r border-sidebar-border glass transition-[width] duration-200 md:flex",
          collapsed ? "w-16" : "w-60"
        )}
      >
        {sidebarInner}
      </aside>

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
        {readonly && (
          <div className="flex items-center justify-between gap-3 bg-amber-500/15 px-4 py-2 text-sm text-amber-200">
            <span>
              {t("readonlyBanner")}
              {impersonator ? ` · ${impersonator}` : ""}
            </span>
            <Button size="sm" variant="outline" onClick={onExitViewAs}>
              {t("exitViewAs")}
            </Button>
          </div>
        )}

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

        <nav className="fixed inset-x-0 bottom-0 z-30 flex border-t border-border bg-background/90 backdrop-blur-xl md:hidden">
          {nav.slice(0, 5).map((item) => (
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
              {t(item.labelKey).split(" ")[0]}
            </NavLink>
          ))}
        </nav>
      </div>

      <CommandPalette open={cmdOpen} onOpenChange={setCmdOpen} tenants={tenants} isAdmin={isAdmin} />
    </div>
  );
}
