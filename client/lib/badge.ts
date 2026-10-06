import type { VariantProps } from "class-variance-authority";

import type { badgeVariants } from "@/components/ui/badge";

type BadgeVariant = NonNullable<VariantProps<typeof badgeVariants>["variant"]>;

interface BadgeMeta {
  variant: BadgeVariant;
  label: string;
}

export function noteStatusBadge(status: string): BadgeMeta {
  return status === "active"
    ? { variant: "info", label: "進行中" }
    : { variant: "success", label: "完了" };
}

const UNDERSTANDING_BADGES: Record<string, BadgeMeta> = {
  high: { variant: "success", label: "高" },
  medium: { variant: "info", label: "中" },
  low: { variant: "warning", label: "低" },
};

export function understandingBadge(level: string): BadgeMeta {
  return UNDERSTANDING_BADGES[level] ?? { variant: "secondary", label: level };
}
