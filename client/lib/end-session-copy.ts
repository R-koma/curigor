export type SessionKind = "learning" | "review" | "explore";

export const END_SESSION_COPY: Record<
  SessionKind,
  { primary: string; primaryPoints: string[]; saveNots: string[] }
> = {
  learning: {
    primary: "終了してノートを作成",
    primaryPoints: [
      "このセッションを終わりにします",
      "ノートとフィードバックを作ります",
      "復習の予定に入り、日をおいて思い出す練習をします",
    ],
    saveNots: [
      "ノートもフィードバックもまだ作りません",
      "復習の予定には入りません",
    ],
  },
  review: {
    primary: "終了してノートを更新",
    primaryPoints: [
      "このセッションを終わりにします",
      "ノートとフィードバックを更新します",
      "次の復習日が決まります",
    ],
    saveNots: [
      "ノートもフィードバックもまだ更新しません",
      "次の復習日はまだ変わりません",
    ],
  },
  explore: {
    primary: "終了して学習メモを作成",
    primaryPoints: ["このセッションを終わりにします", "学習メモを作ります"],
    saveNots: ["学習メモはまだ作りません"],
  },
};

export const DIALOG_TITLE = "セッションをどうしますか？";
export const END_WHEN = "学び終えたとき";
export const SAVE_WHEN = "まだ途中のとき";
export const SAVE_LABEL = "保存して後で続ける";
export const SAVE_POINT =
  "会話はそのまま残り、サイドバーの「続きから」で再開できます（30 日）";
export const DISCARD_LABEL = "保存せずに捨てる";
export const DISCARD_CONFIRM = "この会話を消します。元に戻せません";
export const DISCARD_YES = "捨てる";
export const DISCARD_NO = "やめる";
