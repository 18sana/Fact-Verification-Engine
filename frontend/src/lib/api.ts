const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api/v1';

async function fetchAPI<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${API_URL}${path}`, {
    ...options,
    headers: { 'Content-Type': 'application/json', ...options?.headers },
  });
  if (!res.ok) {
    const detail = await res.text();
    throw new Error(detail || `API error: ${res.status}`);
  }
  return res.json();
}

export const api = {
  verify: (claim: string) =>
    fetchAPI<import('@/types').VerifyResponse>('/verify', {
      method: 'POST',
      body: JSON.stringify({ claim }),
    }),
  getDebates: () => fetchAPI<import('@/types').DebateListResponse>('/debates'),
  getDebate: (id: string) => fetchAPI<import('@/types').DebateDetail>(`/debates/${id}`),
  getKnowledgeGraph: (entity: string) =>
    fetchAPI<import('@/types').KnowledgeGraphResponse>(`/knowledge-graph?entity=${encodeURIComponent(entity)}`),
  getTrainingStats: () => fetchAPI<import('@/types').TrainingStats>('/training'),
  exportTrainingData: () => fetchAPI<{ path: string; count: number }>('/training/export', { method: 'POST' }),
  getEvaluation: () => fetchAPI<import('@/types').EvaluationMetrics>('/evaluation'),
  getEvaluationCompare: () => fetchAPI<import('@/types').EvaluationCompareResponse>('/evaluation/compare'),
  runEvaluation: () =>
    fetchAPI<import('@/types').EvaluationMetrics>('/evaluation/run', { method: 'POST' }),
  getFineTuningStatus: () => fetchAPI<import('@/types').FineTuningStatus>('/fine-tuning/status'),
  startFineTuning: (name = 'skeptic-qlora-run') =>
    fetchAPI<{ experiment_id: string; status: string; message?: string }>('/fine-tuning/start', {
      method: 'POST',
      body: JSON.stringify({ name }),
    }),
  getHumanReviews: () => fetchAPI<{ reviews: import('@/types').HumanReview[]; total: number }>('/human-reviews'),
  approveReview: (id: string, notes?: string) =>
    fetchAPI<{ id: string; status: string }>(`/human-reviews/${id}/approve`, {
      method: 'POST',
      body: JSON.stringify({ notes }),
    }),
  rejectReview: (id: string, notes?: string) =>
    fetchAPI<{ id: string; status: string }>(`/human-reviews/${id}/reject`, {
      method: 'POST',
      body: JSON.stringify({ notes }),
    }),
  runAdversarialEval: () => fetchAPI<import('@/types').AdversarialRun>('/evaluation/adversarial/run', { method: 'POST' }),
  getAdversarialHistory: () => fetchAPI<{ runs: import('@/types').AdversarialHistoryRun[] }>('/evaluation/adversarial/history'),
  health: () => fetchAPI<{ status: string }>('/health'),
};
