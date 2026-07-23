import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { api, type ModelInfo, type Provider, type SourceDocument } from "../api";

const perMillion = (v: number) => (v > 0 ? `$${(v * 1_000_000).toFixed(2)}` : "—");

const listToArr = (s: string) =>
  s.split(",").map((x) => x.trim()).filter(Boolean);
const linesToArr = (s: string) =>
  s.split("\n").map((x) => x.trim()).filter(Boolean);

export default function NewRun() {
  const nav = useNavigate();
  const [params] = useSearchParams();
  const fromRun = params.get("from");
  const editMode = params.get("edit") === "1";
  const [preset, setPreset] = useState<string | null>(null);
  const [provider, setProvider] = useState<Provider>("stub");
  const [hasKey, setHasKey] = useState(false);
  const [catalog, setCatalog] = useState<ModelInfo[]>([]);
  const [selected, setSelected] = useState<string[]>([]);
  const [orchestratorModel, setOrchestratorModel] = useState("");
  const [modelSearch, setModelSearch] = useState("");
  const [loadingModels, setLoadingModels] = useState(false);
  const [modelsError, setModelsError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [form, setForm] = useState({
    name: "Acme Co",
    website: "https://acme.co",
    category: "project management software",
    description: "Acme Co is a work-management platform for teams to plan, track, and ship projects.",
    products: "Acme Board, Acme Docs",
    competitors: "Asana, Monday.com, ClickUp, Trello, Notion, Linear, Jira",
    aliases: "Acme",
    regions: "North America, Europe",
    referenceSites: "g2.com, capterra.com",
    notes: "",
  });
  const [customQuestions, setCustomQuestions] = useState("");
  const [documents, setDocuments] = useState<SourceDocument[]>([]);
  const [uploading, setUploading] = useState(false);
  const fileInput = useRef<HTMLInputElement>(null);
  const [questionCount, setQuestionCount] = useState(10);
  const [webSearch, setWebSearch] = useState(false);
  const [autoApprove, setAutoApprove] = useState(true);
  const [aiInsights, setAiInsights] = useState(true);
  const [mentionBrand, setMentionBrand] = useState(false);
  const [costCap, setCostCap] = useState(5);
  const [keyInput, setKeyInput] = useState("");
  const [savingKey, setSavingKey] = useState(false);
  const [keyError, setKeyError] = useState<string | null>(null);
  const [editingKey, setEditingKey] = useState(false);

  useEffect(() => {
    api.health().then((h) => {
      setHasKey(h.openrouter_key_present);
      setProvider(h.openrouter_key_present ? "openrouter" : "stub");
    });
  }, []);

  // Pre-fill the form from a past run when arriving via "Re-run" (?from=<id>).
  useEffect(() => {
    if (!fromRun) return;
    api.getRun(fromRun).then((r) => {
      const c = r.company;
      setForm({
        name: c.name ?? "",
        website: c.website ?? "",
        category: c.category ?? "",
        description: c.description ?? "",
        products: (c.products ?? []).join(", "),
        competitors: (c.competitors ?? []).join(", "),
        aliases: (c.aliases ?? []).join(", "),
        regions: (c.regions ?? []).join(", "),
        referenceSites: (c.reference_sites ?? []).join(", "),
        notes: c.notes ?? "",
      });
      setDocuments(c.source_documents ?? []);
      setCustomQuestions((r.options.custom_questions ?? []).join("\n"));
      setSelected(r.options.target_models ?? []);
      setOrchestratorModel(r.options.orchestrator_model ?? "");
      setQuestionCount(r.options.question_count ?? 10);
      setWebSearch(r.options.enable_web_search ?? false);
      setCostCap(r.options.cost_cap_usd ?? 5);
      setAutoApprove(r.options.auto_approve_questions ?? true);
      setMentionBrand(r.options.mention_brand ?? false);
      setPreset(c.name);
    });
  }, [fromRun]);

  const set = (k: keyof typeof form) => (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement>) =>
    setForm({ ...form, [k]: e.target.value });

  const loadModels = useCallback(async () => {
    setLoadingModels(true);
    setModelsError(null);
    try {
      const m = await api.models(provider === "stub");
      setCatalog(m);
    } catch (e) {
      setModelsError((e as Error).message);
      setCatalog([]);
    } finally {
      setLoadingModels(false);
    }
  }, [provider]);

  // Auto-pull the catalog from OpenRouter (or the stub panel) when possible.
  useEffect(() => {
    if (provider === "stub" || (provider === "openrouter" && hasKey)) {
      loadModels();
    } else {
      setCatalog([]);
    }
  }, [provider, hasKey, loadModels]);

  const filteredModels = useMemo(() => {
    const q = modelSearch.trim().toLowerCase();
    const list = q
      ? catalog.filter((m) => `${m.id} ${m.name}`.toLowerCase().includes(q))
      : catalog;
    return list.slice(0, 400); // cap DOM nodes; refine with search
  }, [catalog, modelSearch]);

  // Rough per-run cost estimate from selected models' pricing (OpenRouter only).
  // Input tokens are dominated by web-search context (~8k/question); output ~700/question.
  const estCost = useMemo(() => {
    if (provider !== "openrouter" || !selected.length || !catalog.length) return null;
    const inPerQ = webSearch ? 8000 : 60;
    const outPerQ = 700;
    let total = 0;
    for (const id of selected) {
      const m = catalog.find((x) => x.id === id);
      if (!m) continue;
      total += (200 + questionCount * inPerQ) * m.prompt_price
             + questionCount * outPerQ * m.completion_price;
    }
    return total;
  }, [provider, selected, catalog, questionCount, webSearch]);

  function toggleModel(id: string) {
    setSelected((s) => (s.includes(id) ? s.filter((x) => x !== id) : [...s, id]));
  }

  async function saveKey() {
    if (!keyInput.trim()) return;
    setSavingKey(true);
    setKeyError(null);
    try {
      await api.setKey(keyInput.trim());
      setHasKey(true);
      setProvider("openrouter");
      setKeyInput("");
      setEditingKey(false);
    } catch (e) {
      setKeyError((e as Error).message);
    } finally {
      setSavingKey(false);
    }
  }

  async function onFiles(e: React.ChangeEvent<HTMLInputElement>) {
    const files = Array.from(e.target.files ?? []);
    if (!files.length) return;
    setUploading(true);
    setError(null);
    try {
      const parsed = await api.parseDocuments(files);
      setDocuments((d) => [...d, ...parsed]);
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setUploading(false);
      if (fileInput.current) fileInput.current.value = "";
    }
  }

  async function submit() {
    setSubmitting(true);
    setError(null);
    try {
      const rec = await api.createRun({
        provider,
        profile: {
          name: form.name,
          website: form.website || null,
          category: form.category || null,
          description: form.description || null,
          products: listToArr(form.products),
          competitors: listToArr(form.competitors).slice(0, 20),
          aliases: listToArr(form.aliases),
          regions: listToArr(form.regions),
          notes: form.notes || null,
          reference_sites: listToArr(form.referenceSites),
          source_documents: documents,
        },
        target_models: selected.length ? selected : null,
        orchestrator_model: orchestratorModel.trim() || null,
        question_count: questionCount,
        enable_web_search: webSearch,
        auto_approve_questions: autoApprove,
        enable_ai_insights: aiInsights,
        mention_brand: mentionBrand,
        cost_cap_usd: costCap,
        custom_questions: linesToArr(customQuestions),
      });
      // In edit mode, replace the original run (delete after the new one exists).
      if (editMode && fromRun) {
        await api.deleteRun(fromRun).catch(() => undefined);
      }
      nav(`/runs/${rec.id}`);
    } catch (e) {
      setError((e as Error).message);
      setSubmitting(false);
    }
  }

  return (
    <div className="space-y-4">
      {preset && (
        <div className="card border-ember/40 bg-ember/10 text-sm flex items-center justify-between">
          <span>
            {editMode ? (
              <>Editing <strong>{preset}</strong> — running will <strong>replace</strong> the original run.</>
            ) : (
              <>Reusing settings from a previous run of <strong>{preset}</strong>. Change the models and run again.</>
            )}
          </span>
          <button className="text-muted hover:text-white text-xs" onClick={() => { setPreset(null); nav("/", { replace: true }); }}>
            start blank
          </button>
        </div>
      )}
    <div className="grid gap-6 lg:grid-cols-3">
      <div className="lg:col-span-2 space-y-6">
        <div className="card">
          <h2 className="text-lg font-semibold mb-4">Company profile</h2>
          <div className="grid sm:grid-cols-2 gap-4">
            <Field label="Name *"><input className="input" value={form.name} onChange={set("name")} /></Field>
            <Field label="Website"><input className="input" value={form.website} onChange={set("website")} /></Field>
            <Field label="Category"><input className="input" value={form.category} onChange={set("category")} /></Field>
            <Field label="Brand aliases (comma-separated)"><input className="input" value={form.aliases} onChange={set("aliases")} /></Field>
            <Field label="Description" wide><textarea className="input" rows={2} value={form.description} onChange={set("description")} /></Field>
            <Field label="Products (comma-separated)"><input className="input" value={form.products} onChange={set("products")} /></Field>
            <Field label={`Competitors (comma-separated, up to 20 — ${listToArr(form.competitors).length}/20)`}>
              <input className="input" value={form.competitors} onChange={set("competitors")} />
            </Field>
            <Field label="Reference sites for citation counting (comma-separated)">
              <input className="input" value={form.referenceSites} onChange={set("referenceSites")} />
            </Field>
            <Field label="Regions (comma-separated)"><input className="input" value={form.regions} onChange={set("regions")} /></Field>
            <Field label="Notes" wide><textarea className="input" rows={2} value={form.notes} onChange={set("notes")} /></Field>
          </div>
        </div>

        <div className="card">
          <div className="flex items-center justify-between mb-3">
            <div>
              <h2 className="text-lg font-semibold">Model panel</h2>
              <p className="text-xs text-dim">
                {provider === "stub"
                  ? "Stub panel"
                  : hasKey
                  ? `${catalog.length} models from OpenRouter`
                  : "Add an API key to pull the OpenRouter catalog"}
              </p>
            </div>
            <button className="btn-ghost text-sm" onClick={loadModels} disabled={loadingModels}>
              {loadingModels ? "Loading…" : "Refresh"}
            </button>
          </div>

          {/* Selected chips */}
          {selected.length > 0 && (
            <div className="flex flex-wrap gap-2 mb-3">
              {selected.map((id) => (
                <span key={id} className="pill bg-ember/20 text-ember-400 flex items-center gap-2">
                  {id}
                  <button className="hover:text-white" onClick={() => toggleModel(id)}>×</button>
                </span>
              ))}
              <button className="text-xs text-muted hover:text-white" onClick={() => setSelected([])}>
                clear all
              </button>
            </div>
          )}

          <div className="mb-3">
            <span className="label">
              Orchestrator model
              <span className="text-dim font-normal"> — generates the questions</span>
            </span>
            <input
              className="input"
              list="orchestrator-models"
              placeholder={provider === "stub" ? "stub orchestrator" : "default (server setting) — type to search"}
              value={orchestratorModel}
              onChange={(e) => setOrchestratorModel(e.target.value)}
              disabled={provider === "stub"}
            />
            <datalist id="orchestrator-models">
              {catalog.map((m) => (
                <option key={m.id} value={m.id}>{m.name || m.id}</option>
              ))}
            </datalist>
            <p className="text-xs text-dim mt-1">
              Leave blank to use the server default. This model only writes the
              question set — it is not one of the tested models below.
            </p>
          </div>

          <input
            className="input mb-2"
            placeholder="Search models (e.g. claude, gpt, gemini)…"
            value={modelSearch}
            onChange={(e) => setModelSearch(e.target.value)}
          />

          {modelsError && <p className="text-sm text-wine mb-2">{modelsError}</p>}
          {catalog.length === 0 && !loadingModels && !modelsError ? (
            <p className="text-sm text-muted">
              Leave empty to use the default panel, or add a key and refresh to pick models.
            </p>
          ) : (
            <div className="max-h-72 overflow-y-auto divide-y divide-edge">
              {filteredModels.map((m) => (
                <label key={m.id} className="flex items-center gap-3 text-sm px-2 py-1.5 hover:bg-edge cursor-pointer">
                  <input type="checkbox" checked={selected.includes(m.id)} onChange={() => toggleModel(m.id)} />
                  <span className="flex-1 truncate">{m.id}</span>
                  {provider === "openrouter" && (
                    <span className="text-xs text-dim whitespace-nowrap">
                      {perMillion(m.prompt_price)}/{perMillion(m.completion_price)} per M
                    </span>
                  )}
                </label>
              ))}
              {filteredModels.length === 0 && (
                <p className="text-sm text-dim py-2">No models match “{modelSearch}”.</p>
              )}
            </div>
          )}
          {filteredModels.length > 0 && modelSearch && (
            <p className="text-xs text-dim mt-2">
              {filteredModels.length} of {catalog.length} shown · {selected.length} selected
            </p>
          )}
        </div>

        <div className="card">
          <div className="flex items-center justify-between mb-2">
            <h2 className="text-lg font-semibold">Documents</h2>
            <button className="btn-ghost text-sm" onClick={() => fileInput.current?.click()} disabled={uploading}>
              {uploading ? "Parsing…" : "Upload"}
            </button>
          </div>
          <input ref={fileInput} type="file" multiple hidden accept=".docx,.pdf,.md,.markdown,.txt"
            onChange={onFiles} />
          <p className="text-sm text-muted mb-2">
            docx, pdf, md, txt — parsed and fed to the orchestrator as context.
          </p>
          {documents.length > 0 && (
            <div className="flex flex-wrap gap-2">
              {documents.map((d, i) => (
                <span key={i} className="pill bg-edge flex items-center gap-2">
                  {d.name} · {d.text.length} chars
                  <button className="text-muted hover:text-white"
                    onClick={() => setDocuments((ds) => ds.filter((_, j) => j !== i))}>×</button>
                </span>
              ))}
            </div>
          )}
        </div>

        <div className="card">
          <h2 className="text-lg font-semibold mb-2">Your exact questions (optional)</h2>
          <p className="text-sm text-muted mb-2">
            One per line. These run verbatim; the orchestrator fills the rest up to the question count.
          </p>
          <textarea className="input font-mono text-sm" rows={4}
            placeholder={"Is Acme Co SOC 2 compliant?\nHow does Acme Co price for small teams?"}
            value={customQuestions} onChange={(e) => setCustomQuestions(e.target.value)} />
          {linesToArr(customQuestions).length > 0 && (
            <p className="text-xs text-muted mt-1">{linesToArr(customQuestions).length} custom question(s).</p>
          )}
        </div>
      </div>

      <div className="space-y-6">
        <div className="card">
          <h2 className="text-lg font-semibold mb-4">Run options</h2>
          <Field label="OpenRouter API key">
            {hasKey && !editingKey ? (
              <div className="flex items-center justify-between text-sm">
                <span className="text-ember">✓ Key set</span>
                <button className="text-muted hover:text-white text-xs" onClick={() => setEditingKey(true)}>
                  change
                </button>
              </div>
            ) : (
              <div className="space-y-2">
                <input
                  className="input"
                  type="password"
                  autoComplete="off"
                  placeholder="sk-or-..."
                  value={keyInput}
                  onChange={(e) => setKeyInput(e.target.value)}
                  onKeyDown={(e) => e.key === "Enter" && saveKey()}
                />
                <div className="flex gap-2">
                  <button className="btn-primary text-sm flex-1" onClick={saveKey} disabled={savingKey || !keyInput.trim()}>
                    {savingKey ? "Validating…" : "Save key"}
                  </button>
                  {hasKey && (
                    <button className="btn-ghost text-sm" onClick={() => { setEditingKey(false); setKeyInput(""); }}>
                      Cancel
                    </button>
                  )}
                </div>
                <p className="text-xs text-dim">
                  Stored locally in .env, validated with OpenRouter. Get one at openrouter.ai/keys.
                </p>
                {keyError && <p className="text-xs text-wine">{keyError}</p>}
              </div>
            )}
          </Field>
          <Field label="Provider">
            <div className="flex gap-2">
              <Toggle active={provider === "stub"} onClick={() => setProvider("stub")}>Stub (free)</Toggle>
              <Toggle active={provider === "openrouter"} onClick={() => setProvider("openrouter")} disabled={!hasKey}>
                OpenRouter
              </Toggle>
            </div>
            {!hasKey && <p className="text-xs text-wine mt-1">No API key set — stub only.</p>}
          </Field>
          <Field label="Question count">
            <input type="number" className="input" min={1} max={50} value={questionCount}
              onChange={(e) => setQuestionCount(Math.max(1, Math.min(50, Number(e.target.value))))} />
          </Field>
          <Field label="Cost cap (USD)">
            <input type="number" className="input" min={0} step={0.5} value={costCap}
              onChange={(e) => setCostCap(Number(e.target.value))} />
          </Field>
          <label className="flex items-center gap-2 text-sm mb-2">
            <input type="checkbox" checked={webSearch} onChange={(e) => setWebSearch(e.target.checked)} />
            Enable web search
          </label>
          <label className="flex items-center gap-2 text-sm mb-2">
            <input type="checkbox" checked={autoApprove} onChange={(e) => setAutoApprove(e.target.checked)} />
            Auto-approve questions
          </label>
          <label className="flex items-center gap-2 text-sm mb-2">
            <input type="checkbox" checked={aiInsights} onChange={(e) => setAiInsights(e.target.checked)} />
            AI insights &amp; quotes
          </label>
          <label className="flex items-start gap-2 text-sm">
            <input type="checkbox" className="mt-1" checked={mentionBrand} onChange={(e) => setMentionBrand(e.target.checked)} />
            <span>
              Mention brand in prompt
              <span className="block text-xs text-dim">
                Adds only a neutral test title “AI Visibility Test — {form.name || "Brand"}”.
                Off = fully organic; on = comparable to a named-title manual run.
              </span>
            </span>
          </label>
        </div>

        {estCost !== null && (
          <div className="card text-sm flex items-center justify-between">
            <span className="text-muted">Estimated cost</span>
            <span className="font-mono text-cream">
              ~${estCost < 0.01 ? "<0.01" : estCost.toFixed(2)}
              <span className="text-dim"> / {selected.length} models &times; {questionCount}Q</span>
            </span>
          </div>
        )}

        {error && <div className="card border-wine/50 text-wine text-sm">{error}</div>}

        <button className="btn-primary w-full" onClick={submit} disabled={submitting || !form.name}>
          {submitting ? "Starting…" : editMode ? "Save & re-run" : "Run Scan"}
        </button>
      </div>
    </div>
    </div>
  );
}

function Field({ label, children, wide }: { label: string; children: React.ReactNode; wide?: boolean }) {
  return (
    <div className={`mb-3 ${wide ? "sm:col-span-2" : ""}`}>
      <span className="label">{label}</span>
      {children}
    </div>
  );
}

function Toggle({ active, onClick, disabled, children }: {
  active: boolean; onClick: () => void; disabled?: boolean; children: React.ReactNode;
}) {
  return (
    <button
      onClick={onClick}
      disabled={disabled}
      className={`btn text-sm flex-1 ${active ? "bg-ember text-white" : "border border-edge text-cream"}`}
    >
      {children}
    </button>
  );
}
