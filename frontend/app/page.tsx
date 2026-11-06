"use client";

import dynamic from "next/dynamic";
import { useUser } from "@auth0/nextjs-auth0";
import AlertBanner from "@/components/AlertBanner";
import type { AlertPin, BusStop } from "@/components/CampusMap";
import LoginErrorBanner from "@/components/LoginErrorBanner";
import MapHeader from "@/components/MapHeader";
import MapLegend from "@/components/MapLegend";
import RecommendationsPanel from "@/components/RecommendationsPanel";
import { API_URL } from "@/lib/config";
import { colors } from "@/lib/tokens";
import { useLocalStorageValue } from "@/lib/useLocalStorageValue";
import { useIsMobile } from "@/lib/useMediaQuery";
import { usePolledJson } from "@/lib/usePolledJson";

// Leaflet uses browser APIs — must be loaded client-side only.
const CampusMap = dynamic(() => import("@/components/CampusMap"), { ssr: false });
const POLL_MS = 30_000;

interface AlertsResponse {
  alerts: AlertPin[];
  last_updated: string;
  ai_available: boolean;
  feed_available: boolean;
}

/** The live map: data hooks + layout; each piece of UI lives in its own component. */
export default function HomePage() {
  const isMobile = useIsMobile();
  const { user, isLoading: authLoading } = useUser();
  const alertsPoll = usePolledJson<AlertsResponse>(`${API_URL}/api/alerts`, POLL_MS);
  const busPoll = usePolledJson<{ stops: BusStop[] }>(`${API_URL}/api/buses`, 60_000);
  const [major, setStoredMajor] = useLocalStorageValue("major");

  const data = alertsPoll.data;
  const loading = !alertsPoll.loaded;
  const alerts = data?.alerts ?? [];
  const busStops = busPoll.data?.stops ?? [];
  // The backend identifies the user from the access token (lib/api.ts).
  const displayName = user ? (user.name ?? user.email ?? "Signed in user") : null;

  function handleLogout() {
    localStorage.removeItem("major");
    // Left over from the old client-side user ID; remove it from existing browsers.
    localStorage.removeItem("hashed_netid");
    localStorage.removeItem("hashed_netid_source");
    // A full page load on purpose: /auth/logout is the Auth0 route, not a Next.js page.
    // eslint-disable-next-line @next/next/no-location-assign-relative-destination
    window.location.href = "/auth/logout";
  }

  return (
    <div style={{ display: "flex", flexDirection: "column", height: "100vh" }}>
      <MapHeader
        alerts={alerts}
        loading={loading}
        displayName={displayName}
        authLoading={authLoading}
        onLogout={handleLogout}
      />
      <LoginErrorBanner />
      {data && (
        <AlertBanner
          aiAvailable={data.ai_available}
          feedAvailable={data.feed_available}
          lastUpdated={data.last_updated}
        />
      )}

      {/* Map + optional recommendations panel */}
      <main style={{ flex: 1, display: "flex", flexDirection: isMobile ? "column" : "row", overflow: "hidden" }}>
        <div style={{ flex: 1, position: "relative", height: isMobile ? "60vh" : "auto" }}>
          {loading && (
            <div
              style={{
                position: "absolute",
                inset: 0,
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                background: "rgba(15,23,42,0.7)",
                zIndex: 1000,
                fontSize: 14,
                color: colors.textMuted,
              }}
            >
              Loading campus map…
            </div>
          )}
          <CampusMap alerts={alerts} busStops={busStops} />
          {!loading && alerts.length === 0 && (
            <div style={{
              position: "absolute",
              top: 12,
              left: "50%",
              transform: "translateX(-50%)",
              zIndex: 1000,
              background: colors.lowBg,
              border: `1px solid ${colors.lowBorder}`,
              color: colors.lowText,
              borderRadius: 20,
              padding: "6px 18px",
              fontSize: 12,
              fontWeight: 600,
              display: "flex",
              alignItems: "center",
              gap: 6,
              pointerEvents: "none",
            }}>
              ✓ No active alerts — campus is clear
            </div>
          )}
        </div>

        {user && (
          <RecommendationsPanel
            key={major ?? ""} // a new major resets the panel's state (fresh list, page 1)
            major={major}
            onMajorChange={setStoredMajor}
          />
        )}
      </main>

      <MapLegend />
    </div>
  );
}
