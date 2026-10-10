import Link from "next/link";
import { RotateCcwIcon } from "lucide-react";
import { Button } from "@/components/ui/button";

export function NoteReviewBar({ noteId }: { noteId: string }) {
  return (
    <div className="sticky bottom-0 z-raised border-t bg-background px-4 py-3 md:hidden">
      <Button asChild size="lg" className="w-full gap-2">
        <Link href={`/review/${noteId}`}>
          <RotateCcwIcon className="size-4" aria-hidden />
          復習する
        </Link>
      </Button>
    </div>
  );
}
