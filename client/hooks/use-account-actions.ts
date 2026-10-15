"use client";

import { useRouter } from "next/navigation";
import { toast } from "sonner";
import { useUsageHints } from "@/context/usage-hints-context";
import { authClient } from "@/lib/auth-client";

export function useAccountActions() {
  const router = useRouter();
  const { reset } = useUsageHints();

  const resetHints = async () => {
    try {
      await reset();
      toast.success("ヒントをもう一度表示します");
    } catch {
      toast.error("ヒントを戻せませんでした。もう一度お試しください");
    }
  };

  const signOut = async () => {
    await authClient.signOut({
      fetchOptions: {
        onSuccess: () => {
          router.push("/sign-in");
        },
      },
    });
  };

  const deleteAccount = async (): Promise<boolean> => {
    try {
      const { error } = await authClient.deleteUser();
      if (error) {
        toast.error(
          error.code === "SESSION_EXPIRED"
            ? "安全のため、ログインし直してから削除してください"
            : "削除できませんでした。もう一度お試しください",
        );
        return false;
      }
    } catch {
      toast.error("削除できませんでした。もう一度お試しください");
      return false;
    }
    toast.success("アカウントを削除しました");
    router.push("/sign-in");
    return true;
  };

  return { resetHints, signOut, deleteAccount };
}
