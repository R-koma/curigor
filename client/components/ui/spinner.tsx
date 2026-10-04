import { Loader2Icon } from "lucide-react";

import { cn } from "@/lib/utils";

const SIZES = {
  sm: "size-3.5",
  md: "size-4",
  lg: "size-8",
} as const;

interface SpinnerProps {
  size?: keyof typeof SIZES;
  label?: string;
  className?: string;
}

export function Spinner({ size = "md", label, className }: SpinnerProps) {
  return (
    <Loader2Icon
      className={cn("motion-safe:animate-spin", SIZES[size], className)}
      {...(label
        ? { role: "status", "aria-label": label }
        : { "aria-hidden": true })}
    />
  );
}
