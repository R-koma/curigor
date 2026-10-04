import { NotebookPenIcon } from "lucide-react";
import { Button } from "@/components/ui/button";

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
        <NotebookPenIcon className="h-4 w-4" />
        ノートを作成
      </Button>
    );
  }

  return (
    <div className="group relative">
      <Button
        variant="ghost"
        size="icon"
        onClick={onClick}
        aria-label="ノートを作成"
        className="h-8 w-8 rounded-full"
      >
        <NotebookPenIcon className="h-4.5 w-4.5" />
      </Button>
      <span
        aria-hidden
        className="pointer-events-none absolute top-full left-1/2 mt-1 -translate-x-1/2 whitespace-nowrap rounded-md border bg-popover px-2 py-1 text-xs opacity-0 shadow-sm transition-opacity group-hover:opacity-100"
      >
        ノートを作成
      </span>
    </div>
  );
}
