"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";
import { fetchAPI } from "@/lib/api";
import type { HintId } from "@/lib/hints";

interface UsageHintsContextValue {
  isVisible: (id: HintId) => boolean;
  dismiss: (id: HintId) => void;
  reset: () => Promise<void>;
}

const UsageHintsContext = createContext<UsageHintsContextValue>({
  isVisible: () => false,
  dismiss: () => {},
  reset: async () => {},
});

export function UsageHintsProvider({ children }: { children: ReactNode }) {
  const [dismissed, setDismissed] = useState<ReadonlySet<string> | null>(null);

  useEffect(() => {
    let cancelled = false;
    fetchAPI<{ dismissed: string[] }>("/api/hints/dismissals")
      .then(({ dismissed }) => {
        if (!cancelled) setDismissed(new Set(dismissed));
      })
      .catch(() => {});
    return () => {
      cancelled = true;
    };
  }, []);

  const isVisible = useCallback(
    (id: HintId) => dismissed !== null && !dismissed.has(id),
    [dismissed],
  );

  const dismiss = useCallback((id: HintId) => {
    setDismissed((prev) => new Set(prev).add(id));
    fetchAPI(`/api/hints/dismissals/${id}`, { method: "PUT" }).catch(() => {});
  }, []);

  const reset = useCallback(async () => {
    await fetchAPI("/api/hints/dismissals", { method: "DELETE" });
    setDismissed(new Set());
  }, []);

  const value = useMemo(
    () => ({ isVisible, dismiss, reset }),
    [isVisible, dismiss, reset],
  );

  return (
    <UsageHintsContext.Provider value={value}>
      {children}
    </UsageHintsContext.Provider>
  );
}

export function useUsageHints(): UsageHintsContextValue {
  return useContext(UsageHintsContext);
}

export function useActiveHint(
  candidates: readonly (HintId | false | null | undefined)[],
): HintId | null {
  const { isVisible } = useUsageHints();
  for (const id of candidates) {
    if (id && isVisible(id)) return id;
  }
  return null;
}
