import { ChevronRightIcon } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import {
  FeedbackSections,
  FeedbackWhen,
} from "@/components/notes/note-feedback-card";
import { understandingBadge } from "@/lib/badge";
import type { AspectMap } from "@/lib/aspect-map";
import type { Feedback } from "@/lib/feedback";

export function NoteFeedbackHistory({
  feedbacks,
  aspectMap = null,
}: {
  feedbacks: Feedback[];
  aspectMap?: AspectMap | null;
}) {
  if (feedbacks.length === 0) return null;

  return (
    <section aria-labelledby="feedback-history-heading" className="mt-6">
      <h3
        id="feedback-history-heading"
        className="mb-2 text-xs font-medium text-muted-foreground"
      >
        これまでの評価
      </h3>
      <ol className="space-y-2">
        {feedbacks.map((feedback) => {
          const understanding = understandingBadge(
            feedback.understanding_level,
          );
          return (
            <li key={feedback.id}>
              <details className="group rounded-md border bg-card/50 px-3 py-2">
                <summary className="flex min-h-6 cursor-pointer list-none items-center gap-2 text-xs text-muted-foreground [&::-webkit-details-marker]:hidden">
                  <ChevronRightIcon
                    className="size-3.5 shrink-0 transition-transform group-open:rotate-90 motion-reduce:transition-none"
                    aria-hidden
                  />
                  <FeedbackWhen feedback={feedback} />
                  <Badge
                    variant={understanding.variant}
                    className="ml-auto font-normal"
                  >
                    理解度: {understanding.label}
                  </Badge>
                </summary>
                <div className="mt-3">
                  <FeedbackSections
                    feedback={feedback}
                    headingLevel="h4"
                    aspectMap={aspectMap}
                  />
                </div>
              </details>
            </li>
          );
        })}
      </ol>
    </section>
  );
}
