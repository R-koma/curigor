"use client";

import { createContext, useContext, useState, ReactNode } from "react";
import type { HintId } from "@/lib/hints";

interface NavbarSlotContextValue {
  navbarCenter: ReactNode;
  setNavbarCenter: (node: ReactNode) => void;
  pageHelpIds: readonly HintId[] | null;
  setPageHelpIds: (ids: readonly HintId[] | null) => void;
}

export const NavbarSlotContext = createContext<NavbarSlotContextValue>({
  navbarCenter: null,
  setNavbarCenter: () => {},
  pageHelpIds: null,
  setPageHelpIds: () => {},
});

export function NavbarSlotProvider({ children }: { children: ReactNode }) {
  const [navbarCenter, setNavbarCenter] = useState<ReactNode>(null);
  const [pageHelpIds, setPageHelpIds] = useState<readonly HintId[] | null>(
    null,
  );
  return (
    <NavbarSlotContext.Provider
      value={{ navbarCenter, setNavbarCenter, pageHelpIds, setPageHelpIds }}
    >
      {children}
    </NavbarSlotContext.Provider>
  );
}

export const useNavbarSlot = () => useContext(NavbarSlotContext);
