import { SignInForm } from "@/components/auth/sign-in-form";
import { isDevFixedOtpEnabled } from "@/lib/dev-auth";

export default function SignUpPage() {
  return <SignInForm mode="sign-up" showDevCodeHint={isDevFixedOtpEnabled()} />;
}
