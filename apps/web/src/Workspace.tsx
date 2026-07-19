// Tender Workspace (US-04): rules by family on the left, the PDF with
// click-to-proof highlighting on the right. Click any rule and the document
// shows exactly where it came from — 100% of rules, by construction.
import { useEffect, useState } from "react";
import { fetchRules, runExtraction, type Rule } from "./api";
import { ConfidenceChip } from "./components/ConfidenceChip";
import { PdfProof, type Highlight } from "./components/PdfProof";

const FAMILY_ORDER = ["eligibility", "technical", "commercial", "legal", "submission"];

export function Workspace({
  tenderId,
  title,
  onBack,
}: {
  tenderId: string;
  title: string;
  onBack: () => void;
}) {
  const [rules, setRules] = useState<Rule[]>([]);
  const [highlight, setHighlight] = useState<Highlight | null>(null);
  const [selectedRule, setSelectedRule] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const load = () => fetchRules(tenderId).then(setRules).catch(() => setRules([]));
  useEffect(() => {
    load();
  }, [tenderId]);

  const extract = async () => {
    setBusy(true);
    try {
      await runExtraction(tenderId);
      await load();
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
        <span className="text-xs text-slate-400">{rules.length} rules</span>
        <button
          onClick={extract}
          disabled={busy}
          className="ml-auto rounded border px-2 py-1 text-sm text-slate-600 hover:bg-slate-50 disabled:opacity-50"
        >
          {busy ? "Extracting…" : "Re-extract"}
        </button>
      </header>

      <div className="flex min-h-0 flex-1">
        <aside className="w-[26rem] shrink-0 overflow-auto border-r bg-white">
          {rules.length === 0 && (
            <p className="p-4 text-sm text-slate-500">
              No rules yet — upload finished parsing? Hit re-extract.
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
                      setHighlight({ page_no: rule.page_no, bbox: rule.bbox });
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
        </aside>

        <main className="min-w-0 flex-1">
          <PdfProof tenderId={tenderId} highlight={highlight} />
        </main>
      </div>
    </div>
  );
}
