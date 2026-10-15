// サーバーの MAX_MESSAGE_CONTENT_LENGTH と一致させる
export const MAX_MESSAGE_LENGTH = 20000;

export const MESSAGE_TOO_LONG = `本文が長すぎます（${MAX_MESSAGE_LENGTH.toLocaleString("ja-JP")}字まで）`;

export function isMessageTooLong(text: string): boolean {
  return text.length > MAX_MESSAGE_LENGTH;
}
