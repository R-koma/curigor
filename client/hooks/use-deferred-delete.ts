import { useCallback, useEffect, useRef, useState } from "react";
import { toast } from "sonner";
import { KEEP_ON_OUTSIDE_CLICK_PREFIX } from "@/components/ui/sonner";

export function useDeferredDelete<T extends { session_id: string }>(
  items: T[],
  remove: (item: T) => Promise<void>,
): { visible: T[]; requestDelete: (item: T, label: string) => void } {
  const [hidden, setHidden] = useState<ReadonlySet<string>>(new Set());
  const mountedRef = useRef(true);
  const toastIds = useRef(new Set<string | number>());
  const removeRef = useRef(remove);

  useEffect(() => {
    removeRef.current = remove;
  });

  useEffect(() => {
    mountedRef.current = true;
    const ids = toastIds.current;
    return () => {
      mountedRef.current = false;
      ids.forEach((id) => toast.dismiss(id));
    };
  }, []);

  const unhide = useCallback((id: string) => {
    setHidden((prev) => {
      const next = new Set(prev);
      next.delete(id);
      return next;
    });
  }, []);

  const requestDelete = useCallback(
    (item: T, label: string) => {
      const id = item.session_id;
      let settled = false;
      setHidden((prev) => new Set(prev).add(id));

      const commit = async () => {
        if (settled || !mountedRef.current) return;
        settled = true;
        try {
          await removeRef.current(item);
        } catch {
          if (!mountedRef.current) return;
          unhide(id);
          toast.error("削除できませんでした");
        }
      };

      const toastId = toast(`「${label}」を削除しました`, {
        id: `${KEEP_ON_OUTSIDE_CLICK_PREFIX}${id}`,
        classNames: {
          actionButton:
            "!size-auto !min-h-8 !rounded-full !px-3 !py-1 !text-xs !font-medium",
        },
        action: {
          label: "元に戻す",
          onClick: () => {
            settled = true;
            unhide(id);
          },
        },
        onAutoClose: commit,
        onDismiss: commit,
      });
      toastIds.current.add(toastId);
    },
    [unhide],
  );

  return {
    visible: items.filter((item) => !hidden.has(item.session_id)),
    requestDelete,
  };
}
