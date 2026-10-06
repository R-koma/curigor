import type { Metadata } from "next";
import { notFound } from "next/navigation";

import { NoteFeedbackPreview } from "./preview";

export const metadata: Metadata = {
  title: "ノートのフィードバックの見本",
  robots: { index: false, follow: false },
};

export default function NoteFeedbackPreviewPage() {
  if (process.env.NODE_ENV === "production") notFound();
  return <NoteFeedbackPreview />;
}
