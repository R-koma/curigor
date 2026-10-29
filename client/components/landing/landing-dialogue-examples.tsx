"use client";

import { Card, CardContent } from "@/components/ui/card";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { cn } from "@/lib/utils";

import { sampleDialogues } from "./landing-samples";

export default function LandingDialogueExamples() {
  return (
    <Card className="w-full max-w-md justify-self-center lg:justify-self-end">
      <CardContent className="flex flex-col gap-4">
        <p className="text-xs text-muted-foreground">対話の例</p>
        <Tabs defaultValue={sampleDialogues[0].id}>
          <TabsList aria-label="話題" className="w-full">
            {sampleDialogues.map(({ id, label }) => (
              <TabsTrigger key={id} value={id}>
                {label}
              </TabsTrigger>
            ))}
          </TabsList>
          {sampleDialogues.map(({ id, turns }) => (
            <TabsContent key={id} value={id} className="mt-2 flex flex-col">
              {turns.map(({ role, content }, i) => (
                <div
                  key={i}
                  className={cn(
                    "flex flex-col",
                    role === "user" ? "items-end" : "items-start",
                  )}
                >
                  <span className="sr-only">
                    {role === "user" ? "あなた" : "AI"}:
                  </span>
                  <p
                    className={cn(
                      "max-w-[90%] rounded-2xl px-4 py-3 text-sm leading-relaxed",
                      role === "user" && "bg-muted",
                    )}
                  >
                    {content}
                  </p>
                </div>
              ))}
            </TabsContent>
          ))}
        </Tabs>
        <p className="border-t pt-3 text-xs text-muted-foreground">
          詰まったところが、ノートの「次に学ぶこと」に残ります。
        </p>
      </CardContent>
    </Card>
  );
}
