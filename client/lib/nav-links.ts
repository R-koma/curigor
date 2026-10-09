import {
  BookOpenIcon,
  LayoutDashboardIcon,
  LibraryIcon,
  PlusCircleIcon,
  type LucideIcon,
} from "lucide-react";

export interface NavLink {
  href: string;
  label: string;
  icon: LucideIcon;
}

export const NAV_LINKS: readonly NavLink[] = [
  { href: "/dashboard", label: "復習", icon: LayoutDashboardIcon },
  { href: "/learn", label: "新規", icon: PlusCircleIcon },
  { href: "/notes", label: "履歴", icon: BookOpenIcon },
  { href: "/collections", label: "まとめ", icon: LibraryIcon },
];

export function isNavLinkActive(pathname: string, href: string): boolean {
  return pathname === href || pathname.startsWith(`${href}/`);
}

export const PAGE_TITLES: Readonly<Record<string, string>> = {
  "/dashboard": "今日の復習",
  "/notes": "学習履歴",
  "/collections": "まとめ",
};

export function pageTitleFor(pathname: string): string | null {
  return PAGE_TITLES[pathname] ?? null;
}
