"use client";

import { useEffect, useState, type MouseEvent } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { MenuIcon } from "lucide-react";
import { AppLogo } from "@/components/brand/app-logo";
import { SidebarAccount } from "@/components/layout/sidebar-account";
import { SidebarCalendar } from "@/components/layout/sidebar-calendar";
import { Button } from "@/components/ui/button";
import {
  Sheet,
  SheetContent,
  SheetTitle,
  SheetTrigger,
} from "@/components/ui/sheet";
import { useNavbarSlot } from "@/context/navbar-slot-context";

interface MobileHeaderProps {
  user: {
    id: string;
    name: string;
    email: string;
    image?: string | null;
  };
}

export function MobileHeader({ user }: MobileHeaderProps) {
  const { navbarCenter } = useNavbarSlot();
  const pathname = usePathname();
  const [openPath, setOpenPath] = useState<string | null>(null);
  const open = openPath === pathname;
  const setOpen = (next: boolean) => setOpenPath(next ? pathname : null);

  useEffect(() => {
    const wide = window.matchMedia("(min-width: 48rem)");
    const closeWhenWide = () => {
      if (wide.matches) setOpenPath(null);
    };
    wide.addEventListener("change", closeWhenWide);
    return () => wide.removeEventListener("change", closeWhenWide);
  }, []);

  if (navbarCenter !== null) return null;

  const closeOnLink = (event: MouseEvent) => {
    if ((event.target as Element).closest("a[href]")) setOpen(false);
  };

  return (
    <header className="relative flex min-h-14 shrink-0 items-center border-b bg-background px-2 md:hidden">
      <Sheet open={open} onOpenChange={setOpen}>
        <SheetTrigger asChild>
          <Button
            variant="ghost"
            size="icon"
            aria-label="メニュー"
            className="size-11 rounded-full"
          >
            <MenuIcon className="size-5" />
          </Button>
        </SheetTrigger>
        <SheetContent onClickCapture={closeOnLink}>
          <div className="flex min-h-14 items-center gap-2 border-b px-4 pr-14">
            <AppLogo />
            <SheetTitle>メニュー</SheetTitle>
          </div>
          <div className="flex-1 overflow-y-auto p-3">
            <SidebarCalendar showSkeleton />
          </div>
          <div className="border-t p-2">
            <SidebarAccount user={user} isOpen />
          </div>
        </SheetContent>
      </Sheet>
      <Link
        href="/dashboard"
        className="absolute left-1/2 flex -translate-x-1/2 items-center gap-2 text-lg font-bold tracking-tight"
      >
        <AppLogo />
        <span>Curigor</span>
      </Link>
    </header>
  );
}
