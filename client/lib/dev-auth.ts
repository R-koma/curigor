import "server-only";

export const DEV_EMAIL_DOMAIN = "@example.test";
export const DEV_LOGIN_EMAIL = "dev@example.test";
export const DEV_FIXED_OTP_CODE = "000000";

function isProduction(): boolean {
  return process.env.NODE_ENV === "production";
}

function isFlagOn(name: "DEV_FIXED_OTP" | "DEV_AUTO_LOGIN"): boolean {
  return process.env[name] === "true";
}

export function isDevFixedOtpEnabled(): boolean {
  return isFlagOn("DEV_FIXED_OTP") && !isProduction();
}

export function isDevFixedOtp(email: string): boolean {
  return (
    isDevFixedOtpEnabled() &&
    email.trim().toLowerCase().endsWith(DEV_EMAIL_DOMAIN)
  );
}

export function isDevAutoLogin(): boolean {
  return isFlagOn("DEV_AUTO_LOGIN") && !isProduction();
}

export function assertDevAuthConfig(): void {
  if (isProduction()) {
    for (const name of ["DEV_FIXED_OTP", "DEV_AUTO_LOGIN"] as const) {
      if (process.env[name]) {
        throw new Error(`${name} must not be set in production`);
      }
    }
  }
  if (isFlagOn("DEV_AUTO_LOGIN") && !isFlagOn("DEV_FIXED_OTP")) {
    throw new Error("DEV_AUTO_LOGIN=true requires DEV_FIXED_OTP=true");
  }
}

assertDevAuthConfig();
