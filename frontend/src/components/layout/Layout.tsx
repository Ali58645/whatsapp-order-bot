import { NavLink, Outlet, useLocation, useNavigate } from "react-router-dom";
import { useEffect, useMemo, useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import {
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
  Radio,
  ScrollText,
  Search,
  Settings,
  MessageCircle,
  Sun,
  Users,
  X,
} from "lucide-react";
import {
  api,
  clearSession,
  exitViewAs,
  fetchMe,
  getImpersonatedBy,
  getRole,
  getTenantFilter,
  getViewAsTenantName,
  isOwner,
  isSupportSession,
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
    | "channels"
    | "conversations"
    | "account"
    | "broadcast"
    | "settings";
  icon: typeof Home;
  end?: boolean;
  orderOnly?: boolean;
  leadOnly?: boolean;
};

const OWNER_NAV: NavItem[] = [
  { to: "/", labelKey: "home", icon: Home, end: true },
  { to: "/conversations", labelKey: "conversations", icon: MessageCircle },
  { to: "/customers", labelKey: "customers", icon: Users },
  { to: "/my-bot", labelKey: "myBot", icon: Bot },
  { to: "/channels", labelKey: "channels", icon: Radio },
  { to: "/menu", labelKey: "menu", icon: Package, orderOnly: true },
  { to: "/broadcast", labelKey: "broadcast", icon: MessageCircle },
  { to: "/team", labelKey: "team", icon: Users },
  { to: "/account", labelKey: "account", icon: Settings },
  { to: "/billing", labelKey: "billing", icon: CreditCard },
];

/** Platform console — no tenant inbox in primary nav. */
const ADMIN_NAV: NavItem[] = [
  { to: "/", labelKey: "businesses", icon: Building2, end: true },
  { to: "/team", labelKey: "team", icon: Users },
  { to: "/access-log", labelKey: "accessLog", icon: ScrollText },
  { to: "/channels", labelKey: "channels", icon: Radio },
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
      const [meRes, listRes] = await Promise.allSettled([
        fetchMe(),
        api<{ items?: Tenant[] } | Tenant[]>("/api/dashboard/tenants", { tenant: false }),
      ]);
      if (cancelled) return;
      if (meRes.status === "fulfilled") {
        const me = meRes.value;
        if (me.tenant?.phone_number_id && (me.role === "owner" || me.impersonated_by)) {
          setTenantFilter(me.tenant.phone_number_id);
          setTenantId(me.tenant.phone_number_id);
          setFlowMode(me.tenant.flow_mode || "lead");
          window.dispatchEvent(new Event("tenant-change"));
        }
      }
      if (listRes.status === "fulfilled") {
        const list = listRes.value;
        setTenants(Array.isArray(list) ? list : list.items || []);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        setCmdOpen(true);
      }
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
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
      <div className={cn("flex h-16 items-center gap-3 px-3.5", collapsed && "justify-center px-2")}>
        <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-gradient-to-br from-bahi-400 via-bahi-500 to-bahi-700 text-sm font-extrabold text-white">
          B
        </div>
        {!collapsed && (
          <div className="min-w-0">
            <p className="truncate text-[15px] font-bold tracking-tight">BahiDesk</p>
            <p className="truncate text-[10px] font-medium uppercase tracking-[0.12em] text-muted-foreground">
              {ownerShell ? activeTenant?.name || viewAsName || "Your business" : "Platform"}
            </p>
          </div>
        )}
      </div>

      {ownerShell && !collapsed && (
        <div className="px-3 pb-3">
          <div className="rounded-xl border border-sidebar-border/80 bg-sidebar-accent/40 px-3 py-2.5">
            <p className="truncate text-xs font-semibold">
              {activeTenant?.name || viewAsName || "…"}
            </p>
            <p className="mt-0.5 text-[10px] uppercase tracking-wider text-muted-foreground">
              {supportMode ? "Support mode" : "Your business"}
            </p>
          </div>
        </div>
      )}

      <nav className="flex-1 space-y-0.5 px-2.5">
        {nav.map((item) => (
          <NavLink
            key={item.to}
            to={item.to}
            end={item.end}
            title={t(item.labelKey)}
            className={({ isActive }) =>
              cn(
                "flex items-center gap-3 rounded-xl px-2.5 py-2.5 text-[13px] font-medium transition-all duration-150",
                collapsed && "justify-center px-0",
                isActive
                  ? "nav-item-active"
                  : "text-muted-foreground hover:bg-sidebar-accent/50 hover:text-foreground"
              )
            }
          >
            <item.icon className="h-4 w-4 shrink-0 opacity-90" />
            {!collapsed && <span className="truncate">{t(item.labelKey)}</span>}
          </NavLink>
        ))}
      </nav>

      <div className={cn("space-y-0.5 border-t border-sidebar-border/80 p-2.5", collapsed && "px-1")}>
        <button
          type="button"
          onClick={() => setLang(lang === "en" ? "ur" : "en")}
          className={cn(
            "flex w-full items-center gap-3 rounded-xl px-2.5 py-2 text-[13px] text-muted-foreground transition hover:bg-sidebar-accent/50 hover:text-foreground",
            collapsed && "justify-center px-0"
          )}
        >
          <span className="text-[10px] font-bold uppercase tracking-wider">{lang === "en" ? "EN" : "UR"}</span>
          {!collapsed && <span>{t("language")}</span>}
        </button>
        <button
          type="button"
          onClick={logout}
          className={cn(
            "flex w-full items-center gap-3 rounded-xl px-2.5 py-2 text-[13px] text-muted-foreground transition hover:bg-sidebar-accent/50 hover:text-foreground",
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
    <div className="app-canvas min-h-screen text-foreground">
      <aside
        className={cn(
          "fixed inset-y-0 left-0 z-40 hidden flex-col border-r border-sidebar-border/80 bg-sidebar/90 backdrop-blur-xl transition-[width] duration-200 md:flex",
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
          <div className="flex items-center justify-between gap-3 border-b border-amber-500/20 bg-amber-500/10 px-4 py-2.5 text-sm text-amber-100">
            <span>
              Viewing as{" "}
              <span className="font-semibold text-amber-50">
                {viewAsName || activeTenant?.name || "tenant"}
              </span>{" "}
              — support mode
              {impersonator ? ` · ${impersonator}` : ""}
            </span>
            <Button size="sm" variant="outline" onClick={onExitViewAs}>
              {t("exitViewAs")}
            </Button>
          </div>
        )}

        <header className="sticky top-0 z-30 flex h-14 items-center gap-3 border-b border-border/60 bg-background/70 px-4 backdrop-blur-xl">
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
            <p className="truncate text-[11px] font-medium tracking-wide text-muted-foreground">
              BahiDesk
              <span className="mx-1.5 text-border">/</span>
              <span className="text-foreground">{crumb}</span>
            </p>
          </div>

          <button
            onClick={() => setCmdOpen(true)}
            className="hidden items-center gap-2 rounded-xl border border-border/70 bg-card/50 px-3 py-1.5 text-xs text-muted-foreground transition hover:border-primary/30 hover:bg-card hover:text-foreground sm:flex focus-ring"
          >
            <Search className="h-3.5 w-3.5" />
            Search…
            <kbd className="rounded-md border border-border/80 bg-background/80 px-1.5 py-0.5 text-[10px]">
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

          <Button
            variant="ghost"
            size="icon"
            onClick={toggleTheme}
            aria-label="Toggle theme"
          >
            {theme === "dark" ? <Sun className="h-4 w-4" /> : <Moon className="h-4 w-4" />}
          </Button>
        </header>

        <main className="flex-1 px-4 py-7 pb-24 md:px-8 md:pb-10">
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
