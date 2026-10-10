import { ChevronDownIcon } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { understandingBadge } from "@/lib/badge";
import { newestFirst, splitFeedbackItems, type Feedback } from "@/lib/feedback";

export function NoteFeedbackSummary({ feedbacks }: { feedbacks: Feedback[] }) {
  if (feedbacks.length === 0) return null;

  const [latest] = newestFirst(feedbacks);
  const understanding = understandingBadge(latest.understanding_level);
  const improvementCount = splitFeedbackItems(latest.improvements).length;

  return (
    <a
      href="#feedback"
      className="mb-8 flex items-center gap-3 rounded-lg border bg-card px-4 py-3 text-sm transition-colors hover:bg-muted max-md:hidden lg:hidden"
    >
      <Badge variant={understanding.variant} className="font-normal">
        理解度: {understanding.label}
      </Badge>
      <span className="text-muted-foreground">
        {improvementCount > 0 ? `改善点 ${improvementCount} 件` : "改善点なし"}
      </span>
      <span className="ml-auto flex items-center gap-1 text-xs text-muted-foreground">
        フィードバックを見る
        <ChevronDownIcon className="size-3.5" aria-hidden />
      </span>
    </a>
  );
}
