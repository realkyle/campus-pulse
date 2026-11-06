"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useWindowWidth } from "@/lib/useWindowWidth";
import { colors } from "@/lib/tokens";

const LINKS = [
  { href: "/home",          label: "Home" },
  { href: "/how-it-works",  label: "How It Works" },
  { href: "/user-guide",    label: "User Guide" },
  { href: "/",              label: "Live Map" },
];

export default function SiteNav() {
  const pathname = usePathname();
  const isMobile = useWindowWidth() < 768;

  if (isMobile) {
    return (
      <nav
        style={{
          width: "100%",
          background: colors.bgBase,
          borderBottom: "1px solid #1e293b",
          display: "flex",
          flexDirection: "row",
          alignItems: "center",
          overflowX: "auto",
          padding: "0 8px",
          flexShrink: 0,
        }}
      >
        {LINKS.map(({ href, label }) => {
          const active = pathname === href;
          return (
            <Link
              key={href}
              href={href}
              style={{
                flexShrink: 0,
                padding: "12px 14px",
                fontSize: 12,
                fontWeight: active ? 600 : 400,
                color: active ? colors.blueLight : colors.textMuted,
                borderBottom: active ? "2px solid #3b82f6" : "2px solid transparent",
                textDecoration: "none",
                whiteSpace: "nowrap",
              }}
            >
              {label}
            </Link>
          );
        })}
      </nav>
    );
  }

  return (
    <nav
      style={{
        width: 200,
        flexShrink: 0,
        background: colors.bgBase,
        borderRight: "1px solid #1e293b",
        display: "flex",
        flexDirection: "column",
        padding: "24px 0",
        minHeight: "100vh",
      }}
    >
      <div style={{ padding: "0 20px 24px" }}>
        <div style={{ fontSize: 13, fontWeight: 700, color: colors.textPrimary }}>
          Campus Pulse
        </div>
        <div style={{ fontSize: 11, color: colors.textDimmer, marginTop: 2 }}>
          Live campus map
        </div>
      </div>

      <div style={{ flex: 1 }}>
        {LINKS.map(({ href, label }) => {
          const active = pathname === href;
          return (
            <Link
              key={href}
              href={href}
              style={{
                display: "block",
                padding: "10px 20px",
                fontSize: 13,
                fontWeight: active ? 600 : 400,
                color: active ? colors.blueLight : colors.textMuted,
                background: active ? colors.bgPanel : "transparent",
                borderLeft: active ? "2px solid #3b82f6" : "2px solid transparent",
                textDecoration: "none",
                transition: "all 0.15s",
              }}
            >
              {label}
            </Link>
          );
        })}
      </div>
    </nav>
  );
}
