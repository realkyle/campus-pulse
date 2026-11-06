"use client";

import { colors } from "@/lib/tokens";
import { useNow } from "@/lib/useNow";

interface AlertBannerProps {
  aiAvailable: boolean;
  feedAvailable: boolean;
  lastUpdated: string;
}

export default function AlertBanner({ aiAvailable, feedAvailable, lastUpdated }: AlertBannerProps) {
  const now = useNow(60_000); // re-renders once a minute so "N min ago" stays current
  const minutesAgo = lastUpdated
    ? Math.max(0, Math.floor((now - new Date(lastUpdated).getTime()) / 60000))
    : null;

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
      {!aiAvailable && (
        <div
          role="alert"
          style={{
            background: colors.bannerAiBg,
            color: colors.bannerAiText,
            padding: "8px 16px",
            fontSize: 13,
            fontWeight: 600,
            display: "flex",
            alignItems: "center",
            gap: 6,
          }}
        >
          ⚠ Live AI summarization unavailable — showing raw alert text
        </div>
      )}

      {!feedAvailable && (
        <div
          role="alert"
          style={{
            background: colors.bannerFeedBg,
            color: colors.bannerFeedText,
            padding: "8px 16px",
            fontSize: 13,
            fontWeight: 600,
            display: "flex",
            alignItems: "center",
            gap: 6,
          }}
        >
          ⚠ Live RSS feed unreachable — displaying cached data
        </div>
      )}

      <div
        style={{
          background: "rgba(15,23,42,0.85)",
          color: colors.textMuted,
          padding: "4px 12px",
          fontSize: 11,
          textAlign: "right",
        }}
      >
        {minutesAgo === null
          ? "Fetching data…"
          : minutesAgo === 0
          ? "Last updated just now"
          : `Last updated ${minutesAgo} minute${minutesAgo !== 1 ? "s" : ""} ago`}
      </div>
    </div>
  );
}
