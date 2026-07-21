// Tender Radar (SPEC §17 screen 1): two lists + the Checkpoint-0 queue.
// Every card wears the confidence chip — the design system's trust primitive.
import { useEffect, useState } from "react";
import {
  fetchRadar,
  getOrgId,
  getRole,
  ROLES,
  runModelLab,
  setOrgId,
  setRole,
  type ModelLabResult,
  type RadarCard,
  type RoleName,
} from "./api";
import { ModelLab } from "./components/ModelLab";
import { ConfidenceChip } from "./components/ConfidenceChip";
import { Workspace } from "./Workspace";

const TABS = [
  { id: "in_our_lane", label: "In our lane" },
  { id: "opportunity_radar", label: "Opportunity radar" },
  { id: "needs_human", label: "Needs human" },
] as const;

export default function App() {
  const [org, setOrg] = useState(getOrgId());
  const [role, setRoleState] = useState<RoleName>(getRole());
  const [tab, setTab] = useState<string>("in_our_lane");
  const [cards, setCards] = useState<RadarCard[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [open, setOpen] = useState<{ id: string; title: string } | null>(null);
  const [showLab, setShowLab] = useState(false);
  const [lab, setLab] = useState<ModelLabResult | null>(null);
  const [labBusy, setLabBusy] = useState(false);

  const runLab = async () => {
    setLabBusy(true);
    try {
      setLab(await runModelLab("extraction"));
    } finally {
      setLabBusy(false);
    }
  };

  useEffect(() => {
    if (!org) return;
    setError(null);
    fetchRadar(tab)
      .then(setCards)
      .catch((e) => {
        setCards([]);
        setError(String(e));
      });
  }, [org, tab, open]);

  if (open) {
    return (
      <Workspace
        tenderId={open.id}
        title={open.title}
        onBack={() => setOpen(null)}
      />
    );
  }

  if (showLab) {
    return (
      <div className="min-h-screen bg-slate-50">
        <header className="flex items-center gap-4 border-b bg-white px-6 py-3">
          <h1 className="text-lg font-semibold text-indigo-900">BidProof</h1>
          <button
            onClick={() => setShowLab(false)}
            className="rounded border px-2 py-1 text-sm text-slate-600 hover:bg-slate-50"
          >
            ← Radar
          </button>
        </header>
        <ModelLab result={lab} onRun={runLab} busy={labBusy} />
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-slate-50">
      <header className="border-b bg-white px-6 py-3">
        <div className="flex items-center gap-4">
          <h1 className="text-lg font-semibold text-indigo-900">BidProof</h1>
          <span className="text-xs text-slate-400">Tender Radar</span>
          <button
            onClick={() => setShowLab(true)}
            className="rounded border px-2 py-1 text-xs text-slate-600 hover:bg-slate-50"
          >
            Model Lab
          </button>
          <input
            value={org}
            onChange={(e) => {
              setOrg(e.target.value);
              setOrgId(e.target.value);
            }}
            placeholder="Org id"
            className="ml-auto w-80 rounded border px-2 py-1 font-mono text-xs"
          />
          <select
            data-testid="role-select"
            value={role}
            onChange={(e) => {
              const next = e.target.value as RoleName;
              setRoleState(next);
              setRole(next);
            }}
            className="rounded border px-2 py-1 text-xs"
            title="Acting role — gates sensitive actions"
          >
            {ROLES.map((r) => (
              <option key={r} value={r}>
                {r}
              </option>
            ))}
          </select>
        </div>
      </header>

      <nav className="flex gap-1 border-b bg-white px-6">
        {TABS.map((t) => (
          <button
            key={t.id}
            onClick={() => setTab(t.id)}
            className={`border-b-2 px-3 py-2 text-sm ${
              tab === t.id
                ? "border-indigo-600 font-medium text-indigo-800"
                : "border-transparent text-slate-500 hover:text-slate-700"
            }`}
          >
            {t.label}
          </button>
        ))}
      </nav>

      <main className="mx-auto max-w-3xl px-6 py-6">
        {!org && (
          <p className="text-sm text-slate-500">
            Paste your organisation id above to load the radar.
          </p>
        )}
        {error && <p className="text-sm text-red-600">{error}</p>}
        {org && !error && cards.length === 0 && (
          <p className="text-sm text-slate-500">
            No tenders in this list yet — upload one or run discovery.
          </p>
        )}
        <div className="space-y-3">
          {cards.map((card) => (
            <article
              key={card.tender_id}
              data-testid="radar-card"
              className="rounded-lg border bg-white p-4 shadow-sm"
            >
              <div className="flex items-start justify-between gap-3">
                <button
                  onClick={() => setOpen({ id: card.tender_id, title: card.title })}
                  className="text-left text-sm font-semibold text-slate-900 hover:text-indigo-700"
                >
                  {card.title}
                </button>
                <ConfidenceChip
                  confidence={card.confidence}
                  band={card.band}
                  reason={card.reasons.join(" · ")}
                />
              </div>
              <div className="mt-1 flex items-center gap-2 text-xs text-slate-400">
                <span>{card.source}</span>
                {card.external_id && <span>{card.external_id}</span>}
                {card.fit_score != null && (
                  <span>fit {card.fit_score.toFixed(2)}</span>
                )}
                {card.checkpoint0 && <span>checkpoint-0: {card.checkpoint0}</span>}
              </div>
              <ul className="mt-2 flex flex-wrap gap-1.5">
                {card.reasons.map((reason) => (
                  <li
                    key={reason}
                    className="rounded bg-slate-100 px-2 py-0.5 text-xs text-slate-600"
                  >
                    {reason}
                  </li>
                ))}
              </ul>
            </article>
          ))}
        </div>
      </main>
    </div>
  );
}
