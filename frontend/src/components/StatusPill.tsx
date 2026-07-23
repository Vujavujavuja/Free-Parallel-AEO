const COLORS: Record<string, string> = {
  created: "bg-edge text-cream",
  generating_questions: "bg-ember-400 text-ink",
  awaiting_approval: "bg-wine text-cream",
  running_models: "bg-ember text-ink",
  analyzing: "bg-ember-600 text-cream",
  reporting: "bg-dim text-cream",
  completed: "bg-ember text-ink",
  failed: "bg-wine text-cream",
};

export default function StatusPill({ status }: { status: string }) {
  return (
    <span className={`pill ${COLORS[status] ?? "bg-edge text-cream"}`}>
      {status.replace(/_/g, " ")}
    </span>
  );
}
