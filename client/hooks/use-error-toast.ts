"use client";

import { useEffect, useRef, type ReactNode } from "react";
import { toast } from "sonner";

export const ERROR_TOAST_DURATION_MS = 5000;

interface ErrorToastAction {
  label: ReactNode;
  onClick: () => void;
}

export function useErrorToast(
  message: string | null | undefined,
  action?: ErrorToastAction,
) {
  const actionRef = useRef(action);
  useEffect(() => {
    actionRef.current = action;
  });
  const hasAction = action !== undefined;

  useEffect(() => {
    if (!message) return;
    toast.error(message, {
      id: message,
      duration: ERROR_TOAST_DURATION_MS,
      action: hasAction
        ? {
            label: actionRef.current?.label,
            onClick: () => actionRef.current?.onClick(),
          }
        : undefined,
    });
  }, [message, hasAction]);
}
