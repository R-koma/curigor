import { betterAuth } from "better-auth";
import { emailOTP, jwt } from "better-auth/plugins";
import { Pool } from "pg";

import { authDatabaseHooks } from "@/lib/auth-hooks";
import { DISABLED_EMAIL_OTP_PATHS, emailOtpOptions } from "@/lib/auth-otp";

export const auth = betterAuth({
  database: new Pool({
    connectionString: process.env.DATABASE_URL,
  }),
  socialProviders: {
    google: {
      clientId: process.env.GOOGLE_CLIENT_ID as string,
      clientSecret: process.env.GOOGLE_CLIENT_SECRET as string,
    },
  },
  databaseHooks: authDatabaseHooks,
  disabledPaths: DISABLED_EMAIL_OTP_PATHS,
  plugins: [jwt(), emailOTP(emailOtpOptions)],
});
