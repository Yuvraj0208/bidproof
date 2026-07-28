// The landing page: the product's argument, then the door in.
//
// Design intent — the thing BidProof sells is *certainty*, so the page is built
// on that feeling rather than on excitement: deep indigo, a lot of quiet space,
// one idea per screenful, and a single animated flourish (the proof beam) that
// literally demonstrates click-to-proof. No stock illustration, no gradients for
// their own sake, nothing that moves without saying something.
import { AnimatePresence, motion } from "framer-motion";
import { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import {
  fetchOrganizations,
  signIn,
  type OrgSummary,
} from "../api";
import { OrgBadge } from "../ui/OrgBadge";
import { Button } from "../ui/primitives";

/* ------------------------------------------------------------------ atoms */

const ease = [0.22, 0.61, 0.36, 1] as const;

function Reveal({
  children,
  delay = 0,
  y = 18,
}: {
  children: React.ReactNode;
  delay?: number;
  y?: number;
}) {
  return (
    <motion.div
      initial={{ opacity: 0, y }}
      whileInView={{ opacity: 1, y: 0 }}
      viewport={{ once: true, margin: "-60px" }}
      transition={{ duration: 0.55, delay, ease }}
    >
      {children}
    </motion.div>
  );
}

/** The hero's one flourish: a page of clauses, with the proof box landing on
 *  the clause that matters. It is the product's whole promise in four seconds. */
function ProofBeam() {
  const lines = [
    { w: "62%", t: "TENDER NOTICE No. 42/2026" },
    { w: "88%", t: "Supply of industrial storage racks" },
    { w: "74%", t: "Earnest Money Deposit: Rs 2,50,000", hit: true },
    { w: "80%", t: "Minimum average annual turnover: Rs 5 crore" },
    { w: "56%", t: "Delivery period: 90 days" },
    { w: "70%", t: "Bidder must hold valid ISO 9001" },
  ];
  return (
    <div className="relative rounded-[16px] border border-white/10 bg-white/[0.04] p-5 backdrop-blur-sm">
      <div className="mb-4 flex items-center gap-2 text-[11px] text-white/40">
        <span className="h-2 w-2 rounded-full bg-white/25" />
        <span className="h-2 w-2 rounded-full bg-white/25" />
        <span className="ml-1 font-mono">tender.pdf · page 1</span>
      </div>

      <div className="space-y-2.5">
        {lines.map((line, i) => (
          <div key={line.t} className="relative">
            <motion.div
              initial={{ opacity: 0, x: -8 }}
              animate={{ opacity: 1, x: 0 }}
              transition={{ delay: 0.5 + i * 0.09, duration: 0.4, ease }}
              className="flex items-center"
            >
              <span
                className={`truncate text-[11px] ${
                  line.hit ? "text-white" : "text-white/35"
                }`}
                style={{ width: line.w }}
              >
                {line.t}
              </span>
            </motion.div>

            {line.hit && (
              <motion.div
                initial={{ opacity: 0, scaleX: 0.6 }}
                animate={{ opacity: 1, scaleX: 1 }}
                transition={{ delay: 1.5, duration: 0.5, ease }}
                style={{ originX: 0, width: line.w }}
                className="pointer-events-none absolute -inset-y-1 -left-1.5 rounded-[6px] border-2 border-warning bg-warning/20"
              />
            )}
          </div>
        ))}
      </div>

      <motion.div
        initial={{ opacity: 0, y: 6 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 2.1, duration: 0.45, ease }}
        className="mt-5 flex items-center gap-2 rounded-[8px] border border-success/30 bg-success/10 px-2.5 py-1.5"
      >
        <span aria-hidden className="text-success">✓</span>
        <span className="text-[11px] text-white/80">
          <span className="font-medium">emd_amount = ₹2,50,000</span>
          <span className="text-white/45"> · page 1, box (73, 188) · verified</span>
        </span>
      </motion.div>
    </div>
  );
}

/* --------------------------------------------------------------- sign-in */

function SignInPanel({
  orgs,
  loading,
  error,
  onRetry,
  onClose,
  onSignedIn,
}: {
  orgs: OrgSummary[];
  loading: boolean;
  error: string | null;
  onRetry: () => void;
  onClose: () => void;
  onSignedIn: () => void;
}) {
  const navigate = useNavigate();
  const [picked, setPicked] = useState<OrgSummary | null>(null);
  const [query, setQuery] = useState("");

  const shown = useMemo(
    () =>
      orgs.filter((o) =>
        (o.name + o.slug).toLowerCase().includes(query.trim().toLowerCase()),
      ),
    [orgs, query],
  );

  const enter = () => {
    if (!picked) return;
    signIn(picked);
    // Tell Root the session exists BEFORE navigating: the `storage` event does
    // not fire in the tab that wrote it, so without this the /app route would
    // still see a null session and bounce straight back here.
    onSignedIn();
    navigate("/app");
  };

  return (
    <motion.div
      className="fixed inset-0 z-50 flex items-center justify-center p-4"
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0 }}
      transition={{ duration: 0.18 }}
    >
      <div className="absolute inset-0 bg-ink/70 backdrop-blur-md" onClick={onClose} />
      <motion.div
        data-testid="signin-panel"
        role="dialog"
        aria-modal="true"
        aria-label="Sign in"
        initial={{ opacity: 0, y: 14, scale: 0.985 }}
        animate={{ opacity: 1, y: 0, scale: 1 }}
        exit={{ opacity: 0, y: 8 }}
        transition={{ duration: 0.22, ease }}
        className="relative z-10 w-full max-w-md overflow-hidden rounded-[16px] border border-hairline bg-white shadow-modal"
      >
        <div className="border-b border-hairline px-5 py-4">
          <h2 className="text-base font-semibold text-ink">Sign in to your workspace</h2>
          <p className="mt-0.5 text-xs text-ink-muted">
            Choose the company whose tenders you work on.
          </p>
        </div>

        <div className="px-5 py-4">
          {loading && (
            <p className="py-6 text-center text-sm text-ink-muted">Loading companies…</p>
          )}

          {error && (
            <div className="rounded-[8px] border border-danger/25 bg-danger-tint px-3 py-2">
              <p className="text-sm font-medium text-danger">Could not reach the API</p>
              <p className="mt-1 text-xs text-danger/80">{error}</p>
              <Button size="sm" className="mt-2" onClick={onRetry}>Retry</Button>
            </div>
          )}

          {!loading && !error && orgs.length === 0 && (
            <div className="rounded-[8px] border border-dashed border-hairline bg-surface px-3 py-6 text-center">
              <p className="text-sm font-medium text-ink">No companies yet</p>
              <p className="mt-1 text-xs text-ink-muted">
                Add your company first — it takes a few minutes.
              </p>
              <Button
                variant="primary"
                size="sm"
                className="mt-3"
                onClick={() => navigate("/new-company")}
              >
                Add a company
              </Button>
            </div>
          )}

          {!loading && !error && orgs.length > 0 && (
            <>
              {orgs.length > 4 && (
                <input
                  value={query}
                  onChange={(e) => setQuery(e.target.value)}
                  placeholder="Search companies…"
                  className="mb-2 w-full rounded-[8px] border border-hairline px-2.5 py-1.5 text-sm"
                />
              )}
              <ul className="max-h-64 space-y-1 overflow-auto">
                {shown.map((org) => {
                  const active = picked?.org_id === org.org_id;
                  return (
                    <li key={org.org_id}>
                      <button
                        data-testid="org-option"
                        onClick={() => setPicked(org)}
                        className={`flex w-full items-center gap-3 rounded-[8px] border px-3 py-2 text-left transition-colors duration-150 ${
                          active
                            ? "border-indigo bg-indigo-tint"
                            : "border-hairline hover:bg-surface"
                        }`}
                      >
                        <OrgBadge org={org} size={30} />
                        <span className="min-w-0 flex-1">
                          <span className="block truncate text-sm font-medium text-ink">
                            {org.name}
                          </span>
                          <span className="block truncate text-[11px] text-ink-subtle">
                            {org.slug}
                            {!org.onboarded && " · setup incomplete"}
                          </span>
                        </span>
                        {active && <span aria-hidden className="text-indigo">✓</span>}
                      </button>
                    </li>
                  );
                })}
              </ul>


              <Button
                variant="primary"
                className="mt-4 w-full justify-center"
                disabled={!picked}
                onClick={enter}
              >
                {picked ? `Enter ${picked.name}` : "Choose a company"}
              </Button>
            </>
          )}

          <p className="mt-4 border-t border-hairline pt-3 text-[11px] text-ink-subtle">
            New here?{" "}
            <button
              onClick={() => navigate("/new-company")}
              className="font-medium text-indigo hover:underline"
            >
              Add your company
            </button>
          </p>
        </div>
      </motion.div>
    </motion.div>
  );
}

/* --------------------------------------------------------------- landing */

const PROOF_POINTS = [
  {
    k: "Reads what nobody has time to read",
    v: "300–800 page tenders, some scanned, some in Hindi. Every line is tied to a page and a box before anything downstream may touch it.",
    stat: "13 clauses",
    statNote: "extracted from one tender, each citable",
  },
  {
    k: "Answers in rupees, not a score",
    v: "Expected value with the maths shown term by term — expected profit, minus the cost of bidding, minus the cost of money locked in EMD and PBG. A CFO can argue with it.",
    stat: "₹0.04",
    statNote: "model cost per tender, on screen",
  },
  {
    k: "Allowed to say “I don’t know”",
    v: "An uncited fact cannot be stored — the database refuses it. Where evidence is missing the verdict is “needs human”, never a guess.",
    stat: "zero",
    statNote: "hallucinations, by structure",
  },
];

export default function Landing({ onSignedIn }: { onSignedIn: () => void }) {
  const navigate = useNavigate();
  const [orgs, setOrgs] = useState<OrgSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [showSignIn, setShowSignIn] = useState(false);

  const load = () => {
    setLoading(true);
    setError(null);
    fetchOrganizations()
      .then(setOrgs)
      .catch((e) => setError(String(e)))
      .finally(() => setLoading(false));
  };

  useEffect(load, []);

  return (
    <div className="min-h-screen bg-indigo text-white">
      {/* a single soft light source, not a rainbow */}
      <div
        aria-hidden
        className="pointer-events-none fixed inset-0"
        style={{
          background:
            "radial-gradient(1100px 620px at 68% -8%, rgba(120,128,255,0.30), transparent 62%)," +
            "radial-gradient(800px 500px at 8% 108%, rgba(42,45,143,0.55), transparent 60%)",
        }}
      />

      <div className="relative">
        {/* ---------------------------------------------------------- nav */}
        <header className="mx-auto flex max-w-6xl items-center gap-4 px-6 py-5">
          <span className="text-[17px] font-semibold tracking-[-0.01em]">BidProof</span>
          <span className="hidden text-[11px] text-white/40 sm:inline">
            Proof for every claim
          </span>
          <nav className="ml-auto flex items-center gap-2">
            <button
              onClick={() => navigate("/new-company")}
              className="rounded-[8px] px-3 py-1.5 text-sm text-white/75 transition-colors duration-150 hover:bg-white/10 hover:text-white"
            >
              Add your company
            </button>
            <button
              data-testid="signin-button"
              onClick={() => setShowSignIn(true)}
              className="rounded-[8px] bg-white px-3.5 py-1.5 text-sm font-medium text-indigo transition-transform duration-150 hover:scale-[1.02]"
            >
              Sign in
            </button>
          </nav>
        </header>

        {/* --------------------------------------------------------- hero */}
        <section className="mx-auto grid max-w-6xl items-center gap-12 px-6 pb-20 pt-10 lg:grid-cols-[1.05fr_0.95fr] lg:pt-16">
          <div>
            <motion.p
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.5, ease }}
              className="mb-5 inline-flex items-center gap-2 rounded-full border border-white/15 bg-white/[0.06] px-3 py-1 text-[11px] text-white/70"
            >
              <span className="h-1.5 w-1.5 rounded-full bg-success" />
              Built for Indian government tendering
            </motion.p>

            <motion.h1
              initial={{ opacity: 0, y: 16 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.65, ease }}
              className="text-[clamp(2.4rem,5.2vw,4rem)] font-semibold leading-[1.04] tracking-[-0.03em]"
            >
              One bid in three is
              <br />
              thrown out on
              <br />
              <span className="relative inline-block">
                paperwork.
                <motion.span
                  aria-hidden
                  initial={{ scaleX: 0 }}
                  animate={{ scaleX: 1 }}
                  transition={{ delay: 0.8, duration: 0.6, ease }}
                  style={{ originX: 0 }}
                  className="absolute -bottom-1 left-0 h-[3px] w-full rounded bg-warning"
                />
              </span>
            </motion.h1>

            <motion.p
              initial={{ opacity: 0, y: 12 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.25, duration: 0.6, ease }}
              className="mt-6 max-w-xl text-[17px] leading-relaxed text-white/70"
            >
              BidProof finds the tenders you should bid on, reads all 800 pages,
              checks every rule against what your company actually has, and tells
              you whether to bid — <span className="text-white">as a rupee figure</span>.
              Every sentence clicks back to the page it came from.
            </motion.p>

            <motion.div
              initial={{ opacity: 0, y: 12 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.4, duration: 0.6, ease }}
              className="mt-9 flex flex-wrap items-center gap-3"
            >
              <button
                onClick={() => setShowSignIn(true)}
                className="rounded-[10px] bg-white px-5 py-2.5 text-sm font-semibold text-indigo shadow-lg shadow-black/20 transition-transform duration-150 hover:scale-[1.02]"
              >
                Sign in to your workspace
              </button>
              <button
                onClick={() => navigate("/new-company")}
                className="rounded-[10px] border border-white/20 px-5 py-2.5 text-sm font-medium text-white transition-colors duration-150 hover:bg-white/10"
              >
                Add your company →
              </button>
            </motion.div>

            <motion.p
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              transition={{ delay: 0.7, duration: 0.6 }}
              className="mt-5 text-[11px] text-white/40"
            >
              Live portal discovery from GeM and CPPP · human sign-off at every
              checkpoint · no agent can submit, export or delete
            </motion.p>
          </div>

          <motion.div
            initial={{ opacity: 0, y: 24 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.3, duration: 0.7, ease }}
          >
            <ProofBeam />
          </motion.div>
        </section>

        {/* ------------------------------------------------------ the case */}
        <section className="border-t border-white/10 bg-ink/25">
          <div className="mx-auto max-w-6xl px-6 py-20">
            <Reveal>
              <h2 className="max-w-2xl text-[clamp(1.5rem,3vw,2.1rem)] font-semibold leading-tight tracking-[-0.02em]">
                Most tools summarise. This one proves.
              </h2>
            </Reveal>

            <div className="mt-12 grid gap-10 md:grid-cols-3">
              {PROOF_POINTS.map((point, i) => (
                <Reveal key={point.k} delay={i * 0.09}>
                  <div className="border-t border-white/15 pt-5">
                    <div
                      data-numeric
                      className="text-[2rem] font-semibold tracking-[-0.02em] text-white"
                    >
                      {point.stat}
                    </div>
                    <div className="mt-0.5 text-[11px] uppercase tracking-wide text-white/40">
                      {point.statNote}
                    </div>
                    <h3 className="mt-5 text-[15px] font-semibold text-white">
                      {point.k}
                    </h3>
                    <p className="mt-2 text-sm leading-relaxed text-white/60">
                      {point.v}
                    </p>
                  </div>
                </Reveal>
              ))}
            </div>
          </div>
        </section>

        {/* ------------------------------------------------------ pipeline */}
        <section className="mx-auto max-w-6xl px-6 py-20">
          <Reveal>
            <h2 className="text-[clamp(1.5rem,3vw,2.1rem)] font-semibold tracking-[-0.02em]">
              Five steps, and a human in charge of each one
            </h2>
          </Reveal>
          <div className="mt-10 grid gap-3 sm:grid-cols-2 lg:grid-cols-5">
            {[
              ["Discover", "Watch GeM and CPPP, or upload a PDF. Nothing reaches a model until you press Process."],
              ["Read", "The reader ladder: real text, then OCR, then a human. Never a guess."],
              ["Check", "Every rule against your capability database. Arithmetic in code, never by a model."],
              ["Decide", "Go or no-go as an expected value in rupees, signed off by a named human."],
              ["Draft", "A proposal where every factual sentence is tagged to your own data and fact-checked."],
            ].map(([title, body], i) => (
              <Reveal key={title} delay={i * 0.07}>
                <div className="h-full rounded-[12px] border border-white/10 bg-white/[0.04] p-4">
                  <div className="mb-2 flex h-6 w-6 items-center justify-center rounded-full bg-white/10 text-[11px] font-semibold">
                    {i + 1}
                  </div>
                  <h3 className="text-sm font-semibold">{title}</h3>
                  <p className="mt-1.5 text-[12px] leading-relaxed text-white/55">
                    {body}
                  </p>
                </div>
              </Reveal>
            ))}
          </div>
        </section>

        {/* ---------------------------------------------------------- cta */}
        <section className="border-t border-white/10">
          <div className="mx-auto max-w-3xl px-6 py-24 text-center">
            <Reveal>
              <h2 className="text-[clamp(1.6rem,3.4vw,2.4rem)] font-semibold leading-tight tracking-[-0.02em]">
                Stop losing bids to paperwork
              </h2>
              <p className="mx-auto mt-4 max-w-lg text-[15px] leading-relaxed text-white/65">
                Load your turnover, certifications and product catalogue once.
                Every tender after that is read against them automatically.
              </p>
              <div className="mt-8 flex flex-wrap justify-center gap-3">
                <button
                  onClick={() => navigate("/new-company")}
                  className="rounded-[10px] bg-white px-5 py-2.5 text-sm font-semibold text-indigo transition-transform duration-150 hover:scale-[1.02]"
                >
                  Add your company
                </button>
                <button
                  onClick={() => setShowSignIn(true)}
                  className="rounded-[10px] border border-white/20 px-5 py-2.5 text-sm font-medium transition-colors duration-150 hover:bg-white/10"
                >
                  Sign in
                </button>
              </div>
            </Reveal>
          </div>
        </section>

        <footer className="border-t border-white/10">
          <div className="mx-auto flex max-w-6xl flex-wrap items-center gap-3 px-6 py-6 text-[11px] text-white/35">
            <span className="font-medium text-white/55">BidProof</span>
            <span>Every extracted rule, verdict and sentence carries its page and box.</span>
            <span className="ml-auto">{orgs.length} workspace{orgs.length === 1 ? "" : "s"}</span>
          </div>
        </footer>
      </div>

      <AnimatePresence>
        {showSignIn && (
          <SignInPanel
            orgs={orgs}
            loading={loading}
            error={error}
            onRetry={load}
            onClose={() => setShowSignIn(false)}
            onSignedIn={onSignedIn}
          />
        )}
      </AnimatePresence>
    </div>
  );
}
