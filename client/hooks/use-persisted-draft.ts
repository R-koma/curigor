import { useEffect, useRef, useState } from "react";

export const draftKey = {
  start: (mode: "learning" | "explore") => `curigor:draft:start:${mode}`,
  session: (sessionId: string) => `curigor:draft:session:${sessionId}`,
  side: (threadId: string) => `curigor:draft:side:${threadId}`,
};

function read(key: string): string {
  try {
    return sessionStorage.getItem(key) ?? "";
  } catch {
    return "";
  }
}

function write(key: string, text: string) {
  try {
    if (text) sessionStorage.setItem(key, text);
    else sessionStorage.removeItem(key);
  } catch {}
}

export function removeDraft(key: string) {
  try {
    sessionStorage.removeItem(key);
  } catch {}
}

export function usePersistedDraft(
  key: string | null,
  persistOverride?: string,
): [string, (value: string) => void] {
  const [value, setValue] = useState("");
  const restoredKeyRef = useRef<string | null>(null);
  const persisted = persistOverride ?? value;

  useEffect(() => {
    if (key === null) {
      restoredKeyRef.current = null;
      return;
    }
    if (restoredKeyRef.current !== key) {
      const cameFromNull = restoredKeyRef.current === null;
      restoredKeyRef.current = key;
      if (cameFromNull && persisted) {
        write(key, persisted);
      } else {
        setValue(read(key));
      }
      return;
    }
    write(key, persisted);
  }, [key, persisted]);

  return [value, setValue];
}
