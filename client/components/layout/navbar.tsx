"use client";

import { useNavbarSlot } from "@/context/navbar-slot-context";
import { cn } from "@/lib/utils";

export function Navbar() {
  const { navbarCenter } = useNavbarSlot();

  return (
    <nav
      className={cn(
        "relative min-h-15 shrink-0 items-center bg-background/80 px-4 py-3 backdrop-blur-lg md:flex md:px-6",
        navbarCenter !== null ? "flex border-b md:border-b-0" : "hidden",
      )}
    >
      <div className="min-w-0 flex-1 md:pointer-events-none md:absolute md:inset-0 md:flex md:items-center md:justify-center">
        <div className="md:pointer-events-auto">{navbarCenter}</div>
      </div>
    </nav>
  );
}
