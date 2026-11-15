import { useCallback, useRef } from "react";
import { useRouter } from "next/navigation";
import { toast } from "sonner";
import { fetchAPI } from "@/lib/api";
import { draftKey, removeDraft } from "@/hooks/use-persisted-draft";

export function useLeaveSession(
  sessionId: string | null,
  afterDiscard: () => void,
  disconnect: () => void,
) {
  const router = useRouter();
  const savedRef = useRef(false);

  const onSave = useCallback(() => {
    if (savedRef.current) return;
    savedRef.current = true;
    disconnect();
    toast("保存しました。「続きから」で再開できます");
    router.push("/dashboard");
  }, [router, disconnect]);

  const onDiscard = useCallback(async () => {
    if (!sessionId) return;
    try {
      await fetchAPI(`/api/dialogue-sessions/${sessionId}`, {
        method: "DELETE",
      });
    } catch {
      toast.error("会話を消せませんでした。もう一度お試しください");
      return;
    }
    removeDraft(draftKey.session(sessionId));
    afterDiscard();
  }, [sessionId, afterDiscard]);

  return { onSave, onDiscard };
}
