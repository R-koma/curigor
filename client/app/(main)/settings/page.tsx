import { headers } from "next/headers";
import { redirect } from "next/navigation";

import { PageHeading } from "@/components/layout/page-heading";
import { DeleteAccountSection } from "@/components/settings/delete-account-section";
import { auth } from "@/lib/auth";
import { PAGE_TITLES } from "@/lib/nav-links";

export default async function SettingsPage() {
  const session = await auth.api.getSession({ headers: await headers() });
  if (!session) redirect("/sign-in");

  return (
    <div className="mx-auto max-w-2xl space-y-6 px-4 py-6 md:px-6 md:py-8">
      <PageHeading title={PAGE_TITLES["/settings"]} />
      <section
        aria-labelledby="account-heading"
        className="space-y-1 rounded-xl border p-5"
      >
        <h2 id="account-heading" className="font-semibold">
          アカウント
        </h2>
        <p className="text-sm text-muted-foreground">{session.user.email}</p>
      </section>
      <DeleteAccountSection email={session.user.email} />
    </div>
  );
}
