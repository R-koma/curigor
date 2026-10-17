import { cn } from "@/lib/utils";

export const AI_NOTICE =
  "Curigor は AI です。誤りを含むことがあるので、重要な内容は確かめてください";
export const AI_VOICE_NOTICE = "読み上げは AI の音声です";

export function AiNotice({
  voice = false,
  className,
}: {
  voice?: boolean;
  className?: string;
}) {
  return (
    <p className={cn("text-center text-xs text-muted-foreground", className)}>
      {AI_NOTICE}
      {voice && `。${AI_VOICE_NOTICE}`}
    </p>
  );
}
