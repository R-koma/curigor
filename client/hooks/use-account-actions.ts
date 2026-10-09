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

  return { resetHints, signOut };
}
