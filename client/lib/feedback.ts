export interface Feedback {
  id: string;
  understanding_level: string;
  strength: string;
  improvements: string;
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

export function latestImprovementCount(feedbacks: readonly Feedback[]): number {
  const [latest] = newestFirst(feedbacks);
  return latest ? splitFeedbackItems(latest.improvements).length : 0;
}
