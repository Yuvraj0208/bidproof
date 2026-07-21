// US-17: a new company onboards without a developer through a 5-step wizard —
// company → facts CSV → product catalogue CSV → categories + weights →
// branding — and lands in the product with its org id set.
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { OnboardingWizard, type ProfilePayload } from "./OnboardingWizard";

function handlers(over: Record<string, unknown> = {}) {
  return {
    onCreateOrg: vi.fn(async (_name: string, _slug: string) => ({
      org_id: "org-123",
    })),
    onUploadFacts: vi.fn(async (_csv: string) => 3),
    onUploadProducts: vi.fn(async (_csv: string) => 1),
    onSaveProfile: vi.fn(async (_p: ProfilePayload) => {}),
    onFinish: vi.fn(
      async (_b: { primary_color?: string; logo_url?: string }) => {},
    ),
    onDone: vi.fn((_orgId: string) => {}),
    ...over,
  };
}

describe("OnboardingWizard", () => {
  it("walks the five steps and finishes with the new org id", async () => {
    const h = handlers();
    render(<OnboardingWizard {...h} />);

    // Step 1 — company
    expect(screen.getByTestId("wizard-step")).toHaveTextContent(/company/i);
    fireEvent.change(screen.getByTestId("org-name"), {
      target: { value: "Newco Pvt Ltd" },
    });
    fireEvent.change(screen.getByTestId("org-slug"), {
      target: { value: "newco" },
    });
    fireEvent.click(screen.getByRole("button", { name: /create organisation/i }));
    await waitFor(() =>
      expect(h.onCreateOrg).toHaveBeenCalledWith("Newco Pvt Ltd", "newco"),
    );

    // Step 2 — company facts
    await screen.findByTestId("facts-csv");
    fireEvent.change(screen.getByTestId("facts-csv"), {
      target: { value: "fact_type\nturnover" },
    });
    fireEvent.click(screen.getByRole("button", { name: /upload facts/i }));
    await screen.findByText(/3 facts loaded/i);
    fireEvent.click(screen.getByRole("button", { name: /next/i }));

    // Step 3 — product catalogue
    await screen.findByTestId("products-csv");
    fireEvent.change(screen.getByTestId("products-csv"), {
      target: { value: "product_code,product_name\nR-1,Rack" },
    });
    fireEvent.click(screen.getByRole("button", { name: /upload catalogue/i }));
    await screen.findByText(/1 product loaded/i);
    fireEvent.click(screen.getByRole("button", { name: /next/i }));

    // Step 4 — categories + weights
    await screen.findByTestId("category-name");
    fireEvent.change(screen.getByTestId("category-name"), {
      target: { value: "storage racks" },
    });
    fireEvent.change(screen.getByTestId("category-keywords"), {
      target: { value: "storage, rack, warehouse" },
    });
    fireEvent.click(screen.getByRole("button", { name: /add category/i }));
    expect(screen.getByTestId("category-list")).toHaveTextContent("storage racks");
    fireEvent.click(screen.getByRole("button", { name: /save & continue/i }));
    await waitFor(() => expect(h.onSaveProfile).toHaveBeenCalled());
    const profile = h.onSaveProfile.mock.calls[0][0];
    expect(profile.categories[0].name).toBe("storage racks");
    expect(profile.categories[0].keywords).toEqual([
      "storage",
      "rack",
      "warehouse",
    ]);

    // Step 5 — branding → finish
    await screen.findByTestId("primary-color");
    fireEvent.change(screen.getByTestId("primary-color"), {
      target: { value: "#4B0082" },
    });
    fireEvent.click(screen.getByRole("button", { name: /finish/i }));
    await waitFor(() =>
      expect(h.onFinish).toHaveBeenCalledWith({ primary_color: "#4B0082" }),
    );
    expect(h.onDone).toHaveBeenCalledWith("org-123");
  });

  it("cannot leave step 1 without a name and slug", () => {
    const h = handlers();
    render(<OnboardingWizard {...h} />);
    expect(
      screen.getByRole("button", { name: /create organisation/i }),
    ).toBeDisabled();
  });

  it("surfaces a duplicate-slug error and stays on step 1", async () => {
    const h = handlers({
      onCreateOrg: vi.fn(async () => {
        throw new Error("slug 'newco' is already taken");
      }),
    });
    render(<OnboardingWizard {...h} />);
    fireEvent.change(screen.getByTestId("org-name"), {
      target: { value: "Newco Pvt Ltd" },
    });
    fireEvent.change(screen.getByTestId("org-slug"), {
      target: { value: "newco" },
    });
    fireEvent.click(screen.getByRole("button", { name: /create organisation/i }));
    await screen.findByText(/already taken/i);
    expect(screen.getByTestId("wizard-step")).toHaveTextContent(/company/i);
    expect(h.onDone).not.toHaveBeenCalled();
  });
});
