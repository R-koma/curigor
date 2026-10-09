"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useNavbarSlot } from "@/context/navbar-slot-context";
import { NAV_LINKS, isNavLinkActive } from "@/lib/nav-links";
import { cn } from "@/lib/utils";

export function MobileTabBar() {
  const pathname = usePathname();
  const { navbarCenter } = useNavbarSlot();
  if (navbarCenter !== null) return null;

  return (
    <nav
      aria-label="主なページ"
      className="flex shrink-0 border-t bg-background pb-[env(safe-area-inset-bottom)] md:hidden"
    >
      {NAV_LINKS.map(({ href, label, icon: Icon }) => {
        const active = isNavLinkActive(pathname, href);
        return (
          <Link
            key={href}
            href={href}
            aria-current={active ? "page" : undefined}
            className={cn(
              "flex h-14 flex-1 flex-col items-center justify-center gap-0.5 text-2xs font-medium transition-colors",
              active ? "text-foreground" : "text-muted-foreground",
            )}
          >
            <Icon className="size-5" aria-hidden />
            {label}
          </Link>
        );
      })}
    </nav>
  );
}
