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

export const authDatabaseHooks = {
  user: {
    create: {
      before: async (user) => ({ data: withDefaultName(user) }),
    },
  },
} satisfies NonNullable<BetterAuthOptions["databaseHooks"]>;
