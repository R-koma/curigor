"use client";

import { useCallback, useRef, useState } from "react";
import { fetchActiveSession, type ActiveSession } from "@/lib/active-session";

interface PendingStart {
  session: ActiveSession;
  start: () => void;
  onCancel?: () => void;
}

export function useSessionReplaceConfirm() {
  const [pendingSession, setPendingSession] = useState<ActiveSession | null>(
    null,
  );
  const pendingRef = useRef<PendingStart | null>(null);
  const checkingRef = useRef(false);

  const confirmStart = useCallback(
    async (start: () => void, onCancel?: () => void) => {
      if (checkingRef.current) return;
      checkingRef.current = true;
      let session: ActiveSession | null = null;
      try {
        session = await fetchActiveSession();
      } catch {
        // 確かめられなければ確認を出さずに始める
      }
      if (!session) {
        checkingRef.current = false;
        start();
        return;
      }
      pendingRef.current = { session, start, onCancel };
      setPendingSession(session);
    },
    [],
  );

  const settle = useCallback((confirmed: boolean) => {
    const pending = pendingRef.current;
    if (!pending) return;
    pendingRef.current = null;
    checkingRef.current = false;
    setPendingSession(null);
    if (confirmed) pending.start();
    else pending.onCancel?.();
  }, []);

  const confirm = useCallback(() => settle(true), [settle]);
  const cancel = useCallback(() => settle(false), [settle]);

  return { pendingSession, confirmStart, confirm, cancel };
}
