import { Spinner } from "@/components/ui/spinner";

export function ReconnectingIndicator() {
  return (
    <span
      role="status"
      className="flex items-center gap-1 text-xs text-muted-foreground"
    >
      <Spinner size="sm" />
      再接続中…
    </span>
  );
}
