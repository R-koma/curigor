import { NextResponse } from "next/server";

import { auth } from "@/lib/auth";
import {
  DEV_FIXED_OTP_CODE,
  DEV_LOGIN_EMAIL,
  isDevAutoLogin,
} from "@/lib/dev-auth";

const ALLOWED_FETCH_SITES = new Set(["same-origin", "none"]);

export async function GET(request: Request) {
  if (!isDevAutoLogin()) return new NextResponse(null, { status: 404 });

  const fetchSite = request.headers.get("sec-fetch-site");
  if (fetchSite && !ALLOWED_FETCH_SITES.has(fetchSite)) {
    return new NextResponse(null, { status: 403 });
  }

  await auth.api.sendVerificationOTP({
    body: { email: DEV_LOGIN_EMAIL, type: "sign-in" },
  });
  const { headers } = await auth.api.signInEmailOTP({
    body: { email: DEV_LOGIN_EMAIL, otp: DEV_FIXED_OTP_CODE },
    returnHeaders: true,
  });

  const response = NextResponse.redirect(new URL("/dashboard", request.url));
  for (const cookie of headers.getSetCookie()) {
    response.headers.append("set-cookie", cookie);
  }
  return response;
}
