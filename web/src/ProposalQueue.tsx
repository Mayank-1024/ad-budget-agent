import { useState } from "react";
import { api, type Proposal } from "./api";

const money = (v: number) => `$${v.toLocaleString(undefined, { maximumFractionDigits: 0 })}`;

function Row({ p, exp, onDone }: { p: Proposal; exp: string; onDone: () => void }) {
  const [reason, setReason] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function decide(decision: "approve" | "reject") {
    setBusy(true);
    setError(null);
    try {
      await api.decide(exp, p.proposal_id, decision, reason.trim() || (decision === "approve" ? "Approved in dashboard" : ""));
      onDone();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }

  const clipped = p.requested_budget !== p.final_budget;
  return (
    <tr>
      <td>
        <div className="mono">{p.campaign_id}</div>
        <div className="muted">{p.sim_day} | {p.brand_id}</div>
      </td>
      <td className="num">
        {money(p.current_budget)} to {money(p.final_budget)}
        <div className={p.change_pct >= 0 ? "up" : "down"}>
          {p.change_pct > 0 ? "+" : ""}
          {p.change_pct.toFixed(1)}%
        </div>
        {clipped && <div className="muted">asked {money(p.requested_budget)}</div>}
      </td>
      <td>
        <div>{p.reason}</div>
        <div className="muted">Expected: {p.expected_effect}</div>
        {p.guardrails.length > 0 && <div className="tag">guardrails: {p.guardrails.join(", ")}</div>}
      </td>
      <td>
        <span className={`badge ${p.risk}`}>{p.risk} risk</span>
      </td>
      <td>
        {p.status === "pending" ? (
          <div className="decide">
            <input
              placeholder="Reason (required to reject)"
              value={reason}
              onChange={(e) => setReason(e.target.value)}
              aria-label={`Reason for proposal ${p.proposal_id}`}
            />
            <div>
              <button disabled={busy} onClick={() => decide("approve")}>Approve</button>
              <button disabled={busy || reason.trim().length < 3} className="secondary" onClick={() => decide("reject")}>
                Reject
              </button>
            </div>
            {error && <div className="error">{error}</div>}
          </div>
        ) : (
          <div>
            <span className={`badge ${p.status}`}>{p.status.replace("_", " ")}</span>
            {p.decision_reason && <div className="muted">{p.reviewer}: {p.decision_reason}</div>}
          </div>
        )}
      </td>
    </tr>
  );
}

export function ProposalQueue({ exp, proposals, onChange }: { exp: string; proposals: Proposal[]; onChange: () => void }) {
  const [showAll, setShowAll] = useState(false);
  const pending = proposals.filter((p) => p.status === "pending");
  const rows = showAll ? proposals : pending;
  return (
    <section>
      <div className="section-head">
        <h2>Proposal queue ({pending.length} pending)</h2>
        <label>
          <input type="checkbox" checked={showAll} onChange={(e) => setShowAll(e.target.checked)} /> show decided
        </label>
      </div>
      {rows.length === 0 ? (
        <p className="muted">Nothing waiting for review.</p>
      ) : (
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Campaign</th>
                <th>Budget</th>
                <th>Agent's reason</th>
                <th>Risk</th>
                <th>Decision</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((p) => (
                <Row key={p.proposal_id} p={p} exp={exp} onDone={onChange} />
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}
