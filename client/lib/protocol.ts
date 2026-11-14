// server/schemas/websocket_message.py の PROTOCOL_VERSION と一致させる
export const PROTOCOL_VERSION = 1;

const RELOADED_AT_KEY = "curigor:protocol-reloaded-at";
const RELOAD_INTERVAL_MS = 60_000;

/** ページを読み直す。直前に読み直したばかりなら読み直さず false を返す。 */
export function reloadForNewProtocol(
  reload: () => void = () => window.location.reload(),
  now: number = Date.now(),
): boolean {
  try {
    const last = Number(sessionStorage.getItem(RELOADED_AT_KEY));
    if (last && now - last < RELOAD_INTERVAL_MS) return false;
    sessionStorage.setItem(RELOADED_AT_KEY, String(now));
  } catch {
    return false;
  }
  reload();
  return true;
}
