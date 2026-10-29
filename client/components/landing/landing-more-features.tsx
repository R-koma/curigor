import { ImageIcon, Library, Mic, Sigma } from "lucide-react";

const features = [
  {
    icon: Library,
    title: "まとめノート",
    description: "関連するノートを束ね、全体のまとめの下書きを作る",
  },
  {
    icon: Mic,
    title: "声で話す",
    description: "書かずに、声で説明する。AI の応答の読み上げにも対応",
  },
  {
    icon: Sigma,
    title: "数式・コード・図",
    description: "数式やコード、図を含む内容もそのまま扱える",
  },
  {
    icon: ImageIcon,
    title: "画像の添付",
    description: "教材の図や手書きのメモを添えて質問する",
  },
];

export default function LandingMoreFeatures() {
  return (
    <section className="mx-auto max-w-6xl px-4 py-20 sm:px-6">
      <h2 className="text-center text-2xl font-bold tracking-tight">
        学び方に合わせて
      </h2>
      <ul className="mt-10 grid gap-x-8 gap-y-6 sm:grid-cols-2 lg:grid-cols-4">
        {features.map(({ icon: Icon, title, description }) => (
          <li key={title} className="flex gap-3">
            <Icon
              aria-hidden
              className="mt-0.5 size-5 shrink-0 text-muted-foreground"
            />
            <div className="flex flex-col gap-1">
              <h3 className="font-semibold">{title}</h3>
              <p className="text-sm leading-relaxed text-muted-foreground">
                {description}
              </p>
            </div>
          </li>
        ))}
      </ul>
    </section>
  );
}
