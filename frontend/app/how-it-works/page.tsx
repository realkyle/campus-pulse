import SiteNav from "@/components/SiteNav";
import { colors } from "@/lib/tokens";

const LAYERS = [
  {
    number: "01",
    title: "RSS Ingestion Pipeline",
    color: colors.blue,
    details: [
      "Polls the UW Alerts RSS feed every 5 minutes via a FastAPI background task",
      "Caches the last successful fetch with a UTC timestamp",
      'Displays a "Last updated X minutes ago" indicator at all times',
      "If the feed is unreachable, stale cached alerts remain visible with a warning banner",
    ],
    flow: ["UW Alerts RSS Feed", "FastAPI poller (5 min)", "In-memory cache", "Map pins"],
  },
  {
    number: "02",
    title: "NLP Summarizer",
    color: "#10b981",
    details: [
      'Each new RSS item is sent to GPT-4o-mini with a structured prompt requesting JSON: { building_name, incident_type, severity, recommended_action }',
      "The JSON directly drives pin placement — no valid JSON means no structured alert",
      "On API failure or malformed JSON, the raw RSS text is displayed in a fallback pin at campus center",
      '⚠ "Live AI summarization unavailable" banner is shown so users are never silently given stale data',
      "Success threshold: ≥90% valid JSON across a 20-alert test suite",
    ],
    flow: ["Raw RSS text", "GPT-4o-mini prompt", "JSON response", "Building coords lookup", "Colored map pin"],
  },
  {
    number: "03",
    title: "Live Events Feed",
    color: "#a855f7",
    details: [
      "Polls the official UW Bothell Trumba calendar RSS feeds every 60 minutes via a FastAPI background task",
      "Fetches from both the Student Life and Campus-wide calendars, deduplicates by UID",
      "Filters out past events — only future events are surfaced",
      "Category is inferred from event title and description using keyword matching (technology, science, business, arts, health, sports, social)",
      "Falls back to a static catalog of 20 sample events if both feeds are unreachable",
    ],
    flow: ["Trumba RSS (Student Life + Campus)", "feedparser", "Parse + deduplicate", "Category inference", "For You feed"],
  },
  {
    number: "04",
    title: "Event Recommender",
    color: "#f59e0b",
    details: [
      "Student events only: staff/faculty sessions are left out, and each repeating series appears once (its next date)",
      "Hybrid score: the categories you open, other dates of series you opened, what students with similar clicks opened, 7-day popularity, and how soon the event is",
      "Co-click similarity (item-item collaborative filtering) only counts once there are at least 50 clicks in total",
      "Cold start: first-time users see their major's categories first",
      "Every card shows why it was recommended",
      "Search across all fetched events — bypasses recommendation ranking to surface any event by title, description, or category",
    ],
    flow: ["User views/clicks event", "Interaction logged (hashed user ID)", "Hourly click aggregates", "Hybrid score + reason", "For You feed"],
  },
  {
    number: "05",
    title: "UW Authentication",
    color: "#ec4899",
    details: [
      "Login is handled by Auth0 — users click 'Continue with Google' and sign in with their @uw.edu or @washington.edu email",
      "UW Google Workspace enforces Duo MFA as part of the Google sign-in flow — Duo fires before Auth0 receives the session",
      "Non-UW accounts are blocked by an Auth0 Action before a session is created",
      "The entire app is wrapped in Auth0's UserProvider; session state is available to all components",
      "The For You recommendations panel is only rendered when an authenticated session exists",
      "Auth0 user identifier (sub) is SHA-256 hashed client-side and stored in localStorage for the recommender — the raw sub never reaches the database",
    ],
    flow: ["Continue with Google", "UW Google Workspace + Duo", "Auth0 domain check", "Session created", "Hashed sub → recommender"],
  },
  {
    number: "05",
    title: "Database Layer",
    color: colors.medBorder,
    details: [
      "PostgreSQL hosted on Supabase (cloud, RBAC restricted to project team)",
      "Stores only three fields per row: hashed user ID, event ID, interaction timestamp — no PII",
      "Auth0 user identifier (sub) is SHA-256 hashed client-side before storage; raw credentials never touch the database",
      "Row Level Security (RLS) enabled — anon key has no direct table access",
      "Auto-purge via pg_cron: interactions older than 90 days (one quarter) are deleted every Sunday at 3am UTC",
    ],
    flow: ["hashed_netid", "event_id", "timestamp", "Supabase PostgreSQL", "pg_cron purge (weekly)"],
  },
];

export default function HowItWorksPage() {
  return (
    <div style={{ display: "flex", minHeight: "100vh", background: colors.bgBase }}>
      <SiteNav />

      <main style={{ flex: 1, overflowY: "auto", padding: "48px" }}>
        <h1 style={{ fontSize: 28, fontWeight: 800, color: colors.textPrimary, marginBottom: 8 }}>
          How It Works
        </h1>
        <p style={{ fontSize: 14, color: colors.textFaint, marginBottom: 40, maxWidth: 600 }}>
          Campus Pulse is built in four distinct layers. Each layer has a defined
          fallback so the application remains functional even when individual
          components fail.
        </p>

        <div style={{ display: "flex", flexDirection: "column", gap: 32 }}>
          {LAYERS.map((layer) => (
            <div
              key={layer.number}
              style={{
                background: colors.bgPanel,
                border: `1px solid ${layer.color}33`,
                borderLeft: `4px solid ${layer.color}`,
                borderRadius: 10,
                padding: "24px 28px",
              }}
            >
              <div style={{ display: "flex", alignItems: "center", gap: 12, marginBottom: 16 }}>
                <span
                  style={{
                    fontSize: 11,
                    fontWeight: 700,
                    color: layer.color,
                    background: `${layer.color}22`,
                    borderRadius: 4,
                    padding: "3px 8px",
                  }}
                >
                  Layer {layer.number}
                </span>
                <h2 style={{ fontSize: 16, fontWeight: 700, color: colors.textPrimary }}>
                  {layer.title}
                </h2>
              </div>

              <div
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: 0,
                  marginBottom: 20,
                  overflowX: "auto",
                  paddingBottom: 4,
                }}
              >
                {layer.flow.map((step, i) => (
                  <div key={i} style={{ display: "flex", alignItems: "center", flexShrink: 0 }}>
                    <div
                      style={{
                        background: colors.bgBase,
                        border: `1px solid ${layer.color}55`,
                        borderRadius: 6,
                        padding: "6px 12px",
                        fontSize: 11,
                        color: "#cbd5e1",
                        whiteSpace: "nowrap",
                      }}
                    >
                      {step}
                    </div>
                    {i < layer.flow.length - 1 && (
                      <span style={{ color: layer.color, fontSize: 14, margin: "0 6px" }}>→</span>
                    )}
                  </div>
                ))}
              </div>

              <ul style={{ margin: 0, padding: 0, listStyle: "none" }}>
                {layer.details.map((detail, i) => (
                  <li
                    key={i}
                    style={{
                      fontSize: 13,
                      color: colors.textMuted,
                      lineHeight: 1.6,
                      paddingLeft: 16,
                      position: "relative",
                      marginBottom: 6,
                    }}
                  >
                    <span style={{ position: "absolute", left: 0, color: layer.color, fontWeight: 700 }}>·</span>
                    {detail}
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </div>
      </main>
    </div>
  );
}
