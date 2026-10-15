import { Button } from "@/components/ui/button";

export function EditorLoadError({ onRetry }: { onRetry: () => void }) {
  return (
    <div className="flex items-center gap-2 py-2 text-sm text-muted-foreground">
      <span>エディタを読み込めませんでした</span>
      <Button
        type="button"
        variant="outline"
        size="sm"
        onClick={onRetry}
        className="pointer-coarse:h-11"
      >
        再試行
      </Button>
    </div>
  );
}
