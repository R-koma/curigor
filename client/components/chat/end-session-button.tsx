import { NotebookPenIcon } from "lucide-react";
import { Button } from "@/components/ui/button";

export function EndSessionButton({
  label,
  highlighted = false,
  onClick,
}: {
  label: string;
  highlighted?: boolean;
  onClick: () => void;
}) {
  return (
    <Button
      size="sm"
      variant={highlighted ? "brand" : "outline"}
      onClick={onClick}
      className="h-8 rounded-full px-3"
    >
      <NotebookPenIcon className="size-4" />
      {label}
    </Button>
  );
}
