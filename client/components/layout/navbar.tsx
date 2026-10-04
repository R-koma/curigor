"use client";

import { useState } from "react";
import { authClient } from "@/lib/auth-client";
import { useRouter } from "next/navigation";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar";
import { LogOutIcon, SunIcon, MoonIcon, CameraIcon } from "lucide-react";
import { useTheme } from "next-themes";
import { useNavbarSlot } from "@/context/navbar-slot-context";
import { AvatarSettingsModal } from "@/components/layout/avatar-settings-modal";

interface NavbarProps {
  user: {
    id: string;
    name: string;
    email: string;
    image?: string | null;
  };
}

export function Navbar({ user }: NavbarProps) {
  const router = useRouter();
  const { theme, setTheme } = useTheme();
  const { navbarCenter } = useNavbarSlot();
  const [avatarUrl, setAvatarUrl] = useState<string | null | undefined>(
    user.image,
  );
  const [modalOpen, setModalOpen] = useState(false);
  const [menuOpen, setMenuOpen] = useState(false);

  const handleSignOut = async () => {
    await authClient.signOut({
      fetchOptions: {
        onSuccess: () => {
          router.push("/sign-in");
        },
      },
    });
  };

  const handleImageUpdate = (url: string | null) => {
    setAvatarUrl(url || null);
  };

  return (
    <>
      <nav className="relative bg-background/80 backdrop-blur-lg px-6 py-3 flex items-center shrink-0">
        <div className="absolute inset-0 flex items-center justify-center pointer-events-none">
          <div className="pointer-events-auto">{navbarCenter}</div>
        </div>

        <div className="ml-auto flex items-center gap-2">
          <Button
            variant="ghost"
            size="icon"
            className="size-9 rounded-full hover:!bg-transparent active:!bg-transparent"
            onClick={() => setTheme(theme === "dark" ? "light" : "dark")}
          >
            <SunIcon className="size-4 rotate-0 scale-100 transition-transform dark:rotate-90 dark:scale-0" />
            <MoonIcon className="absolute size-4 rotate-90 scale-0 transition-transform dark:rotate-0 dark:scale-100" />
            <span className="sr-only">テーマ切り替え</span>
          </Button>

          <DropdownMenu open={menuOpen} onOpenChange={setMenuOpen}>
            <DropdownMenuTrigger asChild>
              <Avatar className="size-8 cursor-pointer ring-offset-background transition-opacity hover:opacity-80 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2">
                <AvatarImage src={avatarUrl ?? undefined} />
                <AvatarFallback className="text-xs">
                  {user.name?.charAt(0).toUpperCase() ?? "U"}
                </AvatarFallback>
              </Avatar>
            </DropdownMenuTrigger>
            <DropdownMenuContent className="w-60" align="end">
              <div className="mx-1 mt-1 mb-1 flex items-center gap-3 rounded-md bg-muted/50 px-3 py-2.5">
                <button
                  type="button"
                  aria-label="写真を変更"
                  onClick={() => {
                    setModalOpen(true);
                    setMenuOpen(false);
                  }}
                  className="group relative shrink-0 cursor-pointer rounded-full"
                >
                  <Avatar className="size-9 ring-2 ring-background">
                    <AvatarImage src={avatarUrl ?? undefined} />
                    <AvatarFallback className="text-sm">
                      {user.name?.charAt(0).toUpperCase() ?? "U"}
                    </AvatarFallback>
                  </Avatar>
                  <span className="absolute inset-0 flex items-center justify-center rounded-full bg-black/50 opacity-0 transition-opacity group-hover:opacity-100">
                    <CameraIcon className="size-3.5 text-white" />
                  </span>
                </button>
                <div className="flex flex-col min-w-0">
                  <span className="text-sm font-semibold truncate">
                    {user.name}
                  </span>
                  <span className="text-xs text-muted-foreground truncate">
                    {user.email}
                  </span>
                </div>
              </div>
              <DropdownMenuSeparator />
              <DropdownMenuItem
                onClick={handleSignOut}
                className="group gap-2 text-muted-foreground focus:bg-destructive/10 focus:text-destructive dark:focus:bg-destructive/20"
              >
                <LogOutIcon className="transition-transform group-focus:translate-x-0.5" />
                ログアウト
              </DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
        </div>
      </nav>

      <AvatarSettingsModal
        open={modalOpen}
        onClose={() => setModalOpen(false)}
        currentImage={avatarUrl}
        userName={user.name}
        onImageUpdate={handleImageUpdate}
      />
    </>
  );
}
