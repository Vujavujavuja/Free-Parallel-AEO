import { useCallback, useEffect, useRef, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { api, type ProgressEvent, type Question, type RunRecord } from "../api";
import Dashboard from "../components/Dashboard";
import StatusPill from "../components/StatusPill";

const STAGES = [
  ["generating_questions", "Questions"],
  ["running_models", "Querying models"],
  ["analyzing", "Analyzing"],
  ["reporting", "Reporting"],
  ["completed", "Done"],
] as const;

const TERMINAL = ["completed", "failed"];

export default function RunView() {
  const { id = "" } = useParams();
  const [run, setRun] = useState<RunRecord | null>(null);
  const [event, setEvent] = useState<ProgressEvent | null>(null);
  const esRef = useRef<EventSource | null>(null);

  const subscribe = useCallback(() => {
    esRef.current?.close();
    esRef.current = api.events(id, (ev) => {
      setEvent(ev);
      if (["completed", "failed", "awaiting_approval"].includes(ev.status)) {
        api.getRun(id).then(setRun);
        esRef.current?.close();
      } else {
        setRun((prev) => (prev ? { ...prev, status: ev.status } : prev));
      }
    });
  }, [id]);

  useEffect(() => {
    api.getRun(id).then((r) => {
      setRun(r);
      if (!TERMINAL.includes(r.status)) subscribe();
    });
    return () => esRef.current?.close();
  }, [id, subscribe]);

  if (!run) return <p className="text-slate-400">Loading…</p>;

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-semibold">{run.company.name}</h1>
          <div className="text-xs text-slate-500">
            Run {run.id} · {run.options.target_models.length} models
          </div>
        </div>
        <div className="flex items-center gap-3">
          <StatusPill status={run.status} />
          <Link to={`/?from=${run.id}&edit=1`} className="btn-ghost text-sm">Edit</Link>
          <Link to={`/?from=${run.id}`} className="btn-ghost text-sm">Re-run</Link>
          <Link to="/runs" className="btn-ghost text-sm">All runs</Link>
        </div>
      </div>

      {run.status === "failed" && (
        <div className="card border-red-500/50 text-red-400">Run failed: {run.error}</div>
      )}

      {!TERMINAL.includes(run.status) && run.status !== "awaiting_approval" && (
        <StageTracker status={run.status} event={event} />
      )}

      {run.status === "awaiting_approval" && (
        <QuestionReview run={run} onApprove={() => subscribe()} setRun={setRun} />
      )}

      {run.status === "completed" && <Dashboard run={run} />}
    </div>
  );
}

function StageTracker({ status, event }: { status: string; event: ProgressEvent | null }) {
  const activeIdx = STAGES.findIndex(([s]) => s === status);
  return (
    <div className="card">
      <div className="flex items-center justify-between mb-4">
        {STAGES.map(([s, label], i) => {
          const done = activeIdx > i;
          const active = activeIdx === i;
          return (
            <div key={s} className="flex-1 flex items-center">
              <div className={`w-7 h-7 rounded-full grid place-items-center text-xs font-bold
                ${done ? "bg-green-600" : active ? "bg-blue-600 animate-pulse" : "bg-edge"}`}>
                {done ? "✓" : i + 1}
              </div>
              <span className={`ml-2 text-xs ${active ? "text-white" : "text-slate-500"}`}>{label}</span>
              {i < STAGES.length - 1 && <div className="flex-1 h-px bg-edge mx-2" />}
            </div>
          );
        })}
      </div>
      {event && event.total > 0 && (
        <div>
          <div className="h-2 bg-edge rounded-full overflow-hidden">
            <div className="h-full bg-blue-600 transition-all"
              style={{ width: `${(100 * event.completed) / event.total}%` }} />
          </div>
          <p className="text-xs text-slate-400 mt-2">
            {event.completed}/{event.total} · {event.detail}
          </p>
        </div>
      )}
    </div>
  );
}

function QuestionReview({ run, onApprove, setRun }: {
  run: RunRecord;
  onApprove: () => void;
  setRun: (r: RunRecord) => void;
}) {
  const [questions, setQuestions] = useState<Question[]>(run.questions);
  const [busy, setBusy] = useState(false);

  async function approve() {
    setBusy(true);
    const updated = await api.approve(run.id, questions);
    setRun(updated);
    onApprove();
  }

  return (
    <div className="card">
      <h3 className="font-semibold mb-1">Review questions</h3>
      <p className="text-sm text-slate-400 mb-4">Edit the generated questions, then approve to run the panel.</p>
      <div className="space-y-2">
        {questions.map((q, i) => (
          <div key={q.index} className="flex gap-2 items-start">
            <span className="pill bg-edge mt-2">Q{q.index}</span>
            <textarea
              className="input flex-1"
              rows={2}
              value={q.text}
              onChange={(e) => {
                const next = [...questions];
                next[i] = { ...q, text: e.target.value };
                setQuestions(next);
              }}
            />
          </div>
        ))}
      </div>
      <button className="btn-primary mt-4" onClick={approve} disabled={busy}>
        {busy ? "Approving…" : "Approve & run"}
      </button>
    </div>
  );
}
