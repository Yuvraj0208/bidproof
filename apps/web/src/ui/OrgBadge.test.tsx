// The signed-in company must always be identifiable in the shell: their own
// logo when they gave us one, a branded monogram when they did not.
import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { OrgBadge, monogram } from "./OrgBadge";

describe("monogram", () => {
  it("takes the initials of the meaningful words", () => {
    expect(monogram("Godrej Enterprises Group")).toBe("GE");
    expect(monogram("Demo Storage Co")).toBe("DS");
  });

  it("ignores corporate suffixes", () => {
    // "Pvt"/"Ltd" carry no identity — "NP", not "NP" from "Newco Pvt".
    expect(monogram("Newco Pvt Ltd")).toBe("NE");
  });

  it("copes with a single word or an empty name", () => {
    expect(monogram("Godrej")).toBe("GO");
    expect(monogram("")).toBe("?");
  });
});

describe("OrgBadge", () => {
  it("shows the company's logo when one was supplied", () => {
    render(
      <OrgBadge org={{ name: "Godrej", branding: { logo_url: "https://x/logo.png" } }} />,
    );
    expect(screen.getByTestId("org-badge").tagName).toBe("IMG");
  });

  it("falls back to a monogram when no logo is supplied", () => {
    render(<OrgBadge org={{ name: "Godrej Enterprises Group", branding: {} }} />);
    const badge = screen.getByTestId("org-badge");
    expect(badge.tagName).not.toBe("IMG");
    expect(badge).toHaveTextContent("GE");
  });

  it("paints the monogram in the company's own brand colour", () => {
    render(
      <OrgBadge org={{ name: "Godrej", branding: { primary_color: "#0a5c36" } }} />,
    );
    expect(screen.getByTestId("org-badge")).toHaveStyle({
      background: "#0a5c36",
    });
  });
});
