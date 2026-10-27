import { betterAuth } from "better-auth";
import { emailOTP, jwt } from "better-auth/plugins";

import { deletionTokenPayload, purgeAccountData } from "@/lib/account-deletion";
import { authDatabaseHooks } from "@/lib/auth-hooks";
import { DISABLED_EMAIL_OTP_PATHS, emailOtpOptions } from "@/lib/auth-otp";
import { pool } from "@/lib/db";

export const auth = betterAuth({
  database: pool,
  socialProviders: {
    google: {
      clientId: process.env.GOOGLE_CLIENT_ID as string,
      clientSecret: process.env.GOOGLE_CLIENT_SECRET as string,
    },
  },
  user: {
    deleteUser: {
      enabled: true,
      beforeDelete: async (user): Promise<void> => {
        await purgeAccountData(user.id, { signToken: signDeletionToken });
      },
    },
  },
  databaseHooks: authDatabaseHooks,
  disabledPaths: DISABLED_EMAIL_OTP_PATHS,
  plugins: [jwt(), emailOTP(emailOtpOptions)],
});

async function signDeletionToken(sub: string): Promise<string> {
  const { token } = await auth.api.signJWT({
    body: { payload: deletionTokenPayload(sub) },
  });
  return token;
}
