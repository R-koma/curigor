import { AsyncLocalStorage } from "node:async_hooks";

type Captured = { otp?: string };

const captured = new AsyncLocalStorage<Captured>();

export function captureOtp(otp: string): void {
  const store = captured.getStore();
  if (store) store.otp = otp;
}

export async function issueOtp(
  issue: () => Promise<unknown>,
): Promise<string | undefined> {
  const store: Captured = {};
  await captured.run(store, issue);
  return store.otp;
}
