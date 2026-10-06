import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@/components/ui/tooltip";

export function NavbarTopic({ topic }: { topic: string }) {
  return (
    <Tooltip>
      <TooltipTrigger asChild>
        <h1
          tabIndex={0}
          className="max-w-xs truncate rounded-sm text-sm font-semibold focus-visible:outline-2 focus-visible:outline-ring"
        >
          {topic}
        </h1>
      </TooltipTrigger>
      <TooltipContent className="break-words">{topic}</TooltipContent>
    </Tooltip>
  );
}
