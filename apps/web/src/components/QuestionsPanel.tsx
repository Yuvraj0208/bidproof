// Pre-bid question pack (US-08): a drafted letter for every rule we fail,
// each citing its clause + page. Drafts only — the human sends. There is
// deliberately no "send" button here.
import type { QueryLetter } from "../api";

export function QuestionsPanel({
  letters,
  onGenerate,
  busy,
}: {
  letters: QueryLetter[];
  onGenerate: () => void;
  busy: boolean;
}) {
  const copy = (letter: QueryLetter) => {
    void navigator.clipboard?.writeText(letter.body);
  };

  return (
    <div className="mx-auto max-w-2xl space-y-4 p-6">
      <div className="flex items-center gap-3">
        <h2 className="text-sm font-semibold text-slate-800">
          Pre-bid question pack
        </h2>
        <span className="text-xs text-slate-400">
          drafts only — a human sends each letter
        </span>
        <button
          onClick={onGenerate}
          disabled={busy}
          className="ml-auto rounded border px-2 py-1 text-sm text-slate-600 hover:bg-slate-50 disabled:opacity-50"
        >
          {busy ? "Drafting…" : "Draft questions"}
        </button>
      </div>

      {letters.length === 0 && (
        <p className="text-sm text-slate-500">
          No queries drafted. When a mandatory rule fails, a letter is drafted
          here asking the buyer to relax it.
        </p>
      )}

      {letters.map((letter) => (
        <article
          key={letter.id}
          data-testid="query-letter"
          className="rounded-lg border bg-white p-4"
        >
          <div className="flex items-center gap-2">
            <span className="font-mono text-xs text-slate-700">
              {letter.rule_key}
            </span>
            <span className="text-[11px] text-slate-400">
              cites p.{letter.page_no}
            </span>
            {letter.query_deadline && (
              <span className="text-[11px] text-amber-700">
                before {letter.query_deadline}
              </span>
            )}
            <span className="ml-auto rounded bg-slate-100 px-1.5 text-[11px] text-slate-500">
              {letter.status}
            </span>
            <button
              onClick={() => copy(letter)}
              className="rounded border px-2 py-0.5 text-xs text-slate-600 hover:bg-slate-50"
            >
              Copy
            </button>
          </div>
          <p className="mt-1 text-sm font-medium text-slate-800">
            {letter.subject}
          </p>
          <pre className="mt-2 whitespace-pre-wrap rounded bg-slate-50 p-3 text-xs text-slate-700">
            {letter.body}
          </pre>
        </article>
      ))}
    </div>
  );
}
