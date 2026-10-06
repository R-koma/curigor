import { NotebookPenIcon } from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@/components/ui/tooltip";

export function EndSessionButton({
  highlighted,
  onClick,
}: {
  highlighted: boolean;
  onClick: () => void;
}) {
  if (highlighted) {
    return (
      <Button
        size="sm"
        onClick={onClick}
        className="h-8 rounded-full bg-brand px-3 text-brand-foreground hover:bg-brand/90"
      >
        <NotebookPenIcon className="size-4" />
        ノートを作成
      </Button>
    );
  }

  return (
    <Tooltip>
      <TooltipTrigger asChild>
        <Button
          variant="ghost"
          size="icon"
          onClick={onClick}
          aria-label="ノートを作成"
          className="size-8 rounded-full"
        >
          <NotebookPenIcon className="size-4.5" />
        </Button>
      </TooltipTrigger>
      <TooltipContent>ノートを作成</TooltipContent>
    </Tooltip>
  );
}
