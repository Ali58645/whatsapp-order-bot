import { ReactNode, useEffect, useState } from "react";
import { ChevronLeft, Battery, MoreVertical, Phone, Signal, Video, Wifi } from "lucide-react";
import { ChannelBadge } from "../ChannelBadge";
import { cn } from "../../lib/utils";

type Props = {
  contactName: string;
  subtitle?: string;
  channel?: string;
  botName?: string;
  children: ReactNode;
  footer?: ReactNode;
  onBack?: () => void;
  className?: string;
  takeoverActive?: boolean;
};

function StatusBar() {
  const [time, setTime] = useState("");
  useEffect(() => {
    const tick = () => {
      const d = new Date();
      setTime(
        d.toLocaleTimeString(undefined, { hour: "numeric", minute: "2-digit", hour12: false })
      );
    };
    tick();
    const id = window.setInterval(tick, 30_000);
    return () => window.clearInterval(id);
  }, []);

  return (
    <div className="flex items-center justify-between px-6 pt-2.5 text-[11px] font-semibold text-white">
      <span className="tabular">{time || "9:41"}</span>
      <div className="flex items-center gap-1.5 text-white/90">
        <Signal className="h-3 w-3" strokeWidth={2.5} />
        <Wifi className="h-3 w-3" strokeWidth={2.5} />
        <Battery className="h-3.5 w-4" strokeWidth={2.5} />
      </div>
    </div>
  );
}

export function PhoneChatFrame({
  contactName,
  subtitle,
  channel,
  botName = "Your bot",
  children,
  footer,
  onBack,
  className,
  takeoverActive = false,
}: Props) {
  return (
    <div
      className={cn("relative mx-auto w-full max-w-[390px]", className)}
      aria-label="iPhone chat preview"
    >
      {/* Titanium frame */}
      <div
        className="relative rounded-[3rem] p-[3px] shadow-[0_40px_80px_-20px_rgba(0,0,0,0.85)]"
        style={{
          background:
            "linear-gradient(145deg, #4a4a4f 0%, #1c1c1e 35%, #3a3a3c 65%, #0a0a0b 100%)",
        }}
      >
        {/* Side buttons */}
        <div className="pointer-events-none absolute -left-[2px] top-[88px] h-7 w-[3px] rounded-l bg-zinc-600" />
        <div className="pointer-events-none absolute -left-[2px] top-[130px] h-12 w-[3px] rounded-l bg-zinc-600" />
        <div className="pointer-events-none absolute -left-[2px] top-[188px] h-12 w-[3px] rounded-l bg-zinc-600" />
        <div className="pointer-events-none absolute -right-[2px] top-[148px] h-16 w-[3px] rounded-r bg-zinc-600" />

        <div className="overflow-hidden rounded-[2.85rem] bg-black">
          {/* Dynamic Island */}
          <div className="relative z-20 flex justify-center pt-2">
            <div className="h-[26px] w-[108px] rounded-full bg-black shadow-[inset_0_0_0_1px_rgba(255,255,255,0.06)]" />
          </div>

          <StatusBar />

          {/* Screen */}
          <div className="flex flex-col bg-[#0b141a]" style={{ minHeight: "640px" }}>
            {/* WhatsApp nav bar */}
            <header className="flex items-center gap-1 border-b border-white/5 bg-[#1f2c34]/95 px-1 py-2 backdrop-blur-md">
              {onBack ? (
                <button
                  type="button"
                  onClick={onBack}
                  className="flex items-center rounded-lg p-1.5 text-[#00a884] hover:bg-white/5 lg:hidden"
                  aria-label="Back"
                >
                  <ChevronLeft className="h-6 w-6" />
                </button>
              ) : (
                <span className="hidden w-8 lg:block" />
              )}
              <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-gradient-to-br from-emerald-500 to-teal-700 text-sm font-bold text-white shadow-inner">
                {contactName.charAt(0).toUpperCase()}
              </div>
              <div className="min-w-0 flex-1 px-1">
                <div className="flex items-center gap-1.5">
                  <p className="truncate text-[16px] font-medium leading-tight text-white">
                    {contactName}
                  </p>
                  <ChannelBadge channel={channel} />
                </div>
                <p className="truncate text-[12px] text-emerald-400/90">
                  {takeoverActive ? "Human takeover · online" : subtitle || botName}
                </p>
              </div>
              <div className="flex shrink-0 items-center gap-3 pr-2 text-[#aebac1]">
                <Video className="h-[18px] w-[18px]" />
                <Phone className="h-[16px] w-[16px]" />
                <MoreVertical className="h-[18px] w-[18px]" />
              </div>
            </header>

            <div className="min-h-0 flex-1 overflow-y-auto overscroll-contain">{children}</div>

            {footer ? (
              <div className="border-t border-white/5 bg-[#1f2c34] px-2.5 py-2.5">{footer}</div>
            ) : null}
          </div>

          {/* Home indicator */}
          <div className="flex justify-center bg-black py-2">
            <div className="h-1 w-[120px] rounded-full bg-white/30" />
          </div>
        </div>
      </div>
    </div>
  );
}
