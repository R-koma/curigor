"use client";

import { useNavbarSlot } from "@/context/navbar-slot-context";

export function Navbar() {
  const { navbarCenter } = useNavbarSlot();

  return (
    <nav className="relative flex min-h-15 shrink-0 items-center bg-background/80 px-6 py-3 backdrop-blur-lg">
      <div className="pointer-events-none absolute inset-0 flex items-center justify-center">
        <div className="pointer-events-auto">{navbarCenter}</div>
      </div>
    </nav>
  );
}
