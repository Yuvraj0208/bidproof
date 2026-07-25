// "Add your company" — a public page, reached from the landing page rather than
// from inside the app (it used to be a button on the Tender Radar, which meant
// you had to already be in a workspace to create one).
//
// On finish it signs you straight into the company you just created, so the path
// is: landing → wizard → your own radar, with no id to copy anywhere.
import { useNavigate } from "react-router-dom";
import {
  createOrg,
  fetchOrganizations,
  saveBranding,
  saveOnboardingProfile,
  setOrgId,
  signIn,
  uploadFactsCsv,
  uploadProductsCsv,
} from "../api";
import { OnboardingWizard } from "../components/OnboardingWizard";
import { useToast } from "../ui/overlays";

export default function NewCompany({ onSignedIn }: { onSignedIn: () => void }) {
  const navigate = useNavigate();
  const { push } = useToast();

  return (
    <div className="min-h-screen bg-surface">
      <header className="border-b border-hairline bg-white">
        <div className="mx-auto flex max-w-6xl items-center gap-4 px-6 py-4">
          <button
            onClick={() => navigate("/")}
            className="text-[17px] font-semibold tracking-[-0.01em] text-indigo"
          >
            BidProof
          </button>
          <span className="hidden text-xs text-ink-subtle sm:inline">
            Add your company — no developer needed
          </span>
          <button
            onClick={() => navigate("/")}
            className="ml-auto rounded-[8px] border border-hairline px-3 py-1.5 text-sm text-ink-muted transition-colors duration-150 hover:bg-indigo-tint"
          >
            ← Back
          </button>
        </div>
      </header>

      <OnboardingWizard
        onCreateOrg={async (name, slug) => {
          const created = await createOrg(name, slug);
          // The CSV and profile steps are org-scoped, so set the context now.
          setOrgId(created.org_id);
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
        onDone={async (orgId) => {
          // Sign in as the company just created — including its branding, so the
          // logo/monogram is right immediately.
          try {
            const orgs = await fetchOrganizations();
            const mine = orgs.find((o) => o.org_id === orgId);
            if (mine) signIn(mine, "bid_head");
          } catch {
            /* the org context is already set; the shell will still work */
          }
          onSignedIn();
          push("Your company is live. Welcome to BidProof.", "success");
          navigate("/app");
        }}
        onCancel={() => navigate("/")}
      />
    </div>
  );
}
