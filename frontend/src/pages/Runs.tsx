import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api, type RunSummary } from "../api";
import StatusPill from "../components/StatusPill";

export default function Runs() {
  const [runs, setRuns] = useState<RunSummary[] | null>(null);

  useEffect(() => {
    api.listRuns().then(setRuns).catch(() => setRuns([]));
  }, []);

  if (!runs) return <p className="text-slate-400">Loading…</p>;
  if (runs.length === 0)
    return (
      <div className="card text-center py-12">
        <p className="text-slate-400">No runs yet.</p>
        <Link to="/" className="btn-primary inline-block mt-4">Start a scan</Link>
      </div>
    );

  return (
    <div className="card overflow-x-auto">
      <table className="w-full">
        <thead>
          <tr>
            <th className="th">Company</th>
            <th className="th">Status</th>
            <th className="th">Models</th>
            <th className="th">Questions</th>
            <th className="th">Cost</th>
            <th className="th">Created</th>
          </tr>
        </thead>
        <tbody>
          {runs.map((r) => (
            <tr key={r.id} className="hover:bg-edge/40">
              <td className="td">
                <Link to={`/runs/${r.id}`} className="text-blue-400 hover:underline">
                  {r.company_name}
                </Link>
                <div className="text-xs text-slate-500">{r.id}</div>
              </td>
              <td className="td"><StatusPill status={r.status} /></td>
              <td className="td">{r.num_models}</td>
              <td className="td">{r.num_questions}</td>
              <td className="td">${r.total_cost_usd.toFixed(4)}</td>
              <td className="td text-slate-400">{new Date(r.created_at).toLocaleString()}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
