"use client";

import Link from "next/link";
import { CalendarIcon } from "lucide-react";
import { AppLogo } from "@/components/brand/app-logo";
import { SidebarAccount } from "@/components/layout/sidebar-account";
import { SidebarCalendar } from "@/components/layout/sidebar-calendar";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { TooltipLabel } from "@/components/ui/tooltip";
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

  return (
    <header className="relative flex min-h-14 shrink-0 items-center border-b bg-background px-4 md:hidden">
      {navbarCenter !== null ? (
        <div className="flex min-w-0 flex-1 items-center">{navbarCenter}</div>
      ) : (
        <>
          <Link
            href="/dashboard"
            className="flex items-center gap-2 text-lg font-bold tracking-tight"
          >
            <AppLogo />
            <span>Curigor</span>
          </Link>
          <div className="ml-auto flex items-center gap-1">
            <Dialog>
              <TooltipLabel label="カレンダー">
                <DialogTrigger asChild>
                  <Button
                    variant="ghost"
                    size="icon"
                    aria-label="カレンダー"
                    className="size-11 rounded-full"
                  >
                    <CalendarIcon className="size-5" />
                  </Button>
                </DialogTrigger>
              </TooltipLabel>
              <DialogContent className="max-w-[calc(100vw-2rem)] p-4">
                <DialogTitle>カレンダー</DialogTitle>
                <SidebarCalendar showSkeleton />
              </DialogContent>
            </Dialog>
            <SidebarAccount
              user={user}
              isOpen={false}
              menuSide="bottom"
              themeInMenu
            />
          </div>
        </>
      )}
    </header>
  );
}
