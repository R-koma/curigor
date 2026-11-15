import {
  BookOpenIcon,
  FileTextIcon,
  GraduationCapIcon,
  ListChecksIcon,
  MessagesSquareIcon,
  MicIcon,
  PencilLineIcon,
  TextSelectIcon,
  type LucideIcon,
} from "lucide-react";

// ID はサーバーの schemas/hint.py の HintId と一致させる
export const HINT_TEXT = {
  dashboard:
    "人に教えるように説明して学ぶアプリです。説明の後にノート・フィードバック・復習の予定ができます。新しい学習か、下のお試しから始められます。",
  learn_start:
    "学びたいことを書いて始めます。目的や、今読んでいる資料のことも書くと、AI がそれに合わせて進めます。",
  intake_card:
    "答えると、AI があなたの目的や今の理解に合わせて進めます。答えにくい質問はスキップできます。",
  chat_input: "文字で答えるほか、「声で話す」で話しながら学ぶこともできます。",
  dialogue:
    "自分の言葉で説明すると、AI が問い返して理解を深めます。進み具合は上の「観点」で確かめられます。",
  end_session:
    "終えるときは上の「終了する」を押してください。会話の内容からノートとフィードバックができます。",
  explore_side_question:
    "AI の説明の文字を選ぶと、その箇所について横で質問できます",
  note_detail:
    "要約・内容・観点マップで学んだことを読み返し、フィードバックで次に深めたい点を確かめられます。復習の日が来ると、ダッシュボードに出ます。",
} as const;

export type HintId = keyof typeof HINT_TEXT;

export type HintGuide = { icon: LucideIcon; title: string; body: string };

export const HINT_GUIDE: Record<HintId, HintGuide> = {
  dashboard: {
    icon: GraduationCapIcon,
    title: "教えて学ぶ",
    body: "人に説明するように学びます。新しい学習から始めましょう",
  },
  learn_start: {
    icon: PencilLineIcon,
    title: "学びたいことを書く",
    body: "目的や読んでいる資料も書くと、それに合わせて進みます",
  },
  intake_card: {
    icon: ListChecksIcon,
    title: "質問に答える",
    body: "目的や今の理解に合わせて進みます。スキップもできます",
  },
  dialogue: {
    icon: MessagesSquareIcon,
    title: "自分の言葉で説明する",
    body: "AI が問い返します。進み具合は「観点」で見られます",
  },
  chat_input: {
    icon: MicIcon,
    title: "声で話す",
    body: "文字のほか、話しながら学ぶこともできます",
  },
  end_session: {
    icon: FileTextIcon,
    title: "ノートを作る",
    body: "終えるときは「終了する」。ノートとフィードバックができます",
  },
  explore_side_question: {
    icon: TextSelectIcon,
    title: "選んで質問する",
    body: "説明の文字を選ぶと、その箇所を横で質問できます",
  },
  note_detail: {
    icon: BookOpenIcon,
    title: "読み返す",
    body: "要約と観点マップで振り返り、フィードバックで次に深める点を確かめます",
  },
};
