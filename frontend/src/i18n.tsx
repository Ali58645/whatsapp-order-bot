import { createContext, useContext, useEffect, useMemo, useState, ReactNode } from "react";
import { getUiLang, setUiLang as persistUiLang } from "./api";

type Lang = "en" | "ur";

const DICT = {
  en: {
    home: "Home",
    customers: "Customers",
    myBot: "My Bot",
    channels: "Channels",
    menu: "Order Menu",
    billing: "Billing",
    account: "Account",
    broadcast: "Broadcast",
    activity: "Activity",
    overview: "Overview",
    leads: "Leads",
    orders: "Orders",
    conversations: "Conversations",
    settings: "Settings",
    businesses: "Businesses",
    team: "Team",
    accessLog: "Access Log",
    logout: "Log out",
    refresh: "Refresh",
    save: "Save",
    publish: "Publish",
    welcomeHome: "Your WhatsApp console",
    homeSubtitle: "Today’s customers and bot status",
    newCustomers: "New customers today",
    thisWeek: "This week",
    demos: "Demos booked",
    ordersToday: "Orders today",
    revenueToday: "Revenue today",
    botLive: "Bot is live",
    botPaused: "Bot paused",
    recentActivity: "Recent activity",
    completeBot: "Complete your bot setup",
    completeGreeting: "Add your greeting",
    completeMenu: "Add Order Menu items",
    wiringNote: "Managed by AccellionX",
    language: "Language",
    english: "English",
    romanUrdu: "Roman Urdu",
    viewAsOwner: "View as owner",
    exitViewAs: "Exit support",
    readonlyBanner: "Read-only support view",
    plan: "Plan",
    usage: "This month’s usage",
    messagesSent: "Messages sent",
    templatesSent: "Template messages",
    placeholderBilling: "Usage metering coming soon",
    createOwner: "Create owner account",
    username: "Username",
    password: "Password",
    assignTenant: "Assign business",
    create: "Create",
  },
  ur: {
    home: "Home",
    customers: "Customers",
    myBot: "Mera Bot",
    channels: "Channels",
    menu: "Order Menu",
    billing: "Billing",
    account: "Account",
    broadcast: "Broadcast",
    activity: "Activity",
    overview: "Overview",
    leads: "Leads",
    orders: "Orders",
    conversations: "Baatein",
    settings: "Settings",
    businesses: "Businesses",
    team: "Team",
    accessLog: "Access Log",
    logout: "Log out",
    refresh: "Refresh",
    save: "Save karein",
    publish: "Publish",
    welcomeHome: "Aapka WhatsApp console",
    homeSubtitle: "Aaj ke customers aur bot status",
    newCustomers: "Aap ke naye customers",
    thisWeek: "Is hafte",
    demos: "Demo book hue",
    ordersToday: "Aaj ke orders",
    revenueToday: "Aaj ki sales",
    botLive: "Bot live hai",
    botPaused: "Bot band hai",
    recentActivity: "Hal ki activity",
    completeBot: "Apna bot complete karein",
    completeGreeting: "Greeting add karein",
    completeMenu: "Menu items add karein",
    wiringNote: "AccellionX manage karta hai",
    language: "Zubaan",
    english: "English",
    romanUrdu: "Roman Urdu",
    viewAsOwner: "Owner ke tor pe dekhein",
    exitViewAs: "Support band karein",
    readonlyBanner: "Sirf dekhne ke liye (support)",
    plan: "Plan",
    usage: "Is mahine ka usage",
    messagesSent: "Messages bheje",
    templatesSent: "Template messages",
    placeholderBilling: "Usage counting jald aayegi",
    createOwner: "Owner account banayein",
    username: "Username",
    password: "Password",
    assignTenant: "Business assign karein",
    create: "Banaein",
  },
} as const;

export type UiKey = keyof typeof DICT.en;

type Ctx = {
  lang: Lang;
  setLang: (l: Lang) => void;
  t: (key: UiKey) => string;
};

const I18nContext = createContext<Ctx | null>(null);

export function I18nProvider({ children }: { children: ReactNode }) {
  const [lang, setLangState] = useState<Lang>(getUiLang());

  useEffect(() => {
    const on = () => setLangState(getUiLang());
    window.addEventListener("ui-lang-change", on);
    return () => window.removeEventListener("ui-lang-change", on);
  }, []);

  const value = useMemo<Ctx>(
    () => ({
      lang,
      setLang: (l) => {
        persistUiLang(l);
        setLangState(l);
      },
      t: (key) => DICT[lang][key] || DICT.en[key] || key,
    }),
    [lang]
  );

  return <I18nContext.Provider value={value}>{children}</I18nContext.Provider>;
}

export function useI18n() {
  const ctx = useContext(I18nContext);
  if (!ctx) throw new Error("useI18n outside provider");
  return ctx;
}
