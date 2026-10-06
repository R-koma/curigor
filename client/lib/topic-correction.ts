export interface TopicCorrectionCard {
  previous_topic: string;
  new_topic: string;
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
