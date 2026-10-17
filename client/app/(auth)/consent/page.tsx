import type { Metadata } from "next";
import { headers } from "next/headers";
import { redirect } from "next/navigation";

import { ConsentForm } from "@/components/consent/consent-form";
import { auth } from "@/lib/auth";
import { fetchConsentStatus } from "@/lib/consent";

export const metadata: Metadata = {
  title: "利用規約への同意 | Curigor",
};

export default async function ConsentPage() {
  const requestHeaders = await headers();
  const session = await auth.api.getSession({ headers: requestHeaders });
  if (!session) {
    redirect("/sign-in");
  }

  const consent = await fetchConsentStatus(requestHeaders.get("cookie") ?? "");
  if (consent?.consented) {
    redirect("/dashboard");
  }

  return <ConsentForm termsVersion={consent?.terms_version ?? null} />;
}
