import { useCallback, useSyncExternalStore } from "react";

/**
 * Whether a CSS media query matches, as React state.
 *
 * Read with useSyncExternalStore: server rendering and hydration use
 * `serverValue`, then React re-renders with the real value. The old
 * useWindowWidth read window.innerWidth during the first render, which differed
 * from the server's guess and caused a hydration mismatch on phones.
 */
export function useMediaQuery(query: string, serverValue = false): boolean {
  const subscribe = useCallback(
    (onChange: () => void) => {
      const list = window.matchMedia(query);
      list.addEventListener("change", onChange);
      return () => list.removeEventListener("change", onChange);
    },
    [query],
  );
  return useSyncExternalStore(subscribe, () => window.matchMedia(query).matches, () => serverValue);
}

/** Phone-sized screens (below 768 px), where the layout stacks vertically. */
export function useIsMobile(): boolean {
  return useMediaQuery("(max-width: 767px)");
}
