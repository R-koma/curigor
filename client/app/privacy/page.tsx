import type { Metadata } from "next";
import { notFound } from "next/navigation";

import LandingFooter from "@/components/landing/landing-footer";
import LandingHeader from "@/components/landing/landing-header";
import { OPERATOR, PRIVACY_POLICY_EFFECTIVE_DATE } from "@/lib/legal";

export const metadata: Metadata = {
  title: "プライバシーポリシー | Curigor",
  description:
    "Curigor が取得する情報、利用目的、送り先、保存期間、アカウントの削除の手順、請求の窓口。",
};

const RECIPIENTS = [
  {
    name: "OpenAI",
    country: "米国",
    data: "発言・会話の履歴・添付画像、ノートとフィードバックの生成に使う内容、録音した音声、読み上げる応答の本文",
    purpose:
      "応答・ノート・フィードバックの生成、関連するノートの判定、文字起こし、読み上げ",
  },
  {
    name: "Langfuse",
    country: "EU（ドイツ）",
    data: "発言・応答、ユーザー ID、セッション ID",
    purpose: "応答の生成の記録と、不具合の調査・品質の改善",
  },
  {
    name: "Anthropic",
    country: "米国",
    data: "運営者が品質の評価のために取り出した会話",
    purpose: "応答の品質の評価",
  },
  {
    name: "Resend",
    country: "米国",
    data: "メールアドレス、ログイン用のコード",
    purpose: "ログイン用のコードのメールの送信",
  },
  {
    name: "Google",
    country: "米国",
    data: "Google でログインしたときに、Google から氏名・メールアドレス・プロフィール画像を受け取る",
    purpose: "Google アカウントでのログイン",
  },
];

const RETENTION = [
  {
    data: "対話の全文（途中でやめたセッションを含む）・添付画像・ノート・まとめノート・フィードバック・復習の予定・学習メモ・プロフィール画像",
    period: "アカウントがある間は保存し、アカウントの削除で消します",
  },
  {
    data: "ログインの記録（IP アドレス・ブラウザの種類）",
    period:
      "ログインの有効期限が切れるまで。ログアウトとアカウントの削除でも消えます",
  },
  {
    data: "Langfuse に送った応答の生成の記録",
    period:
      "アカウントの削除のときに消します。消しきれなかった分は、Langfuse の保存期間が過ぎると消えます",
  },
  {
    data: "Google のアクセストークンなど",
    period: "保存しません",
  },
  {
    data: "録音した音声",
    period: "文字起こしに使うだけで保存しません",
  },
];

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

export default function PrivacyPage() {
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
          <h1 className="text-2xl font-bold tracking-tight">
            プライバシーポリシー
          </h1>
          <p className="text-muted-foreground">
            制定日: {PRIVACY_POLICY_EFFECTIVE_DATE}
          </p>
          <p>
            Curigor（以下「本サービス」）の運営者は、利用者の個人情報を次のとおり取り扱います。
          </p>
        </div>

        <Section title="1. 運営者">
          <dl className="grid grid-cols-[auto_1fr] gap-x-4 gap-y-1">
            <dt className="text-muted-foreground">氏名</dt>
            <dd>{operatorName}</dd>
            <dt className="text-muted-foreground">問い合わせ</dt>
            <dd className="break-all">{contact}</dd>
            <dt className="text-muted-foreground">住所</dt>
            <dd>請求があれば遅滞なく回答します</dd>
          </dl>
        </Section>

        <Section title="2. 取得する情報">
          <ul className="list-disc space-y-1 pl-5">
            <li>
              アカウントの情報: メールアドレス、名前、プロフィール画像。Google
              でログインしたときは、Google
              から氏名・メールアドレス・プロフィール画像を受け取ります
            </li>
            <li>
              学習の内容:
              対話の発言と応答、添付した画像、ノート・まとめノート・フィードバック・復習の予定・学習メモ
            </li>
            <li>録音した音声（文字起こしのために受け取ります）</li>
            <li>
              利用の記録: 文字起こしと読み上げの利用量、閉じた使い方のヒント
            </li>
            <li>ログインの記録: IP アドレス、ブラウザの種類</li>
            <li>
              ブラウザに保存する情報: ログインを保つための cookie、表示の設定
            </li>
          </ul>
        </Section>

        <Section title="3. 利用目的">
          <ul className="list-disc space-y-1 pl-5">
            <li>
              本サービスの提供（対話の応答、ノート・フィードバック・復習の予定の作成、関連するノートの提案、文字起こし、読み上げ）
            </li>
            <li>本人の確認とログインの維持</li>
            <li>不正な利用の防止と、利用量の上限の管理</li>
            <li>不具合の調査と、応答の品質の改善</li>
            <li>問い合わせへの対応と、本サービスに関する連絡</li>
          </ul>
        </Section>

        <Section title="4. 外国にある第三者への提供">
          <p>本サービスは、利用目的のために、次の事業者へ情報を送ります。</p>
          <div className="overflow-x-auto">
            <table className="w-full min-w-xl border-collapse text-left">
              <thead>
                <tr className="border-b">
                  <th className="py-2 pr-4 font-medium">送り先</th>
                  <th className="py-2 pr-4 font-medium">所在</th>
                  <th className="py-2 pr-4 font-medium">送る情報</th>
                  <th className="py-2 font-medium">目的</th>
                </tr>
              </thead>
              <tbody>
                {RECIPIENTS.map((recipient) => (
                  <tr key={recipient.name} className="border-b align-top">
                    <td className="py-2 pr-4">{recipient.name}</td>
                    <td className="py-2 pr-4 whitespace-nowrap">
                      {recipient.country}
                    </td>
                    <td className="py-2 pr-4">{recipient.data}</td>
                    <td className="py-2">{recipient.purpose}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <ul className="list-disc space-y-1 pl-5">
            <li>
              米国には、個人情報の保護に関する連邦の包括的な法律がなく、分野ごとの連邦法と州法（カリフォルニア州の消費者プライバシー法など）があります
            </li>
            <li>
              EU
              には一般データ保護規則（GDPR）があり、日本の個人情報保護委員会は、EU
              を日本と同等の水準の制度を持つ地域と認めています
            </li>
            <li>
              OpenAI と Anthropic は、API
              で受け取った情報を自社のモデルの学習に使わないことを規約で定めています。各事業者は、通信と保存の暗号化、アクセスの制限などの措置を講じています
            </li>
          </ul>
        </Section>

        <Section title="5. 外部送信">
          <p>
            Google
            でログインした利用者のプロフィール画像を表示するとき、ブラウザは
            Google
            のサーバー（googleusercontent.com）から画像を読み込みます。このとき、IP
            アドレスとブラウザの種類が Google に送られます。
          </p>
        </Section>

        <Section title="6. 保存期間">
          <div className="overflow-x-auto">
            <table className="w-full min-w-md border-collapse text-left">
              <thead>
                <tr className="border-b">
                  <th className="py-2 pr-4 font-medium">情報</th>
                  <th className="py-2 font-medium">保存期間</th>
                </tr>
              </thead>
              <tbody>
                {RETENTION.map((row) => (
                  <tr key={row.data} className="border-b align-top">
                    <td className="py-2 pr-4">{row.data}</td>
                    <td className="py-2">{row.period}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <p>
            期限を決めて自動で消す処理はありません。ノートを 1
            件ずつ消しても、そのもとになった対話の記録と画像は、アカウントを削除するまで残ることがあります。
          </p>
        </Section>

        <Section title="7. アカウントの削除">
          <ol className="list-decimal space-y-1 pl-5">
            <li>
              アカウント欄（パソコンではサイドバーの一番下、スマートフォンではメニューの中）から「アカウントを削除」を選びます
            </li>
            <li>確認の画面で「削除する」を押します</li>
          </ol>
          <ul className="list-disc space-y-1 pl-5">
            <li>
              本人の確認のため、ログインから 1
              日以内である必要があります。過ぎているときは、ログインし直してから操作してください
            </li>
            <li>
              アカウントと、対話・ノート・まとめノート・学習メモ・画像などの学習の内容がすぐに消え、元に戻せません
            </li>
            <li>
              Langfuse
              に送った記録もこのときに消します。消しきれなかった分は、Langfuse
              の保存期間が過ぎると消えます
            </li>
            <li>
              ログインできないなど本人が操作できないときは、問い合わせ（
              {contact}
              ）へ削除を請求してください
            </li>
          </ul>
        </Section>

        <Section title="8. 開示・訂正・利用停止・削除などの請求">
          <p>
            保有する個人データの開示、訂正・追加・削除、利用の停止・消去、第三者への提供の停止、提供の記録の開示を請求できます。問い合わせ（
            {contact}
            ）へ、アカウントに登録したメールアドレスから請求してください。本人であることを確かめたうえで、遅滞なく対応します。手数料はかかりません。
          </p>
        </Section>

        <Section title="9. 安全管理措置">
          <ul className="list-disc space-y-1 pl-5">
            <li>通信を暗号化しています</li>
            <li>
              利用者のデータは、その利用者のアカウントからしか取得・変更できないようにしています
            </li>
            <li>
              パスワードを保存しません。ログインは、メールに届くコードか Google
              アカウントで行います
            </li>
            <li>個人データを取り扱うのは運営者だけです</li>
            <li>
              外国の事業者のサービスを使うため、4
              の各国の個人情報の保護に関する制度を把握したうえで安全管理措置を講じています
            </li>
          </ul>
        </Section>

        <Section title="10. 改定">
          <p>このポリシーを改定するときは、このページで知らせます。</p>
        </Section>
      </main>
      <LandingFooter />
    </>
  );
}
