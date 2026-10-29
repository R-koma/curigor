const steps = [
  {
    title: "学びたいことを入れる",
    description: "トピックを一言で書きます。",
  },
  {
    title: "説明する、または聞く",
    description: "2 つの学び方のどちらかで AI と話します。",
  },
  {
    title: "終える",
    description: "ノートとフィードバックができ、復習の日が決まります。",
  },
];

export default function LandingHowItWorks() {
  return (
    <section className="border-y bg-muted/30">
      <div className="mx-auto max-w-6xl px-4 py-20 sm:px-6">
        <h2 className="text-center text-3xl font-bold tracking-tight">
          はじめ方
        </h2>
        <ol className="mx-auto mt-12 grid max-w-4xl gap-8 md:grid-cols-3">
          {steps.map(({ title, description }, i) => (
            <li key={title} className="flex flex-col gap-2">
              <span className="text-sm font-semibold text-brand-text">
                ステップ {i + 1}
              </span>
              <h3 className="font-semibold">{title}</h3>
              <p className="text-sm leading-relaxed text-muted-foreground">
                {description}
              </p>
            </li>
          ))}
        </ol>
      </div>
    </section>
  );
}
