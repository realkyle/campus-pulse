"use client";

import { useEffect, useRef, useState } from "react";
import { fetchAsUser } from "@/lib/api";
import { useWindowWidth } from "@/lib/useWindowWidth";
import { colors } from "@/lib/tokens";

interface Event {
  id: string;
  title: string;
  category: string;
  building: string;
  date: string;
  description: string;
  url?: string;
}

interface Props {
  major: string | null;
  onMajorChange: (major: string) => void;
}

const CATEGORY_COLOR: Record<string, string> = {
  technology: "#3b82f6",
  science:    "#10b981",
  business:   "#f59e0b",
  arts:       "#a855f7",
  health:     "#ec4899",
  social:     "#06b6d4",
  sports:     "#ef4444",
};

const MODE_LABEL: Record<string, string> = {
  "cold-start":              "Seeded by major",
  "popularity":              "Trending on campus",
  "collaborative-filtering": "Personalized for you",
};

export default function RecommendationsPanel({ major, onMajorChange }: Props) {
  const isMobile = useWindowWidth() < 768;
  const [events, setEvents] = useState<Event[]>([]);
  const [mode, setMode] = useState("");
  const [loading, setLoading] = useState(true);
  const [majorInput, setMajorInput] = useState(major ?? "");
  const [clickedIds, setClickedIds] = useState<Set<string>>(new Set());
  const [search, setSearch] = useState("");
  const [selectedCategory, setSelectedCategory] = useState<string | null>(null);
  const [displayCount, setDisplayCount] = useState(10);
  const sentinelRef = useRef<HTMLDivElement>(null);

  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetchRecommendations();
  }, [major]);

  async function fetchRecommendations() {
    setLoading(true);
    setDisplayCount(10);
    setSelectedCategory(null);
    setError(null);
    try {
      const params = new URLSearchParams({ limit: "200" });
      if (major) params.set("major", major);
      const res = await fetchAsUser(`/api/recommendations?${params}`);
      if (!res.ok) {
        setEvents([]);
        setError(
          res.status === 401 ? "Your session expired. Please sign in again."
          : res.status === 403 ? "For You is only available to UW accounts."
          : "Recommendations are unavailable right now."
        );
        return;
      }
      const json = await res.json();
      setEvents(json.events ?? []);
      setMode(json.mode ?? "");
    } catch {
      setEvents([]);
      setError("Your session expired. Please sign in again.");
    } finally {
      setLoading(false);
    }
  }

  function handleEventClick(event: Event) {
    // Open the link synchronously inside the click: browsers (notably Safari)
    // block window.open after an await.
    if (event.url) window.open(event.url, "_blank", "noopener,noreferrer");
    setClickedIds((prev) => new Set(prev).add(event.id));
    // Recording the click is best-effort and must not delay or block the link.
    fetchAsUser("/api/interactions", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ event_id: event.id }),
    }).catch(() => {});
  }

  function handleMajorSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (majorInput.trim()) onMajorChange(majorInput.trim());
  }

  // Derive available categories from fetched events
  const availableCategories = Array.from(new Set(events.map((e) => e.category))).sort();

  // Apply category + search filters across all events, then paginate
  const categoryFiltered = selectedCategory
    ? events.filter((e) => e.category === selectedCategory)
    : events;

  const filteredEvents = search.trim()
    ? categoryFiltered.filter((e) =>
        e.title.toLowerCase().includes(search.toLowerCase()) ||
        e.description.toLowerCase().includes(search.toLowerCase()) ||
        e.category.toLowerCase().includes(search.toLowerCase())
      )
    : categoryFiltered.slice(0, displayCount);

  const hasMore = !search.trim() && displayCount < categoryFiltered.length;

  // Infinite scroll — load next 10 when sentinel comes into view
  useEffect(() => {
    if (!sentinelRef.current) return;
    const observer = new IntersectionObserver(
      (entries) => {
        if (entries[0].isIntersecting && hasMore) {
          setDisplayCount((prev) => Math.min(prev + 10, events.length));
        }
      },
      { threshold: 0.1 }
    );
    observer.observe(sentinelRef.current);
    return () => observer.disconnect();
  }, [hasMore, events.length]);

  return (
    <aside
      style={{
        width: isMobile ? "100%" : 280,
        height: isMobile ? "40vh" : "auto",
        flexShrink: 0,
        background: colors.bgBase,
        borderLeft: isMobile ? "none" : `1px solid ${colors.bgPanel}`,
        borderTop: isMobile ? `1px solid ${colors.bgPanel}` : "none",
        display: "flex",
        flexDirection: "column",
        overflow: "hidden",
      }}
    >
      {/* Panel header */}
      <div
        style={{
          padding: "14px 16px 10px",
          borderBottom: `1px solid ${colors.bgPanel}`,
          flexShrink: 0,
        }}
      >
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
          <div style={{ display: "flex", alignItems: "baseline", gap: 8 }}>
            <h2 style={{ fontSize: 13, fontWeight: 700, color: colors.textPrimary }}>For You</h2>
            {!loading && events.length > 0 && (
              <span style={{ fontSize: 10, color: colors.textFaint }}>
                {search.trim() || selectedCategory
                  ? `${filteredEvents.length} result${filteredEvents.length !== 1 ? "s" : ""}`
                  : `${Math.min(displayCount, events.length)} of ${events.length}`}
              </span>
            )}
          </div>
          {mode && (
            <span style={{ fontSize: 10, color: colors.textMuted, background: colors.bgPanel, borderRadius: 10, padding: "2px 8px" }}>
              {MODE_LABEL[mode] ?? mode}
            </span>
          )}
        </div>

        <form onSubmit={handleMajorSubmit} style={{ marginTop: 8, display: "flex", gap: 6 }}>
          <input
            type="text"
            placeholder="Your major (optional)"
            value={majorInput}
            onChange={(e) => setMajorInput(e.target.value)}
            style={{
              flex: 1,
              fontSize: 11,
              padding: "5px 8px",
              background: colors.bgPanel,
              border: `1px solid ${colors.border}`,
              borderRadius: 4,
              color: colors.textPrimary,
            }}
          />
          <button
            type="submit"
            style={{
              fontSize: 11,
              padding: "5px 8px",
              background: colors.border,
              border: "none",
              borderRadius: 4,
              color: colors.textMuted,
              cursor: "pointer",
            }}
          >
            Set
          </button>
        </form>

        <div style={{ marginTop: 8, position: "relative" }}>
          <input
            type="text"
            placeholder="Search events…"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            style={{
              width: "100%",
              fontSize: 11,
              padding: "5px 24px 5px 8px",
              background: colors.bgPanel,
              border: `1px solid ${colors.border}`,
              borderRadius: 4,
              color: colors.textPrimary,
              boxSizing: "border-box",
            }}
          />
          {search && (
            <button
              onClick={() => setSearch("")}
              style={{
                position: "absolute",
                right: 6,
                top: "50%",
                transform: "translateY(-50%)",
                background: "transparent",
                border: "none",
                color: colors.textFaint,
                fontSize: 12,
                cursor: "pointer",
                padding: 0,
                lineHeight: 1,
              }}
            >
              ✕
            </button>
          )}
        </div>
      </div>

      {/* Category filter chips */}
      {!loading && availableCategories.length > 0 && (
        <div style={{ padding: "6px 16px 8px", display: "flex", gap: 6, flexWrap: "wrap", borderBottom: `1px solid ${colors.bgPanel}` }}>
          <button
            onClick={() => { setSelectedCategory(null); setDisplayCount(10); }}
            style={{
              fontSize: 10, fontWeight: 600, padding: "3px 8px", borderRadius: 10, cursor: "pointer",
              background: selectedCategory === null ? colors.blue : colors.bgPanel,
              color: selectedCategory === null ? "#fff" : colors.textMuted,
              border: `1px solid ${selectedCategory === null ? colors.blue : colors.border}`,
            }}
          >
            All
          </button>
          {availableCategories.map((cat) => {
            const catColor = CATEGORY_COLOR[cat] ?? colors.textFaint;
            const active = selectedCategory === cat;
            return (
              <button
                key={cat}
                onClick={() => { setSelectedCategory(active ? null : cat); setDisplayCount(10); }}
                style={{
                  fontSize: 10, fontWeight: 600, padding: "3px 8px", borderRadius: 10, cursor: "pointer",
                  textTransform: "capitalize",
                  background: active ? `${catColor}22` : colors.bgPanel,
                  color: active ? catColor : colors.textMuted,
                  border: `1px solid ${active ? catColor : colors.border}`,
                }}
              >
                {cat}
              </button>
            );
          })}
        </div>
      )}

      {/* Event list */}
      <div style={{ flex: 1, overflowY: "auto" }}>
        {loading ? (
          <div style={{ padding: 16, fontSize: 12, color: colors.textDimmer, textAlign: "center" }}>
            Loading recommendations…
          </div>
        ) : filteredEvents.length === 0 ? (
          <div style={{ padding: 16, fontSize: 12, color: colors.textDimmer, textAlign: "center" }}>
            {error ?? (search ? `No events matching "${search}"` : "No events available right now.")}
          </div>
        ) : (
          filteredEvents.map((event) => {
            const clicked = clickedIds.has(event.id);
            const catColor = CATEGORY_COLOR[event.category] ?? colors.textFaint;
            return (
              <div
                key={event.id}
                onClick={() => handleEventClick(event)}
                style={{
                  padding: "12px 16px",
                  borderBottom: `1px solid ${colors.bgPanel}`,
                  cursor: "pointer",
                  background: clicked ? colors.bgClicked : "transparent",
                  transition: "background 0.15s",
                }}
                onMouseEnter={(e) => {
                  if (!clicked) (e.currentTarget as HTMLDivElement).style.background = colors.bgPanel;
                }}
                onMouseLeave={(e) => {
                  (e.currentTarget as HTMLDivElement).style.background = clicked ? colors.bgClicked : "transparent";
                }}
              >
                <div style={{ display: "flex", alignItems: "flex-start", gap: 8, marginBottom: 4 }}>
                  <span
                    style={{
                      fontSize: 9,
                      fontWeight: 700,
                      color: catColor,
                      background: `${catColor}22`,
                      border: `1px solid ${catColor}44`,
                      borderRadius: 4,
                      padding: "2px 6px",
                      whiteSpace: "nowrap",
                      marginTop: 1,
                      textTransform: "uppercase",
                    }}
                  >
                    {event.category}
                  </span>
                  {clicked && (
                    <span style={{ fontSize: 9, color: colors.lowBorder, marginTop: 2 }}>viewed</span>
                  )}
                  {event.url && (
                    <span style={{ fontSize: 9, color: colors.textFaint, marginTop: 2, marginLeft: "auto" }}>↗ details</span>
                  )}
                </div>
                <div style={{ fontSize: 12, fontWeight: 600, color: colors.textSecondary, marginBottom: 4, lineHeight: 1.3 }}>
                  {event.title}
                </div>
                <div style={{ fontSize: 11, color: colors.textFaint }}>
                  {event.building} · {event.date}
                </div>
                <div style={{ fontSize: 11, color: colors.textDimmer, marginTop: 4, lineHeight: 1.4 }}>
                  {event.description}
                </div>
              </div>
            );
          })
        )}

        {/* Sentinel must be inside the scrollable div to trigger IntersectionObserver */}
        {hasMore && (
          <div
            ref={sentinelRef}
            style={{ padding: "10px 16px", textAlign: "center", fontSize: 11, color: colors.textFaint }}
          >
            Loading more… ({events.length - displayCount} remaining)
          </div>
        )}
      </div>

      <div
        style={{
          padding: "8px 16px",
          borderTop: `1px solid ${colors.bgPanel}`,
          fontSize: 10,
          color: colors.border,
          flexShrink: 0,
        }}
      >
        Click an event to log your interest
      </div>
    </aside>
  );
}
