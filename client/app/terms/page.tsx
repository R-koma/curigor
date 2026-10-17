import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";

import LandingFooter from "@/components/landing/landing-footer";
import LandingHeader from "@/components/landing/landing-header";
import { OPERATOR, TERMS_EFFECTIVE_DATE } from "@/lib/legal";

export const metadata: Metadata = {
  title: "利用規約 | Curigor",
  description:
    "Curigor を利用する条件、AI の応答の扱い、禁止事項、責任の範囲、規約の改定。",
};

function Section({
  title,
  children,
}: {
  title: string;
  children: React.ReactNode;
}) {
  return (
    <section className="space-y-3">
      <h2 className="text-lg font-semibold">{title}</h2>
      {children}
    </section>
  );
}

export default function TermsPage() {
  if (OPERATOR === null && process.env.NODE_ENV === "production") {
    notFound();
  }
  const operatorName = OPERATOR?.name ?? "（未定）";
  const contact = OPERATOR?.email ?? "（未定）";

  return (
    <>
      <LandingHeader />
      <main className="mx-auto max-w-3xl space-y-10 px-4 py-12 text-sm leading-relaxed sm:px-6">
        <div className="space-y-2">
          <h1 className="text-2xl font-bold tracking-tight">利用規約</h1>
          <p className="text-muted-foreground">
            制定日: {TERMS_EFFECTIVE_DATE}
          </p>
          <p>
            この利用規約（以下「本規約」）は、{operatorName}
            （以下「運営者」）が提供する
            Curigor（以下「本サービス」）の利用の条件を定めます。
          </p>
        </div>

        <Section title="1. 適用と同意">
          <ul className="list-disc space-y-1 pl-5">
            <li>
              本規約は、本サービスを利用するすべての方（以下「利用者」）に適用されます
            </li>
            <li>
              利用者は、本規約と
              <Link
                href="/privacy"
                className="text-brand-text underline underline-offset-4"
              >
                プライバシーポリシー
              </Link>
              に同意したうえで本サービスを利用します。同意は、本サービスの同意の画面で行います
            </li>
          </ul>
        </Section>

        <Section title="2. 利用の条件">
          <ul className="list-disc space-y-1 pl-5">
            <li>本サービスを利用できるのは 18 歳以上の方です</li>
            <li>
              利用者は、自分のメールアドレスか Google
              アカウントでアカウントを作り、自分の責任で管理します
            </li>
          </ul>
        </Section>

        <Section title="3. AI による応答">
          <ul className="list-disc space-y-1 pl-5">
            <li>
              本サービスの応答・ノート・フィードバック・読み上げの音声は、AI
              が作ります
            </li>
            <li>
              AI
              の応答には誤りや古い情報が含まれることがあります。運営者は、応答の正確さ・完全さ・特定の目的への適合を保証しません。重要な内容は、利用者が確かめてください
            </li>
            <li>
              本サービスは学習の補助のためのもので、医療・法律・金融などの専門家の助言に代わるものではありません
            </li>
          </ul>
        </Section>

        <Section title="4. 禁止事項">
          <p>利用者は、次の行為をしてはいけません。</p>
          <ul className="list-disc space-y-1 pl-5">
            <li>法令または公序良俗に反する行為</li>
            <li>他人の権利（著作権・プライバシーなど）を侵害する内容の入力</li>
            <li>他人になりすます行為、他人のアカウントを使う行為</li>
            <li>
              本サービスのサーバーやネットワークに過度な負荷をかける行為、不正にアクセスする行為、自動化した手段で大量に利用する行為
            </li>
            <li>
              本サービスの応答を使って、他人を害する情報や違法な情報を作る行為
            </li>
            <li>その他、運営者が不適切と判断する行為</li>
          </ul>
        </Section>

        <Section title="5. 利用者のコンテンツ">
          <ul className="list-disc space-y-1 pl-5">
            <li>
              利用者が入力した内容と、本サービスで作られたノート・まとめノート・学習メモの権利は、利用者にあります
            </li>
            <li>
              運営者は、プライバシーポリシーに書いた利用目的（本サービスの提供・不具合の調査・品質の改善）の範囲でだけ、これらを利用します
            </li>
          </ul>
        </Section>

        <Section title="6. 料金">
          <p>
            有料の機能を設けるときは、料金・支払いの方法・解約の方法を、申し込みの前に本サービスの画面で示します。
          </p>
        </Section>

        <Section title="7. サービスの変更・中断・終了">
          <p>
            運営者は、本サービスの内容を変更し、または中断・終了することがあります。終了するときは、事前に本サービスの画面かメールで知らせます。
          </p>
        </Section>

        <Section title="8. 利用の停止とアカウントの削除">
          <ul className="list-disc space-y-1 pl-5">
            <li>
              利用者が本規約に違反したときは、運営者は事前の通知なく利用を停止し、またはアカウントを削除することがあります
            </li>
            <li>
              利用者は、いつでもアカウントを削除して利用をやめられます。手順はプライバシーポリシーの「アカウントの削除」に書いています
            </li>
          </ul>
        </Section>

        <Section title="9. 責任の範囲">
          <ul className="list-disc space-y-1 pl-5">
            <li>
              運営者は、本サービスの利用によって利用者に生じた損害について、運営者の故意または重大な過失による場合を除き、損害が生じた日の直前
              12
              か月に運営者がその利用者から受け取った利用料の総額を上限として責任を負います
            </li>
            <li>
              運営者の故意または重大な過失による損害については、この上限を適用しません
            </li>
          </ul>
        </Section>

        <Section title="10. 規約の改定">
          <ul className="list-disc space-y-1 pl-5">
            <li>
              運営者は、必要に応じて本規約を改定します。改定するときは、改定後の内容と効力が生じる日をこのページで知らせます
            </li>
            <li>
              利用者に不利な改定をしたときは、本サービスの同意の画面で改めて同意を求めます。同意するまで、本サービスは使えません
            </li>
          </ul>
        </Section>

        <Section title="11. 準拠法と管轄">
          <p>
            本規約は日本法に従って解釈します。本サービスに関する紛争は、運営者の住所地を管轄する地方裁判所を第一審の専属的合意管轄裁判所とします。
          </p>
        </Section>

        <Section title="12. 問い合わせ">
          <p className="break-all">{contact}</p>
        </Section>
      </main>
      <LandingFooter />
    </>
  );
}
