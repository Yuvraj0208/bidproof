// /kitchen-sink — every primitive on one page.
// It exists so the design system can be reviewed (and regressions spotted)
// without clicking through the whole product.
import { useState } from "react";
import { ConfidenceChip } from "./components/ConfidenceChip";
import { CountdownChip, Pill, RiskTag, VerdictBadge, formatInr } from "./ui/chips";
import { DataTable } from "./ui/DataTable";
import { Modal, Tooltip, useToast } from "./ui/overlays";
import {
  Button,
  Card,
  EmptyState,
  FieldLabel,
  PageHeader,
  SkeletonLoader,
  StatCallout,
} from "./ui/primitives";

const DAY = 86_400_000;
const iso = (offsetMs: number) => new Date(Date.now() + offsetMs).toISOString();

interface DemoRow {
  key: string;
  requirement: string;
  verdict: string;
  value: number;
}

const ROWS: DemoRow[] = [
  { key: "min_turnover", requirement: "Minimum average annual turnover", verdict: "complies", value: 50000000 },
  { key: "emd_amount", requirement: "Earnest money deposit", verdict: "needs_human", value: 250000 },
  { key: "delivery_days", requirement: "Delivery within 90 days", verdict: "partial", value: 90 },
  { key: "iso_cert", requirement: "ISO 9001 certification", verdict: "gap", value: 0 },
];

function Row({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <Card className="mb-4">
      <FieldLabel>{title}</FieldLabel>
      <div className="mt-3 flex flex-wrap items-center gap-3">{children}</div>
    </Card>
  );
}

export default function KitchenSink() {
  const [modal, setModal] = useState(false);
  const { push } = useToast();

  return (
    <div className="mx-auto max-w-5xl px-6 py-8">
      <PageHeader
        title="Kitchen sink"
        subtitle="Every primitive in the BidProof design system, on one page."
        actions={<Button variant="primary" onClick={() => push("Saved.", "success")}>Primary action</Button>}
        meta={<><Pill tone="brand">design system</Pill><Pill>v1</Pill></>}
      />

      <Row title="Buttons">
        <Button variant="primary">Primary</Button>
        <Button>Secondary</Button>
        <Button variant="ghost">Ghost</Button>
        <Button variant="danger">Danger</Button>
        <Button disabled>Disabled</Button>
      </Row>

      <Row title="Verdict badges (glyph + word, never colour alone)">
        {["complies", "partial", "gap", "needs_human", "not_applicable"].map((v) => (
          <VerdictBadge key={v} verdict={v} />
        ))}
      </Row>

      <Row title="Countdown chips (amber <7d, red <3d, pulse <24h)">
        <CountdownChip closingAt={iso(30 * DAY)} />
        <CountdownChip closingAt={iso(5 * DAY)} />
        <CountdownChip closingAt={iso(2 * DAY)} />
        <CountdownChip closingAt={iso(6 * 3600_000)} />
        <CountdownChip closingAt={iso(-DAY)} />
        <CountdownChip closingAt={null} />
      </Row>

      <Row title="Risk tags (a risk is only real with its rupee impact)">
        <RiskTag label="Liquidated damages" impactInr={450000} severity="high" />
        <RiskTag label="Delivery window tight" impactInr={120000} severity="medium" />
        <RiskTag label="Warranty extension" impactInr={25000} severity="low" />
      </Row>

      <Row title="Confidence chips (existing API, restyled only)">
        <ConfidenceChip confidence={0.94} band="green" reason="Exact numeric match" />
        <ConfidenceChip confidence={0.71} band="yellow" reason="Partial evidence" />
        <ConfidenceChip confidence={0.35} band="red" reason="No supporting record" />
      </Row>

      <Row title="Stat callouts (tabular figures)">
        <StatCallout label="Expected value" value={formatInr(1155000)} hint="P(win) 30% × margin 10%" tone="success" size="lg" />
        <StatCallout label="Cost this tender" value="₹38.40" hint="14 calls · 213k tokens" tone="brand" />
        <StatCallout label="Rules extracted" value="18" hint="12 pattern · 6 AI" />
      </Row>

      <Row title="Overlays">
        <Button onClick={() => setModal(true)}>Open modal</Button>
        <Button onClick={() => push("Export blocked — 2 unaddressed clauses.", "warning")}>Toast</Button>
        <Tooltip label="Every extracted fact clicks back to its page and box">
          <span className="cursor-help text-sm text-indigo underline decoration-dotted">Hover me</span>
        </Tooltip>
      </Row>

      <Card className="mb-4">
        <FieldLabel>Data table (sticky header, sortable, zebra, keyboard nav, density)</FieldLabel>
        <div className="mt-3">
          <DataTable<DemoRow>
            rows={ROWS}
            rowKey={(r) => r.key}
            caption={`${ROWS.length} requirements`}
            onRowActivate={(r) => push(`Opened ${r.key}`)}
            columns={[
              { key: "requirement", header: "Requirement", sortValue: (r) => r.requirement },
              { key: "verdict", header: "Verdict", render: (r) => <VerdictBadge verdict={r.verdict} />, sortValue: (r) => r.verdict },
              { key: "value", header: "Value", align: "right", numeric: true, sortValue: (r) => r.value, render: (r) => formatInr(r.value) },
            ]}
          />
        </div>
      </Card>

      <Row title="Loading">
        <div className="w-full max-w-md"><SkeletonLoader rows={3} /></div>
      </Row>

      <div className="mb-4">
        <EmptyState
          title="No tenders in this list yet"
          body="Connect a portal to discover tenders automatically, or upload a tender PDF to read it now."
          action={<Button variant="primary">Upload a tender</Button>}
        />
      </div>

      <Modal
        open={modal}
        title="Override the export blocker"
        onClose={() => setModal(false)}
        footer={<>
          <Button onClick={() => setModal(false)}>Cancel</Button>
          <Button variant="danger" onClick={() => { setModal(false); push("Override recorded.", "warning"); }}>
            Override with reason
          </Button>
        </>}
      >
        This proposal has 2 unaddressed mandatory clauses. Overriding is logged
        against your name and shown in the audit trail.
      </Modal>
    </div>
  );
}
