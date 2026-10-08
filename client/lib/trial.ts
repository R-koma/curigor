export interface TrialTopic {
  id: string;
  topic: string;
}

export const TRIAL_TOPICS: readonly TrialTopic[] = [
  { id: "rainbow", topic: "虹が見える理由" },
  { id: "seasons", topic: "夏と冬で気温が違う理由" },
  { id: "bread", topic: "パン生地がふくらむ理由" },
];

export function findTrialTopic(id: string | null): TrialTopic | null {
  return TRIAL_TOPICS.find((t) => t.id === id) ?? null;
}
