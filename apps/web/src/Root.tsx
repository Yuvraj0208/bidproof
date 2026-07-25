// Route table + the shell that wraps every screen.
//
// Before this, screens were swapped with useState booleans inside App.tsx —
// no URLs, no back button, no deep links (FINISH_STATUS D6). Every SPEC §17
// screen now has an address.
import { useEffect, useState } from "react";
import { Navigate, Route, Routes, useNavigate, useParams } from "react-router-dom";
import App from "./App";
import KitchenSink from "./KitchenSink";
import { Workspace } from "./Workspace";
import { ModelLab } from "./components/ModelLab";
import { getOrgId, runModelLab, type ModelLabResult } from "./api";
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
          action={<Button variant="primary" onClick={() => navigate("/")}>Go to Tender Radar</Button>}
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

function Placeholder({ title, body }: { title: string; body: string }) {
  return (
    <div className="p-8">
      <EmptyState title={title} body={body} icon="◭" />
    </div>
  );
}

export default function Root() {
  const { tender, select } = useCurrentTender();
  const [org, setOrg] = useState(getOrgId());

  // Keep the shell's org label in step with the radar's org input.
  useEffect(() => {
    const timer = window.setInterval(() => setOrg(getOrgId()), 1000);
    return () => window.clearInterval(timer);
  }, []);

  return (
    <ToastHost>
      <AppShell orgName={org || "No organisation"} tenderTitle={tender?.title ?? null}>
        <Routes>
          <Route path="/" element={<App onOpenTender={select} />} />
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
          <Route
            path="/analytics"
            element={<Placeholder title="Analytics" body="Funnel, turnaround time, calibration and cost trend land in Task 5." />}
          />
          <Route
            path="/admin"
            element={<Placeholder title="Admin" body="Roles, prompt approvals, model config, audit log and scraper health land in Task 5." />}
          />
          <Route path="/onboarding" element={<App onOpenTender={select} startOnboarding />} />
          <Route path="/kitchen-sink" element={<KitchenSink />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </AppShell>
    </ToastHost>
  );
}
