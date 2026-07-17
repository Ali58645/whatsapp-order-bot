import { Area, AreaChart, ResponsiveContainer } from "recharts";

export default function SparkAreaInner({
  data,
  className,
}: {
  data: number[];
  className?: string;
}) {
  const chartData = data.map((v, i) => ({ i, v }));
  const id = `spark-${data.length}-${data[0] ?? 0}-${data[data.length - 1] ?? 0}`;
  return (
    <div className={className} style={{ width: "100%", height: 48 }}>
      <ResponsiveContainer>
        <AreaChart data={chartData} margin={{ top: 4, right: 0, left: 0, bottom: 0 }}>
          <defs>
            <linearGradient id={id} x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="hsl(168 70% 42%)" stopOpacity={0.45} />
              <stop offset="100%" stopColor="hsl(168 70% 42%)" stopOpacity={0} />
            </linearGradient>
          </defs>
          <Area
            type="monotone"
            dataKey="v"
            stroke="hsl(168 70% 50%)"
            strokeWidth={1.75}
            fill={`url(#${id})`}
            isAnimationActive
            animationDuration={600}
          />
        </AreaChart>
      </ResponsiveContainer>
    </div>
  );
}
