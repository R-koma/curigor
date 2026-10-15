"use client";

import { authClient } from "@/lib/auth-client";
import { GoogleLogo } from "@/components/brand/google-logo";
import { Button } from "../ui/button";

export default function GoogleLoginButton() {
  const handleGoogleSignIn = async () => {
    await authClient.signIn.social({
      provider: "google",
      callbackURL: "/dashboard",
    });
  };
  return (
    <Button
      variant="outline"
      className="w-full h-11"
      onClick={handleGoogleSignIn}
    >
      <GoogleLogo />
      <p className="text-sm text-foreground">Google で続ける</p>
    </Button>
  );
}
