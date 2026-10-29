import { Lightbulb, MessagesSquare } from "lucide-react";

import { Card, CardContent } from "@/components/ui/card";

import Phrases from "./phrases";

const modes = [
  {
    icon: MessagesSquare,
    name: "説明する",
    lead: "知っていることを AI に説明する",
    description:
      "自分の言葉で説明すると、AI が問い返して深く掘ります。どこまで説明できたかが、終わったあとに分かります。",
  },
  {
    icon: Lightbulb,
    name: "理解する",
    lead: "疑問を投げて、AI に教わる",
    description:
      "まだよく知らないことは、疑問を一つずつ聞くところから。聞いたことは学習メモにまとまり、そのまま説明に進めます。",
  },
];

export default function LandingModes() {
  return (
    <section
      id="modes"
      className="mx-auto max-w-6xl scroll-mt-14 px-4 py-20 sm:px-6"
    >
      <h2 className="text-center text-3xl font-bold tracking-tight text-balance">
        <Phrases
          phrases={[
            "知っていることからも、",
            "知らないことからも",
            "始められる",
          ]}
        />
      </h2>
      <div className="mx-auto mt-12 grid max-w-4xl gap-4 md:grid-cols-2">
        {modes.map(({ icon: Icon, name, lead, description }) => (
          <Card key={name}>
            <CardContent className="flex flex-col gap-3">
              <div className="flex items-center gap-2 text-brand-text">
                <Icon aria-hidden className="size-5" />
                <h3 className="font-semibold">{name}</h3>
              </div>
              <p className="font-medium">{lead}</p>
              <p className="text-sm leading-relaxed text-muted-foreground">
                {description}
              </p>
            </CardContent>
          </Card>
        ))}
      </div>
    </section>
  );
}
