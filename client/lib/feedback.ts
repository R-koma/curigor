import { findAspectName, type AspectMap } from "@/lib/aspect-map";

export interface ImprovementItem {
  headline?: string | null;
  text: string;
  aspect_id: string | null;
}

export type ReviewResultStatus =
  "explained" | "explained_with_hint" | "not_explained" | "not_asked";

export interface ReviewResult {
  point_id: string;
  point: string;
  question: string;
  status: ReviewResultStatus;
  aspect_id?: string | null;
}

export const REVIEW_RESULT_LABELS: Record<ReviewResultStatus, string> = {
  explained: "説明できた",
  explained_with_hint: "ヒントで説明できた",
  not_explained: "説明できなかった",
  not_asked: "聞けなかった",
};

export interface Feedback {
  id: string;
  understanding_level: string;
  strength: string;
  improvements: string;
  improvement_items?: ImprovementItem[] | null;
  review_results?: ReviewResult[] | null;
  session_type: string | null;
  created_at: string;
}

const DATE_FORMAT = new Intl.DateTimeFormat("ja-JP", {
  timeZone: "Asia/Tokyo",
  year: "numeric",
  month: "long",
  day: "numeric",
});

const SOURCE_LABELS: Record<string, string> = {
  learning: "学習",
  review: "復習",
};

export function splitFeedbackItems(text: string): string[] {
  return text
    .split("\n")
    .map((line) => line.replace(/^[\s・\-*]+/, "").trim())
    .filter((line) => line.length > 0);
}

export function formatFeedbackDate(iso: string): string {
  return DATE_FORMAT.format(new Date(iso));
}

export function feedbackSourceLabel(sessionType: string | null): string | null {
  if (sessionType === null) return null;
  return SOURCE_LABELS[sessionType] ?? null;
}

export function newestFirst(feedbacks: readonly Feedback[]): Feedback[] {
  return [...feedbacks].sort(
    (a, b) => Date.parse(b.created_at) - Date.parse(a.created_at),
  );
}

export interface LinkedImprovement {
  headline: string | null;
  text: string;
  aspect: { id: string; name: string } | null;
}

export function feedbackImprovements(
  feedback: Feedback,
  aspectMap: AspectMap | null,
): LinkedImprovement[] {
  if (!feedback.improvement_items) {
    return splitFeedbackItems(feedback.improvements).map((text) => ({
      headline: null,
      text,
      aspect: null,
    }));
  }
  return feedback.improvement_items.map(({ headline, text, aspect_id }) => {
    const name = aspect_id ? findAspectName(aspectMap, aspect_id) : null;
    return {
      headline: headline || null,
      text,
      aspect: aspect_id && name ? { id: aspect_id, name } : null,
    };
  });
}
