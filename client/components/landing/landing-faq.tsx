import { ChevronDown } from "lucide-react";
import Link from "next/link";

import { OPERATOR } from "@/lib/legal";

import { PRICING_FAQ } from "./landing-copy";

const faqs: { question: string; answer: React.ReactNode }[] = [
  PRICING_FAQ,
  {
    question: "どんな分野で使えますか？",
    answer:
      "言葉で説明できるものなら、分野を問いません。数式やコード、図を含む内容にも対応しています。",
  },
  {
    question: "AI の答えは正しいですか？",
    answer:
      "AI は誤りを含むことがあります。重要な内容は、教材などで確かめてください。",
  },
  {
    question: "入力した内容は AI の学習に使われますか？",
    answer: (
      <>
        利用している AI の事業者（OpenAI・Anthropic）は、API
        で受け取った情報を自社のモデルの学習に使わないことを規約で定めています。
        {OPERATOR !== null && (
          <>
            詳しくは
            <Link
              href="/privacy"
              className="text-brand-text underline underline-offset-4 hover:opacity-80"
            >
              プライバシーポリシー
            </Link>
            をご覧ください。
          </>
        )}
      </>
    ),
  },
  {
    question: "スマートフォンで使えますか？",
    answer: "ブラウザから、パソコンとスマートフォンの両方で使えます。",
  },
  {
    question: "アカウントは削除できますか？",
    answer:
      "アカウント設定からいつでも削除できます。対話やノートなどのデータも消えます。",
  },
];

export default function LandingFaq() {
  return (
    <section
      id="faq"
      className="mx-auto max-w-3xl scroll-mt-14 px-4 py-20 sm:px-6"
    >
      <h2 className="text-center text-3xl font-bold tracking-tight">
        よくある質問
      </h2>
      <div className="mt-10 divide-y border-y">
        {faqs.map(({ question, answer }) => (
          <details key={question} className="group">
            <summary className="flex cursor-pointer list-none items-center justify-between gap-4 py-4 font-medium [&::-webkit-details-marker]:hidden">
              {question}
              <ChevronDown
                aria-hidden
                className="size-4 shrink-0 text-muted-foreground transition-transform group-open:rotate-180"
              />
            </summary>
            <p className="pb-4 text-sm leading-relaxed text-muted-foreground">
              {answer}
            </p>
          </details>
        ))}
      </div>
    </section>
  );
}
