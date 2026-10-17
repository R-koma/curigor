import { fetchAPI, getToken } from "@/lib/api";

export const CONSENT_PATH = "/consent";

export interface ConsentStatus {
  terms_version: number;
  consented: boolean;
}

export async function fetchConsentStatus(
  cookieHeader: string,
): Promise<ConsentStatus | null> {
  try {
    const token = await getToken(cookieHeader);
    return await fetchAPI<ConsentStatus>("/api/consents/me", { token });
  } catch {
    return null;
  }
}

export async function submitConsent(termsVersion: number): Promise<void> {
  await fetchAPI<void>("/api/consents", {
    method: "POST",
    body: JSON.stringify({ terms_version: termsVersion }),
  });
}

export function goToConsent(
  assign: (url: string) => void = (url) => window.location.assign(url),
): void {
  assign(CONSENT_PATH);
}
