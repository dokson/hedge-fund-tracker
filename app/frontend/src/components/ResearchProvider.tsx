import { useMemo, useState } from "react";
import type { ReactNode } from "react";
import { useLocation } from "react-router";

import { ResearchContext } from "@/hooks/useResearchState";

/** Keeps research controls in this app session without changing direct-link parameters. */
export function ResearchProvider({ children }: { children: ReactNode }) {
  const { pathname } = useLocation();
  const [values] = useState(() => new Map<string, unknown>());
  const memory = useMemo(() => ({ scope: pathname, values }), [pathname, values]);
  return <ResearchContext.Provider value={memory}>{children}</ResearchContext.Provider>;
}
