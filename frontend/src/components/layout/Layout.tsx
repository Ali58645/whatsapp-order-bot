import { NavLink, Outlet, useLocation, useNavigate } from "react-router-dom";
import { useEffect, useMemo, useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import {
  Bell,
  Bot,
  Building2,
  CreditCard,
  Home,
  LogOut,
  Menu,
  Moon,
  Package,
  PanelLeftClose,
  PanelLeft,
  ScrollText,
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
  getViewAsTenantName,
  isOwner,
  isSupportSession,
  MeResponse,
  setTenantFilter,
  Tenant,
} from "../../api";
import { useI18n } from "../../i18n";
import { useSidebarCollapsed } from "../../hooks/use-sidebar";
import { useTheme } from "../../hooks/use-theme";
import { Button } from "../ui/button";
import { cn } from "../../lib/utils";
import { CommandPalette } from "./CommandPalette";

type NavItem = {
  to: string;
  labelKey:
    | "home"
    | "customers"
    | "myBot"
    | "menu"
    | "billing"
    | "businesses"
    | "team"
    | "accessLog"
    | "settings";
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

/** Platform console — no tenant inbox in primary nav. */
const ADMIN_NAV: NavItem[] = [
  { to: "/", labelKey: "businesses", icon: Building2, end: true },
  { to: "/team", labelKey: "team", icon: Users },
  { to: "/access-log", labelKey: "accessLog", icon: ScrollText },
  { to: "/billing", labelKey: "billing", icon: CreditCard },
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
  const supportMode = isSupportSession();
  const ownerShell = isOwner() || supportMode;
  const isAdmin = getRole() === "admin" && !supportMode;
  const impersonator = getImpersonatedBy();
  const viewAsName = getViewAsTenantName();

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
        if (me.tenant?.phone_number_id && (me.role === "owner" || me.impersonated_by)) {
          setTenantFilter(me.tenant.phone_number_id);
          setTenantId(me.tenant.phone_number_id);
          setFlowMode(me.tenant.flow_mode || "lead");
          window.dispatchEvent(new Event("tenant-change"));
        }
      } catch {
        /* ignore bootstrap errors */
      }
      try {
        const list = await api<{ items?: Tenant[] } | Tenant[]>("/api/dashboard/tenants", {
          tenant: false,
        });
        if (!cancelled) {
          const items = Array.isArray(list) ? list : list.items || [];
          setTenants(items);
        }
      } catch {
        /* ignore */
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  const activeTenant = useMemo(
    () => tenants.find((t) => t.phone_number_id === tenantId) || null,
    [tenants, tenantId]
  );

  function logout() {
    clearSession();
    localStorage.removeItem("dash_admin_token_backup");
    navigate("/login");
  }

  function onExitViewAs() {
    if (exitViewAs()) {
      navigate("/", { replace: true });
      window.location.reload();
    }
  }

  const crumb = t(
    (nav.find((n) =>
      n.end ? location.pathname === n.to : location.pathname.startsWith(n.to) && n.to !== "/"
    )?.labelKey as Parameters<typeof t>[0]) || (ownerShell ? "home" : "businesses")
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
              {ownerShell ? activeTenant?.name || viewAsName || "Your business" : "Platform"}
            </p>
          </div>
        )}
      </div>

      {ownerShell && !collapsed && (
        <div className="px-3 pb-3">
          <div className="rounded-xl border border-sidebar-border bg-sidebar-accent/30 px-3 py-2">
            <p className="truncate text-xs font-medium">
              {activeTenant?.name || viewAsName || "…"}
            </p>
            <p className="text-[10px] text-muted-foreground">
              {supportMode ? "Support mode" : "Your business"}
            </p>
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
                  ? "bg-sidebar-accent text-foreground"
                  : "text-muted-foreground hover:bg-sidebar-accent/60 hover:text-foreground"
              )
            }
          >
            <item.icon className="h-4 w-4 shrink-0" />
            {!collapsed && <span className="truncate">{t(item.labelKey)}</span>}
          </NavLink>
        ))}
      </nav>

      <div className={cn("space-y-1 border-t border-sidebar-border p-2", collapsed && "px-1")}>
        <button
          type="button"
          onClick={() => setLang(lang === "en" ? "ur" : "en")}
          className={cn(
            "flex w-full items-center gap-3 rounded-xl px-2.5 py-2 text-sm text-muted-foreground hover:bg-sidebar-accent/60",
            collapsed && "justify-center px-0"
          )}
        >
          <span className="text-xs font-semibold uppercase">{lang === "en" ? "EN" : "UR"}</span>
          {!collapsed && <span>{t("language")}</span>}
        </button>
        <button
          type="button"
          onClick={logout}
          className={cn(
            "flex w-full items-center gap-3 rounded-xl px-2.5 py-2 text-sm text-muted-foreground hover:bg-sidebar-accent/60",
            collapsed && "justify-center px-0"
          )}
        >
          <LogOut className="h-4 w-4" />
          {!collapsed && <span>{t("logout")}</span>}
        </button>
      </div>
    </>
  );

  return (
    <div className="min-h-screen bg-background text-foreground">
      <aside
        className={cn(
          "fixed inset-y-0 left-0 z-40 hidden flex-col border-r border-sidebar-border bg-sidebar transition-[width] duration-200 md:flex",
          collapsed ? "w-16" : "w-60"
        )}
      >
        <Button
          variant="ghost"
          size="icon"
          className="absolute -right-3 top-16 z-50 hidden h-6 w-6 rounded-full border border-border bg-background shadow md:flex"
          onClick={toggle}
          aria-label="Toggle sidebar"
        >
          {collapsed ? (
            <PanelLeft className="h-3.5 w-3.5" />
          ) : (
            <PanelLeftClose className="h-3.5 w-3.5" />
          )}
        </Button>
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
            <button
              type="button"
              className="absolute inset-0 bg-black/50"
              aria-label="Close menu"
              onClick={() => setMobileOpen(false)}
            />
            <motion.aside
              className="absolute inset-y-0 left-0 flex w-72 flex-col border-r border-sidebar-border bg-sidebar"
              initial={{ x: -280 }}
              animate={{ x: 0 }}
              exit={{ x: -280 }}
            >
              <div className="flex justify-end p-2">
                <Button variant="ghost" size="icon" onClick={() => setMobileOpen(false)}>
                  <X className="h-5 w-5" />
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
        {supportMode && (
          <div className="flex items-center justify-between gap-3 bg-amber-500/15 px-4 py-2 text-sm text-amber-200">
            <span>
              Viewing as {viewAsName || activeTenant?.name || "tenant"} — support mode
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
