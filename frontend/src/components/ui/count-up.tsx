import { useEffect, useState } from "react";
import { useSpring, useTransform } from "framer-motion";

/** Animated count-up for stat numbers */
export function CountUp({
  value,
  className,
  prefix = "",
  suffix = "",
}: {
  value: number;
  duration?: number;
  className?: string;
  prefix?: string;
  suffix?: string;
}) {
  const spring = useSpring(0, { stiffness: 90, damping: 22 });
  const display = useTransform(
    spring,
    (v) => `${prefix}${Math.round(v).toLocaleString()}${suffix}`
  );
  const [text, setText] = useState(`${prefix}0${suffix}`);

  useEffect(() => {
    spring.set(value);
  }, [spring, value]);

  useEffect(() => {
    const unsub = display.on("change", setText);
    return () => unsub();
  }, [display]);

  return <span className={className}>{text}</span>;
}
