import Link from "next/link";
import { Button } from "@/components/ui/button";

const SKIPPED: Record<"learning" | "review", string> = {
  learning: "説明がまだ無かったため、ノートは作成しませんでした",
  review: "返答が無かったため、ノートは更新しませんでした",
};

export function SessionEndedNotice({
  kind,
  noteSkipped,
}: {
  kind: "learning" | "review";
  noteSkipped: boolean;
}) {
  return (
    <div className="mx-auto max-w-md rounded-lg border p-4 text-center">
      <p className="text-sm text-muted-foreground">
        {noteSkipped ? SKIPPED[kind] : "セッションが終了しました"}
      </p>
      <Button asChild variant="link" className="mt-2">
        <Link href="/dashboard">ダッシュボードに戻る</Link>
      </Button>
    </div>
  );
}
