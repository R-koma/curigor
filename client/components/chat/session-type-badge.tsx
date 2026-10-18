import {
  SESSION_TYPE_DISPLAY,
  type ResumableSessionType,
} from "@/lib/status-display";
import { TONE_CLASSES } from "@/lib/tone";
import { cn } from "@/lib/utils";

export function SessionTypeBadge({
  type,
  className,
}: {
  type: ResumableSessionType;
  className?: string;
}) {
  const { label, tone } = SESSION_TYPE_DISPLAY[type];
  const classes = TONE_CLASSES[tone];
  return (
    <span
      className={cn(
        "inline-flex shrink-0 items-center rounded-full px-2 py-0.5 text-2xs font-medium",
        classes.soft,
        classes.text,
        className,
      )}
    >
      {label}
    </span>
  );
}
