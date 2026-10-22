import type { ChatMessage } from "@/hooks/use-chat-websocket";

export function canStopGeneration(
  messages: ChatMessage[],
  isLoading: boolean,
  minUserIndex: number,
): boolean {
  if (!isLoading) return false;
  const last = messages.length - 1;
  const index = messages[last]?.role === "assistant" ? last - 1 : last;
  const message = messages[index];
  if (!message || message.role !== "user" || index < minUserIndex) return false;
  if (
    message.intakeAnswered ||
    message.topicCorrectionAnswered ||
    message.topicEdit
  ) {
    return false;
  }
  const previous = messages[index - 1];
  return !previous?.intakeCard && !previous?.topicCorrectionCard;
}
