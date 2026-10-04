import type { Metadata } from "next";
import { InboxIcon } from "lucide-react";
import { notFound } from "next/navigation";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { EmptyState } from "@/components/ui/empty-state";
import { Spinner } from "@/components/ui/spinner";
import { TONE_CLASSES, TONES } from "@/lib/tone";

export const metadata: Metadata = {
  title: "デザイントークン",
  robots: { index: false, follow: false },
};

const SWATCHES = [
  { name: "brand", className: "bg-brand" },
  { name: "brand-soft", className: "bg-brand-soft" },
  { name: "brand-deep", className: "bg-brand-deep" },
  { name: "brand-strong", className: "bg-brand-strong" },
  { name: "success", className: "bg-success" },
  { name: "success-soft", className: "bg-success-soft" },
  { name: "warning", className: "bg-warning" },
  { name: "warning-soft", className: "bg-warning-soft" },
  { name: "caution", className: "bg-caution" },
  { name: "caution-soft", className: "bg-caution-soft" },
  { name: "destructive", className: "bg-destructive" },
  { name: "chart-1", className: "bg-chart-1" },
  { name: "chart-2", className: "bg-chart-2" },
  { name: "chart-3", className: "bg-chart-3" },
  { name: "chart-4", className: "bg-chart-4" },
  { name: "chart-5", className: "bg-chart-5" },
];

const BUTTON_VARIANTS = [
  "default",
  "brand",
  "secondary",
  "outline",
  "ghost",
  "destructive",
  "link",
] as const;

const BADGE_VARIANTS = [
  "default",
  "secondary",
  "info",
  "success",
  "warning",
  "destructive",
  "outline",
] as const;

const TEXT_SIZES = [
  { name: "text-3xs", className: "text-3xs" },
  { name: "text-2xs", className: "text-2xs" },
  { name: "text-xs", className: "text-xs" },
  { name: "text-sm", className: "text-sm" },
  { name: "text-prose", className: "text-prose" },
];

const Z_LAYERS = [
  { name: "z-raised", value: 10, className: "z-raised" },
  { name: "z-menu", value: 20, className: "z-menu" },
  { name: "z-drawer", value: 40, className: "z-drawer" },
  { name: "z-overlay", value: 50, className: "z-overlay" },
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

export default function DesignTokensPage() {
  if (process.env.NODE_ENV === "production") notFound();

  return (
    <main className="mx-auto max-w-4xl space-y-10 p-6">
      <h1 className="text-2xl font-bold">デザイントークン</h1>

      <Section title="色">
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
          {SWATCHES.map((swatch) => (
            <div key={swatch.name} className="space-y-1">
              <div className={`h-12 rounded-lg border ${swatch.className}`} />
              <p className="text-xs text-muted-foreground">{swatch.name}</p>
            </div>
          ))}
        </div>
      </Section>

      <Section title="トーン">
        <div className="flex flex-wrap gap-3">
          {TONES.map((tone) => {
            const classes = TONE_CLASSES[tone];
            return (
              <span
                key={tone}
                className={`rounded-full border px-3 py-1 text-sm font-medium ${classes.soft} ${classes.text} ${classes.border}`}
              >
                <span
                  className={`mr-1.5 inline-block size-2 rounded-full ${classes.marker}`}
                />
                {tone}
              </span>
            );
          })}
        </div>
      </Section>

      <Section title="ボタン">
        <div className="flex flex-wrap gap-3">
          {BUTTON_VARIANTS.map((variant) => (
            <Button key={variant} variant={variant}>
              {variant}
            </Button>
          ))}
        </div>
      </Section>

      <Section title="バッジ">
        <div className="flex flex-wrap gap-3">
          {BADGE_VARIANTS.map((variant) => (
            <Badge key={variant} variant={variant}>
              {variant}
            </Badge>
          ))}
        </div>
      </Section>

      <Section title="文字サイズ">
        <div className="space-y-1">
          {TEXT_SIZES.map((size) => (
            <p key={size.name} className={size.className}>
              {size.name} — 教えることで学ぶ
            </p>
          ))}
        </div>
      </Section>

      <Section title="重なり順">
        <ul className="space-y-1 text-sm">
          {Z_LAYERS.map((layer) => (
            <li key={layer.name} className="flex items-center gap-2">
              <span
                className={`relative rounded bg-muted px-2 py-0.5 ${layer.className}`}
              >
                {layer.name}
              </span>
              <span className="text-muted-foreground">{layer.value}</span>
            </li>
          ))}
        </ul>
      </Section>

      <Section title="スピナー">
        <div className="flex items-center gap-4">
          <Spinner size="sm" />
          <Spinner size="md" />
          <Spinner size="lg" />
        </div>
      </Section>

      <Section title="空表示">
        <EmptyState
          icon={InboxIcon}
          title="まだありません"
          description="説明の例"
          className="rounded-xl border py-10"
        />
      </Section>

      <Section title="グラデーション">
        <div className="grid gap-3 sm:grid-cols-2">
          <div className="flex h-24 items-center justify-center rounded-xl border bg-brand-wash text-sm">
            bg-brand-wash
          </div>
          <div className="flex h-24 items-center justify-center rounded-xl bg-brand-bold text-sm text-brand-foreground">
            bg-brand-bold
          </div>
        </div>
      </Section>
    </main>
  );
}
