import type { Metadata } from "next";
import { notFound } from "next/navigation";

import { SignInPreview } from "./preview";

export const metadata: Metadata = {
  title: "ログイン画面の見本",
  robots: { index: false, follow: false },
};

export default function SignInPreviewPage() {
  if (process.env.NODE_ENV === "production") notFound();
  return <SignInPreview />;
}
