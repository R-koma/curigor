import Link from "next/link";
import { Button } from "@/components/ui/button";
import { TRIAL_TOPICS } from "@/lib/trial";

export function TrialLearningCard() {
  return (
    <section
      aria-labelledby="trial-learning-title"
      className="mb-6 rounded-xl border bg-card p-5"
    >
      <h2 id="trial-learning-title" className="font-semibold">
        お試しで学習する
      </h2>
      <p className="mt-1 text-sm text-muted-foreground">
        身近なトピックを選んで、知っていることを自分の言葉で説明してみましょう。数回のやりとりでノートとフィードバックができます。
      </p>
      <ul className="mt-4 flex flex-wrap gap-2">
        {TRIAL_TOPICS.map(({ id, topic }) => (
          <li key={id}>
            <Button asChild variant="outline">
              <Link href={`/learn?trial=${id}`}>{topic}</Link>
            </Button>
          </li>
        ))}
      </ul>
    </section>
  );
}
