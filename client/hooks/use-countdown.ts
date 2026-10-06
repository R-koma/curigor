import { useCallback, useEffect, useRef, useState } from "react";

export function useCountdown(seconds: number) {
  const [remaining, setRemaining] = useState(0);
  const [tick, setTick] = useState(0);
  const deadlineRef = useRef(0);

  const sync = useCallback(() => {
    setRemaining(
      Math.max(0, Math.ceil((deadlineRef.current - Date.now()) / 1000)),
    );
    setTick((value) => value + 1);
  }, []);

  useEffect(() => {
    if (remaining <= 0) return;
    const timer = setTimeout(sync, 1000);
    return () => clearTimeout(timer);
  }, [remaining, tick, sync]);

  useEffect(() => {
    const onVisible = () => {
      if (document.visibilityState === "visible") sync();
    };
    document.addEventListener("visibilitychange", onVisible);
    return () => document.removeEventListener("visibilitychange", onVisible);
  }, [sync]);

  const restart = useCallback(() => {
    deadlineRef.current = Date.now() + seconds * 1000;
    setRemaining(seconds);
    setTick((value) => value + 1);
  }, [seconds]);

  return { remaining, restart };
}
