// Tender Workspace: Rules and the Compliance Matrix on the left, the PDF
// with click-to-proof on the right. More tabs (Decision, Console) arrive
// with their stories.
import { useEffect, useState } from "react";
import {
  amendTender,
  approveSection,
  askChat,
  attachChecklistFile,
  computeDecision,
  downloadMatrix,
  fetchAgentRuns,
  fetchAmendments,
  fetchChatHistory,
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
import { MatrixTable } from "./components/MatrixTable";
import { PdfProof, type Highlight } from "./components/PdfProof";

const FAMILY_ORDER = ["eligibility", "technical", "commercial", "legal", "submission"];

type Tab =
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
  const [tab, setTab] = useState<Tab>("rules");
  const [rules, setRules] = useState<Rule[]>([]);
  const [verdicts, setVerdicts] = useState<Verdict[]>([]);
  const [decision, setDecision] = useState<DecisionData | null>(null);
  const [risks, setRisks] = useState<BriefRisk[]>([]);
  const [agentRuns, setAgentRuns] = useState<AgentRunData[]>([]);
  const [consoleTotals, setConsoleTotals] = useState<ConsoleTotals | null>(null);
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
    fetchRules(tenderId).then(setRules).catch(() => setRules([]));
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
    fetchAmendments(tenderId).then(setAmendments).catch(() => setAmendments([]));
    fetchQuestions(tenderId).then(setLetters).catch(() => setLetters([]));
    fetchProposal(tenderId).then(setProposal).catch(() => setProposal(null));
    exportPreflight(tenderId)
      .then((p) => setBlockers(p.blockers))
      .catch(() => setBlockers(null));
    fetchChecklist(tenderId).then(setChecklist).catch(() => setChecklist(null));
    fetchChatHistory(tenderId).then(setChatTurns).catch(() => setChatTurns([]));
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

  return (
    <div className="flex h-screen flex-col">
      <header className="flex items-center gap-3 border-b bg-white px-4 py-2">
        <button
          onClick={onBack}
          className="rounded border px-2 py-1 text-sm text-slate-600 hover:bg-slate-50"
        >
          ← Radar
        </button>
        <h1 className="truncate text-sm font-semibold text-slate-800">{title}</h1>
        <nav className="ml-4 flex gap-1">
          {(
            [
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
                className={`rounded px-2 py-1 text-sm ${
                  tab === t
                    ? "bg-indigo-50 font-medium text-indigo-800"
                    : "text-slate-500 hover:text-slate-700"
                }`}
              >
                {t === "rules"
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
        <div className="ml-auto flex gap-2">
          {tab === "matrix" && verdicts.length > 0 && (
            <button
              onClick={() => downloadMatrix(tenderId)}
              className="rounded border px-2 py-1 text-sm text-slate-600 hover:bg-slate-50"
            >
              Export .xlsx
            </button>
          )}
          <button
            onClick={recheck}
            disabled={busy}
            className="rounded border px-2 py-1 text-sm text-slate-600 hover:bg-slate-50 disabled:opacity-50"
          >
            {busy ? "Working…" : "Re-run"}
          </button>
        </div>
      </header>

      {tab === "chat" ? (
        <div className="min-h-0 flex-1 overflow-hidden bg-slate-50">
          <ChatPanel turns={chatTurns} onAsk={handleAsk} busy={asking} />
        </div>
      ) : tab === "checklist" ? (
        <div className="min-h-0 flex-1 overflow-auto bg-slate-50">
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
        <div className="min-h-0 flex-1 overflow-auto bg-slate-50">
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
            busy={writing}
          />
        </div>
      ) : tab === "questions" ? (
        <div className="min-h-0 flex-1 overflow-auto bg-slate-50">
          <QuestionsPanel
            letters={letters}
            onGenerate={handleDraftQuestions}
            busy={drafting}
          />
        </div>
      ) : tab === "amendments" ? (
        <div className="min-h-0 flex-1 overflow-auto bg-slate-50">
          <AmendmentsPanel
            amendments={amendments}
            onAmend={handleAmend}
            busy={amending}
          />
        </div>
      ) : tab === "console" ? (
        <div className="min-h-0 flex-1 overflow-auto bg-slate-50">
          <AgentConsole
            runs={agentRuns}
            totals={consoleTotals}
            onReplay={handleReplay}
            replaying={replaying}
          />
        </div>
      ) : tab === "decision" ? (
        <div className="min-h-0 flex-1 overflow-auto bg-white">
          {!decision && (
            <div className="p-6">
              <button
                onClick={decideNow}
                className="rounded bg-indigo-600 px-3 py-1.5 text-sm font-medium text-white"
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
          />
        </div>
      ) : (
      <div className="flex min-h-0 flex-1">
        <aside className="w-[30rem] shrink-0 overflow-auto border-r bg-white">
          {tab === "matrix" ? (
            <MatrixTable verdicts={verdicts} onProof={setHighlight} />
          ) : (
            <>
              {rules.length === 0 && (
                <p className="p-4 text-sm text-slate-500">
                  No rules yet — upload finished parsing? Hit re-run.
                </p>
              )}
              {families.map((family) => (
                <section key={family}>
                  <h2 className="sticky top-0 border-b bg-slate-50 px-3 py-1.5 text-xs font-semibold uppercase tracking-wide text-slate-500">
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
                        className={`block w-full border-b px-3 py-2 text-left hover:bg-amber-50 ${
                          selectedRule === rule.rule_id ? "bg-amber-50" : ""
                        }`}
                      >
                        <div className="flex items-center justify-between gap-2">
                          <span className="font-mono text-xs text-slate-700">
                            {rule.key}
                          </span>
                          <ConfidenceChip
                            confidence={rule.confidence}
                            band={rule.band}
                            reason={rule.reason}
                          />
                        </div>
                        {rule.value && (
                          <div className="mt-0.5 text-sm font-medium text-slate-900">
                            {rule.value}
                          </div>
                        )}
                        <div className="mt-0.5 line-clamp-2 text-xs text-slate-500">
                          {rule.requirement_text}
                        </div>
                        <div className="mt-1 flex items-center gap-2 text-[11px] text-slate-400">
                          <span>p.{rule.page_no}</span>
                          <span>{rule.source}</span>
                          {rule.status === "needs_human" && (
                            <span className="rounded bg-red-100 px-1 text-red-700">
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
