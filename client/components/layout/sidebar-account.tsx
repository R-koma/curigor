"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { useTheme } from "next-themes";
import { CameraIcon, LogOutIcon, MoonIcon, SunIcon } from "lucide-react";

import { AvatarSettingsModal } from "@/components/layout/avatar-settings-modal";
import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { authClient } from "@/lib/auth-client";
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
  const router = useRouter();
  const { theme, setTheme } = useTheme();
  const [avatarUrl, setAvatarUrl] = useState<string | null | undefined>(
    user.image,
  );
  const [modalOpen, setModalOpen] = useState(false);
  const [menuOpen, setMenuOpen] = useState(false);

  const initial = user.name?.charAt(0).toUpperCase() ?? "U";
  const busy = menuOpen || modalOpen;

  useEffect(() => {
    onBusyChange?.(busy);
  }, [busy, onBusyChange]);

  const handleSignOut = async () => {
    await authClient.signOut({
      fetchOptions: {
        onSuccess: () => {
          router.push("/sign-in");
        },
      },
    });
  };

  return (
    <>
      <div
        className={cn(
          "flex items-center gap-1 p-2",
          !isOpen && "justify-center",
        )}
      >
        <DropdownMenu open={menuOpen} onOpenChange={setMenuOpen}>
          <DropdownMenuTrigger asChild>
            <button
              type="button"
              aria-label="アカウントメニュー"
              className={cn(
                "flex min-w-0 cursor-pointer items-center gap-2 rounded-md p-1 text-left outline-none hover:bg-muted/50",
                isOpen && "flex-1",
              )}
            >
              <Avatar className="size-8">
                <AvatarImage src={avatarUrl ?? undefined} />
                <AvatarFallback className="text-xs">{initial}</AvatarFallback>
              </Avatar>
              {isOpen && (
                <span className="truncate text-sm font-medium">
                  {user.name}
                </span>
              )}
            </button>
          </DropdownMenuTrigger>
          <DropdownMenuContent className="w-60" side="top" align="start">
            <div className="mx-1 mt-1 mb-1 flex items-center gap-3 rounded-md bg-muted/50 px-3 py-2.5">
              <button
                type="button"
                aria-label="写真を変更"
                onClick={() => {
                  setModalOpen(true);
                  setMenuOpen(false);
                }}
                className="group relative shrink-0 cursor-pointer rounded-full outline-none"
              >
                <Avatar className="size-9 ring-2 ring-background">
                  <AvatarImage src={avatarUrl ?? undefined} />
                  <AvatarFallback className="text-sm">{initial}</AvatarFallback>
                </Avatar>
                <span className="absolute inset-0 flex items-center justify-center rounded-full bg-black/50 opacity-0 transition-opacity group-hover:opacity-100">
                  <CameraIcon className="size-3.5 text-white" />
                </span>
              </button>
              <div className="flex min-w-0 flex-col">
                <span className="truncate text-sm font-semibold">
                  {user.name}
                </span>
                <span className="truncate text-xs text-muted-foreground">
                  {user.email}
                </span>
              </div>
            </div>
            <DropdownMenuSeparator />
            <DropdownMenuItem
              onClick={handleSignOut}
              className="gap-2 text-muted-foreground focus:bg-destructive/10 focus:text-destructive dark:focus:bg-destructive/20"
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
            onClick={() => setTheme(theme === "dark" ? "light" : "dark")}
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
