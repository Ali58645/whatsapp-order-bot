import { createContext, useContext, useEffect, useMemo, useState, ReactNode } from "react";
import { getUiLang, setUiLang as persistUiLang } from "./api";

type Lang = "en" | "ur";

const DICT = {
  en: {
    home: "Home",
    customers: "Customers",
    myBot: "My Bot",
    botGreeting: "Greeting",
    botQuestions: "Questions",
    botFaq: "Knowledge Base",
    botMore: "More replies",
    channels: "Channels",
    channelWhatsapp: "WhatsApp",
    channelInstagram: "Instagram",
    channelFacebook: "Facebook",
    menu: "Order Menu",
    billing: "Billing",
    account: "Account",
    broadcast: "Broadcast",
    activity: "Activity",
    overview: "Overview",
    leads: "Leads",
    orders: "Orders",
    conversations: "Conversations",
    inbox: "Inbox",
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
    // Setup wizard
    setupTitle: "Set up your WhatsApp bot",
    setupSubtitle:
      "Answer a few questions about your business — we fill your knowledge base, greeting, questions, and replies.",
    setupStepBusiness: "Business",
    setupStepCategory: "Category",
    setupStepHours: "Hours",
    setupStepAbout: "About",
    setupStepReview: "Review",
    setupBusinessName: "Business name",
    setupBotJob: "What should the bot do?",
    setupBotJobHint:
      "You can change this later — picking a category on the next step will match lead vs order automatically.",
    setupLeadMode: "Capture leads / bookings",
    setupLeadModeBlurb: "Ask questions, book demos or appointments",
    setupOrderMode: "Take orders",
    setupOrderModeBlurb: "Share a menu and collect orders",
    setupGreetingLang: "Bot language",
    setupGreetingLangHint:
      "Every greeting, question, label, and reply will use this language only.",
    setupCategory: "Business category",
    setupHours: "Business hours",
    setupHoursHint: "Used when the bot is closed and stored in your company knowledge.",
    setupOverview: "What does your business do?",
    setupOffer: "What do you offer?",
    setupOfferOrder: "What do you sell?",
    setupLocation: "Location / service area",
    setupContact: "Contact / WhatsApp number",
    setupGreetingSection: "1. Greeting",
    setupGreetingHint: "First message customers see on WhatsApp.",
    setupEditGreeting: "Edit greeting",
    setupQuestionsSection: "2. Questions preview",
    setupQuestionsHint: "Questions your bot asks — edit to match your business.",
    setupMoreSection: "3. More replies",
    setupMoreHint: "Confirmation and handoff messages after they answer.",
    setupOptions: "Options (buttons on WhatsApp)",
    setupOptionsHint: "Add each choice separated by commas.",
    setupContinue: "Continue",
    setupBack: "Back",
    setupSkip: "Skip for now",
    setupApply: "Apply & go live",
    setupQName: "Name",
    setupQType: "Type / service",
    setupQLocation: "Location",
    setupQFollowup: "Follow-up",
    setupQScheduling: "Scheduling",
    setupMConfirm: "Slot booked",
    setupMHandoff: "Handoff",
    setupMAck: "Name recorded",
  },
  ur: {
    home: "Home",
    customers: "Customers",
    myBot: "Mera Bot",
    botGreeting: "Greeting",
    botQuestions: "Sawalat",
    botFaq: "Knowledge Base",
    botMore: "Zyada replies",
    channels: "Channels",
    channelWhatsapp: "WhatsApp",
    channelInstagram: "Instagram",
    channelFacebook: "Facebook",
    menu: "Order Menu",
    billing: "Billing",
    account: "Account",
    broadcast: "Broadcast",
    activity: "Activity",
    overview: "Overview",
    leads: "Leads",
    orders: "Orders",
    conversations: "Baatein",
    inbox: "Inbox",
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
    newCustomers: "Aaj ke naye customers",
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
    // Setup wizard
    setupTitle: "Apna WhatsApp bot set karein",
    setupSubtitle:
      "Apne business ke kuch sawalat ke jawab dein — hum knowledge base, greeting, sawalat aur replies bhar denge.",
    setupStepBusiness: "Business",
    setupStepCategory: "Category",
    setupStepHours: "Hours",
    setupStepAbout: "About",
    setupStepReview: "Review",
    setupBusinessName: "Business ka naam",
    setupBotJob: "Bot kya kare?",
    setupBotJobHint:
      "Baad mein change kar sakte hain — agli step ki category lead ya order set kar degi.",
    setupLeadMode: "Leads / bookings lo",
    setupLeadModeBlurb: "Sawalat poochho, demo ya appointment book karo",
    setupOrderMode: "Orders lo",
    setupOrderModeBlurb: "Menu share karo aur order collect karo",
    setupGreetingLang: "Bot ki zubaan",
    setupGreetingLangHint:
      "Har greeting, sawal, label aur reply isi zubaan mein hoga — mix nahi hoga.",
    setupCategory: "Business category",
    setupHours: "Business hours",
    setupHoursHint: "Band hone par use hota hai aur knowledge base mein save hota hai.",
    setupOverview: "Aapka business kya karta hai?",
    setupOffer: "Aap kya offer karte hain?",
    setupOfferOrder: "Aap kya bechte hain?",
    setupLocation: "Location / service area",
    setupContact: "Contact / WhatsApp number",
    setupGreetingSection: "1. Greeting",
    setupGreetingHint: "Customer ko WhatsApp par pehla message.",
    setupEditGreeting: "Greeting edit karein",
    setupQuestionsSection: "2. Questions preview",
    setupQuestionsHint: "Bot ke sawalat — apne business ke mutabiq edit karein.",
    setupMoreSection: "3. More replies",
    setupMoreHint: "Confirm aur handoff messages jab woh jawab dein.",
    setupOptions: "Options (WhatsApp buttons)",
    setupOptionsHint: "Har choice comma se alag likhein.",
    setupContinue: "Agey",
    setupBack: "Wapas",
    setupSkip: "Abhi skip karein",
    setupApply: "Apply karke live karein",
    setupQName: "Naam",
    setupQType: "Type / service",
    setupQLocation: "Location",
    setupQFollowup: "Follow-up",
    setupQScheduling: "Scheduling",
    setupMConfirm: "Slot booked",
    setupMHandoff: "Handoff",
    setupMAck: "Naam record",
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
