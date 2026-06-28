export interface AgentResponse {
  agent: string;
  reasoning: string;
  confidence: number;
  sources: string[];
  evidence_used?: string[];
  challenges: { type: string; description: string }[];
  verdict?: string;
  latency_ms: number;
  cost_usd: number;
}

export interface Evidence {
  id: string;
  content: string;
  source_title: string;
  source_url?: string;
  credibility: number;
  rerank_score?: number;
}

export interface AtomicClaim {
  id: string;
  subject: string;
  predicate: string;
  object: string;
  confidence: number;
  verification_status: string;
}

export interface VerifyResponse {
  claim_id: string;
  debate_id: string;
  overall_verdict: string;
  overall_confidence: number;
  requires_human_review: boolean;
  atomic_claims: AtomicClaim[];
  advocate: AgentResponse;
  skeptic: AgentResponse;
  judge: AgentResponse;
  evidence: Evidence[];
}

export interface DebateSummary {
  id: string;
  claim_id: string;
  verdict: string | null;
  confidence: number | null;
  requires_human_review: boolean;
  total_latency_ms: number;
  total_cost_usd: number;
  created_at: string;
}

export interface DebateListResponse {
  debates: DebateSummary[];
  total: number;
}

export interface DebateDetail {
  id: string;
  claim_id: string;
  verdict: string | null;
  confidence: number | null;
  requires_human_review: boolean;
  turns: { agent: string; response: string; confidence: number; latency_ms: number }[];
  created_at: string;
}

export interface KnowledgeGraphResponse {
  nodes: { id: string; name: string; type: string }[];
  edges: { source: string; target: string; relationship: string; confidence: number; status: string }[];
}

export interface TrainingStats {
  total_samples: number;
  eligible_samples: number;
  duplicates_rejected: number;
  human_approved: number;
  training_blocked?: boolean;
  training_block_reason?: string | null;
}

export interface EvaluationMetrics {
  challenge_recall: number;
  challenge_precision: number;
  challenge_f1: number;
  miss_rate: number;
  avg_latency_ms: number;
  avg_cost_usd: number;
  model_name: string;
  sample_count: number;
}

export interface EvaluationComparisonItem {
  model: string;
  challenge_recall: number;
  challenge_precision: number;
  challenge_f1: number;
  miss_rate: number;
  avg_latency_ms: number;
  avg_cost_usd: number;
  sample_count: number;
  created_at: string;
  inference_model?: string | null;
}

export interface EvaluationCompareResponse {
  comparisons: EvaluationComparisonItem[];
  has_base: boolean;
  has_finetuned: boolean;
}

export interface FineTuningStatus {
  experiments: {
    id: string;
    name: string;
    status: string;
    teacher_model: string;
    student_model: string;
    started_at?: string;
    completed_at?: string;
  }[];
  training_blocked?: boolean;
  training_block_reason?: string | null;
  finetuned_path?: string;
  use_finetuned_skeptic?: boolean;
}

export interface HumanReview {
  id: string;
  debate_id: string;
  claim_text: string;
  judge_confidence: number;
  status: string;
  created_at: string;
}

export interface AdversarialRun {
  run_id: string;
  total_claims: number;
  challenges_detected: number;
  miss_rate: number;
  attack_breakdown: Record<string, { total: number; detected: number }>;
  model_name: string;
}

export interface AdversarialHistoryRun {
  run_id: string;
  total_claims: number;
  challenges_detected: number;
  miss_rate: number;
  attack_breakdown?: Record<string, { total: number; detected: number }>;
  model_name: string;
  created_at: string;
}
