import { NotebookPenIcon } from "lucide-react";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

export function EndSessionButton({
  label,
  highlighted = false,
  compact = false,
  onClick,
}: {
  label: string;
  highlighted?: boolean;
  compact?: boolean;
  onClick: () => void;
}) {
  const iconOnly = compact && !highlighted;
  return (
    <Button
      size="sm"
      variant={highlighted ? "brand" : "outline"}
      onClick={onClick}
      aria-label={label}
      className={cn(
        "h-8 rounded-full px-3",
        iconOnly && "size-11 px-0 md:h-8 md:w-auto md:px-3",
      )}
    >
      <NotebookPenIcon className="size-4" />
      <span className={cn(iconOnly && "sr-only md:not-sr-only")}>{label}</span>
    </Button>
  );
}
