import { initials } from "../../lib/utils";

const PALETTES = [
  "bg-bahi-100 text-bahi-800",
  "bg-sky-100 text-sky-800",
  "bg-amber-100 text-amber-900",
  "bg-violet-100 text-violet-800",
  "bg-rose-100 text-rose-800",
];

function palette(name: string) {
  let h = 0;
  for (let i = 0; i < name.length; i++) h = (h + name.charCodeAt(i)) % PALETTES.length;
  return PALETTES[h];
}

type Props = { name: string; size?: "sm" | "md" };

export default function Avatar({ name, size = "md" }: Props) {
  const sz = size === "sm" ? "h-8 w-8 text-xs" : "h-10 w-10 text-sm";
  return (
    <span
      className={`inline-flex shrink-0 items-center justify-center rounded-full font-bold ${sz} ${palette(name)}`}
      aria-hidden
    >
      {initials(name)}
    </span>
  );
}
