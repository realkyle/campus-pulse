import { useCallback, useSyncExternalStore } from "react";

const CHANGE_EVENT = "campus-pulse:local-storage";

function read(key: string): string | null {
  try {
    return window.localStorage.getItem(key);
  } catch {
    return null; // storage blocked (e.g. some private-browsing modes)
  }
}

function subscribe(onChange: () => void): () => void {
  window.addEventListener("storage", onChange); // other tabs
  window.addEventListener(CHANGE_EVENT, onChange); // this tab
  return () => {
    window.removeEventListener("storage", onChange);
    window.removeEventListener(CHANGE_EVENT, onChange);
  };
}

/**
 * A localStorage value as React state.
 *
 * Read with useSyncExternalStore instead of "useEffect + setState on mount":
 * no extra render, and server rendering sees null, so hydration never mismatches.
 * Writing updates every component using the same key (and other tabs).
 */
export function useLocalStorageValue(key: string): [string | null, (value: string | null) => void] {
  const value = useSyncExternalStore(subscribe, () => read(key), () => null);
  const setValue = useCallback(
    (next: string | null) => {
      try {
        if (next === null) window.localStorage.removeItem(key);
        else window.localStorage.setItem(key, next);
      } catch {
        // Storage blocked: the value just isn't remembered.
      }
      window.dispatchEvent(new Event(CHANGE_EVENT));
    },
    [key],
  );
  return [value, setValue];
}
