// server/schemas/websocket_message.py の PROTOCOL_VERSION と一致させる
export const PROTOCOL_VERSION = 1;

const RELOADED_AT_KEY = "curigor:protocol-reloaded-at";
const DRAFT_KEY = "curigor:protocol-reload-draft";
const RELOAD_INTERVAL_MS = 60_000;

/** 入力中の文を残してページを読み直す。直前に読み直したばかりなら読み直さず false を返す。 */
export function reloadForNewProtocol(
  draft: string,
  reload: () => void = () => window.location.reload(),
  now: number = Date.now(),
): boolean {
  try {
    const last = Number(sessionStorage.getItem(RELOADED_AT_KEY));
    if (last && now - last < RELOAD_INTERVAL_MS) return false;
    sessionStorage.setItem(RELOADED_AT_KEY, String(now));
    if (draft) sessionStorage.setItem(DRAFT_KEY, draft);
    else sessionStorage.removeItem(DRAFT_KEY);
  } catch {
    return false;
  }
  reload();
  return true;
}

export function takeDraftSavedForReload(): string | null {
  try {
    const draft = sessionStorage.getItem(DRAFT_KEY);
    sessionStorage.removeItem(DRAFT_KEY);
    return draft;
  } catch {
    return null;
  }
}
