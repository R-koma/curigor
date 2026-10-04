import { CheckIcon } from "lucide-react";

export function IntakeAnsweredNotice({
  onOpenPanel,
}: {
  onOpenPanel?: () => void;
}) {
  return (
    <div className="flex items-center justify-end gap-2 text-xs text-muted-foreground">
      <CheckIcon aria-hidden className="size-3.5" />
      <span>学習の前提を回答しました</span>
      {onOpenPanel && (
        <button
          type="button"
          onClick={onOpenPanel}
          className="cursor-pointer font-medium text-blue-700 underline-offset-2 hover:underline dark:text-blue-300"
        >
          観点マップで確認
        </button>
      )}
    </div>
  );
}
