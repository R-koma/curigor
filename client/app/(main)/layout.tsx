import { MainLayoutClient } from "@/components/layout/main-layout-client";
import { auth } from "@/lib/auth";
import { isDevAutoLogin } from "@/lib/dev-auth";
import { headers } from "next/headers";
import { redirect } from "next/navigation";

export default async function MainLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const session = await auth.api.getSession({
    headers: await headers(),
  });

  if (!session) {
    redirect(isDevAutoLogin() ? "/api/dev/login" : "/sign-in");
  }

  return <MainLayoutClient user={session.user}>{children}</MainLayoutClient>;
}
