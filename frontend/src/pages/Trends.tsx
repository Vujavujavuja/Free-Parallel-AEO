import { useEffect, useState } from "react";
import {
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { api, type CompanyTrend } from "../api";

export default function Trends() {
  const [trends, setTrends] = useState<CompanyTrend[] | null>(null);

  useEffect(() => {
    api.trends().then(setTrends).catch(() => setTrends([]));
  }, []);

  if (!trends) return <p className="text-muted">Loading…</p>;

  const multi = trends.filter((t) => t.runs >= 2);
  if (multi.length === 0)
    return (
      <div className="card text-center py-12">
        <p className="text-muted">
          No trends yet — run the same company at least twice to track mentions over time.
        </p>
      </div>
    );

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-xl font-semibold">Trends</h1>
        <p className="text-sm text-dim">Brand visibility over time, per company.</p>
      </div>
      {multi.map((t) => (
        <TrendCard key={t.company} trend={t} />
      ))}
    </div>
  );
}

function TrendCard({ trend }: { trend: CompanyTrend }) {
  const data = trend.points.map((p) => ({
    date: new Date(p.created_at).toLocaleDateString(),
    mentions: p.brand_mentions,
    mentioning: p.models_mentioning,
    searchDriven: p.search_driven,
  }));
  const last = trend.points[trend.points.length - 1];
  const first = trend.points[0];
  const delta = last.brand_mentions - first.brand_mentions;

  return (
    <div className="card">
      <div className="flex items-center justify-between mb-3">
        <h3 className="font-semibold">{trend.company}</h3>
        <span className="text-xs font-mono text-muted">
          {trend.runs} runs ·{" "}
          <span className={delta >= 0 ? "text-ember" : "text-wine"}>
            {delta >= 0 ? "+" : ""}{delta} mentions
          </span>{" "}
          since first
        </span>
      </div>
      <ResponsiveContainer width="100%" height={220}>
        <LineChart data={data} margin={{ left: -10, right: 10 }}>
          <CartesianGrid stroke="#322c27" vertical={false} />
          <XAxis dataKey="date" stroke="#968c82" fontSize={11} />
          <YAxis stroke="#968c82" fontSize={11} />
          <Tooltip contentStyle={{ background: "#1f1b18", border: "1px solid #322c27", color: "#ece7df" }} />
          <Line type="monotone" dataKey="mentions" name="Brand mentions" stroke="#ee5e13" strokeWidth={2} dot isAnimationActive={false} />
          <Line type="monotone" dataKey="mentioning" name="Models mentioning" stroke="#b23656" strokeWidth={2} dot isAnimationActive={false} />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}
