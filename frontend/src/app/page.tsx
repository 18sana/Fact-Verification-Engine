'use client';

import { useState } from 'react';
import { api } from '@/lib/api';
import type {
  VerifyResponse,
  DebateSummary,
  TrainingStats,
  EvaluationCompareResponse,
  EvaluationComparisonItem,
  EvaluationMetrics,
  HumanReview,
  AdversarialHistoryRun,
  FineTuningStatus,
} from '@/types';
import {
  AgentPanel,
  AtomicClaimCard,
  EvidencePanel,
  KnowledgeGraphViz,
  VerdictBadge,
  VerdictHero,
} from '@/components/Panels';
import {
  AlertBanner,
  Card,
  EmptyState,
  LoadingButton,
  PageHeader,
  StatCard,
  StepProgress,
  TabBadge,
} from '@/components/ui';
import {
  BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, LineChart, Line, CartesianGrid, Cell,
} from 'recharts';
import {
  Search, Scale, Shield, Gavel, Database, Brain, TestTube, Activity, UserCheck,
  History, Sparkles, Layers, Clock, DollarSign, FileJson, Play, RefreshCw,
  Calendar, Zap, Target, TrendingDown, CheckCircle2, XCircle, HelpCircle, AlertTriangle,
  ArrowLeftRight,
} from 'lucide-react';
import clsx from 'clsx';

type Tab = 'verify' | 'history' | 'reviews' | 'training' | 'evaluation' | 'adversarial';

const EXAMPLE_CLAIM_GROUPS: { category: string; examples: { label: string; claim: string }[] }[] = [
  {
    category: 'History',
    examples: [
      { label: 'Moon landing', claim: 'Neil Armstrong became the first human to walk on the Moon on July 20, 1969.' },
      { label: 'Everest summit', claim: 'Edmund Hillary and Tenzing Norgay first reached the summit of Mount Everest in 1953.' },
      { label: 'Marie Curie', claim: 'Marie Curie is the only person to win Nobel Prizes in two different sciences.' },
    ],
  },
  {
    category: 'Technology',
    examples: [
      { label: 'World Wide Web', claim: 'Tim Berners-Lee invented the World Wide Web in 1989 at CERN.' },
      { label: 'First iPhone', claim: 'Apple introduced the first iPhone on January 9, 2007.' },
      { label: 'Wrong inventor', claim: 'Bill Gates invented the World Wide Web at Microsoft in 1995.' },
    ],
  },
  {
    category: 'Geography',
    examples: [
      { label: 'Everest height', claim: 'Mount Everest is 8,849 meters above sea level.' },
      { label: 'Amazon river', claim: 'The Amazon River has the largest discharge volume of any river in the world.' },
      { label: 'Wrong peak', claim: 'K2 is the highest mountain on Earth above sea level.' },
    ],
  },
  {
    category: 'Science & Health',
    examples: [
      { label: 'Penicillin', claim: 'Alexander Fleming discovered penicillin in 1928.' },
      { label: 'Photosynthesis', claim: 'Photosynthesis converts light energy into chemical energy in plants.' },
      { label: 'Earth orbit', claim: 'Earth completes one orbit around the Sun in approximately 365.25 days.' },
      { label: 'COVID pandemic', claim: 'WHO declared COVID-19 a global pandemic on March 11, 2020.' },
    ],
  },
  {
    category: 'Sports',
    examples: [
      { label: 'Argentina 2022', claim: 'Argentina won the 2022 FIFA World Cup in Qatar.' },
      { label: 'Messi Golden Ball', claim: 'Lionel Messi won the Golden Ball at the 2022 World Cup.' },
      { label: 'India 2011 WC', claim: 'India won the Cricket World Cup in 2011 under MS Dhoni.' },
      { label: 'Wrong WC winner', claim: 'France won the 2022 FIFA World Cup final outright without penalties.' },
    ],
  },
  {
    category: 'Stress test',
    examples: [
      { label: 'Contradiction', claim: 'India won the 2011 World Cup but lost the final.' },
      { label: 'Off-topic', claim: 'The Moon is made of green cheese.' },
      { label: 'No evidence', claim: 'Tokyo is the capital of Brazil.' },
    ],
  },
];

const TAB_META: Record<Tab, { title: string; description: string }> = {
  verify: {
    title: 'Verify a Claim',
    description: 'Submit a factual statement. Three AI agents will debate it using retrieved evidence — Advocate defends, Skeptic challenges, Judge decides.',
  },
  history: {
    title: 'Debate History',
    description: 'Browse past verification runs with verdicts, confidence scores, and latency.',
  },
  reviews: {
    title: 'Human Review Queue',
    description: 'Low-confidence verdicts land here. Approve to add them to the Skeptic training dataset.',
  },
  training: {
    title: 'Training Pipeline',
    description: 'Monitor collected debate samples, export JSONL, and trigger QLoRA fine-tuning for the Skeptic model.',
  },
  evaluation: {
    title: 'Skeptic Evaluation',
    description: 'Compare base vs fine-tuned Skeptic on the held-out debate benchmark — F1, recall, precision, and miss rate side by side.',
  },
  adversarial: {
    title: 'Adversarial Testing',
    description: 'Stress-test whether the Skeptic agent speaks up when fed subtly wrong claims — wrong dates, swapped names, misleading wording.',
  },
};

const VERIFY_STEPS = [
  'Extract atomic claims',
  'Retrieve hybrid evidence',
  'Run 3-agent debate',
  'Propagate confidence',
];

const ADVERSARIAL_ATTACKS = [
  {
    key: 'subtle_date_change',
    label: 'Wrong year',
    description: 'A real event with an incorrect date',
    example: 'India won the World Cup in 2007',
    color: 'border-amber-500/20 bg-amber-500/5',
  },
  {
    key: 'entity_swap',
    label: 'Wrong winner',
    description: 'Right event, wrong team or person',
    example: 'Australia won the 2011 World Cup',
    color: 'border-rose-500/20 bg-rose-500/5',
  },
  {
    key: 'misleading_wording',
    label: 'Misleading wording',
    description: 'Technically vague or hedged phrasing',
    example: 'India almost won the 2011 World Cup',
    color: 'border-brand-500/20 bg-brand-500/5',
  },
  {
    key: 'contradictory',
    label: 'Contradiction',
    description: 'Two facts that cannot both be true',
    example: 'India won the 2011 final but lost it',
    color: 'border-purple-500/20 bg-purple-500/5',
  },
  {
    key: 'partially_true',
    label: 'Hedged claim',
    description: 'Uncertain language on a factual statement',
    example: 'India may have won the 2011 World Cup',
    color: 'border-slate-500/20 bg-slate-500/5',
  },
];

const ATTACK_LABELS: Record<string, string> = Object.fromEntries(
  ADVERSARIAL_ATTACKS.map((a) => [a.key, a.label])
);

export default function Dashboard() {
  const [tab, setTab] = useState<Tab>('verify');
  const [claim, setClaim] = useState('');
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<VerifyResponse | null>(null);
  const [error, setError] = useState('');
  const [debates, setDebates] = useState<DebateSummary[]>([]);
  const [training, setTraining] = useState<TrainingStats | null>(null);
  const [finetuning, setFinetuning] = useState<FineTuningStatus | null>(null);
  const [evalCompare, setEvalCompare] = useState<EvaluationCompareResponse | null>(null);
  const [latestEvalRun, setLatestEvalRun] = useState<EvaluationMetrics | null>(null);
  const [reviews, setReviews] = useState<HumanReview[]>([]);
  const [adversarialHistory, setAdversarialHistory] = useState<AdversarialHistoryRun[]>([]);
  const [adversarialLoading, setAdversarialLoading] = useState(false);
  const [evalLoading, setEvalLoading] = useState(false);
  const [kgData, setKgData] = useState<import('@/types').KnowledgeGraphResponse | null>(null);
  const [progressStep, setProgressStep] = useState(-1);
  const [actionMsg, setActionMsg] = useState('');
  const [actionType, setActionType] = useState<'info' | 'warning' | 'success'>('info');

  const handleVerify = async () => {
    if (!claim.trim()) return;
    setLoading(true);
    setError('');
    setResult(null);
    setKgData(null);
    setProgressStep(0);

    const stepTimer = setInterval(() => {
      setProgressStep((s) => (s < VERIFY_STEPS.length - 1 ? s + 1 : s));
    }, 1200);

    try {
      const res = await api.verify(claim);
      setResult(res);
      setProgressStep(VERIFY_STEPS.length);

      if (res.atomic_claims.length > 0) {
        const kg = await api.getKnowledgeGraph(res.atomic_claims[0].subject);
        setKgData(kg);
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Verification failed');
    } finally {
      clearInterval(stepTimer);
      setLoading(false);
    }
  };

  const loadHistory = async () => {
    const data = await api.getDebates();
    setDebates(data.debates);
  };

  const loadTraining = async () => {
    const [data, ft] = await Promise.all([api.getTrainingStats(), api.getFineTuningStatus()]);
    setTraining(data);
    setFinetuning(ft);
  };

  const loadReviews = async () => {
    try {
      const data = await api.getHumanReviews();
      setReviews(data.reviews);
    } catch (e) {
      setActionMsg(e instanceof Error ? e.message : 'Failed to load review queue');
      setActionType('warning');
      setReviews([]);
    }
  };

  const loadEvaluationCached = async () => {
    try {
      const [compare, latest] = await Promise.all([
        api.getEvaluationCompare(),
        api.getEvaluation().catch(() => null),
      ]);
      setEvalCompare(compare);
      setLatestEvalRun(latest);
    } catch {
      setEvalCompare(null);
      setLatestEvalRun(null);
    }
  };

  const runBenchmark = async () => {
    setEvalLoading(true);
    setActionMsg('Running benchmark (~20–40 sec for 15 samples)...');
    setActionType('info');
    try {
      const data = await api.runEvaluation();
      setLatestEvalRun(data);
      const compare = await api.getEvaluationCompare();
      setEvalCompare(compare);
      setActionMsg(`Benchmark complete for ${data.model_name.replace(/_/g, ' ')}.`);
      setActionType('success');
      setTimeout(() => setActionMsg(''), 4000);
    } catch (e) {
      setActionMsg(e instanceof Error ? e.message : 'Benchmark failed');
      setActionType('warning');
    } finally {
      setEvalLoading(false);
    }
  };

  const loadAdversarial = async () => {
    const data = await api.getAdversarialHistory();
    setAdversarialHistory(data.runs);
  };

  const runAdversarial = async () => {
    setAdversarialLoading(true);
    setActionMsg('Running adversarial eval (5 claims, ~15–30 sec)...');
    setActionType('info');
    try {
      await api.runAdversarialEval();
      await loadAdversarial();
      setActionMsg('Adversarial evaluation complete.');
      setActionType('success');
      setTimeout(() => setActionMsg(''), 3000);
    } catch (e) {
      setActionMsg(e instanceof Error ? e.message : 'Adversarial run failed');
      setActionType('warning');
    } finally {
      setAdversarialLoading(false);
    }
  };

  const handleTabChange = (id: Tab) => {
    setTab(id);
    setActionMsg('');
    if (id === 'history') loadHistory();
    if (id === 'training') loadTraining();
    if (id === 'reviews') loadReviews();
    if (id === 'evaluation') loadEvaluationCached();
    if (id === 'adversarial') loadAdversarial();
  };

  const tabs: { id: Tab; label: string; icon: React.ReactNode; desc: string }[] = [
    { id: 'verify', label: 'Verify', icon: <Search size={18} />, desc: 'Submit claims' },
    { id: 'history', label: 'History', icon: <History size={18} />, desc: 'Past debates' },
    { id: 'reviews', label: 'Reviews', icon: <UserCheck size={18} />, desc: 'Human queue' },
    { id: 'training', label: 'Training', icon: <Brain size={18} />, desc: 'Fine-tune Skeptic' },
    { id: 'evaluation', label: 'Evaluation', icon: <TestTube size={18} />, desc: 'Benchmark' },
    { id: 'adversarial', label: 'Adversarial', icon: <Shield size={18} />, desc: 'Stress tests' },
  ];

  const baseEval = evalCompare?.comparisons.find((c) => c.model === 'base_skeptic') ?? null;
  const finetunedEval = evalCompare?.comparisons.find((c) => c.model === 'finetuned_skeptic') ?? null;
  const hasCompareData = (evalCompare?.comparisons.length ?? 0) > 0;

  const formatModelName = (model: string) =>
    model.replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase());

  const formatDelta = (base: number, finetuned: number, higherIsBetter: boolean) => {
    const delta = finetuned - base;
    if (Math.abs(delta) < 0.0001) return { text: 'No change', tone: 'slate' as const };
    const improved = higherIsBetter ? delta > 0 : delta < 0;
    return {
      text: `${delta > 0 ? '+' : ''}${(delta * 100).toFixed(1)}%`,
      tone: improved ? ('emerald' as const) : ('rose' as const),
    };
  };

  const comparisonChartData = [
    { metric: 'F1', base: baseEval?.challenge_f1 ?? 0, finetuned: finetunedEval?.challenge_f1 ?? 0 },
    { metric: 'Recall', base: baseEval?.challenge_recall ?? 0, finetuned: finetunedEval?.challenge_recall ?? 0 },
    { metric: 'Precision', base: baseEval?.challenge_precision ?? 0, finetuned: finetunedEval?.challenge_precision ?? 0 },
    { metric: 'Miss Rate', base: baseEval?.miss_rate ?? 0, finetuned: finetunedEval?.miss_rate ?? 0 },
  ];

  const renderModelMetrics = (item: EvaluationComparisonItem, accent: 'brand' | 'emerald') => (
    <Card className={clsx(accent === 'brand' ? 'border-brand-500/20' : 'border-emerald-500/20')}>
      <div className="flex items-start justify-between gap-3 mb-5">
        <div>
          <p className={clsx('text-xs font-semibold uppercase tracking-wider', accent === 'brand' ? 'text-brand-400' : 'text-emerald-400')}>
            {formatModelName(item.model)}
          </p>
          <p className="text-xs text-slate-500 mt-1">
            {item.sample_count} samples · {new Date(item.created_at).toLocaleString()}
            {item.inference_model && (
              <> · <span className="text-slate-400">{item.inference_model}</span></>
            )}
          </p>
        </div>
        <span className={clsx('px-2 py-1 rounded-lg text-xs font-medium border', accent === 'brand' ? 'bg-brand-500/10 text-brand-300 border-brand-500/20' : 'bg-emerald-500/10 text-emerald-300 border-emerald-500/20')}>
          {item.model === 'base_skeptic' ? 'Before' : 'After'}
        </span>
      </div>
      <div className="grid grid-cols-2 gap-3">
        {[
          { label: 'F1', value: `${(item.challenge_f1 * 100).toFixed(1)}%` },
          { label: 'Recall', value: `${(item.challenge_recall * 100).toFixed(1)}%` },
          { label: 'Precision', value: `${(item.challenge_precision * 100).toFixed(1)}%` },
          { label: 'Miss Rate', value: `${(item.miss_rate * 100).toFixed(1)}%` },
          { label: 'Latency', value: `${item.avg_latency_ms.toFixed(0)}ms` },
          { label: 'Cost', value: `$${item.avg_cost_usd.toFixed(4)}` },
        ].map((m) => (
          <div key={m.label} className="rounded-xl bg-surface-overlay border border-surface-border p-3">
            <p className="text-xs text-slate-500">{m.label}</p>
            <p className="text-lg font-semibold text-white tabular-nums mt-0.5">{m.value}</p>
          </div>
        ))}
      </div>
    </Card>
  );

  const missRateChart = [...adversarialHistory]
    .reverse()
    .map((r, i) => ({
      run: `#${i + 1}`,
      miss: r.miss_rate,
      date: new Date(r.created_at).toLocaleDateString(),
    }));

  const latestAdversarial = adversarialHistory[0] ?? null;
  const missesDetected = latestAdversarial
    ? latestAdversarial.total_claims - latestAdversarial.challenges_detected
    : 0;

  const meta = TAB_META[tab];

  return (
    <div className="min-h-screen flex">
      {/* Sidebar */}
      <aside className="hidden lg:flex flex-col w-64 shrink-0 border-r border-surface-border bg-surface-raised/60 backdrop-blur-xl sticky top-0 h-screen">
        <div className="p-6 border-b border-surface-border">
          <div className="flex items-center gap-3">
            <div className="p-2.5 rounded-xl bg-gradient-to-br from-brand-500 to-brand-700 shadow-glow">
              <Scale size={22} className="text-white" />
            </div>
            <div>
              <h1 className="font-bold text-white text-sm leading-tight">Fact-Verification</h1>
              <p className="text-[11px] text-slate-500 mt-0.5">Adversarial debate engine</p>
            </div>
          </div>
        </div>

        <nav className="flex-1 p-4 space-y-1 overflow-y-auto">
          {tabs.map((t) => (
            <button
              key={t.id}
              type="button"
              onClick={() => handleTabChange(t.id)}
              className={clsx('nav-item', tab === t.id ? 'nav-item-active' : 'nav-item-inactive')}
            >
              <span className={tab === t.id ? 'text-brand-400' : 'text-slate-500'}>{t.icon}</span>
              <div className="text-left">
                <div>{t.label}</div>
                <div className="text-[10px] text-slate-600 font-normal">{t.desc}</div>
              </div>
              {t.id === 'reviews' && <TabBadge count={reviews.length} />}
            </button>
          ))}
        </nav>

        <div className="p-4 border-t border-surface-border">
          <div className="glass-card p-3 text-xs text-slate-500 space-y-1">
            <div className="flex items-center gap-2 text-slate-400 font-medium">
              <Sparkles size={12} className="text-brand-400" />
              Pipeline
            </div>
            <p>Extract → Retrieve → Debate → Judge → Learn</p>
          </div>
        </div>
      </aside>

      {/* Main */}
      <div className="flex-1 flex flex-col min-w-0">
        {/* Mobile nav */}
        <header className="lg:hidden sticky top-0 z-20 border-b border-surface-border bg-surface-raised/90 backdrop-blur-xl">
          <div className="flex items-center gap-2 px-4 py-3 overflow-x-auto">
            {tabs.map((t) => (
              <button
                key={t.id}
                type="button"
                onClick={() => handleTabChange(t.id)}
                className={clsx(
                  'flex items-center gap-1.5 px-3 py-2 rounded-lg text-xs font-medium whitespace-nowrap shrink-0 transition-colors',
                  tab === t.id ? 'bg-brand-500/20 text-brand-400' : 'text-slate-400'
                )}
              >
                {t.icon}
                {t.label}
                {t.id === 'reviews' && reviews.length > 0 && (
                  <span className="w-4 h-4 rounded-full bg-rose-500 text-white text-[10px] flex items-center justify-center">
                    {reviews.length}
                  </span>
                )}
              </button>
            ))}
          </div>
        </header>

        {actionMsg && (
          <div className="px-6 pt-4 max-w-5xl">
            <AlertBanner type={actionType}>{actionMsg}</AlertBanner>
          </div>
        )}

        <main className="flex-1 px-4 sm:px-6 lg:px-10 py-8 max-w-5xl">
          <PageHeader title={meta.title} description={meta.description} />

          {/* ── VERIFY ── */}
          {tab === 'verify' && (
            <div className="space-y-6 animate-fade-in">
              <Card>
                <label htmlFor="claim-input" className="block text-sm font-medium text-slate-300 mb-3">
                  Enter a factual claim to verify
                </label>
                <textarea
                  id="claim-input"
                  value={claim}
                  onChange={(e) => setClaim(e.target.value)}
                  placeholder="Type or paste a factual statement..."
                  rows={4}
                  className="input-field"
                  onKeyDown={(e) => {
                    if (e.key === 'Enter' && (e.metaKey || e.ctrlKey)) handleVerify();
                  }}
                />

                <div className="mt-4 space-y-3">
                  <span className="text-xs text-slate-600">Try an example:</span>
                  {EXAMPLE_CLAIM_GROUPS.map((group) => (
                    <div key={group.category}>
                      <p className="text-[11px] font-semibold uppercase tracking-wider text-slate-500 mb-2">
                        {group.category}
                      </p>
                      <div className="flex flex-wrap gap-2">
                        {group.examples.map(({ label, claim }) => (
                          <button
                            key={claim}
                            type="button"
                            title={claim}
                            onClick={() => setClaim(claim)}
                            className="chip"
                          >
                            {label}
                          </button>
                        ))}
                      </div>
                    </div>
                  ))}
                </div>

                <div className="flex items-center gap-4 mt-5">
                  <LoadingButton loading={loading} onClick={handleVerify} disabled={!claim.trim()}>
                    {loading ? 'Verifying…' : 'Verify Claim'}
                  </LoadingButton>
                  <span className="text-xs text-slate-600 hidden sm:inline">⌘ + Enter to submit</span>
                </div>

                {error && (
                  <div className="mt-4">
                    <AlertBanner type="error">{error}</AlertBanner>
                  </div>
                )}

                {loading && (
                  <StepProgress steps={VERIFY_STEPS} activeIndex={progressStep} />
                )}
              </Card>

              {result && (
                <div className="space-y-6 animate-slide-up">
                  <VerdictHero
                    verdict={result.overall_verdict}
                    confidence={result.overall_confidence}
                    requiresReview={result.requires_human_review}
                  />

                  {result.atomic_claims.length > 0 && (
                    <Card>
                      <div className="flex items-center gap-2 mb-4">
                        <Layers size={16} className="text-brand-400" />
                        <h3 className="text-sm font-semibold text-slate-300">Atomic Claims</h3>
                        <span className="text-xs text-slate-600 ml-auto">{result.atomic_claims.length} extracted</span>
                      </div>
                      <div className="grid gap-2">
                        {result.atomic_claims.map((ac) => (
                          <AtomicClaimCard
                            key={ac.id}
                            subject={ac.subject}
                            predicate={ac.predicate}
                            object={ac.object}
                            confidence={ac.confidence}
                          />
                        ))}
                      </div>
                    </Card>
                  )}

                  <Card>
                    <div className="flex items-center gap-2 mb-5">
                      <Database size={16} className="text-brand-400" />
                      <h3 className="text-sm font-semibold text-slate-300">Retrieved Evidence</h3>
                      <span className="text-xs text-slate-600 ml-auto">{result.evidence.length} sources</span>
                    </div>
                    <EvidencePanel evidence={result.evidence} />
                  </Card>

                  <div>
                    <h3 className="text-sm font-semibold text-slate-400 uppercase tracking-wider mb-4">
                      Agent Debate
                    </h3>
                    <div className="grid lg:grid-cols-3 gap-4">
                      <AgentPanel title="Advocate" agent={result.advocate} color="border-emerald-500/20" evidence={result.evidence} />
                      <AgentPanel title="Skeptic" agent={result.skeptic} color="border-rose-500/20" evidence={result.evidence} />
                      <AgentPanel title="Judge" agent={result.judge} color="border-brand-500/20" evidence={result.evidence} />
                    </div>
                  </div>

                  {kgData && (
                    <Card>
                      <h3 className="text-sm font-semibold text-slate-300 mb-4">Knowledge Graph</h3>
                      <KnowledgeGraphViz data={kgData} />
                    </Card>
                  )}
                </div>
              )}
            </div>
          )}

          {/* ── HISTORY ── */}
          {tab === 'history' && (
            <div className="animate-fade-in">
              {debates.length === 0 ? (
                <Card>
                  <EmptyState
                    icon={<Activity size={28} />}
                    title="No debates yet"
                    description="Verify your first claim to see debate history here."
                    action={
                      <button type="button" className="btn-primary" onClick={() => setTab('verify')}>
                        Go to Verify
                      </button>
                    }
                  />
                </Card>
              ) : (
                <div className="space-y-3">
                  {debates.map((d, i) => (
                    <div
                      key={d.id}
                      className="glass-card-hover p-4 flex flex-col sm:flex-row sm:items-center gap-3 animate-slide-up"
                      style={{ animationDelay: `${i * 50}ms` }}
                    >
                      <div className="flex items-center gap-3 flex-wrap flex-1">
                        <div className="flex items-center gap-1.5 text-xs text-slate-500">
                          <Calendar size={12} />
                          {new Date(d.created_at).toLocaleString()}
                        </div>
                        {d.verdict && <VerdictBadge verdict={d.verdict} />}
                        {d.requires_human_review && (
                          <span className="text-xs font-medium text-amber-400 bg-amber-500/10 px-2 py-1 rounded-lg border border-amber-500/20">
                            Needs review
                          </span>
                        )}
                      </div>
                      <div className="flex items-center gap-4 text-sm text-slate-400 shrink-0">
                        {d.confidence != null && (
                          <span className="font-semibold text-white tabular-nums">{(d.confidence * 100).toFixed(0)}%</span>
                        )}
                        <span className="flex items-center gap-1 text-xs">
                          <Clock size={12} />{d.total_latency_ms.toFixed(0)}ms
                        </span>
                        <span className="flex items-center gap-1 text-xs">
                          <DollarSign size={12} />{d.total_cost_usd.toFixed(4)}
                        </span>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}

          {/* ── REVIEWS ── */}
          {tab === 'reviews' && (
            <div className="animate-fade-in">
              {reviews.length === 0 ? (
                <Card>
                  <EmptyState
                    icon={<Gavel size={28} />}
                    title="Review queue is empty"
                    description="Low-confidence verdicts appear here for approval before training. Submit a tricky claim (e.g. Earth orbit with weak evidence) or refresh — resolved reviews are removed from the queue."
                    action={
                      <button type="button" className="btn-secondary" onClick={loadReviews}>
                        <RefreshCw size={16} /> Refresh queue
                      </button>
                    }
                  />
                </Card>
              ) : (
                <div className="space-y-4">
                  {reviews.map((r, i) => (
                    <Card key={r.id} className="animate-slide-up" style={{ animationDelay: `${i * 60}ms` }}>
                      <p className="text-sm text-slate-200 leading-relaxed mb-4">{r.claim_text}</p>
                      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pt-3 border-t border-surface-border">
                        <div className="flex items-center gap-3 text-xs text-slate-500">
                          <span className="font-semibold text-amber-400">
                            {(r.judge_confidence * 100).toFixed(0)}% confidence
                          </span>
                          <span>·</span>
                          <span>{new Date(r.created_at).toLocaleString()}</span>
                        </div>
                        <div className="flex gap-2">
                          <button
                            type="button"
                            className="btn-success"
                            onClick={async () => {
                              await api.approveReview(r.id);
                              loadReviews();
                            }}
                          >
                            Approve
                          </button>
                          <button
                            type="button"
                            className="btn-danger"
                            onClick={async () => {
                              await api.rejectReview(r.id);
                              loadReviews();
                            }}
                          >
                            Reject
                          </button>
                        </div>
                      </div>
                    </Card>
                  ))}
                </div>
              )}
            </div>
          )}

          {/* ── TRAINING ── */}
          {tab === 'training' && (
            <div className="space-y-6 animate-fade-in">
              {!training ? (
                <Card>
                  <EmptyState
                    icon={<Brain size={28} />}
                    title="Training data not loaded"
                    description="Load statistics to see sample counts and fine-tuning status."
                    action={
                      <button type="button" className="btn-primary" onClick={loadTraining}>
                        <RefreshCw size={16} /> Load Stats
                      </button>
                    }
                  />
                </Card>
              ) : (
                <>
                  <Card>
                    <h3 className="text-sm font-semibold text-slate-300 mb-2 flex items-center gap-2">
                      <HelpCircle size={16} className="text-brand-400" /> How training works
                    </h3>
                    <p className="text-sm text-slate-400 leading-relaxed">
                      High-confidence debates become <strong className="text-slate-300">training samples</strong>.
                      Export them as JSONL, then fine-tune a smaller Skeptic model (Phi-2 + LoRA).
                      Fine-tuning is <strong className="text-slate-300">blocked</strong> if the latest{' '}
                      <strong className="text-slate-300">Evaluation benchmark</strong> miss rate is too high — that
                      means Skeptic quality is not good enough yet to learn from.
                    </p>
                  </Card>

                  {training.training_blocked ? (
                    <AlertBanner type="warning">
                      <p className="font-medium">Fine-tuning blocked</p>
                      <p className="text-sm mt-1 opacity-90">{training.training_block_reason}</p>
                      <p className="text-xs mt-2 opacity-75">
                        To unblock: run Evaluation again with better results, or set{' '}
                        <code className="text-slate-300">TRAINING_BLOCK_MISS_RATE_THRESHOLD=1.0</code> in .env for demo only.
                      </p>
                    </AlertBanner>
                  ) : (
                    <AlertBanner type="success">
                      Fine-tuning is allowed — latest benchmark miss rate is below the training threshold.
                    </AlertBanner>
                  )}

                  {training.eligible_samples < 10 && (
                    <AlertBanner type="info">
                      Only {training.eligible_samples} sample{training.eligible_samples === 1 ? '' : 's'} so far.
                      Fine-tuning may run but needs more debates (10+) for meaningful improvement.
                    </AlertBanner>
                  )}

                  <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
                    <StatCard label="Total Samples" value={training.total_samples} icon={<Database size={16} />} delay={0} />
                    <StatCard label="Eligible" value={training.eligible_samples} icon={<Target size={16} />} accent="emerald" delay={50} />
                    <StatCard label="Duplicates" value={training.duplicates_rejected} icon={<Layers size={16} />} accent="amber" delay={100} />
                    <StatCard label="Human Approved" value={training.human_approved} icon={<UserCheck size={16} />} accent="brand" delay={150} />
                  </div>

                  <Card>
                    <h3 className="text-sm font-semibold text-slate-300 mb-4">Actions</h3>
                    <div className="flex flex-wrap gap-3">
                      <button
                        type="button"
                        className="btn-secondary"
                        onClick={async () => {
                          const res = await api.exportTrainingData();
                          setActionMsg(`Exported ${res.count} samples to ${res.path}`);
                          setActionType('success');
                        }}
                      >
                        <FileJson size={16} /> Export JSONL
                      </button>
                      <button
                        type="button"
                        className="btn-primary"
                        disabled={training.training_blocked}
                        onClick={async () => {
                          const res = await api.startFineTuning();
                          setActionMsg(res.message || `Started experiment ${res.experiment_id}`);
                          setActionType('info');
                          loadTraining();
                        }}
                      >
                        <Play size={16} /> Start QLoRA Fine-tuning
                      </button>
                      <button type="button" className="btn-secondary" onClick={loadTraining}>
                        <RefreshCw size={16} /> Refresh
                      </button>
                    </div>
                  </Card>

                  {finetuning && finetuning.experiments.length > 0 && (
                    <Card>
                      <h3 className="text-sm font-semibold text-slate-300 mb-1">Experiments</h3>
                      <p className="text-xs text-slate-500 mb-4">
                        QLoRA trains Phi-2 on your JSONL. Failures are common on CPU-only Docker — use a GPU machine for real runs.
                      </p>
                      <div className="space-y-2">
                        {finetuning.experiments.map((e) => (
                          <div
                            key={e.id}
                            className="flex items-center justify-between bg-surface-overlay rounded-xl px-4 py-3 border border-surface-border"
                          >
                            <div>
                              <span className="text-sm font-medium text-slate-200">{e.name}</span>
                              <p className="text-xs text-slate-600 mt-0.5">{e.student_model}</p>
                            </div>
                            <span
                              className={clsx(
                                'text-xs font-semibold px-2.5 py-1 rounded-full border capitalize',
                                e.status === 'completed' && 'bg-emerald-500/15 text-emerald-400 border-emerald-500/30',
                                e.status === 'failed' && 'bg-rose-500/15 text-rose-400 border-rose-500/30',
                                !['completed', 'failed'].includes(e.status) && 'bg-amber-500/15 text-amber-400 border-amber-500/30'
                              )}
                            >
                              {e.status}
                            </span>
                          </div>
                        ))}
                      </div>
                    </Card>
                  )}
                </>
              )}
            </div>
          )}

          {/* ── EVALUATION ── */}
          {tab === 'evaluation' && (
            <div className="space-y-6 animate-fade-in">
              <Card>
                <h3 className="text-sm font-semibold text-slate-300 mb-2 flex items-center gap-2">
                  <HelpCircle size={16} className="text-brand-400" /> Before / after comparison
                </h3>
                <p className="text-sm text-slate-400 leading-relaxed">
                  <strong className="text-slate-300">Base</strong> Skeptic uses{' '}
                  <strong className="text-slate-300">Haiku</strong>;{' '}
                  <strong className="text-slate-300">fine-tuned</strong> path uses{' '}
                  <strong className="text-slate-300">Sonnet</strong> (stronger, slower).
                  Run benchmark once with <code className="text-brand-300">USE_FINETUNED_SKEPTIC=false</code>, then again with{' '}
                  <code className="text-brand-300">true</code> after recreating the backend.
                </p>
                {latestEvalRun && (
                  <p className="text-xs text-slate-500 mt-3">
                    Last run: <span className="text-slate-400">{formatModelName(latestEvalRun.model_name)}</span>
                    {' · '}F1 {(latestEvalRun.challenge_f1 * 100).toFixed(1)}%
                    {' · '}{latestEvalRun.sample_count} samples
                  </p>
                )}
              </Card>

              {!hasCompareData ? (
                <Card>
                  <EmptyState
                    icon={<TestTube size={28} />}
                    title="No benchmark results yet"
                    description="Quick benchmark: 15 held-out debates in parallel (~30 sec). Set BENCHMARK_MAX_SAMPLES=0 in .env for all 55 debates."
                    action={
                      <LoadingButton loading={evalLoading} onClick={runBenchmark}>
                        <Zap size={16} /> Run Benchmark
                      </LoadingButton>
                    }
                  />
                </Card>
              ) : (
                <>
                  {evalCompare?.has_base && evalCompare?.has_finetuned && baseEval && finetunedEval && (
                    <Card className="border-brand-500/20 bg-brand-500/5">
                      <h3 className="text-sm font-semibold text-slate-300 mb-4 flex items-center gap-2">
                        <ArrowLeftRight size={16} className="text-brand-400" /> Fine-tuned vs base delta
                      </h3>
                      <div className="grid sm:grid-cols-3 gap-3">
                        {[
                          { label: 'F1 change', ...formatDelta(baseEval.challenge_f1, finetunedEval.challenge_f1, true) },
                          { label: 'Miss rate change', ...formatDelta(baseEval.miss_rate, finetunedEval.miss_rate, false) },
                          { label: 'Recall change', ...formatDelta(baseEval.challenge_recall, finetunedEval.challenge_recall, true) },
                        ].map((d) => (
                          <div key={d.label} className="rounded-xl border border-surface-border bg-surface-overlay p-4">
                            <p className="text-xs text-slate-500">{d.label}</p>
                            <p className={clsx('text-2xl font-bold tabular-nums mt-1', d.tone === 'emerald' && 'text-emerald-400', d.tone === 'rose' && 'text-rose-400', d.tone === 'slate' && 'text-slate-400')}>
                              {d.text}
                            </p>
                          </div>
                        ))}
                      </div>
                    </Card>
                  )}

                  {(!evalCompare?.has_base || !evalCompare?.has_finetuned) && (
                    <Card className="border-amber-500/20 bg-amber-500/5">
                      <div className="flex gap-3">
                        <AlertTriangle size={18} className="text-amber-400 shrink-0 mt-0.5" />
                        <div className="text-sm text-slate-400">
                          <p className="font-medium text-amber-300 mb-1">Partial comparison</p>
                          {!evalCompare?.has_base && <p>Missing <strong className="text-slate-300">base_skeptic</strong> run — set USE_FINETUNED_SKEPTIC=false and run benchmark.</p>}
                          {!evalCompare?.has_finetuned && <p>Missing <strong className="text-slate-300">finetuned_skeptic</strong> run — complete fine-tuning, set USE_FINETUNED_SKEPTIC=true, then run benchmark again.</p>}
                        </div>
                      </div>
                    </Card>
                  )}

                  <div className={clsx('grid gap-4', baseEval && finetunedEval ? 'lg:grid-cols-2' : 'grid-cols-1')}>
                    {baseEval && renderModelMetrics(baseEval, 'brand')}
                    {finetunedEval && renderModelMetrics(finetunedEval, 'emerald')}
                    {!baseEval && !finetunedEval && evalCompare?.comparisons.map((item) => (
                      <div key={item.model}>
                        {renderModelMetrics(item, item.model.includes('finetuned') ? 'emerald' : 'brand')}
                      </div>
                    ))}
                  </div>

                  {baseEval && finetunedEval && (
                    <Card>
                      <h3 className="text-sm font-semibold text-slate-300 mb-5 flex items-center gap-2">
                        <Target size={16} className="text-brand-400" /> Side-by-side metrics
                      </h3>
                      <ResponsiveContainer width="100%" height={300}>
                        <BarChart data={comparisonChartData} barGap={4} barCategoryGap="20%">
                          <CartesianGrid strokeDasharray="3 3" stroke="#2a3042" vertical={false} />
                          <XAxis dataKey="metric" stroke="#64748b" fontSize={12} tickLine={false} axisLine={false} />
                          <YAxis stroke="#64748b" fontSize={12} domain={[0, 1]} tickLine={false} axisLine={false} tickFormatter={(v) => `${(v * 100).toFixed(0)}%`} />
                          <Tooltip
                            contentStyle={{ background: '#161922', border: '1px solid #2a3042', borderRadius: 12 }}
                            formatter={(v: number) => [`${(v * 100).toFixed(1)}%`, '']}
                          />
                          <Bar dataKey="base" name="Base Skeptic" fill="#3b82f6" radius={[6, 6, 0, 0]} />
                          <Bar dataKey="finetuned" name="Fine-tuned Skeptic" fill="#10b981" radius={[6, 6, 0, 0]} />
                        </BarChart>
                      </ResponsiveContainer>
                      <div className="flex flex-wrap gap-4 mt-4 text-xs text-slate-500">
                        <span className="flex items-center gap-2"><span className="w-3 h-3 rounded-sm bg-[#3b82f6]" /> Base Skeptic</span>
                        <span className="flex items-center gap-2"><span className="w-3 h-3 rounded-sm bg-[#10b981]" /> Fine-tuned Skeptic</span>
                      </div>
                    </Card>
                  )}

                  <Card>
                    <h3 className="text-sm font-semibold text-slate-300 mb-4">F1 vs miss rate</h3>
                    <div className="grid sm:grid-cols-2 gap-6">
                      <div>
                        <p className="text-xs text-slate-500 mb-3">Challenge F1 (higher is better)</p>
                        <ResponsiveContainer width="100%" height={200}>
                          <BarChart
                            data={evalCompare?.comparisons.map((c) => ({
                              model: formatModelName(c.model).replace(' Skeptic', ''),
                              value: c.challenge_f1,
                              fill: c.model === 'finetuned_skeptic' ? '#10b981' : '#3b82f6',
                            })) ?? []}
                            barSize={48}
                          >
                            <CartesianGrid strokeDasharray="3 3" stroke="#2a3042" vertical={false} />
                            <XAxis dataKey="model" stroke="#64748b" fontSize={11} tickLine={false} axisLine={false} />
                            <YAxis stroke="#64748b" fontSize={11} domain={[0, 1]} tickLine={false} axisLine={false} tickFormatter={(v) => `${(v * 100).toFixed(0)}%`} />
                            <Tooltip contentStyle={{ background: '#161922', border: '1px solid #2a3042', borderRadius: 12 }} formatter={(v: number) => [`${(v * 100).toFixed(1)}%`, 'F1']} />
                            <Bar dataKey="value" radius={[6, 6, 0, 0]}>
                              {evalCompare?.comparisons.map((c, i) => (
                                <Cell key={i} fill={c.model === 'finetuned_skeptic' ? '#10b981' : '#3b82f6'} />
                              ))}
                            </Bar>
                          </BarChart>
                        </ResponsiveContainer>
                      </div>
                      <div>
                        <p className="text-xs text-slate-500 mb-3">Miss rate (lower is better)</p>
                        <ResponsiveContainer width="100%" height={200}>
                          <BarChart
                            data={evalCompare?.comparisons.map((c) => ({
                              model: formatModelName(c.model).replace(' Skeptic', ''),
                              value: c.miss_rate,
                            })) ?? []}
                            barSize={48}
                          >
                            <CartesianGrid strokeDasharray="3 3" stroke="#2a3042" vertical={false} />
                            <XAxis dataKey="model" stroke="#64748b" fontSize={11} tickLine={false} axisLine={false} />
                            <YAxis stroke="#64748b" fontSize={11} domain={[0, 'auto']} tickLine={false} axisLine={false} tickFormatter={(v) => `${(v * 100).toFixed(0)}%`} />
                            <Tooltip contentStyle={{ background: '#161922', border: '1px solid #2a3042', borderRadius: 12 }} formatter={(v: number) => [`${(v * 100).toFixed(1)}%`, 'Miss rate']} />
                            <Bar dataKey="value" radius={[6, 6, 0, 0]}>
                              {evalCompare?.comparisons.map((c, i) => (
                                <Cell key={i} fill={c.model === 'finetuned_skeptic' ? '#f59e0b' : '#ef4444'} />
                              ))}
                            </Bar>
                          </BarChart>
                        </ResponsiveContainer>
                      </div>
                    </div>
                  </Card>

                  <LoadingButton loading={evalLoading} onClick={runBenchmark} className="btn-secondary">
                    <RefreshCw size={16} /> Re-run Benchmark 
                  </LoadingButton>
                </>
              )}
            </div>
          )}

          {/* ── ADVERSARIAL ── */}
          {tab === 'adversarial' && (
            <div className="space-y-6 animate-fade-in">
              {/* How it works */}
              <Card>
                <h3 className="text-sm font-semibold text-slate-300 mb-2 flex items-center gap-2">
                  <HelpCircle size={16} className="text-brand-400" /> What does this test?
                </h3>
                <p className="text-sm text-slate-400 leading-relaxed mb-5">
                  We auto-generate <strong className="text-slate-300">tricky false claims</strong> and check whether the
                  <strong className="text-slate-300"> Skeptic agent pushes back</strong>. A good Skeptic should challenge
                  every bad claim — staying silent counts as a miss.
                </p>
                <ol className="grid sm:grid-cols-3 gap-3 text-sm">
                  {[
                    { step: '1', text: 'Generate subtly wrong claims (see types below)' },
                    { step: '2', text: 'Ask Skeptic to challenge each one' },
                    { step: '3', text: 'Score: did Skeptic speak up or stay silent?' },
                  ].map((s) => (
                    <li key={s.step} className="flex gap-3 p-3 rounded-xl bg-surface-overlay border border-surface-border">
                      <span className="flex items-center justify-center w-7 h-7 rounded-lg bg-brand-500/15 text-brand-400 text-xs font-bold shrink-0">
                        {s.step}
                      </span>
                      <span className="text-slate-400 leading-snug">{s.text}</span>
                    </li>
                  ))}
                </ol>
              </Card>

              {/* Run + latest results */}
              <Card>
                <div className="flex flex-col sm:flex-row sm:items-start justify-between gap-4 mb-6">
                  <div>
                    <h3 className="text-sm font-semibold text-slate-300">Run stress test</h3>
                    <p className="text-xs text-slate-500 mt-1">
                      Tests 5 claims in parallel (~15–30 sec). Each run is saved below.
                    </p>
                  </div>
                  <LoadingButton loading={adversarialLoading} onClick={runAdversarial}>
                    Run Adversarial Eval
                  </LoadingButton>
                </div>

                {latestAdversarial ? (
                  <div className="rounded-xl border border-surface-border bg-surface-overlay p-5 space-y-4">
                    <div className="flex flex-wrap items-center justify-between gap-3">
                      <div>
                        <p className="text-xs font-semibold uppercase tracking-wider text-slate-500">Latest run</p>
                        <p className="text-xs text-slate-600 mt-0.5">
                          {new Date(latestAdversarial.created_at).toLocaleString()}
                        </p>
                      </div>
                      <span
                        className={clsx(
                          'inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-semibold border',
                          latestAdversarial.miss_rate === 0
                            ? 'bg-emerald-500/15 text-emerald-400 border-emerald-500/30'
                            : latestAdversarial.miss_rate <= 0.15
                              ? 'bg-amber-500/15 text-amber-400 border-amber-500/30'
                              : 'bg-rose-500/15 text-rose-400 border-rose-500/30'
                        )}
                      >
                        {latestAdversarial.miss_rate === 0 ? (
                          <CheckCircle2 size={13} />
                        ) : (
                          <AlertTriangle size={13} />
                        )}
                        {latestAdversarial.miss_rate === 0
                          ? 'All claims challenged'
                          : `${missesDetected} miss${missesDetected === 1 ? '' : 'es'}`}
                      </span>
                    </div>

                    <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
                      <div className="p-3 rounded-lg bg-surface-raised border border-surface-border text-center">
                        <p className="text-2xl font-bold text-white tabular-nums">
                          {latestAdversarial.challenges_detected}/{latestAdversarial.total_claims}
                        </p>
                        <p className="text-[11px] text-slate-500 mt-1">Claims challenged</p>
                      </div>
                      <div className="p-3 rounded-lg bg-surface-raised border border-surface-border text-center">
                        <p className="text-2xl font-bold text-emerald-400 tabular-nums">
                          {(latestAdversarial.challenges_detected / latestAdversarial.total_claims * 100).toFixed(0)}%
                        </p>
                        <p className="text-[11px] text-slate-500 mt-1">Catch rate</p>
                      </div>
                      <div className="p-3 rounded-lg bg-surface-raised border border-surface-border text-center">
                        <p className={clsx(
                          'text-2xl font-bold tabular-nums',
                          latestAdversarial.miss_rate === 0 ? 'text-emerald-400' : 'text-rose-400'
                        )}>
                          {(latestAdversarial.miss_rate * 100).toFixed(0)}%
                        </p>
                        <p className="text-[11px] text-slate-500 mt-1">Miss rate</p>
                      </div>
                      <div className="p-3 rounded-lg bg-surface-raised border border-surface-border text-center">
                        <p className="text-2xl font-bold text-slate-300 tabular-nums">{missesDetected}</p>
                        <p className="text-[11px] text-slate-500 mt-1">Silent failures</p>
                      </div>
                    </div>

                    <p className="text-xs text-slate-500 leading-relaxed border-t border-surface-border pt-3">
                      <strong className="text-slate-400">Miss rate</strong> = claims Skeptic did{' '}
                      <em>not</em> challenge. <strong className="text-emerald-400/80">0%</strong> means Skeptic spoke up
                      on every bad claim. This is simpler than the Evaluation benchmark, which also checks challenge{' '}
                      <em>type</em>.
                    </p>

                    {latestAdversarial.attack_breakdown && (
                      <div className="space-y-2">
                        <p className="text-xs font-semibold uppercase tracking-wider text-slate-500">By attack type</p>
                        <div className="space-y-2">
                          {Object.entries(latestAdversarial.attack_breakdown).map(([key, stats]) => {
                            const ok = stats.detected === stats.total;
                            return (
                              <div
                                key={key}
                                className="flex items-center justify-between gap-3 p-2.5 rounded-lg bg-surface-raised border border-surface-border"
                              >
                                <div className="flex items-center gap-2 min-w-0">
                                  {ok ? (
                                    <CheckCircle2 size={14} className="text-emerald-400 shrink-0" />
                                  ) : (
                                    <XCircle size={14} className="text-rose-400 shrink-0" />
                                  )}
                                  <span className="text-sm text-slate-300 truncate">
                                    {ATTACK_LABELS[key] ?? key.replace(/_/g, ' ')}
                                  </span>
                                </div>
                                <span className="text-xs font-mono text-slate-500 shrink-0">
                                  {stats.detected}/{stats.total} caught
                                </span>
                              </div>
                            );
                          })}
                        </div>
                      </div>
                    )}
                  </div>
                ) : (
                  <EmptyState
                    icon={<Shield size={24} />}
                    title="No runs yet"
                    description='Click "Run Adversarial Eval" above to test whether Skeptic challenges tricky false claims.'
                  />
                )}
              </Card>

              {/* Attack types reference */}
              <Card>
                <h3 className="text-sm font-semibold text-slate-300 mb-1">Claim types we generate</h3>
                <p className="text-xs text-slate-500 mb-4">
                  Each run picks from these patterns. Skeptic should challenge all of them.
                </p>
                <div className="grid sm:grid-cols-2 gap-3">
                  {ADVERSARIAL_ATTACKS.map((t) => (
                    <div key={t.key} className={clsx('rounded-xl p-4 border', t.color)}>
                      <span className="text-xs font-bold uppercase tracking-wider text-slate-400">{t.label}</span>
                      <p className="text-xs text-slate-500 mt-1">{t.description}</p>
                      <p className="text-sm text-slate-300 mt-2 font-mono leading-relaxed">
                        &ldquo;{t.example}&rdquo;
                      </p>
                    </div>
                  ))}
                </div>
              </Card>

              {/* History chart */}
              {missRateChart.length > 1 && (
                <Card>
                  <h3 className="text-sm font-semibold text-slate-300 mb-1">Miss rate over time</h3>
                  <p className="text-xs text-slate-500 mb-4">Lower is better — tracks Skeptic silence across past runs.</p>
                  <ResponsiveContainer width="100%" height={220}>
                    <LineChart data={missRateChart}>
                      <CartesianGrid strokeDasharray="3 3" stroke="#2a3042" vertical={false} />
                      <XAxis dataKey="run" stroke="#64748b" fontSize={12} tickLine={false} axisLine={false} />
                      <YAxis stroke="#64748b" fontSize={12} domain={[0, 1]} tickLine={false} axisLine={false} tickFormatter={(v) => `${(v * 100).toFixed(0)}%`} />
                      <Tooltip
                        contentStyle={{ background: '#161922', border: '1px solid #2a3042', borderRadius: 12 }}
                        formatter={(v: number) => [`${(v * 100).toFixed(1)}%`, 'Miss rate']}
                        labelFormatter={(_, payload) => payload?.[0]?.payload?.date ?? ''}
                      />
                      <Line type="monotone" dataKey="miss" stroke="#f43f5e" strokeWidth={2.5} dot={{ fill: '#f43f5e', strokeWidth: 2, r: 4 }} activeDot={{ r: 6 }} />
                    </LineChart>
                  </ResponsiveContainer>
                </Card>
              )}
            </div>
          )}
        </main>
      </div>
    </div>
  );
}
