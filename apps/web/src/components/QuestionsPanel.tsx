// Pre-bid question pack (US-08): a drafted letter for every rule we fail,
// each citing its clause + page. Drafts only — the human sends. There is
// deliberately no "send" button here.
import { MessageSquareQuote } from "lucide-react";
import { EmptyState } from "../ui/primitives";
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
        <h2 className="text-sm font-semibold text-ink">
          Pre-bid question pack
        </h2>
        <span className="text-xs text-ink-subtle">
          drafts only — a human sends each letter
        </span>
        <button
          onClick={onGenerate}
          disabled={busy}
          className="ml-auto rounded-[8px] border border-hairline px-2 py-1 text-sm text-ink-muted hover:bg-surface disabled:opacity-50"
        >
          {busy ? "Drafting…" : "Draft questions"}
        </button>
      </div>

      {letters.length === 0 && (
        <EmptyState
          icon={<MessageSquareQuote size={40} strokeWidth={1.25} className="text-ink-subtle" />}
          title="No queries drafted"
          body="When a mandatory rule fails, a letter is drafted here asking the buyer to relax it — with the clause it refers to already cited."
        />
      )}

      {letters.map((letter) => (
        <article
          key={letter.id}
          data-testid="query-letter"
          className="rounded-[12px] border border-hairline bg-white p-4"
        >
          <div className="flex items-center gap-2">
            <span className="font-mono text-xs text-ink">
              {letter.rule_key}
            </span>
            <span className="text-[11px] text-ink-subtle">
              cites p.{letter.page_no}
            </span>
            {letter.query_deadline && (
              <span className="text-[11px] text-warning">
                before {letter.query_deadline}
              </span>
            )}
            <span className="ml-auto rounded-[8px] bg-surface px-1.5 text-[11px] text-ink-muted">
              {letter.status}
            </span>
            <button
              onClick={() => copy(letter)}
              className="rounded-[8px] border border-hairline px-2 py-0.5 text-xs text-ink-muted hover:bg-surface"
            >
              Copy
            </button>
          </div>
          <p className="mt-1 text-sm font-medium text-ink">
            {letter.subject}
          </p>
          <pre className="mt-2 whitespace-pre-wrap rounded-[8px] bg-surface p-3 text-xs text-ink">
            {letter.body}
          </pre>
        </article>
      ))}
    </div>
  );
}
