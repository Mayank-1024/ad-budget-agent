import { useCallback, useEffect, useState } from "react";
import { api, type CampaignsResponse, type DailyPoint, type Proposal } from "./api";
import { LineChart } from "./LineChart";
import { ProposalQueue } from "./ProposalQueue";

const money = (v: number) => `$${v.toLocaleString(undefined, { maximumFractionDigits: 0 })}`;

export function App() {
  const [experiments, setExperiments] = useState<string[]>([]);
  const [exp, setExp] = useState<string>("");
  const [data, setData] = useState<CampaignsResponse | null>(null);
  const [proposals, setProposals] = useState<Proposal[]>([]);
  const [selected, setSelected] = useState<string>("");
  const [series, setSeries] = useState<DailyPoint[]>([]);
  const [showTable, setShowTable] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api.experiments()
      .then((xs) => {
        setExperiments(xs);
        setExp(xs.includes("demo") ? "demo" : xs[0] ?? "");
      })
      .catch((e) => setError(e.message));
  }, []);

  const refresh = useCallback(() => {
    if (!exp) return;
    Promise.all([api.campaigns(exp), api.proposals(exp)])
      .then(([c, p]) => {
        setData(c);
        setProposals(p);
        setSelected((s) => s || c.campaigns[0]?.campaign_id || "");
      })
      .catch((e) => setError(e.message));
  }, [exp]);

  useEffect(refresh, [refresh]);

  useEffect(() => {
    if (exp && selected) api.daily(exp, selected).then(setSeries).catch((e) => setError(e.message));
  }, [exp, selected, proposals]);

  return (
    <main>
      <header>
        <div>
          <h1>Ad Budget Agent</h1>
          <p className="muted">Synthetic data. The agent proposes, a reviewer approves, code executes.</p>
        </div>
        <label>
          Experiment{" "}
          <select value={exp} onChange={(e) => { setExp(e.target.value); setSelected(""); }}>
            {experiments.map((x) => (
              <option key={x}>{x}</option>
            ))}
          </select>
        </label>
      </header>
      {error && <p className="error">API error: {error}. Is the API running on port 8000?</p>}

      {exp && <ProposalQueue exp={exp} proposals={proposals} onChange={refresh} />}

      {data && (
        <section>
          <div className="section-head">
            <h2>Campaigns</h2>
            <span className="muted">data through {data.data_through ?? "n/a"}; last 7 days, reported</span>
          </div>
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Campaign</th>
                  <th className="num">Daily budget</th>
                  <th className="num">Spend</th>
                  <th className="num">Revenue</th>
                  <th className="num">ROAS</th>
                  <th className="num">Conversions</th>
                </tr>
              </thead>
              <tbody>
                {data.campaigns.map((c) => (
                  <tr key={c.campaign_id} className={c.campaign_id === selected ? "selected" : ""} onClick={() => setSelected(c.campaign_id)}>
                    <td>
                      <div className="mono">{c.campaign_id}</div>
                      <div className="muted">{c.name}</div>
                    </td>
                    <td className="num">{money(c.daily_budget)}</td>
                    <td className="num">{c.last_7_days ? money(c.last_7_days.spend) : "n/a"}</td>
                    <td className="num">{c.last_7_days ? money(c.last_7_days.revenue) : "n/a"}</td>
                    <td className="num">{c.last_7_days?.roas?.toFixed(2) ?? "n/a"}</td>
                    <td className="num">{c.last_7_days?.conversions ?? "n/a"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      )}

      {selected && (
        <section>
          <div className="section-head">
            <h2 className="mono">{selected}</h2>
            <label>
              <input type="checkbox" checked={showTable} onChange={(e) => setShowTable(e.target.checked)} /> table view
            </label>
          </div>
          <div className="charts">
            <LineChart title="Daily spend (USD)" points={series.map((p) => ({ label: p.day, value: p.spend }))} format={money} />
            <LineChart title="Daily reported ROAS" points={series.map((p) => ({ label: p.day, value: p.roas }))} format={(v) => v.toFixed(2)} />
          </div>
          {showTable && (
            <table>
              <thead>
                <tr><th>Day</th><th className="num">Spend</th><th className="num">Clicks</th><th className="num">Conversions</th><th className="num">Revenue</th><th className="num">ROAS</th></tr>
              </thead>
              <tbody>
                {series.map((p) => (
                  <tr key={p.day}>
                    <td>{p.day}</td><td className="num">{money(p.spend)}</td><td className="num">{p.clicks}</td>
                    <td className="num">{p.conversions}</td><td className="num">{money(p.revenue)}</td><td className="num">{p.roas?.toFixed(2) ?? "n/a"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </section>
      )}
    </main>
  );
}
