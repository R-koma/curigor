import type { Metadata } from "next";
import { notFound } from "next/navigation";

import { ProgressPreview } from "./preview";

export const metadata: Metadata = {
  title: "観点マップの見本",
  robots: { index: false, follow: false },
};

export default function ProgressPreviewPage() {
  if (process.env.NODE_ENV === "production") notFound();
  return <ProgressPreview />;
}
