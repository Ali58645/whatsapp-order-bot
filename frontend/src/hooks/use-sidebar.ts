import { useEffect, useState } from "react";

const KEY = "bahidesk-sidebar-collapsed";

export function useSidebarCollapsed() {
  const [collapsed, setCollapsed] = useState(() => localStorage.getItem(KEY) === "1");

  useEffect(() => {
    localStorage.setItem(KEY, collapsed ? "1" : "0");
  }, [collapsed]);

  return {
    collapsed,
    toggle: () => setCollapsed((c) => !c),
    setCollapsed,
  };
}
