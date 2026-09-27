import type { LearningProgress } from "@/hooks/use-chat-websocket";

export function LearningProgressIndicator({
  progress,
}: {
  progress: LearningProgress;
}) {
  const reached = Math.min(
    progress.reached_aspects.length,
    progress.target_count,
  );
  const title =
    progress.reached_aspects.length > 0
      ? `説明できた観点: ${progress.reached_aspects.join("、")}`
      : "まだ説明できた観点はありません";

  return (
    <div className="flex items-center gap-2" title={title}>
      <div className="flex gap-0.5">
        {Array.from({ length: progress.target_count }, (_, i) => (
          <span
            key={i}
            className={`h-1.5 w-4 rounded-full ${i < reached ? "bg-blue-500" : "bg-muted"}`}
          />
        ))}
      </div>
      <span className="text-xs tabular-nums text-muted-foreground">
        {reached}/{progress.target_count}
      </span>
    </div>
  );
}
