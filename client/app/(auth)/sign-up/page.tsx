import { headers } from "next/headers";

import { SignInForm } from "@/components/auth/sign-in-form";
import { isDevFixedOtpEnabled } from "@/lib/dev-auth";

export default async function SignUpPage() {
  const nonce = (await headers()).get("x-nonce") ?? undefined;
  return (
    <SignInForm
      mode="sign-up"
      showDevCodeHint={isDevFixedOtpEnabled()}
      turnstileSiteKey={process.env.TURNSTILE_SITE_KEY || null}
      nonce={nonce}
    />
  );
}
