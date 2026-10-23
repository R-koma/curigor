import { SquareIcon } from "lucide-react";
import { Button } from "@/components/ui/button";
import { TooltipLabel } from "@/components/ui/tooltip";

export function StopGenerationButton({
  onClick,
  disabled,
}: {
  onClick: () => void;
  disabled?: boolean;
}) {
  return (
    <TooltipLabel label="停止">
      <Button
        type="button"
        size="icon"
        aria-label="停止"
        onClick={onClick}
        disabled={disabled}
        className="size-8 rounded-full pointer-coarse:size-11"
      >
        <SquareIcon className="size-4" />
      </Button>
    </TooltipLabel>
  );
}
