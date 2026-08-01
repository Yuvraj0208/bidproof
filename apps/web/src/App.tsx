// Tender Radar (SPEC §17 screen 1) — the home screen.
//
// Two lists Priya lives in (In our lane / Opportunity radar) plus the
// Checkpoint-0 queue. Every card explains itself: fit, why it matched, its
// countdown, and the confidence chip. The default next action sits top-right.
import { useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import {
  createOrg,
  deleteTender,
  bulkDeleteTenders,
  fetchPortalDocument,
  fetchRadar,
  getOrgId,
  processTender,
  runDiscovery,
  saveBranding,
  saveOnboardingProfile,
  setOrgId,
  uploadFactsCsv,
  uploadProductsCsv,
  uploadTender,
  type RadarCard,
} from "./api";
import {
  Copy,
  ExternalLink,
  RefreshCw,
  Trash2,
  Upload,
  Zap,
} from "lucide-react";
import { ConfidenceChip } from "./components/ConfidenceChip";
import { OnboardingWizard } from "./components/OnboardingWizard";
import { RadarArt } from "./ui/artwork";
import { CountdownChip, daysUntil, Pill } from "./ui/chips";
import { Stagger } from "./ui/motion";
import { Modal, useToast } from "./ui/overlays";
import {
  Button,
  Card,
  EmptyState,
  SkeletonLoader,
  ReadingIndicator,
} from "./ui/primitives";

const TABS = [
  { id: "in_our_lane", label: "In our lane" },
  { id: "opportunity_radar", label: "Opportunity radar" },
  { id: "needs_human", label: "Needs human" },
] as const;

/** How well this tender matches what the company can actually do.
 *
 *  A ring rather than a bar: at this size a ring reads as a score while a bar
 *  reads as progress, and fit is not something that fills up. The number stays
 *  in the middle as text so it is readable, announced, and testable.
 */
function FitRing({ value }: { value: number }) {
  const pct = Math.round(value * 100);
  const r = 15;
  const circumference = 2 * Math.PI * r;
  const tone =
    pct >= 70 ? "stroke-success" : pct >= 40 ? "stroke-indigo" : "stroke-ink-subtle";

  return (
    <span
      className="relative shrink-0"
      title={`Fit ${pct}% — how well this matches your catalogue and past wins`}
    >
      <svg width={38} height={38} role="img" aria-label={`fit ${pct} percent`}>
        <circle cx={19} cy={19} r={r} fill="none" strokeWidth={3} className="stroke-surface" />
        <circle
          cx={19} cy={19} r={r} fill="none" strokeWidth={3} strokeLinecap="round"
          className={tone}
          strokeDasharray={`${(pct / 100) * circumference} ${circumference}`}
          transform="rotate(-90 19 19)"
        />
        <text
          x={19} y={19} textAnchor="middle" dy="0.36em"
          data-numeric
          className="fill-ink text-[10px] font-semibold"
        >
          {pct}
        </text>
      </svg>
    </span>
  );
}

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
  const [tab, setTab] = useState<string>("in_our_lane");
  const [cards, setCards] = useState<RadarCard[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [onboarding, setOnboarding] = useState(startOnboarding);
  const [busy, setBusy] = useState<string | null>(null);
  const [refresh, setRefresh] = useState(0);
  const fileInput = useRef<HTMLInputElement>(null);
  const [confirmDelete, setConfirmDelete] = useState<RadarCard | null>(null);
  // Bulk selection. Portal discovery brings in far more noise than anyone
  // wants to dismiss a row at a time.
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [confirmBulk, setConfirmBulk] = useState(false);

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

  // While any tender is mid-parse, re-check every few seconds. Parsing runs in
  // a background task, so without this the card sits at "Reading…" until the
  // user reloads the page and hopes.
  const reading = cards.some(
    (c) => c.parse_status === "pending" || c.parse_status === "running",
  );

  // The header band's figures. Every one is derived from the tenders actually
  // loaded — `fetchRadar` returns one list at a time, so this counts THIS list
  // and says so. Inventing a radar-wide total here would need a second request
  // and would be a number nobody could check against what is on screen.
  const counts = {
    total: cards.length,
    closingSoon: cards.filter((c) => {
      const days = daysUntil(c.closing_at);
      return days !== null && days <= 7;
    }).length,
    reading: cards.filter(
      (c) => c.parse_status === "pending" || c.parse_status === "running",
    ).length,
  };
  useEffect(() => {
    if (!reading) return;
    const timer = setInterval(() => setRefresh((n) => n + 1), 4000);
    return () => clearInterval(timer);
  }, [reading]);

  const open = (card: { tender_id: string; title: string }) => {
    onOpenTender?.({ id: card.tender_id, title: card.title });
    navigate(`/workspace/${card.tender_id}`);
  };

  // Upload parses and triages only. Reading it with a model costs money, so
  // that is a separate, explicit press on this tender (FINISH_STATUS R2).
  const onUpload = async (file: File) => {
    setBusy(`Uploading ${file.name}…`);
    try {
      await uploadTender(file);
      push(
        `${file.name} uploaded and parsed. Press "Process with AI" on the card when you want it read.`,
        "success",
      );
      setRefresh((n) => n + 1);
    } catch (e) {
      push(`Upload failed: ${String(e)}`, "danger");
    } finally {
      setBusy(null);
    }
  };

  const onProcess = async (card: RadarCard) => {
    setBusy(`Reading "${card.title.slice(0, 40)}" with AI…`);
    try {
      const result = await processTender(card.tender_id);
      push(
        `${result.rules} rules extracted · ${result.model_calls} model call(s).`,
        "success",
      );
      open({ tender_id: card.tender_id, title: card.title });
    } catch (e) {
      const message = String(e);
      push(
        message.includes("409")
          ? "This tender has no PDF — portal listings often carry metadata only. Upload the document to read it."
          : `Processing failed: ${message}`,
        "warning",
      );
    } finally {
      setBusy(null);
    }
  };

  const toggle = (tenderId: string) =>
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(tenderId)) next.delete(tenderId);
      else next.add(tenderId);
      return next;
    });

  const onBulkDelete = async () => {
    const ids = cards.filter((c) => selected.has(c.tender_id)).map((c) => c.tender_id);
    setConfirmBulk(false);
    setBusy("bulk");
    try {
      const result = await bulkDeleteTenders(ids);
      setSelected(new Set());
      push(
        result.not_found.length
          ? `Deleted ${result.deleted.length}; ${result.not_found.length} were already gone.`
          : `Deleted ${result.deleted.length} tender${result.deleted.length === 1 ? "" : "s"}.`,
        "success",
      );
      setRefresh((n) => n + 1);
    } catch (e) {
      push(
        String(e).includes("403")
          ? "Deleting is audited and needs an operator with full access."
          : `Bulk delete failed: ${String(e)}`,
        "danger",
      );
    } finally {
      setBusy(null);
    }
  };

  const copyReference = async (reference: string) => {
    try {
      await navigator.clipboard.writeText(reference);
      push(`Copied ${reference} — paste it into the portal's search.`, "success");
    } catch {
      push(`Could not copy. The reference is ${reference}.`, "info");
    }
  };

  const onFetchDocument = async (card: RadarCard) => {
    setBusy(card.tender_id);
    try {
      const result = await fetchPortalDocument(card.tender_id);
      push(
        `Read ${result.pages} page${result.pages === 1 ? "" : "s"} from ${card.source.toUpperCase()}. You can process it now.`,
        "success",
      );
      setRefresh((n) => n + 1);
    } catch (e) {
      push(`Could not fetch the document: ${String(e)}`, "danger");
    } finally {
      setBusy(null);
    }
  };

  const onDelete = async () => {
    if (!confirmDelete) return;
    const card = confirmDelete;
    setConfirmDelete(null);
    setBusy(`Deleting "${card.title.slice(0, 40)}"…`);
    try {
      await deleteTender(card.tender_id);
      push("Tender deleted. The action is in the audit log.", "success");
      setRefresh((n) => n + 1);
    } catch (e) {
      push(
        String(e).includes("403")
          ? "The API refused the delete for this operator."
          : `Delete failed: ${String(e)}`,
        "danger",
      );
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
      {/* The Radar opens on the dark register. This is the first screen after
          sign-in and it was a white page with a heading on it — accurate, but
          it told you nothing before you started reading. The band answers
          "what have you got, and what needs me?" in one glance. */}
      <div className="on-void relative mb-6 overflow-hidden rounded-[18px] border border-void-line bg-void px-8 py-8 shadow-glow">
        <div aria-hidden className="pointer-events-none absolute inset-0 void-grid" />
        <div aria-hidden className="pointer-events-none absolute inset-0 void-glow" />
        <div className="relative flex flex-wrap items-end justify-between gap-6">
          <div>
            <p className="eyebrow text-accent">tender radar</p>
            <h1 className="mt-2 text-[clamp(1.8rem,3.4vw,2.6rem)] font-semibold leading-[1.05] tracking-[-0.03em] text-white">
              Tenders in your lane
            </h1>
            <p className="mt-2 max-w-md text-[15px] text-white/50">
              And the ones you could win but never bid on.
            </p>
          </div>

          <dl className="flex flex-wrap gap-9">
            {[
              { k: "in this list", v: counts.total },
              { k: "closing in 7 days", v: counts.closingSoon, warn: counts.closingSoon > 0 },
              { k: "still being read", v: counts.reading },
            ].map((stat) => (
              <div key={stat.k}>
                <dd
                  data-numeric
                  className={`text-[2.25rem] font-semibold leading-none tracking-[-0.035em] ${
                    stat.warn ? "text-warning" : "text-white"
                  }`}
                >
                  {stat.v}
                </dd>
                <dt className="mt-1.5 text-[11px] text-white/45">{stat.k}</dt>
              </div>
            ))}
          </dl>
        </div>
      </div>

      {/* Actions sit with the tab bar now: the dark band above carries the
          title, so a second heading here would just repeat it. */}
      <div className="mb-4 flex flex-wrap items-center gap-2 border-b border-hairline pb-3">
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
              <RefreshCw
                size={14}
                strokeWidth={2}
                aria-hidden
                className={busy === "scrape" ? "animate-spin" : ""}
              />
              Scrape now
            </Button>
            <Button
              variant="primary"
              onClick={() => fileInput.current?.click()}
              disabled={!org || busy !== null}
            >
              <Upload size={14} strokeWidth={2} aria-hidden />
              Upload tender
            </Button>
          </>
      </div>

      {busy && (
        <Card className="mb-4 border-indigo/20 bg-indigo-tint">
          <span className="text-sm text-indigo">{busy}</span>
        </Card>
      )}

      {/* A segmented control rather than an underline. These three lists are
          peers you switch between, not a hierarchy you drill into, and the
          filled pill says which one you are in from across the room. */}
      <nav className="mb-4 inline-flex gap-1 rounded-[10px] border border-hairline bg-white p-1">
        {TABS.map((t) => (
          <button
            key={t.id}
            onClick={() => setTab(t.id)}
            aria-current={tab === t.id ? "page" : undefined}
            className={`rounded-[7px] px-3 py-1.5 text-sm transition-colors duration-150 ${
              tab === t.id
                ? "bg-indigo font-medium text-white shadow-card"
                : "text-ink-muted hover:bg-indigo-tint hover:text-indigo"
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
          icon={<RadarArt />}
          title="No tenders in this list yet"
          body="Scrape the connected portals to discover live tenders, or upload a tender PDF to read it right now."
          action={
            <div className="flex gap-2">
              <Button onClick={onScrape}>
                <RefreshCw size={14} strokeWidth={2} aria-hidden />
                Scrape now
              </Button>
              <Button variant="primary" onClick={() => fileInput.current?.click()}>
                <Upload size={14} strokeWidth={2} aria-hidden />
                Upload tender
              </Button>
            </div>
          }
        />
      )}

      <Modal
        open={confirmDelete !== null}
        title="Delete this tender?"
        onClose={() => setConfirmDelete(null)}
        footer={<>
          <Button onClick={() => setConfirmDelete(null)}>Cancel</Button>
          <Button variant="danger" onClick={onDelete}>Delete permanently</Button>
        </>}
      >
        <p className="text-sm text-ink">
          <span className="font-medium">{confirmDelete?.title}</span>
        </p>
        <p className="mt-2 text-sm text-ink-muted">
          This removes the tender and everything derived from it — rules,
          verdicts, decision and proposal. It cannot be undone. The deletion is
          recorded in the audit log against your role.
        </p>
      </Modal>

      <Modal
        open={confirmBulk}
        title={`Delete ${selected.size} tender${selected.size === 1 ? "" : "s"}?`}
        onClose={() => setConfirmBulk(false)}
        footer={<>
          <Button onClick={() => setConfirmBulk(false)}>Cancel</Button>
          <Button variant="danger" onClick={onBulkDelete}>
            Delete {selected.size} permanently
          </Button>
        </>}
      >
        <ul className="max-h-48 space-y-1 overflow-auto text-sm text-ink">
          {cards
            .filter((c) => selected.has(c.tender_id))
            .map((c) => (
              <li key={c.tender_id} className="truncate">• {c.title}</li>
            ))}
        </ul>
        <p className="mt-3 text-sm text-ink-muted">
          This removes each tender and everything derived from it — rules,
          verdicts, decision and proposal. It cannot be undone. Every deletion is
          recorded separately in the audit log.
        </p>
      </Modal>

      {/* Selection bar: only present once something is selected, so the radar
          stays quiet when you are just reading. */}
      {!loading && cards.length > 0 && (
        <div className="mb-3 flex flex-wrap items-center gap-2 rounded-[10px] border border-hairline bg-white px-3 py-2">
          <label className="flex items-center gap-2 text-xs text-ink-muted">
            <input
              type="checkbox"
              data-testid="select-all"
              checked={selected.size > 0 && selected.size === cards.length}
              ref={(el) => {
                if (el)
                  el.indeterminate =
                    selected.size > 0 && selected.size < cards.length;
              }}
              onChange={(e) =>
                setSelected(
                  e.target.checked
                    ? new Set(cards.map((c) => c.tender_id))
                    : new Set(),
                )
              }
            />
            Select all {cards.length}
          </label>
          {selected.size > 0 ? (
            <>
              <span className="text-xs font-medium text-ink">
                {selected.size} selected
              </span>
              <Button size="sm" onClick={() => setSelected(new Set())}>
                Clear
              </Button>
              <Button
                size="sm"
                variant="danger"
                disabled={busy !== null}
                onClick={() => setConfirmBulk(true)}
              >
                <Trash2 size={13} strokeWidth={2} aria-hidden />
                {busy === "bulk" ? "Deleting…" : `Delete ${selected.size}`}
              </Button>
            </>
          ) : (
            <span className="text-xs text-ink-muted">
              Tick tenders to clear several at once.
            </span>
          )}
        </div>
      )}

      {/* The list arrives staggered rather than all at once. `Stagger` caps the
          cascade at half a second, so a long radar still settles promptly. */}
      <Stagger className="space-y-3">
        {(loading ? [] : cards).map((card) => (
            <Card key={card.tender_id} as="article" className="transition-shadow duration-150 hover:shadow-overlay">
              <div data-testid="radar-card">
                <div className="flex items-start justify-between gap-3">
                  <div className="flex min-w-0 items-start gap-3">
                    <input
                      type="checkbox"
                      className="mt-1.5 shrink-0"
                      data-testid="select-tender"
                      aria-label={`Select ${card.title}`}
                      checked={selected.has(card.tender_id)}
                      onChange={() => toggle(card.tender_id)}
                    />
                    {/* Fit is the one number that decides whether this row is
                        worth your afternoon, and it was a grey pill among five
                        other grey pills. As a ring it is the first thing the
                        eye lands on, and it still prints the figure. */}
                    {card.fit_score != null && (
                      <FitRing value={card.fit_score} />
                    )}
                    <button
                      onClick={() => open(card)}
                      className="mt-0.5 text-left text-[15px] font-semibold leading-snug text-ink transition-colors duration-150 hover:text-indigo"
                    >
                      {card.title}
                    </button>
                  </div>
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
                  {card.checkpoint0 && <Pill tone="warning">checkpoint-0: {card.checkpoint0}</Pill>}
                </div>

                {/* Still being read: parsing runs in the background, and a
                    tender with no radar list used to be invisible in every tab,
                    which read as "my upload vanished". */}
                {(card.parse_status === "pending" ||
                  card.parse_status === "running") && (
                  <div className="mt-2">
                    <ReadingIndicator
                      label="Reading the document"
                      detail="scanned pages go through OCR, which can take a few minutes"
                    />
                  </div>
                )}

                {card.parse_status === "failed" && (
                  <p className="mt-2 text-xs text-danger">
                    This document could not be read. Open it to see why, or
                    upload the PDF again.
                  </p>
                )}

                {/* Read, but triage has not sorted it into a list yet. */}
                {card.radar_list === null &&
                  card.parse_status !== "pending" &&
                  card.parse_status !== "running" &&
                  card.parse_status !== "failed" && (
                    <p className="mt-2 text-xs text-ink-muted">
                      Read, and waiting to be scored against your lanes.
                    </p>
                  )}

                {!card.has_document && (
                  <p className="mt-2 text-xs text-ink-muted">
                    {card.can_fetch_document ? (
                      <>
                        Not read yet — {card.source.toUpperCase()} serves this
                        tender's PDF directly, so BidProof can fetch and read it
                        for you. Reading is free; only “Process with AI” costs
                        anything.
                      </>
                    ) : (
                      <>
                        {card.portal_hint ?? (
                          <>
                            Listing only — {card.source.toUpperCase()} publishes
                            the details but not the document, so there is nothing
                            to read yet. Upload the PDF here to read it.
                          </>
                        )}
                      </>
                    )}
                  </p>
                )}

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

                {/* Per-tender control: nothing here has cost money yet. */}
                <div className="mt-3 flex flex-wrap items-center gap-2 border-t border-hairline pt-3">
                  {card.has_document ? (
                    <Button
                      size="sm"
                      variant="primary"
                      // Pressing this mid-parse would extract from a document
                      // that has no elements yet.
                      disabled={
                        busy !== null ||
                        card.parse_status === "pending" ||
                        card.parse_status === "running"
                      }
                      onClick={() => onProcess(card)}
                      title={
                        card.parse_status === "running" ||
                        card.parse_status === "pending"
                          ? "Still reading the document — this becomes available once it is read"
                          : "Extract the rules and check them — this is the step that calls a model"
                      }
                    >
                      <Zap size={13} strokeWidth={2} aria-hidden />
                      Process with AI
                    </Button>
                  ) : (
                    <>
                      {/* No PDF to read: the portal published a listing only, so
                          offering "Process with AI" here could only ever fail. */}
                      {card.portal_url ? (
                        <a
                          href={card.portal_url}
                          target="_blank"
                          rel="noreferrer noopener"
                          className="inline-flex items-center gap-1.5 rounded-[8px] border border-indigo/25 bg-indigo-tint px-2.5 py-1 text-xs font-medium text-indigo transition-colors duration-150 hover:bg-indigo/10"
                        >
                          <ExternalLink size={12} strokeWidth={2} aria-hidden />
                          Open on portal
                        </a>
                      ) : (
                        /* No link can land on this tender. Offer the reference to
                           paste and a search page labelled for what it costs —
                           sending every row to an unlabelled captcha form is what
                           made this look broken. */
                        <>
                          {card.external_id && (
                            <button
                              onClick={() => copyReference(card.external_id!)}
                              className="inline-flex items-center gap-1.5 rounded-[8px] border border-hairline bg-white px-2.5 py-1 font-mono text-xs text-ink transition-colors duration-150 hover:bg-surface"
                              title="Copy the tender reference, to paste into the portal's search"
                            >
                              <Copy size={12} strokeWidth={2} aria-hidden />
                              {card.external_id}
                            </button>
                          )}
                          {card.portal_search_url && (
                            <a
                              href={card.portal_search_url}
                              target="_blank"
                              rel="noreferrer noopener"
                              className="text-xs text-ink-muted underline decoration-hairline underline-offset-2 transition-colors duration-150 hover:text-ink"
                              title={
                                card.portal_requires_captcha
                                  ? "Opens the portal's search form, which asks you to solve a captcha"
                                  : "Opens the portal's search page"
                              }
                            >
                              {card.portal_requires_captcha
                                ? "Search manually (captcha) ↗"
                                : "Search the portal ↗"}
                            </a>
                          )}
                        </>
                      )}
                      {card.can_fetch_document ? (
                        <Button
                          size="sm"
                          variant="primary"
                          disabled={busy !== null}
                          onClick={() => onFetchDocument(card)}
                          title="This portal serves the PDF directly — fetch and read it now (free, no model call)"
                        >
                          {busy === card.tender_id ? "Fetching…" : "Fetch its PDF"}
                        </Button>
                      ) : (
                        <Button
                          size="sm"
                          disabled={busy !== null}
                          onClick={() => fileInput.current?.click()}
                          title="Download the PDF from the portal, then upload it here to read it"
                        >
                          <Upload size={13} strokeWidth={2} aria-hidden />
                          Upload its PDF
                        </Button>
                      )}
                    </>
                  )}
                  <Button size="sm" onClick={() => open(card)}>
                    Open
                  </Button>
                  <Button
                    size="sm"
                    variant="ghost"
                    className="ml-auto text-danger"
                    disabled={busy !== null}
                    onClick={() => setConfirmDelete(card)}
                    title="Delete this tender — irreversible, and written to the audit log"
                  >
                    <Trash2 size={13} strokeWidth={2} aria-hidden />
                    Delete
                  </Button>
                </div>
              </div>
            </Card>
        ))}
      </Stagger>
    </div>
  );
}
