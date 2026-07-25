// The signed-in company's mark, shown in the shell so it is always obvious
// whose workspace you are in.
//
// If the organisation supplied a `logo_url` during onboarding, that is shown.
// Otherwise we render a monogram in the company's own brand colour — we do NOT
// go and fetch a logo from the web on a company's behalf: their brand assets are
// theirs to provide (SPEC §17, "ask each tenant for a brand kit").
import { useState } from "react";
import type { OrgSummary } from "../api";

/** Initials from a company name: "Godrej Enterprises Group" → "GE". */
export function monogram(name: string): string {
  const words = name
    .replace(/\b(pvt|ltd|limited|inc|llp|co|group|the|and|&)\b/gi, " ")
    .split(/\s+/)
    .filter(Boolean);
  if (!words.length) return name.slice(0, 2).toUpperCase() || "?";
  if (words.length === 1) return words[0].slice(0, 2).toUpperCase();
  return (words[0][0] + words[1][0]).toUpperCase();
}

export function OrgBadge({
  org,
  size = 28,
  onDark = false,
}: {
  org: Pick<OrgSummary, "name" | "branding">;
  size?: number;
  onDark?: boolean;
}) {
  const [logoFailed, setLogoFailed] = useState(false);
  const logo = org.branding?.logo_url;
  const brand = org.branding?.primary_color;

  if (logo && !logoFailed) {
    return (
      <img
        data-testid="org-badge"
        src={logo}
        alt={org.name}
        onError={() => setLogoFailed(true)}
        style={{ width: size, height: size }}
        className="shrink-0 rounded-[8px] bg-white object-contain p-0.5"
      />
    );
  }

  return (
    <span
      data-testid="org-badge"
      title={org.name}
      style={{
        width: size,
        height: size,
        background: brand ?? (onDark ? "rgba(255,255,255,0.14)" : undefined),
        fontSize: Math.max(10, size * 0.4),
      }}
      className={`inline-flex shrink-0 items-center justify-center rounded-[8px] font-semibold tracking-tight ${
        brand || onDark ? "text-white" : "bg-indigo-tint text-indigo"
      }`}
    >
      {monogram(org.name)}
    </span>
  );
}
