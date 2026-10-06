import {
  NoteFeedbackCard,
  NoteFeedbackEmpty,
} from "@/components/notes/note-feedback-card";
import { NoteFeedbackHistory } from "@/components/notes/note-feedback-history";
import { newestFirst, type Feedback } from "@/lib/feedback";

export function NoteFeedbackPanel({ feedbacks }: { feedbacks: Feedback[] }) {
  if (feedbacks.length === 0) return <NoteFeedbackEmpty />;

  const [latest, ...older] = newestFirst(feedbacks);
  return (
    <>
      <NoteFeedbackCard feedback={latest} />
      <NoteFeedbackHistory feedbacks={older} />
    </>
  );
}
