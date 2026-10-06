import { SignInForm } from "@/components/auth/sign-in-form";
import { isDevFixedOtpEnabled } from "@/lib/dev-auth";

export default function SignInPage() {
  return <SignInForm mode="sign-in" showDevCodeHint={isDevFixedOtpEnabled()} />;
}
