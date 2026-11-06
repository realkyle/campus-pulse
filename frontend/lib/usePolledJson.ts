import { useEffect, useState } from "react";

export interface Polled<T> {
  data: T | null;
  /** True once the first request has finished (successfully or not). */
  loaded: boolean;
}

/**
 * GET `url` now and every `intervalMs`, as React state.
 *
 * A failed request keeps the last good data (stale beats empty on a safety map).
 * State is only set after a response arrives, never synchronously in the effect,
 * and not after unmount. While the tab is hidden, polls are skipped (saving
 * backend requests and API quota); returning to the tab refreshes immediately.
 */
export function usePolledJson<T>(url: string, intervalMs: number): Polled<T> {
  const [state, setState] = useState<Polled<T>>({ data: null, loaded: false });

  useEffect(() => {
    let cancelled = false;
    const load = () =>
      fetch(url)
        .then((res) => (res.ok ? res.json() : Promise.reject(new Error(`HTTP ${res.status}`))))
        .then((data: T) => {
          if (!cancelled) setState({ data, loaded: true });
        })
        .catch(() => {
          if (!cancelled) setState((previous) => ({ ...previous, loaded: true }));
        });
    const loadIfVisible = () => {
      if (document.visibilityState === "visible") load();
    };
    load();
    const id = setInterval(loadIfVisible, intervalMs);
    document.addEventListener("visibilitychange", loadIfVisible);
    return () => {
      cancelled = true;
      clearInterval(id);
      document.removeEventListener("visibilitychange", loadIfVisible);
    };
  }, [url, intervalMs]);

  return state;
}
