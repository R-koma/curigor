import type { BetterAuthOptions } from "better-auth";

export function defaultNameFromEmail(email: string): string {
  const at = email.indexOf("@");
  return at > 0 ? email.slice(0, at) : email;
}

export function withDefaultName<
  T extends { name?: string | null; email: string },
>(user: T): T {
  return user.name ? user : { ...user, name: defaultNameFromEmail(user.email) };
}

const NO_OAUTH_TOKENS = {
  accessToken: null,
  refreshToken: null,
  idToken: null,
  accessTokenExpiresAt: null,
  refreshTokenExpiresAt: null,
};

export function withoutOAuthTokens<T extends object>(
  account: T,
): T & typeof NO_OAUTH_TOKENS {
  return { ...account, ...NO_OAUTH_TOKENS };
}

export const authDatabaseHooks = {
  user: {
    create: {
      before: async (user) => ({ data: withDefaultName(user) }),
    },
  },
  account: {
    create: {
      before: async (account) => ({ data: withoutOAuthTokens(account) }),
    },
    update: {
      before: async (account) => ({ data: withoutOAuthTokens(account) }),
    },
  },
} satisfies NonNullable<BetterAuthOptions["databaseHooks"]>;
