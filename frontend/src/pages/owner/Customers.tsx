import { useEffect, useState } from "react";
import { api, MeResponse } from "../../api";
import Leads from "../Leads";
import Orders from "../Orders";
import { Skeleton } from "../../components/ui/avatar";

/** Owner pipeline — leads or orders based on their tenant flow_mode. */
export default function Customers() {
  const [mode, setMode] = useState<"lead" | "order" | null>(null);

  useEffect(() => {
    api<MeResponse>("/api/dashboard/me", { tenant: false })
      .then((me) => setMode(me.tenant?.flow_mode === "order" ? "order" : "lead"))
      .catch(() => setMode("lead"));
  }, []);

  if (!mode) {
    return (
      <div className="space-y-4">
        <Skeleton className="h-8 w-40" />
        <Skeleton className="h-48 w-full rounded-2xl" />
      </div>
    );
  }

  return mode === "order" ? <Orders /> : <Leads />;
}
