import { Loader2Icon } from "lucide-react";

export function ReconnectingIndicator() {
  return (
    <span
      role="status"
      className="flex items-center gap-1 text-xs text-muted-foreground"
    >
      <Loader2Icon className="h-3.5 w-3.5 animate-spin" />
      再接続中…
    </span>
  );
}
