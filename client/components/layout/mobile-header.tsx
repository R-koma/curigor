"use client";

import { useEffect, useState, type MouseEvent } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { CalendarIcon, MenuIcon } from "lucide-react";
import { AppLogo } from "@/components/brand/app-logo";
import { DrawerRecent } from "@/components/layout/drawer-recent";
import { SidebarAccount } from "@/components/layout/sidebar-account";
import { SidebarCalendar } from "@/components/layout/sidebar-calendar";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import {
  Sheet,
  SheetContent,
  SheetTitle,
  SheetTrigger,
} from "@/components/ui/sheet";
import { useNavbarSlot } from "@/context/navbar-slot-context";
import { pageTitleFor } from "@/lib/nav-links";

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

  const title = pageTitleFor(pathname);

  return (
    <header className="flex min-h-14 shrink-0 items-center gap-1 bg-background px-2 md:hidden">
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
          <div className="flex min-h-14 items-center px-4 pr-14">
            <SheetTitle className="sr-only">メニュー</SheetTitle>
            <Link
              href="/dashboard"
              className="flex items-center gap-2 text-lg font-bold tracking-tight"
            >
              <AppLogo />
              <span>Curigor</span>
            </Link>
          </div>
          <div className="flex-1 space-y-4 overflow-y-auto px-2 py-2">
            <Dialog>
              <DialogTrigger asChild>
                <button
                  type="button"
                  className="flex min-h-11 w-full items-center gap-2 rounded-lg px-3 text-sm transition-colors hover:bg-muted"
                >
                  <CalendarIcon
                    className="size-4 text-muted-foreground"
                    aria-hidden
                  />
                  カレンダー
                </button>
              </DialogTrigger>
              <DialogContent className="top-0 left-0 h-dvh max-w-none translate-x-0 translate-y-0 content-start overflow-y-auto rounded-none pt-[max(1.5rem,env(safe-area-inset-top))] pb-[max(1.5rem,env(safe-area-inset-bottom))] ring-0">
                <DialogTitle>カレンダー</DialogTitle>
                <SidebarCalendar showSkeleton />
              </DialogContent>
            </Dialog>
            <DrawerRecent />
          </div>
          <div className="border-t p-2">
            <SidebarAccount user={user} isOpen />
          </div>
        </SheetContent>
      </Sheet>
      {title && (
        <p aria-hidden className="truncate text-xl font-bold">
          {title}
        </p>
      )}
    </header>
  );
}
