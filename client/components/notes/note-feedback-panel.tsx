import {
  NoteFeedbackCard,
  NoteFeedbackEmpty,
} from "@/components/notes/note-feedback-card";
import { NoteFeedbackHistory } from "@/components/notes/note-feedback-history";
import { newestFirst, type Feedback } from "@/lib/feedback";

export function NoteFeedbackPanel({
  noteId,
  feedbacks,
  justUpdated = false,
}: {
  noteId: string;
  feedbacks: Feedback[];
  justUpdated?: boolean;
}) {
  if (feedbacks.length === 0) return <NoteFeedbackEmpty />;

  const [latest, ...older] = newestFirst(feedbacks);
  return (
    <>
      <NoteFeedbackCard
        feedback={latest}
        reviewHref={`/review/${noteId}`}
        justUpdated={justUpdated}
      />
      <NoteFeedbackHistory feedbacks={older} />
    </>
  );
}
