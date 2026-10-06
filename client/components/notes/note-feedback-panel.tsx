import {
  NoteFeedbackCard,
  NoteFeedbackEmpty,
} from "@/components/notes/note-feedback-card";
import { NoteFeedbackHistory } from "@/components/notes/note-feedback-history";
import type { AspectMap } from "@/lib/aspect-map";
import { newestFirst, type Feedback } from "@/lib/feedback";

export function NoteFeedbackPanel({
  noteId,
  feedbacks,
  justUpdated = false,
  aspectMap = null,
}: {
  noteId: string;
  feedbacks: Feedback[];
  justUpdated?: boolean;
  aspectMap?: AspectMap | null;
}) {
  const reviewHref = `/review/${noteId}`;
  if (feedbacks.length === 0)
    return <NoteFeedbackEmpty reviewHref={reviewHref} />;

  const [latest, ...older] = newestFirst(feedbacks);
  return (
    <>
      <NoteFeedbackCard
        feedback={latest}
        reviewHref={reviewHref}
        justUpdated={justUpdated}
        aspectMap={aspectMap}
      />
      <NoteFeedbackHistory feedbacks={older} aspectMap={aspectMap} />
    </>
  );
}
