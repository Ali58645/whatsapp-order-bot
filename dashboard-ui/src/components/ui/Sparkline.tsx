type Props = {
  values: number[];
  className?: string;
  color?: string;
};

export default function Sparkline({ values, className = "", color = "#0f655e" }: Props) {
  const w = 80;
  const h = 28;
  const max = Math.max(1, ...values);
  const pts = values.map((v, i) => {
    const x = values.length <= 1 ? w / 2 : (i / (values.length - 1)) * w;
    const y = h - (v / max) * (h - 4) - 2;
    return `${x},${y}`;
  });
  const line = pts.join(" ");
  const area = `${line} ${w},${h} 0,${h}`;

  return (
    <svg
      viewBox={`0 0 ${w} ${h}`}
      className={`h-7 w-[5rem] ${className}`}
      aria-hidden
      preserveAspectRatio="none"
    >
      <polygon points={area} fill={color} fillOpacity={0.12} />
      <polyline
        points={line}
        fill="none"
        stroke={color}
        strokeWidth="1.75"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}
