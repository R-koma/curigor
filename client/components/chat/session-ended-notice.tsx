import Link from "next/link";
import { Button } from "@/components/ui/button";

type SessionKind = "learning" | "review" | "explore";

const SKIPPED: Record<SessionKind, string> = {
  learning: "説明がまだ無かったため、ノートは作成しませんでした",
  review: "返答が無かったため、ノートは更新しませんでした",
  explore: "教わった内容がまだ無かったため、学習メモは作成しませんでした",
};

export function SessionEndedNotice({
  kind,
  noteSkipped,
}: {
  kind: SessionKind;
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
