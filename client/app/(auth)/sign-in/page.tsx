import { headers } from "next/headers";

import { SignInForm } from "@/components/auth/sign-in-form";
import { isDevFixedOtpEnabled } from "@/lib/dev-auth";

export default async function SignInPage() {
  const nonce = (await headers()).get("x-nonce") ?? undefined;
  return (
    <SignInForm
      mode="sign-in"
      showDevCodeHint={isDevFixedOtpEnabled()}
      turnstileSiteKey={process.env.TURNSTILE_SITE_KEY || null}
      nonce={nonce}
    />
  );
}
