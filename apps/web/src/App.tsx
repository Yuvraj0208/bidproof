// Tender Radar (SPEC §17 screen 1) — the home screen.
//
// Two lists Priya lives in (In our lane / Opportunity radar) plus the
// Checkpoint-0 queue. Every card explains itself: fit, why it matched, its
// countdown, and the confidence chip. The default next action sits top-right.
import { useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import {
  createOrg,
  fetchRadar,
  getOrgId,
  getRole,
  ROLES,
  runCheck,
  runDiscovery,
  runExtraction,
  saveBranding,
  saveOnboardingProfile,
  setOrgId,
  setRole,
  uploadFactsCsv,
  uploadProductsCsv,
  uploadTender,
  type RadarCard,
  type RoleName,
} from "./api";
import { ConfidenceChip } from "./components/ConfidenceChip";
import { OnboardingWizard } from "./components/OnboardingWizard";
import { CountdownChip, Pill } from "./ui/chips";
import { useToast } from "./ui/overlays";
import {
  Button,
  Card,
  EmptyState,
  PageHeader,
  SkeletonLoader,
} from "./ui/primitives";

const TABS = [
  { id: "in_our_lane", label: "In our lane" },
  { id: "opportunity_radar", label: "Opportunity radar" },
  { id: "needs_human", label: "Needs human" },
] as const;

export default function App({
  onOpenTender,
  startOnboarding = false,
}: {
  onOpenTender?: (tender: { id: string; title: string }) => void;
  startOnboarding?: boolean;
}) {
  const navigate = useNavigate();
  const { push } = useToast();

  const [org, setOrg] = useState(getOrgId());
  const [role, setRoleState] = useState<RoleName>(getRole());
  const [tab, setTab] = useState<string>("in_our_lane");
  const [cards, setCards] = useState<RadarCard[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [onboarding, setOnboarding] = useState(startOnboarding);
  const [busy, setBusy] = useState<string | null>(null);
  const [refresh, setRefresh] = useState(0);
  const fileInput = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (!org) {
      setCards([]);
      return;
    }
    setLoading(true);
    setError(null);
    fetchRadar(tab)
      .then(setCards)
      .catch((e) => {
        setCards([]);
        setError(String(e));
      })
      .finally(() => setLoading(false));
  }, [org, tab, refresh]);

  const open = (card: { tender_id: string; title: string }) => {
    onOpenTender?.({ id: card.tender_id, title: card.title });
    navigate(`/workspace/${card.tender_id}`);
  };

  const onUpload = async (file: File) => {
    setBusy(`Uploading ${file.name}…`);
    try {
      const { tender_id } = await uploadTender(file);
      setBusy("Extracting rules…");
      await runExtraction(tender_id);
      setBusy("Checking against your capability…");
      await runCheck(tender_id);
      push(`${file.name} read and checked.`, "success");
      open({ tender_id, title: file.name });
    } catch (e) {
      push(`Upload failed: ${String(e)}`, "danger");
    } finally {
      setBusy(null);
    }
  };

  const onScrape = async () => {
    setBusy("Scraping portals…");
    try {
      const result = await runDiscovery();
      const ingested = result.runs.reduce((n, r) => n + r.ingested, 0);
      const ok = result.runs.filter((r) => r.ok).map((r) => r.adapter);
      const failed = result.runs.filter((r) => !r.ok).map((r) => r.adapter);
      push(
        `Scraped ${ingested} tender(s) from ${ok.join(", ") || "no"} portal(s)` +
          (failed.length ? ` · unavailable: ${failed.join(", ")}` : ""),
        failed.length ? "warning" : "success",
      );
      setRefresh((n) => n + 1);
    } catch (e) {
      push(`Scrape failed: ${String(e)}`, "danger");
    } finally {
      setBusy(null);
    }
  };

  if (onboarding) {
    return (
      <OnboardingWizard
        onCreateOrg={async (name, slug) => {
          const created = await createOrg(name, slug);
          setOrgId(created.org_id);
          setOrg(created.org_id);
          return created;
        }}
        onUploadFacts={uploadFactsCsv}
        onUploadProducts={uploadProductsCsv}
        onSaveProfile={async (profile) => {
          await saveOnboardingProfile(profile);
        }}
        onFinish={async (branding) => {
          await saveBranding({ ...branding, finish: true });
        }}
        onDone={() => {
          setOnboarding(false);
          push("Organisation is live.", "success");
          navigate("/");
        }}
        onCancel={() => {
          setOnboarding(false);
          navigate("/");
        }}
      />
    );
  }

  return (
    <div className="mx-auto max-w-6xl px-6 py-8">
      <PageHeader
        title="Tender Radar"
        subtitle="Tenders in your lane, and the ones you could win but never bid on."
        actions={
          <>
            <input
              ref={fileInput}
              type="file"
              accept="application/pdf,.pdf"
              className="hidden"
              onChange={(e) => {
                const file = e.target.files?.[0];
                if (file) onUpload(file);
                e.target.value = "";
              }}
            />
            <Button onClick={onScrape} disabled={!org || busy !== null}>
              ⟳ Scrape now
            </Button>
            <Button
              variant="primary"
              onClick={() => fileInput.current?.click()}
              disabled={!org || busy !== null}
            >
              ↑ Upload tender
            </Button>
          </>
        }
        meta={
          <>
            <input
              value={org}
              onChange={(e) => {
                setOrg(e.target.value);
                setOrgId(e.target.value);
              }}
              placeholder="Organisation id"
              aria-label="Organisation id"
              className="w-80 rounded-[8px] border border-hairline bg-white px-2 py-1 font-mono text-xs text-ink"
            />
            <select
              data-testid="role-select"
              value={role}
              onChange={(e) => {
                const next = e.target.value as RoleName;
                setRoleState(next);
                setRole(next);
              }}
              title="Acting role — gates sensitive actions"
              className="rounded-[8px] border border-hairline bg-white px-2 py-1 text-xs text-ink"
            >
              {ROLES.map((r) => (
                <option key={r} value={r}>{r}</option>
              ))}
            </select>
            <Button size="sm" variant="ghost" onClick={() => setOnboarding(true)}>
              + New company
            </Button>
          </>
        }
      />

      {busy && (
        <Card className="mb-4 border-indigo/20 bg-indigo-tint">
          <span className="text-sm text-indigo">{busy}</span>
        </Card>
      )}

      <nav className="mb-4 flex gap-1 border-b border-hairline">
        {TABS.map((t) => (
          <button
            key={t.id}
            onClick={() => setTab(t.id)}
            className={`-mb-px border-b-2 px-3 py-2 text-sm transition-colors duration-150 ${
              tab === t.id
                ? "border-indigo font-medium text-indigo"
                : "border-transparent text-ink-muted hover:text-ink"
            }`}
          >
            {t.label}
          </button>
        ))}
      </nav>

      {!org && (
        <EmptyState
          title="No organisation selected"
          body="Paste an organisation id above to load its radar, or set up a new company in under an hour."
          action={<Button variant="primary" onClick={() => setOnboarding(true)}>Set up a company</Button>}
        />
      )}

      {org && error && (
        <Card className="border-danger/25 bg-danger-tint">
          <div className="text-sm font-medium text-danger">Could not load the radar</div>
          <div className="mt-1 text-xs text-danger/80">{error}</div>
          <Button size="sm" className="mt-3" onClick={() => setRefresh((n) => n + 1)}>
            Retry
          </Button>
        </Card>
      )}

      {org && loading && !error && (
        <div className="space-y-3">
          {[0, 1, 2].map((i) => (
            <Card key={i}><SkeletonLoader rows={2} /></Card>
          ))}
        </div>
      )}

      {org && !loading && !error && cards.length === 0 && (
        <EmptyState
          title="No tenders in this list yet"
          body="Scrape the connected portals to discover live tenders, or upload a tender PDF to read it right now."
          action={
            <div className="flex gap-2">
              <Button onClick={onScrape}>⟳ Scrape now</Button>
              <Button variant="primary" onClick={() => fileInput.current?.click()}>
                ↑ Upload tender
              </Button>
            </div>
          }
        />
      )}

      <div className="space-y-3">
        {!loading &&
          cards.map((card) => (
            <Card key={card.tender_id} as="article" className="transition-shadow duration-150 hover:shadow-overlay">
              <div data-testid="radar-card">
                <div className="flex items-start justify-between gap-3">
                  <button
                    onClick={() => open(card)}
                    className="text-left text-sm font-semibold text-ink transition-colors duration-150 hover:text-indigo"
                  >
                    {card.title}
                  </button>
                  <div className="flex shrink-0 items-center gap-2">
                    <CountdownChip closingAt={card.closing_at} />
                    <ConfidenceChip
                      confidence={card.confidence}
                      band={card.band}
                      reason={card.reasons.join(" · ")}
                    />
                  </div>
                </div>

                <div className="mt-2 flex flex-wrap items-center gap-2 text-xs text-ink-subtle">
                  <Pill>{card.source}</Pill>
                  {card.external_id && <Pill>{card.external_id}</Pill>}
                  {card.fit_score != null && (
                    <Pill tone="brand">
                      <span data-numeric>fit {(card.fit_score * 100).toFixed(0)}%</span>
                    </Pill>
                  )}
                  {card.checkpoint0 && <Pill tone="warning">checkpoint-0: {card.checkpoint0}</Pill>}
                </div>

                {card.reasons.length > 0 && (
                  <ul className="mt-2 flex flex-wrap gap-1.5">
                    {card.reasons.map((reason) => (
                      <li
                        key={reason}
                        className="rounded-[8px] bg-surface px-2 py-0.5 text-xs text-ink-muted"
                      >
                        {reason}
                      </li>
                    ))}
                  </ul>
                )}
              </div>
            </Card>
          ))}
      </div>
    </div>
  );
}
