import {
  Bar,
  BarChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { api, type RunRecord } from "../api";

const PROV_COLOR: Record<string, string> = {
  organic: "#22c55e",
  search_driven: "#3b82f6",
  absent: "#64748b",
};

export default function Dashboard({ run }: { run: RunRecord }) {
  const a = run.analysis;
  if (!a) return null;
  const ranked = [...a.models].sort((x, y) => y.brand_mentions - x.brand_mentions);
  const maxHeat = Math.max(1, ...a.models.flatMap((m) => Object.values(m.per_question_brand)));

  const provCounts = a.models.reduce<Record<string, number>>((acc, m) => {
    acc[m.provenance] = (acc[m.provenance] ?? 0) + 1;
    return acc;
  }, {});

  const compTotals = a.competitors.map((c) => ({
    name: c,
    value: a.models.reduce((s, m) => s + (m.competitor_totals[c] ?? 0), 0),
  }));

  const brandTotal = a.models.reduce((s, m) => s + m.brand_mentions, 0);

  return (
    <div className="space-y-6">
      {/* Stat tiles */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <Stat label="Models mentioning brand" value={`${a.models.filter((m) => m.brand_mentions > 0).length}/${a.models.length}`} />
        <Stat label="Total brand mentions" value={brandTotal} />
        <Stat label="Questions" value={a.question_indices.length} />
        <Stat label="Run cost" value={`$${run.total_cost_usd.toFixed(4)}`} />
      </div>

      {/* Downloads */}
      <div className="flex flex-wrap gap-3">
        {["pdf", "xlsx", "csv", "json"].map((fmt) => (
          <a key={fmt} className={fmt === "pdf" ? "btn-primary text-sm" : "btn-ghost text-sm"}
             href={api.reportUrl(run.id, fmt)}>
            Download {fmt.toUpperCase()}
          </a>
        ))}
      </div>

      {/* Insights */}
      {a.insights.length > 0 && (
        <Section title="Insights">
          <ul className="space-y-1 text-sm">
            {a.insights.map((t, i) => (
              <li key={i}>• {t}</li>
            ))}
          </ul>
        </Section>
      )}

      <div className="grid lg:grid-cols-2 gap-6">
        {/* Provenance */}
        <Section title="Provenance">
          <div className="flex gap-3">
            {["organic", "search_driven", "absent"].map((p) => (
              <div key={p} className="flex-1 text-center rounded-lg py-3" style={{ background: `${PROV_COLOR[p]}22` }}>
                <div className="text-2xl font-semibold" style={{ color: PROV_COLOR[p] }}>{provCounts[p] ?? 0}</div>
                <div className="text-xs text-slate-400">{p.replace(/_/g, " ")}</div>
              </div>
            ))}
          </div>
        </Section>

        {/* Competitor SoV */}
        <Section title="Competitor share of voice">
          {compTotals.length === 0 ? (
            <p className="text-sm text-slate-400">No competitors tracked.</p>
          ) : (
            <ResponsiveContainer width="100%" height={180}>
              <BarChart data={compTotals} layout="vertical" margin={{ left: 20 }}>
                <XAxis type="number" stroke="#64748b" fontSize={12} />
                <YAxis type="category" dataKey="name" stroke="#94a3b8" fontSize={12} width={90} />
                <Tooltip contentStyle={{ background: "#111725", border: "1px solid #1f2937" }} />
                <Bar dataKey="value" fill="#f59e0b" radius={[0, 4, 4, 0]} />
              </BarChart>
            </ResponsiveContainer>
          )}
        </Section>
      </div>

      {/* Overview table */}
      <Section title="Overview (ranked by brand visibility)">
        <div className="overflow-x-auto">
          <table className="w-full">
            <thead>
              <tr>
                {["#", "Model", "Search", "Brand", "Q's", "Domains", "In table", "Provenance"].map((h) => (
                  <th key={h} className="th">{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {ranked.map((m, i) => (
                <tr key={m.model_id} className="hover:bg-edge/40">
                  <td className="td text-slate-500">{i + 1}</td>
                  <td className="td font-medium">{m.model_id}</td>
                  <td className="td">{m.web_search_used ? `Yes (${m.num_searches})` : "No"}</td>
                  <td className="td">{m.brand_mentions}</td>
                  <td className="td">{m.questions_mentioning}</td>
                  <td className="td">{m.unique_domains.length}</td>
                  <td className="td">{m.in_vendor_table ? "✓" : ""}</td>
                  <td className="td">
                    <span className="pill" style={{ background: `${PROV_COLOR[m.provenance]}33`, color: PROV_COLOR[m.provenance] }}>
                      {m.provenance.replace(/_/g, " ")}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Section>

      {/* Heatmap */}
      <Section title="Mention heatmap (model × question)">
        <div className="overflow-x-auto">
          <table className="border-collapse">
            <thead>
              <tr>
                <th className="th sticky left-0 bg-panel">Model</th>
                {a.question_indices.map((q) => (
                  <th key={q} className="th text-center">Q{q}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {a.models.map((m) => (
                <tr key={m.model_id}>
                  <td className="td whitespace-nowrap sticky left-0 bg-panel font-medium">{m.model_id}</td>
                  {a.question_indices.map((q) => {
                    const v = m.per_question_brand[String(q)] ?? 0;
                    return (
                      <td key={q} className="td text-center"
                        style={{ background: v ? `rgba(59,130,246,${0.15 + (0.85 * v) / maxHeat})` : undefined }}>
                        {v || ""}
                      </td>
                    );
                  })}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Section>

      {/* Question aggregate */}
      <Section title="Question aggregate">
        <div className="overflow-x-auto">
          <table className="w-full">
            <thead>
              <tr>{["Q#", "Question", "Total", "Models", "Avg", "Peak"].map((h) => <th key={h} className="th">{h}</th>)}</tr>
            </thead>
            <tbody>
              {a.questions.map((q) => (
                <tr key={q.index} className="hover:bg-edge/40">
                  <td className="td">{q.index}</td>
                  <td className="td max-w-md">{q.text}</td>
                  <td className="td">{q.total_mentions}</td>
                  <td className="td">{q.models_mentioning}</td>
                  <td className="td">{q.avg_per_model}</td>
                  <td className="td text-slate-400">{q.peak_model || "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Section>

      <div className="grid lg:grid-cols-2 gap-6">
        {/* Domain frequency */}
        <Section title="Domain frequency">
          <div className="overflow-y-auto max-h-72">
            <table className="w-full">
              <thead><tr>{["Domain", "Models", "Brand", "Ref"].map((h) => <th key={h} className="th">{h}</th>)}</tr></thead>
              <tbody>
                {a.domain_frequency.map((d) => (
                  <tr key={d.domain} className={d.brand_owned ? "bg-green-500/10" : d.is_reference ? "bg-amber-500/10" : ""}>
                    <td className="td">{d.domain}</td>
                    <td className="td">{d.num_models}</td>
                    <td className="td">{d.brand_owned ? "✓" : ""}</td>
                    <td className="td">{d.is_reference ? "★" : ""}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Section>

        {/* Search queries */}
        <Section title="Search queries">
          <div className="overflow-y-auto max-h-72 space-y-3 text-sm">
            {a.models.filter((m) => m.search_queries.length).map((m) => (
              <div key={m.model_id}>
                <div className="font-medium text-slate-300">{m.model_id}</div>
                <ul className="text-slate-400 list-disc pl-5">
                  {m.search_queries.map((q, i) => <li key={i}>{q}</li>)}
                </ul>
              </div>
            ))}
            {a.models.every((m) => !m.search_queries.length) && (
              <p className="text-slate-400">No search queries recorded.</p>
            )}
          </div>
        </Section>
      </div>

      {/* Quotes */}
      {a.quotes.length > 0 && (
        <Section title="Representative quotes">
          <div className="space-y-3">
            {a.quotes.map((q, i) => (
              <blockquote key={i} className="border-l-2 border-blue-600 pl-3 text-sm">
                <span className="text-slate-300">“{q.quote}”</span>
                <div className="text-xs text-slate-500">— {q.model}</div>
              </blockquote>
            ))}
          </div>
        </Section>
      )}
    </div>
  );
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="card">
      <h3 className="font-semibold mb-3">{title}</h3>
      {children}
    </div>
  );
}

function Stat({ label, value }: { label: string; value: string | number }) {
  return (
    <div className="card">
      <div className="text-2xl font-semibold">{value}</div>
      <div className="text-xs text-slate-400 mt-1">{label}</div>
    </div>
  );
}
