import type { Metadata } from "next";
import { notFound } from "next/navigation";

import { TooltipPreview } from "./preview";

export const metadata: Metadata = {
  title: "ツールチップの見本",
  robots: { index: false, follow: false },
};

export default function TooltipPreviewPage() {
  if (process.env.NODE_ENV === "production") notFound();
  return <TooltipPreview />;
}
