import SiteNav from "@/components/SiteNav";
import { colors } from "@/lib/tokens";

const STEPS = [
  {
    n: 1,
    title: "Open the map",
    body: 'Navigate to the Campus Pulse URL. The map loads immediately — no account required. You\'ll see the campus centered with any active alert pins visible.',
  },
  {
    n: 2,
    title: "Read the status bar",
    body: 'Below the header you\'ll see a status bar showing when the data was last updated and whether live AI summarization is active. If the bar shows "⚠ Live AI summarization unavailable", alerts are still displayed using raw RSS text.',
  },
  {
    n: 3,
    title: "Click a pin for alert details",
    body: "Click any colored circle on the map to open a popup showing the incident type, severity level, affected building, recommended action, and raw alert text. Pin color indicates severity: red = high, yellow = medium, green = low.",
  },
  {
    n: 4,
    title: "Sign in with your UW Google account",
    body: 'Click "Sign in with Auth0" in the top-right corner, then click "Continue with Google" and use your @uw.edu or @washington.edu email. Duo MFA will fire as part of the UW Google login. Only UW accounts are accepted — non-UW logins are blocked. Your account identifier is hashed before any data is stored; no personally identifiable information is retained.',
  },
  {
    n: 5,
    title: "View your For You feed",
    body: 'After signing in, a "For You" panel appears on the right side of the map showing live upcoming campus events pulled from the official UW Bothell events calendar. New users see popularity-ranked events; returning users with enough interaction history receive personalized collaborative-filtering recommendations. Scroll down in the panel to load more events.',
  },
  {
    n: 6,
    title: "Search events",
    body: 'Use the search bar in the For You panel to find specific events by title, category, or description. Search looks across all available events — not just the ones currently visible — so you can find anything even if it hasn\'t loaded yet.',
  },
  {
    n: 7,
    title: "Set your major for better cold-start recommendations",
    body: 'Type your major in the field at the top of the For You panel and click Set. This seeds your recommendations with events matching your field of study (e.g. CSS → technology events, Biology → science events). Your major is stored locally and can be updated any time.',
  },
  {
    n: 8,
    title: "Click events to view details and register your interest",
    body: 'Click any event card to log your interest and open the event\'s page on the UWB events calendar or Handshake in a new tab. Clicked events are marked "viewed". Over time, your interaction history improves the quality of your recommendations.',
  },
  {
    n: 9,
    title: "Sign out when done",
    body: 'Click "Sign out" in the header to clear your session. The map remains fully functional for anonymous browsing after sign-out.',
  },
];

export default function UserGuidePage() {
  return (
    <div style={{ display: "flex", minHeight: "100vh", background: colors.bgBase }}>
      <SiteNav />

      <main style={{ flex: 1, overflowY: "auto", padding: "48px" }}>
        <h1 style={{ fontSize: 28, fontWeight: 800, color: colors.textPrimary, marginBottom: 8 }}>
          User Guide
        </h1>
        <p style={{ fontSize: 14, color: colors.textFaint, marginBottom: 40, maxWidth: 560 }}>
          Step-by-step instructions for using Campus Pulse, from opening the map
          to getting personalized event recommendations.
        </p>

        <div style={{ display: "flex", flexDirection: "column", gap: 20, maxWidth: 680 }}>
          {STEPS.map((step) => (
            <div
              key={step.n}
              style={{
                display: "flex",
                gap: 20,
                background: colors.bgPanel,
                border: `1px solid ${colors.border}`,
                borderRadius: 10,
                padding: "20px 24px",
              }}
            >
              <div
                style={{
                  width: 32,
                  height: 32,
                  borderRadius: "50%",
                  background: colors.blueDark,
                  border: `2px solid ${colors.blue}`,
                  color: colors.blueLight,
                  fontSize: 13,
                  fontWeight: 700,
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  flexShrink: 0,
                  marginTop: 2,
                }}
              >
                {step.n}
              </div>
              <div>
                <h3 style={{ fontSize: 14, fontWeight: 700, color: colors.textPrimary, marginBottom: 8 }}>
                  {step.title}
                </h3>
                <p style={{ fontSize: 13, color: colors.textMuted, lineHeight: 1.7, margin: 0 }}>
                  {step.body}
                </p>
              </div>
            </div>
          ))}
        </div>
      </main>
    </div>
  );
}
