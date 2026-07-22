const COLORS: Record<string, string> = {
  created: "bg-slate-600 text-white",
  generating_questions: "bg-indigo-600 text-white",
  awaiting_approval: "bg-amber-500 text-black",
  running_models: "bg-blue-600 text-white",
  analyzing: "bg-purple-600 text-white",
  reporting: "bg-teal-600 text-white",
  completed: "bg-green-600 text-white",
  failed: "bg-red-600 text-white",
};

export default function StatusPill({ status }: { status: string }) {
  return (
    <span className={`pill ${COLORS[status] ?? "bg-slate-600 text-white"}`}>
      {status.replace(/_/g, " ")}
    </span>
  );
}
