'use client';

import clsx from 'clsx';
import { useEffect, useState } from 'react';
import {
  Shield, Swords, Gavel, ChevronDown, ChevronUp,
  ExternalLink, AlertTriangle, CheckCircle2, XCircle, HelpCircle,
} from 'lucide-react';
import { AgentReasoning, EvidenceCitedList } from '@/components/AgentReasoning';
import { isValidUrl } from '@/lib/formatAgentText';

const verdictConfig: Record<string, { style: string; icon: React.ReactNode; label: string }> = {
  supported: {
    style: 'bg-emerald-500/15 text-emerald-400 border-emerald-500/30',
    icon: <CheckCircle2 size={14} />,
    label: 'Supported',
  },
  refuted: {
    style: 'bg-rose-500/15 text-rose-400 border-rose-500/30',
    icon: <XCircle size={14} />,
    label: 'Refuted',
  },
  partially_supported: {
    style: 'bg-amber-500/15 text-amber-400 border-amber-500/30',
    icon: <AlertTriangle size={14} />,
    label: 'Partially Supported',
  },
  insufficient_evidence: {
    style: 'bg-slate-500/15 text-slate-400 border-slate-500/30',
    icon: <HelpCircle size={14} />,
    label: 'Insufficient Evidence',
  },
};

export function VerdictBadge({ verdict, size = 'md' }: { verdict: string; size?: 'sm' | 'md' | 'lg' }) {
  const cfg = verdictConfig[verdict] || verdictConfig.insufficient_evidence;
  return (
    <span
      className={clsx(
        'inline-flex items-center gap-1.5 rounded-full font-semibold border capitalize',
        cfg.style,
        size === 'sm' && 'px-2.5 py-0.5 text-xs',
        size === 'md' && 'px-3.5 py-1 text-sm',
        size === 'lg' && 'px-5 py-2 text-base'
      )}
    >
      {cfg.icon}
      {cfg.label}
    </span>
  );
}

export function ConfidenceBar({
  value,
  label,
  size = 'md',
}: {
  value: number;
  label?: string;
  size?: 'sm' | 'md' | 'lg';
}) {
  const pct = Math.round(value * 100);
  const color =
    value >= 0.8 ? 'from-emerald-500 to-emerald-400' :
    value >= 0.6 ? 'from-amber-500 to-amber-400' :
    'from-rose-500 to-rose-400';

  return (
    <div className={clsx('space-y-2', size === 'lg' && 'w-full')}>
      {label && (
        <div className="flex justify-between items-center">
          <span className="text-sm text-slate-400">{label}</span>
          <span className={clsx('font-bold tabular-nums', size === 'lg' ? 'text-2xl text-white' : 'text-sm text-slate-200')}>
            {pct}%
          </span>
        </div>
      )}
      <div className={clsx('bg-surface-overlay rounded-full overflow-hidden', size === 'lg' ? 'h-3' : 'h-2')}>
        <div
          className={clsx('h-full rounded-full bg-gradient-to-r transition-all duration-700 ease-out', color)}
          style={{ width: `${pct}%` }}
        />
      </div>
    </div>
  );
}

const agentThemes: Record<string, { border: string; header: string; icon: React.ReactNode; accent: string }> = {
  Advocate: {
    border: 'border-emerald-500/20',
    header: 'text-emerald-400',
    icon: <Shield size={18} />,
    accent: 'bg-emerald-500/10',
  },
  Skeptic: {
    border: 'border-rose-500/20',
    header: 'text-rose-400',
    icon: <Swords size={18} />,
    accent: 'bg-rose-500/10',
  },
  Judge: {
    border: 'border-brand-500/20',
    header: 'text-brand-400',
    icon: <Gavel size={18} />,
    accent: 'bg-brand-500/10',
  },
};

export function AgentPanel({
  title,
  agent,
  color,
  evidence = [],
}: {
  title: string;
  agent: import('@/types').AgentResponse;
  color: string;
  evidence?: import('@/types').Evidence[];
}) {
  const [expanded, setExpanded] = useState(true);
  const theme = agentThemes[title] || { border: color, header: 'text-slate-300', icon: null, accent: 'bg-surface-overlay' };
  const role = title.toLowerCase() as 'advocate' | 'skeptic' | 'judge';
  const citedIds = agent.evidence_used?.length ? agent.evidence_used : agent.sources;

  return (
    <div className={clsx('glass-card overflow-hidden animate-slide-up border', theme.border)}>
      <button
        type="button"
        onClick={() => setExpanded(!expanded)}
        className="w-full flex items-center justify-between p-5 hover:bg-surface-overlay/50 transition-colors"
      >
        <div className="flex items-center gap-3">
          <span className={clsx('p-2 rounded-lg', theme.accent, theme.header)}>{theme.icon}</span>
          <div className="text-left">
            <h3 className={clsx('font-semibold', theme.header)}>{title}</h3>
            <p className="text-xs text-slate-500 mt-0.5">
              {agent.latency_ms.toFixed(0)}ms · ${agent.cost_usd.toFixed(4)}
            </p>
          </div>
        </div>
        <div className="flex items-center gap-3">
          <span className="text-sm font-bold text-white tabular-nums">{(agent.confidence * 100).toFixed(0)}%</span>
          {expanded ? <ChevronUp size={16} className="text-slate-500" /> : <ChevronDown size={16} className="text-slate-500" />}
        </div>
      </button>

      {expanded && (
        <div className="px-5 pb-5 space-y-4 border-t border-surface-border pt-4 animate-fade-in">
          <ConfidenceBar value={agent.confidence} size="sm" />

          <AgentReasoning reasoning={agent.reasoning} evidence={evidence} role={role} />

          {citedIds && citedIds.length > 0 && (
            <EvidenceCitedList evidenceIds={citedIds} evidence={evidence} />
          )}

          {agent.challenges.length > 0 && (
            <div className="space-y-2">
              <h4 className="text-xs font-semibold text-slate-500 uppercase tracking-wider">Challenges</h4>
              {agent.challenges.map((c, i) => (
                <div key={i} className="bg-surface-overlay rounded-xl p-3 border border-amber-500/20">
                  <span className="inline-block text-xs font-semibold text-amber-400 bg-amber-500/10 px-2 py-0.5 rounded-md mb-2 capitalize">
                    {c.type.replace(/_/g, ' ')}
                  </span>
                  <p className="text-sm text-slate-300 leading-relaxed">{c.description}</p>
                </div>
              ))}
            </div>
          )}

          {agent.verdict && (
            <div className="pt-2 border-t border-surface-border">
              <p className="text-xs text-slate-500 mb-2 uppercase tracking-wider font-semibold">Ruling</p>
              <VerdictBadge verdict={agent.verdict} size="sm" />
            </div>
          )}
        </div>
      )}
    </div>
  );
}

export function EvidencePanel({ evidence }: { evidence: import('@/types').Evidence[] }) {
  const [expandedId, setExpandedId] = useState<string | null>(evidence[0]?.id ?? null);

  useEffect(() => {
    const onExpand = (e: Event) => {
      const id = (e as CustomEvent<{ id: string }>).detail?.id;
      if (id) setExpandedId(id);
    };
    window.addEventListener('fve:expand-evidence', onExpand);
    return () => window.removeEventListener('fve:expand-evidence', onExpand);
  }, []);

  if (!evidence.length) {
    return (
      <p className="text-slate-500 text-sm italic py-4 text-center">No evidence retrieved for this claim.</p>
    );
  }

  return (
    <div className="space-y-3">
      {evidence.map((ev, i) => {
        const isOpen = expandedId === ev.id;
        const credColor =
          ev.credibility >= 0.8 ? 'text-emerald-400' :
          ev.credibility >= 0.6 ? 'text-amber-400' : 'text-rose-400';
        const hasLink = isValidUrl(ev.source_url);

        return (
          <div
            key={ev.id}
            id={`evidence-${ev.id}`}
            className={clsx(
              'rounded-xl border transition-all duration-200 overflow-hidden scroll-mt-24',
              isOpen ? 'border-brand-500/30 bg-brand-500/5' : 'border-surface-border bg-surface-overlay hover:border-surface-border/80'
            )}
          >
            <div className="flex items-start justify-between p-4 gap-3">
              <div className="flex items-start gap-3 flex-1 min-w-0">
                <span className="flex items-center justify-center w-7 h-7 rounded-lg bg-brand-500/15 text-brand-400 text-xs font-bold shrink-0">
                  {i + 1}
                </span>
                <div className="min-w-0 flex-1">
                  <div className="flex items-center gap-2 flex-wrap">
                    {hasLink ? (
                      <a
                        href={ev.source_url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="text-sm font-medium text-brand-300 hover:text-brand-200 hover:underline inline-flex items-center gap-1.5"
                      >
                        {ev.source_title}
                        <ExternalLink size={12} className="shrink-0" />
                      </a>
                    ) : (
                      <span className="text-sm font-medium text-slate-200">{ev.source_title}</span>
                    )}
                  </div>
                  {!isOpen && (
                    <p className="text-xs text-slate-500 mt-1 line-clamp-2">{ev.content}</p>
                  )}
                </div>
              </div>
              <div className="flex items-center gap-2 shrink-0">
                <span className={clsx('text-xs font-semibold tabular-nums', credColor)} title="Source credibility">
                  Trust {(ev.credibility * 100).toFixed(0)}%
                </span>
                <button
                  type="button"
                  onClick={() => setExpandedId(isOpen ? null : ev.id)}
                  className="p-1 rounded-lg hover:bg-surface-border text-slate-500 transition-colors"
                  aria-label={isOpen ? 'Collapse' : 'Expand'}
                >
                  {isOpen ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
                </button>
              </div>
            </div>
            {isOpen && (
              <div className="px-4 pb-4 pl-14 animate-fade-in border-t border-surface-border/50 pt-3 mx-4 mb-1">
                <p className="text-sm text-slate-300 leading-relaxed">{ev.content}</p>
                <div className="flex flex-wrap items-center gap-3 mt-3">
                  {hasLink && (
                    <a
                      href={ev.source_url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="inline-flex items-center gap-1.5 text-xs font-medium text-brand-400 hover:text-brand-300 bg-brand-500/10 px-2.5 py-1 rounded-lg border border-brand-500/20"
                    >
                      <ExternalLink size={11} /> Open source
                    </a>
                  )}
                  {ev.rerank_score != null && (
                    <span className="text-xs text-slate-600">
                      Relevance: <span className="font-mono text-slate-500">{(ev.rerank_score * 100).toFixed(0)}%</span>
                    </span>
                  )}
                </div>
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}

export function KnowledgeGraphViz({ data }: { data: import('@/types').KnowledgeGraphResponse }) {
  if (!data.nodes.length) {
    return (
      <p className="text-slate-500 text-sm italic py-6 text-center">
        No graph data yet. Verify a claim to populate the knowledge graph.
      </p>
    );
  }

  return (
    <div className="space-y-6">
      <div>
        <h4 className="text-xs font-semibold text-slate-500 uppercase tracking-wider mb-3">Entities</h4>
        <div className="flex flex-wrap gap-2">
          {data.nodes.map((n) => (
            <div
              key={n.id}
              className="px-4 py-2 bg-brand-500/10 border border-brand-500/25 rounded-xl text-sm font-medium text-brand-300 hover:bg-brand-500/15 transition-colors"
            >
              {n.name}
              <span className="ml-2 text-xs text-brand-500/60">{n.type}</span>
            </div>
          ))}
        </div>
      </div>

      {data.edges.length > 0 && (
        <div>
          <h4 className="text-xs font-semibold text-slate-500 uppercase tracking-wider mb-3">Relationships</h4>
          <div className="space-y-2">
            {data.edges.map((e, i) => (
              <div
                key={i}
                className="flex flex-wrap items-center gap-2 text-sm bg-surface-overlay rounded-xl px-4 py-3 border border-surface-border"
              >
                <span className="font-medium text-slate-200">{e.source}</span>
                <span className="text-brand-400 font-mono text-xs px-2 py-0.5 bg-brand-500/10 rounded">
                  {e.relationship}
                </span>
                <span className="font-medium text-slate-200">{e.target}</span>
                <span className="ml-auto text-xs text-slate-500 tabular-nums">
                  {(e.confidence * 100).toFixed(0)}% conf
                </span>
                <span
                  className={clsx(
                    'text-xs px-2 py-0.5 rounded-full font-medium border',
                    e.status === 'unresolved'
                      ? 'bg-amber-500/15 text-amber-400 border-amber-500/30'
                      : 'bg-emerald-500/15 text-emerald-400 border-emerald-500/30'
                  )}
                >
                  {e.status}
                </span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

export function VerdictHero({
  verdict,
  confidence,
  requiresReview,
}: {
  verdict: string;
  confidence: number;
  requiresReview: boolean;
}) {
  return (
    <div className="glass-card p-6 md:p-8 animate-slide-up">
      <div className="flex flex-col md:flex-row md:items-center gap-6 md:gap-10">
        <div className="shrink-0">
          <p className="text-xs font-semibold text-slate-500 uppercase tracking-wider mb-2">Verdict</p>
          <VerdictBadge verdict={verdict} size="lg" />
        </div>
        <div className="flex-1 min-w-0">
          <ConfidenceBar value={confidence} label="Overall Confidence" size="lg" />
        </div>
        {requiresReview && (
          <div className="shrink-0 flex items-center gap-2 px-4 py-3 rounded-xl bg-amber-500/10 border border-amber-500/25 text-amber-300 text-sm">
            <AlertTriangle size={16} />
            <span className="font-medium">Needs human review</span>
          </div>
        )}
      </div>
    </div>
  );
}

export function AtomicClaimCard({
  subject,
  predicate,
  object: obj,
  confidence,
}: {
  subject: string;
  predicate: string;
  object: string;
  confidence: number;
}) {
  return (
    <div className="flex flex-wrap items-center gap-2 md:gap-3 bg-surface-overlay rounded-xl px-4 py-3 border border-surface-border text-sm animate-slide-up">
      <span className="font-semibold text-brand-300">{subject}</span>
      <span className="text-slate-600 font-mono text-xs px-2 py-0.5 bg-surface rounded">{predicate}</span>
      <span className="text-slate-200">{obj}</span>
      <span className="ml-auto text-xs font-bold tabular-nums text-slate-400">
        {(confidence * 100).toFixed(0)}%
      </span>
    </div>
  );
}
