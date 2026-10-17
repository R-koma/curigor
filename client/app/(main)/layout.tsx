import { MainLayoutClient } from "@/components/layout/main-layout-client";
import { auth } from "@/lib/auth";
import { CONSENT_PATH, fetchConsentStatus } from "@/lib/consent";
import { isDevAutoLogin } from "@/lib/dev-auth";
import { headers } from "next/headers";
import { redirect } from "next/navigation";

export default async function MainLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const requestHeaders = await headers();
  const session = await auth.api.getSession({ headers: requestHeaders });

  if (!session) {
    redirect(isDevAutoLogin() ? "/api/dev/login" : "/sign-in");
  }

  const consent = await fetchConsentStatus(requestHeaders.get("cookie") ?? "");
  if (consent && !consent.consented) {
    redirect(CONSENT_PATH);
  }

  return <MainLayoutClient user={session.user}>{children}</MainLayoutClient>;
}
