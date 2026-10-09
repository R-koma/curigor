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
