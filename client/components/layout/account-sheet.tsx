"use client";

import { useState } from "react";
import { useTheme } from "next-themes";
import {
  CameraIcon,
  LightbulbIcon,
  LogOutIcon,
  MonitorIcon,
  MoonIcon,
  SunIcon,
} from "lucide-react";
import { AvatarSettingsModal } from "@/components/layout/avatar-settings-modal";
import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar";
import { Sheet, SheetContent, SheetTitle } from "@/components/ui/sheet";
import { useAccountActions } from "@/hooks/use-account-actions";
import { cn } from "@/lib/utils";

const THEMES = [
  { value: "light", label: "ライト", icon: SunIcon },
  { value: "dark", label: "ダーク", icon: MoonIcon },
  { value: "system", label: "自動", icon: MonitorIcon },
] as const;

const ROW =
  "flex min-h-11 w-full items-center gap-3 rounded-lg px-3 text-sm transition-colors hover:bg-muted";

interface AccountSheetProps {
  user: { id: string; name: string; email: string; image?: string | null };
  avatarUrl: string | null | undefined;
  onAvatarChange: (url: string | null) => void;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

export function AccountSheet({
  user,
  avatarUrl,
  onAvatarChange,
  open,
  onOpenChange,
}: AccountSheetProps) {
  const { theme, setTheme } = useTheme();
  const { resetHints, signOut } = useAccountActions();
  const [photoOpen, setPhotoOpen] = useState(false);
  const initial = user.name?.charAt(0).toUpperCase() || "U";
  const current = theme ?? "system";

  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent side="bottom" className="px-4 pt-2">
        <div
          aria-hidden
          className="mx-auto mb-3 h-1 w-10 rounded-full bg-muted-foreground/30"
        />
        <SheetTitle className="sr-only">アカウント</SheetTitle>
        <div className="flex flex-col items-center gap-1 pb-4">
          <button
            type="button"
            aria-label="写真を変更"
            onClick={() => setPhotoOpen(true)}
            className="relative mb-2 rounded-full"
          >
            <Avatar className="size-16">
              <AvatarImage src={avatarUrl ?? undefined} />
              <AvatarFallback className="text-xl">{initial}</AvatarFallback>
            </Avatar>
            <span className="absolute -right-1 -bottom-1 flex size-7 items-center justify-center rounded-full border bg-background text-muted-foreground shadow-sm">
              <CameraIcon className="size-3.5" aria-hidden />
            </span>
          </button>
          <p className="font-semibold">{user.name}</p>
          <p className="text-xs text-muted-foreground">{user.email}</p>
        </div>

        <div className="space-y-1">
          <div className="flex min-h-11 items-center justify-between gap-3 px-3">
            <span className="text-sm">テーマ</span>
            <div
              role="group"
              aria-label="テーマ"
              className="inline-flex rounded-lg border bg-muted p-1"
            >
              {THEMES.map(({ value, label, icon: Icon }) => (
                <button
                  key={value}
                  type="button"
                  aria-pressed={current === value}
                  onClick={() => setTheme(value)}
                  className={cn(
                    "flex h-9 items-center gap-1 rounded-md px-2.5 text-xs font-medium transition-colors",
                    current === value
                      ? "bg-background text-foreground shadow-sm"
                      : "text-muted-foreground",
                  )}
                >
                  <Icon className="size-3.5" aria-hidden />
                  {label}
                </button>
              ))}
            </div>
          </div>
          <button
            type="button"
            onClick={() => void resetHints()}
            className={ROW}
          >
            <LightbulbIcon
              className="size-4 text-muted-foreground"
              aria-hidden
            />
            ヒントをもう一度表示する
          </button>
        </div>

        <div data-slot="account-danger" className="mt-3 border-t pt-3">
          <button
            type="button"
            onClick={() => void signOut()}
            className={cn(ROW, "text-destructive")}
          >
            <LogOutIcon className="size-4" aria-hidden />
            ログアウト
          </button>
        </div>
        <AvatarSettingsModal
          open={photoOpen}
          onClose={() => setPhotoOpen(false)}
          currentImage={avatarUrl}
          userName={user.name}
          onImageUpdate={(url) => onAvatarChange(url || null)}
        />
      </SheetContent>
    </Sheet>
  );
}
