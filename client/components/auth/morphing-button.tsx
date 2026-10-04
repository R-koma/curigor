import * as React from "react";
import { Spinner } from "@/components/ui/spinner";
import { cn } from "@/lib/utils";

interface MorphingButtonProps extends React.ComponentProps<"button"> {
  isLoading: boolean;
}

export function MorphingButton({
  isLoading,
  disabled,
  children,
  className,
  ...props
}: MorphingButtonProps) {
  return (
    <button
      disabled={isLoading || disabled}
      aria-busy={isLoading}
      className={cn(
        "w-full h-11 rounded-lg px-4",
        "inline-flex items-center justify-center gap-2",
        "text-sm font-medium cursor-pointer",
        "transition-colors",
        "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-offset-2",
        "disabled:cursor-not-allowed disabled:opacity-50",
        className,
      )}
      {...props}
    >
      {isLoading && <Spinner />}
      {children}
    </button>
  );
}
