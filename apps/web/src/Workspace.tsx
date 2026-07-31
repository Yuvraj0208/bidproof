// Tender Workspace: Rules and the Compliance Matrix on the left, the PDF
// with click-to-proof on the right. More tabs (Decision, Console) arrive
// with their stories.
import { useEffect, useState } from "react";
import {
  amendTender,
  approveSection,
  approveSections,
  resolveClaim,
  askChat,
  attachChecklistFile,
  computeDecision,
  downloadMatrix,
  fetchAgentRuns,
  fetchAmendments,
  fetchChatHistory,
  fetchConductorGraph,
  fetchConductorRun,
  type ConductorGraph,
  fetchChecklist,
  generateChecklist,
  tickChecklistItem,
  fetchBrief,
  exportPreflight,
  exportProposal,
  fetchProposal,
  fetchQuestions,
  fetchRules,
  fetchVerdicts,
  generateProposal,
  generateQuestions,
  overrideDecision,
  replayTender,
  runCheck,
  runExtraction,
  signOffDecision,
  type Amendment,
  type ChatTurn,
  type Checklist,
  type ExportBlocker,
  type Proposal,
  type QueryLetter,
  type Rule,
  type Verdict,
  fetchTenderDetail,
  decideVerdict,
  HUMAN_VERDICTS,
  type TenderDetail,
} from "./api";
import { AmendmentsPanel } from "./components/AmendmentsPanel";
import { ChatPanel } from "./components/ChatPanel";
import { ChecklistPanel } from "./components/ChecklistPanel";
import { ExportBar } from "./components/ExportBar";
import { ProposalPanel } from "./components/ProposalPanel";
import { QuestionsPanel } from "./components/QuestionsPanel";
import {
  AgentConsole,
  type AgentRunData,
  type ConsoleTotals,
} from "./components/AgentConsole";
import { ConfidenceChip } from "./components/ConfidenceChip";
import {
  DecisionRoom,
  type BriefRisk,
  type DecisionData,
} from "./components/DecisionRoom";
import { LearnedNote } from "./components/LearnedNote";
import { ReviewHub, pendingReviews } from "./components/ReviewHub";
import { Button } from "./ui/primitives";
import { Modal, useToast } from "./ui/overlays";
import { MatrixTable } from "./components/MatrixTable";
import { PdfProof, type Highlight } from "./components/PdfProof";

const FAMILY_ORDER = ["eligibility", "technical", "commercial", "legal", "submission"];

type Tab =
  | "review"
  | "rules"
  | "matrix"
  | "decision"
  | "console"
  | "amendments"
  | "questions"
  | "proposal"
  | "checklist"
  | "chat";

export function Workspace({
  tenderId,
  title,
  onBack,
}: {
  tenderId: string;
  title: string;
  onBack: () => void;
}) {
  const [tab, setTab] = useState<Tab>("review");
  const { push } = useToast();
  const [loadError, setLoadError] = useState<string | null>(null);
  const [detail, setDetail] = useState<TenderDetail | null>(null);
  // Checkpoint 3: the verdict the system refused to guess, and the answer being
  // written for it. The name is remembered across rows — the same person is
  // usually settling several in one sitting.
  const [deciding, setDeciding] = useState<Verdict | null>(null);
  const [decidedName, setDecidedName] = useState("");
  const [decision2, setDecision2] = useState({
    verdict: "complies",
    reason: "",
    name: "",
  });
  const [savingDecision, setSavingDecision] = useState(false);
  const [rules, setRules] = useState<Rule[]>([]);
  const [verdicts, setVerdicts] = useState<Verdict[]>([]);
  const [decision, setDecision] = useState<DecisionData | null>(null);
  const [risks, setRisks] = useState<BriefRisk[]>([]);
  const [agentRuns, setAgentRuns] = useState<AgentRunData[]>([]);
  const [consoleTotals, setConsoleTotals] = useState<ConsoleTotals | null>(null);
  const [conductorGraph, setConductorGraph] = useState<ConductorGraph | null>(null);
  const [pausedAt, setPausedAt] = useState<number | null>(null);
  const [replaying, setReplaying] = useState(false);
  const [amendments, setAmendments] = useState<Amendment[]>([]);
  const [amending, setAmending] = useState(false);
  const [letters, setLetters] = useState<QueryLetter[]>([]);
  const [drafting, setDrafting] = useState(false);
  const [proposal, setProposal] = useState<Proposal | null>(null);
  const [writing, setWriting] = useState(false);
  const [blockers, setBlockers] = useState<ExportBlocker[] | null>(null);
  const [exporting, setExporting] = useState(false);
  const [checklist, setChecklist] = useState<Checklist | null>(null);
  const [checklistName, setChecklistName] = useState("");
  const [chatTurns, setChatTurns] = useState<ChatTurn[]>([]);
  const [asking, setAsking] = useState(false);
  const [highlight, setHighlight] = useState<Highlight | null>(null);
  const [selectedRule, setSelectedRule] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const load = () => {
    // A failure here used to be swallowed into empty panels, so a dead database
    // looked like "an empty tender" (FINISH_STATUS R0). Rules is the canonical
    // read: if IT fails, something is actually wrong and we say so.
    setLoadError(null);
    fetchRules(tenderId)
      .then((r) => { setRules(r); setLoadError(null); })
      .catch((e) => { setRules([]); setLoadError(String(e)); });
    fetchVerdicts(tenderId).then(setVerdicts).catch(() => setVerdicts([]));
    fetchBrief(tenderId)
      .then((brief) => {
        setDecision(brief.decision as DecisionData | null);
        setRisks(brief.top_risks as BriefRisk[]);
      })
      .catch(() => setDecision(null));
    fetchAgentRuns(tenderId)
      .then((console_) => {
        setAgentRuns(console_.runs as AgentRunData[]);
        setConsoleTotals(console_.totals as ConsoleTotals);
      })
      .catch(() => setAgentRuns([]));
    // The pipeline shape. Failing quietly is right: the console's job is the
    // cost ledger, and it should still render if the graph is unavailable.
    fetchConductorGraph()
      .then(setConductorGraph)
      .catch(() => setConductorGraph(null));
    fetchConductorRun(tenderId)
      .then((run) => setPausedAt(run.paused_at))
      .catch(() => setPausedAt(null));
    fetchAmendments(tenderId).then(setAmendments).catch(() => setAmendments([]));
    fetchQuestions(tenderId).then(setLetters).catch(() => setLetters([]));
    fetchProposal(tenderId).then(setProposal).catch(() => setProposal(null));
    exportPreflight(tenderId)
      .then((p) => setBlockers(p.blockers))
      .catch(() => setBlockers(null));
    fetchChecklist(tenderId).then(setChecklist).catch(() => setChecklist(null));
    fetchChatHistory(tenderId).then(setChatTurns).catch(() => setChatTurns([]));
    fetchTenderDetail(tenderId).then(setDetail).catch(() => setDetail(null));
  };

  const submitVerdictDecision = async () => {
    if (deciding === null) return;
    setSavingDecision(true);
    try {
      await decideVerdict(tenderId, deciding.id, decision2);
      setDecidedName(decision2.name);
      setDeciding(null);
      push(`Recorded: ${deciding.key} is ${decision2.verdict}.`, "success");
      load();
    } catch (e) {
      push(`Could not record the decision: ${String(e)}`, "danger");
    } finally {
      setSavingDecision(false);
    }
  };

  const handleAsk = async (question: string) => {
    setAsking(true);
    try {
      await askChat(tenderId, question);
    } finally {
      setChatTurns(await fetchChatHistory(tenderId));
      setAsking(false);
    }
  };

  const handleGenerateChecklist = async () => {
    setChecklist(await generateChecklist(tenderId));
  };
  const handleAttach = async (itemId: string, format: string, signed: boolean) => {
    await attachChecklistFile(itemId, format, signed);
    setChecklist(await fetchChecklist(tenderId));
  };
  const handleTick = async (itemId: string) => {
    try {
      await tickChecklistItem(itemId, checklistName.trim());
    } finally {
      setChecklist(await fetchChecklist(tenderId));
    }
  };

  const handleExport = async (override?: { name: string; reason: string }) => {
    setExporting(true);
    try {
      const remaining = await exportProposal(tenderId, override);
      setBlockers(remaining);
    } finally {
      setExporting(false);
    }
  };

  const handleDraftProposal = async () => {
    setWriting(true);
    try {
      await generateProposal(tenderId);
      load();
    } finally {
      setWriting(false);
    }
  };

  const handleApproveSection = async (sectionId: string, name: string) => {
    try {
      await approveSection(tenderId, sectionId, name);
      push("Section approved.", "success");
    } catch (e) {
      // The refusal used to be swallowed here, so a section that could not be
      // approved looked like a button that did nothing.
      push(`Could not approve: ${String(e)}`, "danger");
    } finally {
      load();
    }
  };

  const handleApproveSections = async (sectionIds: string[], name: string) => {
    try {
      const out = await approveSections(tenderId, sectionIds, name);
      const skipped = out.skipped.length
        ? ` ${out.skipped.length} skipped (${out.skipped
            .map((s) => s.section)
            .join(", ")}) — resolve their flags.`
        : "";
      push(`${out.approved.length} section(s) approved.${skipped}`,
           out.skipped.length ? "warning" : "success");
    } catch (e) {
      push(`Could not approve: ${String(e)}`, "danger");
    } finally {
      load();
    }
  };

  const handleResolveClaim = async (
    sectionId: string,
    claimIndex: number,
    action: "drop" | "accept",
    by: string,
    reason: string,
  ) => {
    try {
      await resolveClaim(tenderId, sectionId, claimIndex, action, by, reason);
      push(
        action === "drop"
          ? "Sentence removed from the section."
          : "Claim accepted — recorded with your name and reason.",
        "success",
      );
    } catch (e) {
      push(`Could not resolve the claim: ${String(e)}`, "danger");
    } finally {
      load();
    }
  };

  const handleDraftQuestions = async () => {
    setDrafting(true);
    try {
      await generateQuestions(tenderId);
      load();
    } finally {
      setDrafting(false);
    }
  };

  const handleReplay = async () => {
    setReplaying(true);
    try {
      await replayTender(tenderId);
      load();
    } finally {
      setReplaying(false);
    }
  };

  const handleAmend = async (file: File) => {
    setAmending(true);
    try {
      await amendTender(tenderId, file);
      load();
    } finally {
      setAmending(false);
    }
  };
  useEffect(() => {
    load();
  }, [tenderId]);

  const decideNow = async () => {
    await computeDecision(tenderId);
    load();
  };
  const handleSignOff = async (name: string) => {
    await signOffDecision(tenderId, name);
    load();
  };
  const handleOverride = async (name: string, rec: string, reason: string) => {
    await overrideDecision(tenderId, name, rec, reason);
    load();
  };

  const recheck = async () => {
    setBusy(true);
    try {
      await runExtraction(tenderId);
      await runCheck(tenderId);
      load();
    } finally {
      setBusy(false);
    }
  };

  const families = FAMILY_ORDER.filter((f) => rules.some((r) => r.family === f));

  // Every outstanding human decision, derived from state already loaded.
  const reviewItems = pendingReviews({
    rulesNeedingHuman: rules.filter((r) => r.status === "needs_human").length,
    verdictsNeedingHuman: verdicts.filter((v) => v.verdict === "needs_human").length,
    decisionStatus: decision?.status ?? null,
    decisionRecommendation: decision?.recommendation ?? null,
    proposalSections: proposal?.sections ?? null,
    exportBlockers: blockers?.length ?? 0,
    checklistRequired: checklist?.required_count ?? 0,
    checklistTicked: checklist?.ticked_count ?? 0,
  });

  return (
    <div className="flex h-full min-h-0 flex-col">
      <header className="flex items-center gap-3 border-b bg-white px-4 py-2">
        <button
          onClick={onBack}
          className="rounded-[8px] border border-hairline px-2 py-1 text-sm text-ink-muted hover:bg-surface"
        >
          ← Radar
        </button>
        <h1 className="truncate text-sm font-semibold text-ink">{title}</h1>
        <nav className="ml-4 flex gap-1">
          {(
            [
              "review",
              "rules",
              "matrix",
              "decision",
              "console",
              "amendments",
              "questions",
              "proposal",
              "checklist",
              "chat",
            ] as Tab[]
          ).map((t) => (
              <button
                key={t}
                onClick={() => setTab(t)}
                className={`rounded-[8px] px-2 py-1 text-sm ${
                  tab === t
                    ? "bg-indigo-tint font-medium text-indigo"
                    : "text-ink-muted hover:text-ink"
                }`}
              >
                {t === "review"
                  ? `Review${reviewItems.length ? ` (${reviewItems.length})` : ""}`
                  : t === "rules"
                  ? `Rules (${rules.length})`
                  : t === "matrix"
                    ? `Matrix (${verdicts.length})`
                    : t === "decision"
                      ? "Decision"
                      : t === "console"
                        ? `Console (${agentRuns.length})`
                        : t === "amendments"
                          ? `Amendments${amendments.length ? ` (${amendments.length})` : ""}`
                          : t === "questions"
                            ? `Questions${letters.length ? ` (${letters.length})` : ""}`
                            : t === "proposal"
                              ? "Proposal"
                              : t === "checklist"
                                ? "Checklist"
                                : "Ask BidProof"}
              </button>
          ))}
        </nav>
        <div className="ml-auto flex items-center gap-2">
          {tab === "matrix" && verdicts.length > 0 && (
            <button
              onClick={() => downloadMatrix(tenderId)}
              className="rounded-[8px] border border-hairline px-2 py-1 text-sm text-ink-muted hover:bg-surface"
            >
              Export .xlsx
            </button>
          )}
          <button
            onClick={recheck}
            disabled={busy}
            className="rounded-[8px] border border-hairline px-2 py-1 text-sm text-ink-muted hover:bg-surface disabled:opacity-50"
          >
            {busy ? "Working…" : "Re-run"}
          </button>
        </div>
      </header>

      {loadError && (
        <div className="border-b border-danger/25 bg-danger-tint px-4 py-3">
          <div className="text-sm font-medium text-danger">
            Could not load this tender
          </div>
          <div className="mt-1 text-xs text-danger/80">{loadError}</div>
          <div className="mt-1 text-xs text-danger/80">
            If this mentions a timeout or a connection, the database is not
            answering — restart the Postgres container and retry.
          </div>
          <Button size="sm" className="mt-2" onClick={load}>Retry</Button>
        </div>
      )}

      {/* Checkpoint 3 (SPEC §7). The system said "I do not know" rather than
          guessing; this is where the human answers. It never auto-passes, and
          the answer is stored as a human decision, not a machine verdict. */}
      <Modal
        open={deciding !== null}
        title={deciding ? `Decide: ${deciding.key}` : "Decide"}
        onClose={() => setDeciding(null)}
        footer={<>
          <Button onClick={() => setDeciding(null)}>Cancel</Button>
          <Button
            variant="primary"
            disabled={
              savingDecision ||
              decision2.reason.trim().length < 3 ||
              decision2.name.trim().length < 2
            }
            onClick={submitVerdictDecision}
          >
            {savingDecision ? "Recording…" : "Record decision"}
          </Button>
        </>}
      >
        {deciding && (
          <div className="space-y-3">
            <div>
              <div className="text-xs font-medium text-ink-muted">
                What the tender requires
              </div>
              <p className="mt-1 text-sm text-ink">{deciding.requirement_text}</p>
              <button
                onClick={() => {
                  setHighlight({
                    page_no: deciding.page_no,
                    bbox: deciding.bbox,
                    document_id: deciding.document_id,
                  });
                  setDeciding(null);
                }}
                className="mt-1 text-[11px] text-indigo underline decoration-hairline underline-offset-2"
              >
                see it on page {deciding.page_no} ↗
              </button>
            </div>

            <div className="rounded-[10px] bg-surface px-3 py-2 text-xs text-ink-muted">
              Why this reached you: {deciding.reason}
            </div>

            <label className="block text-xs font-medium text-ink-muted">
              Your verdict
              <select
                data-testid="decide-verdict-select"
                value={decision2.verdict}
                onChange={(e) =>
                  setDecision2({ ...decision2, verdict: e.target.value })
                }
                className="mt-1 w-full rounded-[8px] border border-hairline bg-white px-2 py-1.5 text-sm text-ink"
              >
                {HUMAN_VERDICTS.map((v) => (
                  <option key={v} value={v}>
                    {v.replace(/_/g, " ")}
                  </option>
                ))}
              </select>
            </label>

            <label className="block text-xs font-medium text-ink-muted">
              Why (this goes into the compliance matrix and the audit log)
              <textarea
                data-testid="decide-verdict-reason"
                value={decision2.reason}
                onChange={(e) =>
                  setDecision2({ ...decision2, reason: e.target.value })
                }
                rows={3}
                placeholder="e.g. We have 6 years on comparable FDN surveys — see contract 2021/MoD/114."
                className="mt-1 w-full rounded-[8px] border border-hairline bg-white px-2 py-1.5 text-sm text-ink"
              />
            </label>

            <label className="block text-xs font-medium text-ink-muted">
              Your name
              <input
                data-testid="decide-verdict-name"
                value={decision2.name}
                onChange={(e) =>
                  setDecision2({ ...decision2, name: e.target.value })
                }
                placeholder="Who is deciding this"
                className="mt-1 w-full rounded-[8px] border border-hairline bg-white px-2 py-1.5 text-sm text-ink"
              />
            </label>

            <p className="text-[11px] text-ink-subtle">
              Recorded as your decision, not the system's. What the checker
              originally said is kept alongside it.
            </p>
          </div>
        )}
      </Modal>

      {/* A scraped listing has no PDF. Every panel below reads FROM the PDF, so
          without this the workspace just looks broken. Explain it once, here. */}
      {detail && !detail.has_document && (
        <div className="border-b border-warning/30 bg-warning-tint px-4 py-3">
          <div className="text-sm font-medium text-ink">
            Listing only — there is no document to read yet
          </div>
          <div className="mt-1 max-w-3xl text-xs text-ink-muted">
            {detail.portal_hint ??
              `${detail.source.toUpperCase()} publishes the tender's details but not
               the document, so nothing here has been read or extracted.`}{" "}
            Upload the PDF and every panel below fills in — with a page and a box
            behind each fact.
          </div>
          <div className="mt-2 flex flex-wrap items-center gap-2">
            {detail.portal_url ? (
              <a
                href={detail.portal_url}
                target="_blank"
                rel="noreferrer noopener"
                className="inline-flex items-center gap-1.5 rounded-[8px] border border-hairline bg-white px-2.5 py-1 text-xs font-medium text-ink transition-colors duration-150 hover:bg-surface"
              >
                Open on {detail.source.toUpperCase()} ↗
              </a>
            ) : (
              detail.portal_search_url && (
                <a
                  href={detail.portal_search_url}
                  target="_blank"
                  rel="noreferrer noopener"
                  className="text-xs text-ink-muted underline decoration-hairline underline-offset-2 transition-colors duration-150 hover:text-ink"
                >
                  {detail.portal_requires_captcha
                    ? `Search ${detail.source.toUpperCase()} manually (captcha) ↗`
                    : `Search ${detail.source.toUpperCase()} ↗`}
                </a>
              )
            )}
          </div>
        </div>
      )}

      {/* The parse itself failed — different problem, different answer. */}
      {detail?.parse?.status === "failed" && (
        <div className="border-b border-danger/25 bg-danger-tint px-4 py-3">
          <div className="text-sm font-medium text-danger">
            This document could not be read
          </div>
          <div className="mt-1 text-xs text-danger/80">
            {detail.parse.error ?? "The parse run failed."}
          </div>
        </div>
      )}

      {tab === "review" ? (
        <div className="min-h-0 flex-1 overflow-auto bg-surface">
          <ReviewHub items={reviewItems} onGoTo={(next) => setTab(next as Tab)} />
        </div>
      ) : tab === "chat" ? (
        <div className="min-h-0 flex-1 overflow-hidden bg-surface">
          <ChatPanel turns={chatTurns} onAsk={handleAsk} busy={asking} />
        </div>
      ) : tab === "checklist" ? (
        <div className="min-h-0 flex-1 overflow-auto bg-surface">
          <ChecklistPanel
            checklist={checklist}
            name={checklistName}
            onName={setChecklistName}
            onAttach={handleAttach}
            onTick={handleTick}
            onGenerate={handleGenerateChecklist}
          />
        </div>
      ) : tab === "proposal" ? (
        <div className="min-h-0 flex-1 overflow-auto bg-surface">
          {proposal && (
            <div className="mx-auto max-w-2xl px-6 pt-6">
              <ExportBar
                blockers={blockers}
                onExport={() => handleExport()}
                onOverride={(name, reason) => handleExport({ name, reason })}
                busy={exporting}
              />
            </div>
          )}
          <ProposalPanel
            proposal={proposal}
            onGenerate={handleDraftProposal}
            onApprove={handleApproveSection}
            onResolveClaim={handleResolveClaim}
            onApproveMany={handleApproveSections}
            busy={writing}
          />
        </div>
      ) : tab === "questions" ? (
        <div className="min-h-0 flex-1 overflow-auto bg-surface">
          <QuestionsPanel
            letters={letters}
            onGenerate={handleDraftQuestions}
            busy={drafting}
          />
        </div>
      ) : tab === "amendments" ? (
        <div className="min-h-0 flex-1 overflow-auto bg-surface">
          <AmendmentsPanel
            amendments={amendments}
            onAmend={handleAmend}
            busy={amending}
          />
        </div>
      ) : tab === "console" ? (
        <div className="min-h-0 flex-1 overflow-auto bg-surface">
          <AgentConsole
            runs={agentRuns}
            totals={consoleTotals}
            onReplay={handleReplay}
            replaying={replaying}
            graph={conductorGraph}
            pausedAt={pausedAt}
          />
        </div>
      ) : tab === "decision" ? (
        <div className="min-h-0 flex-1 overflow-auto bg-white">
          {!decision && (
            <div className="p-6">
              <button
                onClick={decideNow}
                className="rounded-[8px] bg-indigo px-3 py-1.5 text-sm font-medium text-white"
              >
                Compute EV
              </button>
            </div>
          )}
          <DecisionRoom
            decision={decision}
            risks={risks}
            onSignOff={handleSignOff}
            onOverride={handleOverride}
            /* Single operator: the same person signs off. The checkpoint
               itself still stands — it just never waits on someone else. */
            canSignOff
            roleNote=""
          />
        </div>
      ) : (
      <div className="flex min-h-0 flex-1">
        <aside className="w-[30rem] shrink-0 overflow-auto border-r bg-white">
          {tab === "matrix" ? (
            <MatrixTable
              verdicts={verdicts}
              onProof={setHighlight}
              onDecide={(row) => {
                setDeciding(row);
                setDecision2({ verdict: "complies", reason: "", name: decidedName });
              }}
            />
          ) : (
            <>
              {rules.length === 0 && (
                <p className="p-4 text-sm text-ink-muted">
                  No rules yet — upload finished parsing? Hit re-run.
                </p>
              )}
              {families.map((family) => (
                <section key={family}>
                  <h2 className="sticky top-0 border-b bg-surface px-3 py-1.5 text-xs font-semibold uppercase tracking-wide text-ink-muted">
                    {family}
                  </h2>
                  {rules
                    .filter((r) => r.family === family)
                    .map((rule) => (
                      <button
                        key={rule.rule_id}
                        data-testid="rule-row"
                        onClick={() => {
                          setSelectedRule(rule.rule_id);
                          setHighlight({
                            page_no: rule.page_no,
                            bbox: rule.bbox,
                            document_id: rule.document_id,
                          });
                        }}
                        className={`block w-full border-b px-3 py-2 text-left hover:bg-warning-tint ${
                          selectedRule === rule.rule_id ? "bg-warning-tint" : ""
                        }`}
                      >
                        <div className="flex items-center justify-between gap-2">
                          <span className="flex min-w-0 items-center gap-1.5">
                            {rule.clause_ref && (
                              <span className="shrink-0 rounded-[8px] bg-indigo-tint px-1.5 text-[11px] font-medium text-indigo">
                                {rule.clause_ref}
                              </span>
                            )}
                            <span className="truncate font-mono text-xs text-ink">
                              {rule.key}
                            </span>
                            {rule.obligation !== "mandatory" && (
                              <span
                                className="shrink-0 text-[11px] text-ink-subtle"
                                title="This clause does not strictly bind the bidder"
                              >
                                {rule.obligation}
                              </span>
                            )}
                          </span>
                          <ConfidenceChip
                            confidence={rule.confidence}
                            band={rule.band}
                            reason={rule.reason}
                          />
                        </div>
                        {rule.value && (
                          <div className="mt-0.5 text-sm font-medium text-ink">
                            {rule.value}
                          </div>
                        )}
                        <div className="mt-0.5 line-clamp-2 text-xs text-ink-muted">
                          {rule.requirement_text}
                        </div>
                        {rule.learned && <LearnedNote learned={rule.learned} />}
                        <div className="mt-1 flex items-center gap-2 text-[11px] text-ink-subtle">
                          <span>p.{rule.page_no}</span>
                          <span>{rule.source}</span>
                          {rule.status === "needs_human" && (
                            <span className="rounded-[8px] bg-danger-tint px-1 text-danger">
                              needs human
                            </span>
                          )}
                        </div>
                      </button>
                    ))}
                </section>
              ))}
            </>
          )}
        </aside>

        <main className="min-w-0 flex-1">
          <PdfProof
            tenderId={tenderId}
            documentId={highlight?.document_id ?? rules[0]?.document_id ?? null}
            highlight={highlight}
          />
        </main>
      </div>
      )}
    </div>
  );
}
