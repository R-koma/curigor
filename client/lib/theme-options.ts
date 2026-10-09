import { MonitorIcon, MoonIcon, SunIcon } from "lucide-react";

export const THEME_OPTIONS = [
  { value: "light", label: "ライト", icon: SunIcon },
  { value: "dark", label: "ダーク", icon: MoonIcon },
  { value: "system", label: "自動", icon: MonitorIcon },
] as const;
