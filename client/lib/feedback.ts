import { findAspectName, type AspectMap } from "@/lib/aspect-map";

export interface ImprovementItem {
  text: string;
  aspect_id: string | null;
}

export interface Feedback {
  id: string;
  understanding_level: string;
  strength: string;
  improvements: string;
  improvement_items?: ImprovementItem[] | null;
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
  text: string;
  aspect: { id: string; name: string } | null;
}

export function feedbackImprovements(
  feedback: Feedback,
  aspectMap: AspectMap | null,
): LinkedImprovement[] {
  if (!feedback.improvement_items) {
    return splitFeedbackItems(feedback.improvements).map((text) => ({
      text,
      aspect: null,
    }));
  }
  return feedback.improvement_items.map(({ text, aspect_id }) => {
    const name = aspect_id ? findAspectName(aspectMap, aspect_id) : null;
    return { text, aspect: aspect_id && name ? { id: aspect_id, name } : null };
  });
}

export function latestImprovementCount(feedbacks: readonly Feedback[]): number {
  const [latest] = newestFirst(feedbacks);
  return latest ? feedbackImprovements(latest, null).length : 0;
}

export interface FocusAspect {
  id: string;
  name: string;
  count: number;
}

export function latestFocusAspects(
  feedbacks: readonly Feedback[],
  aspectMap: AspectMap | null,
): FocusAspect[] {
  const [latest] = newestFirst(feedbacks);
  if (!latest) return [];
  const byId = new Map<string, FocusAspect>();
  for (const { aspect } of feedbackImprovements(latest, aspectMap)) {
    if (!aspect) continue;
    const existing = byId.get(aspect.id);
    if (existing) existing.count += 1;
    else byId.set(aspect.id, { ...aspect, count: 1 });
  }
  return [...byId.values()];
}
