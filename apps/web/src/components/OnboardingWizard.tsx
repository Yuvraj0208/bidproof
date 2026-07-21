// Onboarding wizard (US-17, SPEC §15): a new company goes live without a
// developer. Five steps — company → facts CSV → product catalogue CSV →
// categories + weights → branding — then it lands in the product with its org
// id set. The parent owns the API calls; this component owns the flow.
import { useState } from "react";
import { FACTS_CSV_TEMPLATE_URL, PRODUCTS_CSV_TEMPLATE_URL } from "../api";

export interface ProfilePayload {
  categories: { name: string; keywords: string[] }[];
  weights: Record<string, number>;
  value_band_inr: { min_inr?: number; max_inr?: number };
  locations: string[];
  win_categories: string[];
}

export interface OnboardingWizardProps {
  onCreateOrg: (name: string, slug: string) => Promise<{ org_id: string }>;
  onUploadFacts: (csv: string) => Promise<number>;
  onUploadProducts: (csv: string) => Promise<number>;
  onSaveProfile: (profile: ProfilePayload) => Promise<void>;
  onFinish: (branding: {
    primary_color?: string;
    logo_url?: string;
  }) => Promise<void>;
  onDone: (orgId: string) => void;
  onCancel?: () => void;
}

const STEPS = [
  "Company",
  "Company facts",
  "Product catalogue",
  "Categories & weights",
  "Branding",
] as const;

const DEFAULT_WEIGHTS: Record<string, number> = {
  category_fit: 0.4,
  value_band: 0.3,
  past_wins: 0.3,
};

function Stepper({ step }: { step: number }) {
  return (
    <ol className="mb-5 flex flex-wrap gap-2 text-xs">
      {STEPS.map((label, i) => (
        <li
          key={label}
          className={`rounded px-2 py-1 ${
            i + 1 === step
              ? "bg-indigo-600 font-medium text-white"
              : i + 1 < step
                ? "bg-emerald-100 text-emerald-800"
                : "bg-slate-100 text-slate-400"
          }`}
        >
          {i + 1 < step ? "✓ " : `${i + 1}. `}
          {label}
        </li>
      ))}
    </ol>
  );
}

function csvUploadArea(
  id: string,
  templateUrl: string,
  value: string,
  onChange: (v: string) => void,
) {
  return (
    <>
      <div className="mb-2 flex items-center gap-3 text-xs text-slate-500">
        <a href={templateUrl} className="text-indigo-600 hover:underline">
          Download CSV template
        </a>
        <span>· or paste rows below · or</span>
        <label className="cursor-pointer text-indigo-600 hover:underline">
          choose a file
          <input
            type="file"
            accept=".csv,text/csv"
            className="hidden"
            onChange={async (e) => {
              const file = e.target.files?.[0];
              if (file) onChange(await file.text());
            }}
          />
        </label>
      </div>
      <textarea
        data-testid={id}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        rows={6}
        placeholder="paste CSV rows here"
        className="w-full rounded border p-2 font-mono text-xs"
      />
    </>
  );
}

export function OnboardingWizard(props: OnboardingWizardProps) {
  const [step, setStep] = useState(1);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [orgId, setOrgId] = useState<string | null>(null);
  const [name, setName] = useState("");
  const [slug, setSlug] = useState("");

  const [factsCsv, setFactsCsv] = useState("");
  const [factsLoaded, setFactsLoaded] = useState<number | null>(null);
  const [productsCsv, setProductsCsv] = useState("");
  const [productsLoaded, setProductsLoaded] = useState<number | null>(null);

  const [categories, setCategories] = useState<
    { name: string; keywords: string[] }[]
  >([]);
  const [catName, setCatName] = useState("");
  const [catKeywords, setCatKeywords] = useState("");
  const [bandMin, setBandMin] = useState("");
  const [bandMax, setBandMax] = useState("");

  const [color, setColor] = useState("");
  const [logo, setLogo] = useState("");

  async function guard(fn: () => Promise<void>) {
    setBusy(true);
    setError(null);
    try {
      await fn();
    } catch (e) {
      setError(String(e instanceof Error ? e.message : e));
    } finally {
      setBusy(false);
    }
  }

  const createOrg = () =>
    guard(async () => {
      const { org_id } = await props.onCreateOrg(name.trim(), slug.trim());
      setOrgId(org_id);
      setStep(2);
    });

  const uploadFacts = () =>
    guard(async () => setFactsLoaded(await props.onUploadFacts(factsCsv)));

  const uploadProducts = () =>
    guard(async () => setProductsLoaded(await props.onUploadProducts(productsCsv)));

  const addCategory = () => {
    const nm = catName.trim();
    if (!nm) return;
    const keywords = catKeywords
      .split(",")
      .map((k) => k.trim())
      .filter(Boolean);
    setCategories((c) => [...c, { name: nm, keywords }]);
    setCatName("");
    setCatKeywords("");
  };

  const saveProfile = () =>
    guard(async () => {
      const value_band_inr: { min_inr?: number; max_inr?: number } = {};
      if (bandMin) value_band_inr.min_inr = Number(bandMin);
      if (bandMax) value_band_inr.max_inr = Number(bandMax);
      await props.onSaveProfile({
        categories,
        weights: DEFAULT_WEIGHTS,
        value_band_inr,
        locations: [],
        win_categories: categories.map((c) => c.name),
      });
      setStep(5);
    });

  const finish = () =>
    guard(async () => {
      const branding: { primary_color?: string; logo_url?: string } = {};
      if (color.trim()) branding.primary_color = color.trim();
      if (logo.trim()) branding.logo_url = logo.trim();
      await props.onFinish(branding);
      if (orgId) props.onDone(orgId);
    });

  return (
    <div className="mx-auto max-w-2xl p-6">
      <div className="mb-4 flex items-center gap-3">
        <h1 className="text-lg font-semibold text-indigo-900">
          Welcome to BidProof
        </h1>
        <span className="text-xs text-slate-400">
          Get your company live — no developer needed
        </span>
        {props.onCancel && (
          <button
            onClick={props.onCancel}
            className="ml-auto rounded border px-2 py-1 text-xs text-slate-500 hover:bg-slate-50"
          >
            Cancel
          </button>
        )}
      </div>

      <Stepper step={step} />

      <div className="rounded-lg border bg-white p-5 shadow-sm">
        <h2
          data-testid="wizard-step"
          className="mb-3 text-sm font-semibold text-slate-800"
        >
          Step {step} of {STEPS.length} — {STEPS[step - 1]}
        </h2>

        {error && (
          <p className="mb-3 rounded bg-red-50 px-3 py-2 text-sm text-red-700">
            {error}
          </p>
        )}

        {step === 1 && (
          <div className="space-y-3">
            <label className="block text-xs text-slate-500">
              Company name
              <input
                data-testid="org-name"
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder="Newco Pvt Ltd"
                className="mt-1 w-full rounded border px-2 py-1 text-sm"
              />
            </label>
            <label className="block text-xs text-slate-500">
              URL slug (lowercase, letters/numbers/hyphens)
              <input
                data-testid="org-slug"
                value={slug}
                onChange={(e) =>
                  setSlug(e.target.value.toLowerCase().replace(/[^a-z0-9-]/g, "-"))
                }
                placeholder="newco"
                className="mt-1 w-full rounded border px-2 py-1 font-mono text-sm"
              />
            </label>
            <button
              onClick={createOrg}
              disabled={busy || name.trim().length < 2 || slug.trim().length < 2}
              className="rounded bg-indigo-600 px-3 py-1.5 text-sm font-medium text-white disabled:opacity-50"
            >
              {busy ? "Creating…" : "Create organisation"}
            </button>
          </div>
        )}

        {step === 2 && (
          <div className="space-y-3">
            <p className="text-xs text-slate-500">
              Your turnover, certifications, MSME status, blacklist status — the
              facts every eligibility rule is checked against.
            </p>
            {csvUploadArea("facts-csv", FACTS_CSV_TEMPLATE_URL, factsCsv, setFactsCsv)}
            <div className="flex items-center gap-3">
              <button
                onClick={uploadFacts}
                disabled={busy || !factsCsv.trim()}
                className="rounded border border-indigo-600 px-3 py-1.5 text-sm text-indigo-700 disabled:opacity-50"
              >
                {busy ? "Uploading…" : "Upload facts"}
              </button>
              {factsLoaded != null && (
                <span
                  data-testid="facts-loaded"
                  className="text-sm text-emerald-700"
                >
                  ✓ {factsLoaded} facts loaded
                </span>
              )}
              <button
                onClick={() => setStep(3)}
                disabled={factsLoaded == null}
                className="ml-auto rounded bg-indigo-600 px-3 py-1.5 text-sm font-medium text-white disabled:opacity-50"
              >
                Next →
              </button>
            </div>
          </div>
        )}

        {step === 3 && (
          <div className="space-y-3">
            <p className="text-xs text-slate-500">
              Your product catalogue — codes, standards, lead times, capacity,
              price bands. This is what every tender is matched against.
            </p>
            {csvUploadArea(
              "products-csv",
              PRODUCTS_CSV_TEMPLATE_URL,
              productsCsv,
              setProductsCsv,
            )}
            <div className="flex items-center gap-3">
              <button
                onClick={uploadProducts}
                disabled={busy || !productsCsv.trim()}
                className="rounded border border-indigo-600 px-3 py-1.5 text-sm text-indigo-700 disabled:opacity-50"
              >
                {busy ? "Uploading…" : "Upload catalogue"}
              </button>
              {productsLoaded != null && (
                <span
                  data-testid="products-loaded"
                  className="text-sm text-emerald-700"
                >
                  ✓ {productsLoaded}{" "}
                  {productsLoaded === 1 ? "product loaded" : "products loaded"}
                </span>
              )}
              <button
                onClick={() => setStep(4)}
                disabled={productsLoaded == null}
                className="ml-auto rounded bg-indigo-600 px-3 py-1.5 text-sm font-medium text-white disabled:opacity-50"
              >
                Next →
              </button>
            </div>
          </div>
        )}

        {step === 4 && (
          <div className="space-y-3">
            <p className="text-xs text-slate-500">
              The tender categories you bid in. Keywords steer the radar; the
              default weights below are a sensible start and can be tuned later.
            </p>
            <div className="grid grid-cols-2 gap-2">
              <input
                data-testid="category-name"
                value={catName}
                onChange={(e) => setCatName(e.target.value)}
                placeholder="storage racks"
                className="rounded border px-2 py-1 text-sm"
              />
              <input
                data-testid="category-keywords"
                value={catKeywords}
                onChange={(e) => setCatKeywords(e.target.value)}
                placeholder="storage, rack, warehouse"
                className="rounded border px-2 py-1 text-sm"
              />
            </div>
            <button
              onClick={addCategory}
              className="rounded border px-3 py-1 text-sm text-slate-600 hover:bg-slate-50"
            >
              + Add category
            </button>
            <ul
              data-testid="category-list"
              className="flex flex-wrap gap-1.5 text-xs"
            >
              {categories.map((c) => (
                <li
                  key={c.name}
                  className="rounded bg-slate-100 px-2 py-0.5 text-slate-700"
                >
                  {c.name}
                  {c.keywords.length > 0 && (
                    <span className="text-slate-400"> · {c.keywords.join(", ")}</span>
                  )}
                </li>
              ))}
            </ul>
            <div className="grid grid-cols-2 gap-2">
              <label className="text-xs text-slate-500">
                Value band min (₹)
                <input
                  value={bandMin}
                  onChange={(e) => setBandMin(e.target.value.replace(/[^0-9]/g, ""))}
                  placeholder="1000000"
                  className="mt-1 w-full rounded border px-2 py-1 font-mono text-sm"
                />
              </label>
              <label className="text-xs text-slate-500">
                Value band max (₹)
                <input
                  value={bandMax}
                  onChange={(e) => setBandMax(e.target.value.replace(/[^0-9]/g, ""))}
                  placeholder="1000000000"
                  className="mt-1 w-full rounded border px-2 py-1 font-mono text-sm"
                />
              </label>
            </div>
            <div className="flex justify-end">
              <button
                onClick={saveProfile}
                disabled={busy || categories.length === 0}
                className="rounded bg-indigo-600 px-3 py-1.5 text-sm font-medium text-white disabled:opacity-50"
              >
                {busy ? "Saving…" : "Save & continue →"}
              </button>
            </div>
          </div>
        )}

        {step === 5 && (
          <div className="space-y-3">
            <p className="text-xs text-slate-500">
              Optional brand touches for your proposals. You can skip and add
              these later.
            </p>
            <label className="block text-xs text-slate-500">
              Primary colour
              <input
                data-testid="primary-color"
                value={color}
                onChange={(e) => setColor(e.target.value)}
                placeholder="#4B0082"
                className="mt-1 w-full rounded border px-2 py-1 font-mono text-sm"
              />
            </label>
            <label className="block text-xs text-slate-500">
              Logo URL
              <input
                value={logo}
                onChange={(e) => setLogo(e.target.value)}
                placeholder="https://…/logo.png"
                className="mt-1 w-full rounded border px-2 py-1 text-sm"
              />
            </label>
            <div className="flex justify-end">
              <button
                onClick={finish}
                disabled={busy}
                className="rounded bg-emerald-600 px-4 py-1.5 text-sm font-medium text-white disabled:opacity-50"
              >
                {busy ? "Finishing…" : "Finish — take me in"}
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
