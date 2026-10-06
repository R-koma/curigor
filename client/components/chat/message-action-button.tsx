"use client";

import type { ComponentProps } from "react";

import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import { cn } from "@/lib/utils";

interface MessageActionButtonProps extends ComponentProps<"button"> {
  label: string;
  alwaysVisible?: boolean;
}

export function MessageActionButton({
  label,
  alwaysVisible = false,
  className,
  children,
  ...props
}: MessageActionButtonProps) {
  return (
    <Tooltip>
      <TooltipTrigger asChild>
        <button
          type="button"
          aria-label={label}
          className={cn(
            "mt-2 cursor-pointer transition-opacity",
            alwaysVisible
              ? "opacity-100"
              : "opacity-0 group-hover:opacity-100 group-focus-within:opacity-100 focus-visible:opacity-100 not-hover:opacity-100",
            className,
          )}
          {...props}
        >
          {children}
        </button>
      </TooltipTrigger>
      <TooltipContent>{label}</TooltipContent>
    </Tooltip>
  );
}
