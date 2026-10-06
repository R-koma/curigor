import type { Metadata } from "next";
import { notFound } from "next/navigation";

import { IntakeCardPreview } from "./preview";

export const metadata: Metadata = {
  title: "聞き取りカードの見本",
  robots: { index: false, follow: false },
};

export default function IntakeCardPreviewPage() {
  if (process.env.NODE_ENV === "production") notFound();
  return <IntakeCardPreview />;
}
