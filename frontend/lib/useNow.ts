import { useCallback, useSyncExternalStore } from "react";

/**
 * The current time in ms, rounded down to `intervalMs`, re-rendering once per interval.
 *
 * Calling Date.now() during render makes rendering impure (the output changes on
 * every re-render). This reads the clock as an external store instead. Server
 * rendering sees 0.
 */
export function useNow(intervalMs: number): number {
  const subscribe = useCallback(
    (onTick: () => void) => {
      const id = setInterval(onTick, intervalMs);
      return () => clearInterval(id);
    },
    [intervalMs],
  );
  return useSyncExternalStore(subscribe, () => Math.floor(Date.now() / intervalMs) * intervalMs, () => 0);
}
