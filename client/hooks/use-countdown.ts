import { useCallback, useEffect, useState } from "react";

export function useCountdown(seconds: number) {
  const [remaining, setRemaining] = useState(0);

  useEffect(() => {
    if (remaining <= 0) return;
    const timer = setTimeout(() => setRemaining((value) => value - 1), 1000);
    return () => clearTimeout(timer);
  }, [remaining]);

  const restart = useCallback(() => setRemaining(seconds), [seconds]);

  return { remaining, restart };
}
