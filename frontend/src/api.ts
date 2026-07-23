// Typed client for the Parallel-AEO REST API.

export type Provider = "openrouter" | "stub";
export type PromptMode = "single_shot" | "per_question";

export interface SourceDocument {
  name: string;
  text: string;
}

export interface CompanyProfile {
  name: string;
  website?: string | null;
  description?: string | null;
  category?: string | null;
  products?: string[];
  competitors?: string[];
  aliases?: string[];
  regions?: string[];
  notes?: string | null;
  reference_sites?: string[];
  source_documents?: SourceDocument[];
}

export interface Question {
  index: number;
  category: string;
  text: string;
  intent?: string | null;
  expected_source_types?: string[];
}

export interface ModelInfo {
  id: string;
  name: string;
  context_length?: number | null;
  prompt_price: number;
  completion_price: number;
}

export interface RunCreateRequest {
  profile: CompanyProfile;
  provider: Provider;
  target_models?: string[] | null;
  question_count?: number | null;
  prompt_mode?: PromptMode | null;
  enable_web_search?: boolean | null;
  cost_cap_usd?: number | null;
  auto_approve_questions?: boolean | null;
  enable_ai_insights?: boolean | null;
  mention_brand?: boolean | null;
  custom_questions?: string[] | null;
}

export interface ModelAnalysis {
  model_id: string;
  provider: string;
  web_search_used: boolean;
  num_searches: number;
  search_queries: string[];
  brand_mentions: number;
  subbrand_mentions: number;
  in_vendor_table: boolean;
  questions_mentioning: number;
  per_question_brand: Record<string, number>;
  competitor_totals: Record<string, number>;
  citations: { domain: string; url: string; question_index: number | null; brand_owned: boolean; is_reference: boolean }[];
  unique_domains: string[];
  reference_citations: number;
  answer_length: number;
  provenance: "organic" | "search_driven" | "absent";
  error?: string | null;
}

export interface QuestionAggregate {
  index: number;
  text: string;
  total_mentions: number;
  models_mentioning: number;
  avg_per_model: number;
  peak_model: string;
  interpretation: string;
}

export interface DomainStat {
  domain: string;
  num_models: number;
  models: string[];
  brand_owned: boolean;
  is_reference: boolean;
}

export interface UrlStat {
  url: string;
  host: string;
  path: string;
  registrable: string;
  kind: string;
  num_models: number;
  models: string[];
  brand_owned: boolean;
  is_reference: boolean;
}

export interface AnalysisResult {
  models: ModelAnalysis[];
  question_indices: number[];
  questions: QuestionAggregate[];
  heatmap: Record<string, Record<string, number>>;
  competitors: string[];
  competitor_sov: Record<string, Record<string, number>>;
  domain_frequency: DomainStat[];
  url_frequency: UrlStat[];
  insights: string[];
  quotes: { model: string; quote: string }[];
}

export interface RunRecord {
  id: string;
  created_at: string;
  completed_at?: string | null;
  status: string;
  stage_detail?: string | null;
  company: CompanyProfile;
  options: {
    target_models: string[];
    question_count: number;
    provider: string;
    custom_questions?: string[];
    enable_web_search?: boolean;
    cost_cap_usd?: number;
    auto_approve_questions?: boolean;
    mention_brand?: boolean;
  };
  questions: Question[];
  competitors: string[];
  brand_aliases: string[];
  analysis?: AnalysisResult | null;
  total_cost_usd: number;
  error?: string | null;
  reports: Record<string, string>;
  logs: string[];
}

export interface RunSummary {
  id: string;
  created_at: string;
  status: string;
  company_name: string;
  total_cost_usd: number;
  num_models: number;
  num_questions: number;
}

export interface ProgressEvent {
  run_id: string;
  status: string;
  detail: string;
  completed: number;
  total: number;
  log?: string | null;
}

export interface TrendPoint {
  run_id: string;
  created_at: string;
  brand_mentions: number;
  models_mentioning: number;
  models_total: number;
  organic: number;
  search_driven: number;
  absent: number;
  top_competitor: string;
  top_competitor_count: number;
  cost_usd: number;
}

export interface CompanyTrend {
  company: string;
  runs: number;
  points: TrendPoint[];
}

async function j<T>(res: Response): Promise<T> {
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error((body as { detail?: string }).detail || `${res.status} ${res.statusText}`);
  }
  return res.json() as Promise<T>;
}

export const api = {
  health: () => fetch("/api/health").then(j<{ openrouter_key_present: boolean }>),
  setKey: (key: string) =>
    fetch("/api/settings/openrouter-key", {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ key }),
    }).then(j<{ key_present: boolean }>),
  models: (stub: boolean) =>
    fetch(`/api/models?stub=${stub}`).then(j<ModelInfo[]>),
  parseDocuments: (files: File[]) => {
    const fd = new FormData();
    files.forEach((f) => fd.append("files", f));
    return fetch("/api/documents/parse", { method: "POST", body: fd }).then(j<SourceDocument[]>);
  },
  createRun: (req: RunCreateRequest) =>
    fetch("/api/runs", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(req),
    }).then(j<RunRecord>),
  listRuns: () => fetch("/api/runs").then(j<RunSummary[]>),
  trends: () => fetch("/api/trends").then(j<CompanyTrend[]>),
  getRun: (id: string) => fetch(`/api/runs/${id}`).then(j<RunRecord>),
  approve: (id: string, questions?: Question[]) =>
    fetch(`/api/runs/${id}/questions/approve`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ questions: questions ?? null }),
    }).then(j<RunRecord>),
  deleteRun: (id: string) => fetch(`/api/runs/${id}`, { method: "DELETE" }),
  reportUrl: (id: string, format: string) => `/api/runs/${id}/report?format=${format}`,
  events: (id: string, onEvent: (e: ProgressEvent) => void) => {
    const es = new EventSource(`/api/runs/${id}/events`);
    es.addEventListener("progress", (ev) => {
      onEvent(JSON.parse((ev as MessageEvent).data));
    });
    return es;
  },
};
