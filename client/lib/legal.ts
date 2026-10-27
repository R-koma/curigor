export type Operator = {
  name: string;
  email: string;
};

export function operatorFromEnv(
  env: Record<string, string | undefined> = process.env,
): Operator | null {
  const name = env.OPERATOR_NAME?.trim();
  const email = env.OPERATOR_EMAIL?.trim();
  if (!name || !email) return null;
  return { name, email };
}

export const OPERATOR: Operator | null = operatorFromEnv();

export const PRIVACY_POLICY_EFFECTIVE_DATE = "2026年10月16日";

export const PRIVACY_POLICY_REVISED_DATE = "2026年10月27日";

export const TERMS_EFFECTIVE_DATE = "2026年10月17日";
