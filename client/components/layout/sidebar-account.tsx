"use client";

import { useEffect, useRef, useState } from "react";
import { useTheme } from "next-themes";
import {
  CameraIcon,
  ChevronUpIcon,
  LightbulbIcon,
  LogOutIcon,
  MoonIcon,
  SunIcon,
} from "lucide-react";

import { AvatarSettingsModal } from "@/components/layout/avatar-settings-modal";
import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuRadioGroup,
  DropdownMenuRadioItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { useAccountActions } from "@/hooks/use-account-actions";
import { THEME_OPTIONS } from "@/lib/theme-options";
import { cn } from "@/lib/utils";

interface SidebarAccountProps {
  user: {
    id: string;
    name: string;
    email: string;
    image?: string | null;
  };
  isOpen: boolean;
  onBusyChange?: (busy: boolean) => void;
}

export function SidebarAccount({
  user,
  isOpen,
  onBusyChange,
}: SidebarAccountProps) {
  const { theme, resolvedTheme, setTheme } = useTheme();
  const { resetHints, signOut } = useAccountActions();
  const [avatarUrl, setAvatarUrl] = useState<string | null | undefined>(
    user.image,
  );
  const [modalOpen, setModalOpen] = useState(false);
  const [menuOpen, setMenuOpen] = useState(false);
  const [menuWidth, setMenuWidth] = useState<number>();
  const rowRef = useRef<HTMLDivElement>(null);

  const initial = user.name?.charAt(0).toUpperCase() || "U";
  const busy = menuOpen || modalOpen;

  useEffect(() => {
    onBusyChange?.(busy);
  }, [busy, onBusyChange]);

  const handleMenuOpenChange = (open: boolean) => {
    if (open) setMenuWidth(rowRef.current?.offsetWidth);
    setMenuOpen(open);
  };

  return (
    <>
      <div
        ref={rowRef}
        className={cn(
          "flex items-center gap-1",
          isOpen ? "w-full" : "justify-center",
        )}
      >
        <DropdownMenu open={menuOpen} onOpenChange={handleMenuOpenChange}>
          <DropdownMenuTrigger asChild>
            <button
              type="button"
              aria-label="アカウントメニュー"
              className={cn(
                "flex min-w-0 cursor-pointer items-center gap-2 rounded-md text-left outline-none hover:bg-muted/50",
                isOpen ? "flex-1 px-2 py-1" : "p-1",
              )}
            >
              <Avatar className="size-8">
                <AvatarImage src={avatarUrl ?? undefined} />
                <AvatarFallback className="text-xs">{initial}</AvatarFallback>
              </Avatar>
              {isOpen && (
                <>
                  <span className="truncate text-sm font-medium">
                    {user.name}
                  </span>
                  <ChevronUpIcon
                    aria-hidden
                    className="ml-auto size-4 shrink-0 text-muted-foreground"
                  />
                </>
              )}
            </button>
          </DropdownMenuTrigger>
          <DropdownMenuContent
            className="min-w-60"
            style={{ width: menuWidth }}
            side="top"
            align="start"
          >
            <DropdownMenuLabel className="truncate text-xs font-normal text-foreground">
              {user.email}
            </DropdownMenuLabel>
            <DropdownMenuSeparator />
            <DropdownMenuLabel className="text-xs font-normal text-muted-foreground">
              テーマ
            </DropdownMenuLabel>
            <DropdownMenuRadioGroup
              value={theme ?? "system"}
              onValueChange={setTheme}
            >
              {THEME_OPTIONS.map(({ value, label, icon: Icon }) => (
                <DropdownMenuRadioItem
                  key={value}
                  value={value}
                  className="gap-2 text-foreground"
                >
                  <Icon />
                  {label}
                </DropdownMenuRadioItem>
              ))}
            </DropdownMenuRadioGroup>
            <DropdownMenuSeparator />
            <DropdownMenuItem
              onSelect={() => setModalOpen(true)}
              className="gap-2 text-foreground"
            >
              <CameraIcon />
              写真を変更
            </DropdownMenuItem>
            <DropdownMenuItem
              onSelect={() => void resetHints()}
              className="gap-2 text-foreground"
            >
              <LightbulbIcon />
              ヒントをもう一度表示する
            </DropdownMenuItem>
            <DropdownMenuItem
              onClick={() => void signOut()}
              className="gap-2 text-foreground"
            >
              <LogOutIcon />
              ログアウト
            </DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>

        {isOpen && (
          <Button
            variant="ghost"
            size="icon"
            className="size-9 shrink-0 rounded-full outline-none hover:!bg-transparent focus-visible:border-transparent focus-visible:ring-0 active:!bg-transparent"
            onClick={() =>
              setTheme((resolvedTheme ?? theme) === "dark" ? "light" : "dark")
            }
          >
            <SunIcon className="size-4 rotate-0 scale-100 transition-transform dark:rotate-90 dark:scale-0" />
            <MoonIcon className="absolute size-4 rotate-90 scale-0 transition-transform dark:rotate-0 dark:scale-100" />
            <span className="sr-only">テーマ切り替え</span>
          </Button>
        )}
      </div>

      <AvatarSettingsModal
        open={modalOpen}
        onClose={() => setModalOpen(false)}
        currentImage={avatarUrl}
        userName={user.name}
        onImageUpdate={(url) => setAvatarUrl(url || null)}
      />
    </>
  );
}
