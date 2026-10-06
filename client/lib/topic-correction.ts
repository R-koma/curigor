export interface TopicCorrectionCard {
  previous_topic: string;
  new_topic: string;
}

export function isTopicCorrectionCard(
  card: unknown,
): card is TopicCorrectionCard {
  if (typeof card !== "object" || card === null) return false;
  const { previous_topic, new_topic } = card as Record<string, unknown>;
  return typeof previous_topic === "string" && typeof new_topic === "string";
}

export type TopicCorrectionAnswer = "accept" | "decline";

const ANSWER_TEXT: Record<TopicCorrectionAnswer, string> = {
  accept: "はい、トピックを変更する",
  decline: "いいえ、変更しない",
};

export function topicCorrectionAnswerText(
  answer: TopicCorrectionAnswer,
): string {
  return ANSWER_TEXT[answer];
}
