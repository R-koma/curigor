import * as React from "react";

import { Button } from "@/components/ui/button";
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
    <Button
      variant="brand"
      disabled={isLoading || disabled}
      aria-busy={isLoading}
      className={cn("h-11 w-full gap-2 px-4", className)}
      {...props}
    >
      {isLoading && <Spinner />}
      {children}
    </Button>
  );
}
