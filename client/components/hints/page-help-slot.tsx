"use client";

import { useEffect } from "react";
import { useNavbarSlot } from "@/context/navbar-slot-context";
import type { HintId } from "@/lib/hints";

export function PageHelpSlot({ ids }: { ids: readonly HintId[] }) {
  const { setPageHelpIds } = useNavbarSlot();
  const key = ids.join(",");

  useEffect(() => {
    setPageHelpIds(key.split(",") as HintId[]);
    return () => setPageHelpIds(null);
  }, [key, setPageHelpIds]);

  return null;
}
