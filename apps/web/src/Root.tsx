// Route table. Two worlds: the public landing/onboarding pages, and the signed-in
// application inside the AppShell.
//
// Signing in means choosing a company. That is a WORKSPACE SELECTOR, not
// authentication — there is no password and the API still trusts the X-Org-Id
// header. Real sign-in (SSO/OIDC per SPEC §11.4) has to land before this is put
// on a public URL; until then it is a local-demo convenience.
import { useEffect, useState } from "react";
import { Navigate, Route, Routes, useNavigate, useParams } from "react-router-dom";
import App from "./App";
import KitchenSink from "./KitchenSink";
import Landing from "./screens/Landing";
import NewCompany from "./screens/NewCompany";
import Analytics from "./screens/Analytics";
import Admin from "./screens/Admin";
import { Workspace } from "./Workspace";
import { ModelLab } from "./components/ModelLab";
import {
  getSession,
  runModelLab,
  signOut as clearSession,
  type ModelLabResult,
  type OrgSummary,
} from "./api";
import { AppShell } from "./ui/AppShell";
import { EmptyState, Button } from "./ui/primitives";
import { ToastHost } from "./ui/overlays";

/** The tender currently in context, remembered across screens and reloads. */
export function useCurrentTender() {
  const [tender, setTender] = useState<{ id: string; title: string } | null>(() => {
    try {
      const raw = localStorage.getItem("bidproof_tender");
      return raw ? JSON.parse(raw) : null;
    } catch {
      return null;
    }
  });
  const select = (next: { id: string; title: string } | null) => {
    setTender(next);
    if (next) localStorage.setItem("bidproof_tender", JSON.stringify(next));
    else localStorage.removeItem("bidproof_tender");
  };
  return { tender, select };
}

function WorkspaceRoute({
  tender,
  onBack,
}: {
  tender: { id: string; title: string } | null;
  onBack: () => void;
}) {
  const navigate = useNavigate();
  const { tenderId } = useParams();
  const id = tenderId ?? tender?.id;
  if (!id) {
    return (
      <div className="p-8">
        <EmptyState
          title="No tender open"
          body="Pick a tender from the radar to read it, check it, and decide on it."
          action={
            <Button variant="primary" onClick={() => navigate("/app")}>
              Go to Tender Radar
            </Button>
          }
        />
      </div>
    );
  }
  return <Workspace tenderId={id} title={tender?.title ?? "Tender"} onBack={onBack} />;
}

function LabRoute() {
  const [result, setResult] = useState<ModelLabResult | null>(null);
  const [busy, setBusy] = useState(false);
  const run = async () => {
    setBusy(true);
    try {
      setResult(await runModelLab("extraction"));
    } finally {
      setBusy(false);
    }
  };
  return <ModelLab result={result} onRun={run} busy={busy} />;
}

/** Everything inside the shell requires a chosen company. */
function Signed({
  session,
  onSignOut,
}: {
  session: OrgSummary;
  onSignOut: () => void;
}) {
  const { tender, select } = useCurrentTender();

  return (
    <AppShell
      org={session}
      tenderTitle={tender?.title ?? null}
      onSignOut={onSignOut}
    >
      <Routes>
        <Route path="/app" element={<App onOpenTender={select} />} />
        <Route
          path="/workspace"
          element={<WorkspaceRoute tender={tender} onBack={() => select(null)} />}
        />
        <Route
          path="/workspace/:tenderId"
          element={<WorkspaceRoute tender={tender} onBack={() => select(null)} />}
        />
        {/* The matrix, decision, proposal and console are tabs inside the
            workspace today; their routes deep-link into it. */}
        <Route path="/matrix" element={<Navigate to="/workspace" replace />} />
        <Route path="/decision" element={<Navigate to="/workspace" replace />} />
        <Route path="/proposal" element={<Navigate to="/workspace" replace />} />
        <Route path="/console" element={<Navigate to="/workspace" replace />} />
        <Route path="/model-lab" element={<LabRoute />} />
        <Route path="/analytics" element={<Analytics />} />
        <Route path="/admin" element={<Admin />} />
        <Route path="/kitchen-sink" element={<KitchenSink />} />
        <Route path="*" element={<Navigate to="/app" replace />} />
      </Routes>
    </AppShell>
  );
}

export default function Root() {
  const [session, setSession] = useState<OrgSummary | null>(getSession);

  // Another tab signing in or out should not leave this one stale.
  useEffect(() => {
    const sync = () => setSession(getSession());
    window.addEventListener("storage", sync);
    return () => window.removeEventListener("storage", sync);
  }, []);

  const signOut = () => {
    clearSession();
    setSession(null);
  };

  return (
    <ToastHost>
      <Routes>
        {/* Public */}
        <Route
          path="/"
          element={
            session ? (
              <Navigate to="/app" replace />
            ) : (
              <Landing onSignedIn={() => setSession(getSession())} />
            )
          }
        />
        <Route
          path="/new-company"
          element={<NewCompany onSignedIn={() => setSession(getSession())} />}
        />

        {/* Signed in — everything else lives inside the shell */}
        <Route
          path="*"
          element={
            session ? (
              <Signed session={session} onSignOut={signOut} />
            ) : (
              <Navigate to="/" replace />
            )
          }
        />
      </Routes>
    </ToastHost>
  );
}
