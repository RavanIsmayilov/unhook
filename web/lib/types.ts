export type VerdictLabel = "scam" | "suspicious" | "safe";

export interface LinkInfo {
  url: string;
  domain: string;
  status: "official" | "lookalike" | "suspicious" | "shortener" | "unknown";
  flags: string[];
}

export interface CheckResult {
  verdict: VerdictLabel;
  scheme: string;
  scheme_az: string;
  reasons: string[];
  actions: string[];
  confidence: number;
  explanation_az: string;
  links: LinkInfo[];
  phones: string[];
  text_redacted: string;
  degraded: boolean;
  provider: string;
  model: string;
  report_id: number | null;
}

export interface DailyPoint { date: string; total: number; scam: number }

export interface Stats {
  total_reports: number;
  reports_last_24h: number;
  by_verdict: Record<VerdictLabel, number>;
  degraded_reports: number;
  by_scheme: { scheme: string; scheme_az: string; count: number }[];
  top_brands: { brand: string; count: number }[];
  top_domains: { domain: string; count: number }[];
  by_source: Record<string, number>;
  campaigns_total: number;
  campaigns_active_24h: number;
  daily: DailyPoint[];
  feedback: { total: number; agree: number; disagree: number };
}

export interface Campaign {
  id: string;
  name: string;
  scheme: string;
  scheme_az: string;
  count: number;
  reports_last_24h: number;
  first_seen: string;
  last_seen: string;
  example: string;
  domains: string[];
  brands: string[];
  verdicts: Partial<Record<VerdictLabel, number>>;
  report_ids: number[];
}

export interface ReportRow {
  id: number;
  created_at: string;
  source: string;
  verdict: VerdictLabel;
  scheme: string;
  scheme_az: string;
  confidence: number;
  text_redacted: string;
  domains: string[];
  brands: string[];
  provider: string;
  degraded: boolean;
}

export interface EvalMetrics {
  n: number;
  n_scam: number;
  n_safe: number;
  n_degraded: number;
  recall_flagged: number | null;
  recall_strict: number | null;
  fpr_flagged: number | null;
  fpr_strict: number | null;
  recall_flagged_by_variant: Record<string, number | null>;
  consistency_verdict: number | null;
  consistency_flagged: number | null;
  consistency_groups: number;
}

export interface EvalSystem { key: string; label: string; kind: "baseline" | "llm"; metrics: EvalMetrics }

export interface EvalFailure {
  id: string; label: string; variant: string; verdict: string; type: string; text: string; reasons: string[];
}

export interface EvalResults {
  generated: string;
  n_rows: number;
  systems: EvalSystem[];
  failures: Record<string, { total: number; items: EvalFailure[] }>;
}

export interface AttackRates {
  n: number;
  degraded: number;
  detected_flagged: number | null;
  detected_strict: number | null;
  missed: number;
}

export interface AttackResults {
  generated: string | null;
  config: { attacker_provider: string; attacker_model: string; analyzer_provider: string; analyzer_model: string; n_seeds: number };
  overall: AttackRates;
  by_technique: (AttackRates & { technique: string })[];
  heldout_before: AttackRates | null;
  heldout_after: AttackRates | null;
  false_positives_before: { n: number; fpr_flagged: number | null; fpr_strict: number | null } | null;
  false_positives_after: { n: number; fpr_flagged: number | null; fpr_strict: number | null } | null;
  fewshot: { id: string; technique: string; text: string }[];
  misses: { id: string; technique: string; text: string; confidence: number }[];
}

export interface ResultsPayload { eval: EvalResults | null; attack: AttackResults | null }

export interface BlocklistRow {
  domain: string;
  reports: number;
  first_seen: string;
  last_seen: string;
  brands: string[];
  status: "lookalike" | "suspicious" | "unknown" | "shortener" | "official";
}

export interface FeedbackRow {
  id: number;
  created_at: string;
  report_id: number;
  model_verdict: VerdictLabel;
  suggested: "scam" | "safe" | null;
  scheme: string;
  text_redacted: string;
  note: string;
}
