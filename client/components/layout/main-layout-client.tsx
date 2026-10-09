"use client";

import { ReactNode } from "react";
import { Navbar } from "@/components/layout/navbar";
import { Sidebar } from "@/components/layout/sidebar";
import { NavbarSlotProvider } from "@/context/navbar-slot-context";
import { UsageHintsProvider } from "@/context/usage-hints-context";

interface MainLayoutClientProps {
  user: {
    id: string;
    name: string;
    email: string;
    image?: string | null;
  };
  children: ReactNode;
}

export function MainLayoutClient({ user, children }: MainLayoutClientProps) {
  return (
    <UsageHintsProvider>
      <NavbarSlotProvider>
        <div className="flex h-dvh">
          <Sidebar user={user} />
          <div className="flex flex-1 flex-col overflow-hidden">
            <Navbar />
            <main className="flex-1 overflow-auto">{children}</main>
          </div>
        </div>
      </NavbarSlotProvider>
    </UsageHintsProvider>
  );
}
