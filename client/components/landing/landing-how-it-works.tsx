const steps = [
  {
    title: "トピックを選んで AI に教える",
    description:
      "学びたいことを選び、AI を相手に自分の言葉で説明します。AI が質問で理解を深掘りします。",
  },
  {
    title: "ノートとフィードバックが自動生成",
    description:
      "対話が終わると、内容を整理した学習ノートと理解度のフィードバックが自動で作られます。",
  },
  {
    title: "最適なタイミングで復習して定着",
    description:
      "忘却曲線に基づく復習スケジュールに沿って振り返り、知識を長期記憶に定着させます。",
  },
];

export default function LandingHowItWorks() {
  return (
    <section className="border-y bg-muted/30">
      <div className="mx-auto max-w-6xl px-4 py-20 sm:px-6">
        <h2 className="text-center text-3xl font-bold tracking-tight">
          使い方は 3 ステップ
        </h2>
        <div className="mt-12 grid gap-10 md:grid-cols-3">
          {steps.map(({ title, description }, i) => (
            <div
              key={title}
              className="flex flex-col items-center gap-4 text-center"
            >
              <div className="flex size-10 items-center justify-center rounded-full bg-brand font-bold text-brand-foreground">
                {i + 1}
              </div>
              <h3 className="font-semibold">{title}</h3>
              <p className="text-sm leading-relaxed text-muted-foreground">
                {description}
              </p>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}
