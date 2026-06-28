'use client';

import clsx from 'clsx';
import { BookOpen } from 'lucide-react';
import type { Evidence } from '@/types';
import {
  buildEvidenceIndex,
  parseReasoningBlocks,
  sanitizeAgentText,
} from '@/lib/formatAgentText';

/** Scroll to matching evidence card and briefly highlight it */
export function scrollToEvidence(evId: string) {
  window.dispatchEvent(new CustomEvent('fve:expand-evidence', { detail: { id: evId } }));
  // Allow React state update before scrolling
  window.requestAnimationFrame(() => {
    const el = document.getElementById(`evidence-${evId}`);
    if (!el) return;
    el.scrollIntoView({ behavior: 'smooth', block: 'center' });
    el.classList.add('ring-2', 'ring-brand-400', 'ring-offset-2', 'ring-offset-surface');
    window.setTimeout(() => {
      el.classList.remove('ring-2', 'ring-brand-400', 'ring-offset-2', 'ring-offset-surface');
    }, 2200);
  });
}

function CitationChip({ num, ev }: { num: number; ev: Evidence }) {
  return (
    <button
      type="button"
      onClick={(e) => {
        e.stopPropagation();
        scrollToEvidence(ev.id);
      }}
      aria-label={`View evidence ${num}: ${ev.source_title}`}
      title={ev.source_title}
      className="inline-flex items-center mx-0.5 px-1.5 py-0.5 rounded-md text-xs font-bold
        bg-brand-500/20 text-brand-300 border border-brand-500/30
        hover:bg-brand-500/35 hover:border-brand-400/50 hover:text-brand-200
        cursor-pointer transition-colors align-baseline"
    >
      [{num}]
    </button>
  );
}

function CitationText({ text, evidence }: { text: string; evidence: Evidence[] }) {
  const parts = text.split(/(\[(?:\d+|Evidence\s*#?\d+|Source\s*#?\d+)\])/gi);

  return (
    <span>
      {parts.map((part, i) => {
        const match = part.match(/^\[(?:(\d+)|(?:Evidence|Source)\s*#?(\d+))\]$/i);
        if (match) {
          const num = parseInt(match[1] || match[2], 10);
          const hit = evidence[num - 1];
          if (hit) {
            return <CitationChip key={i} num={num} ev={hit} />;
          }
          return (
            <span
              key={i}
              className="inline-flex items-center mx-0.5 px-1.5 py-0.5 rounded-md text-xs font-bold
                bg-surface-overlay text-slate-500 border border-surface-border align-baseline"
              title="Evidence not in retrieved set"
            >
              [{num}]
            </span>
          );
        }
        return <span key={i}>{part}</span>;
      })}
    </span>
  );
}

export function AgentReasoning({
  reasoning,
  evidence,
  role,
}: {
  reasoning: string;
  evidence: Evidence[];
  role: 'advocate' | 'skeptic' | 'judge';
}) {
  const cleaned = sanitizeAgentText(reasoning, evidence);
  const blocks = parseReasoningBlocks(cleaned);

  const roleAccent = {
    advocate: 'border-emerald-500/20 bg-emerald-500/5',
    skeptic: 'border-rose-500/20 bg-rose-500/5',
    judge: 'border-brand-500/20 bg-brand-500/5',
  }[role];

  return (
    <div className={clsx('rounded-xl border p-4 space-y-3', roleAccent)}>
      <p className="text-xs font-semibold text-slate-500 uppercase tracking-wider">Analysis</p>
      <div className="space-y-3">
        {blocks.map((block, i) =>
          block.type === 'list' ? (
            <ul key={i} className="space-y-2 pl-1">
              {block.items.map((item, j) => (
                <li key={j} className="flex gap-2 text-sm text-slate-300 leading-relaxed">
                  <span className="text-slate-600 shrink-0 mt-1">•</span>
                  <span>
                    <CitationText text={item} evidence={evidence} />
                  </span>
                </li>
              ))}
            </ul>
          ) : (
            <p key={i} className="text-sm text-slate-300 leading-relaxed">
              <CitationText text={block.text} evidence={evidence} />
            </p>
          )
        )}
      </div>
    </div>
  );
}

export function EvidenceCitedList({
  evidenceIds,
  evidence,
}: {
  evidenceIds: string[];
  evidence: Evidence[];
}) {
  const index = buildEvidenceIndex(evidence);
  const cited = evidenceIds
    .map((id) => index.get(id.toLowerCase()))
    .filter((x): x is { num: number; ev: Evidence } => Boolean(x));

  if (!cited.length) return null;

  return (
    <div className="space-y-2">
      <p className="text-xs font-semibold text-slate-500 uppercase tracking-wider flex items-center gap-1.5">
        <BookOpen size={12} /> Evidence cited
      </p>
      <div className="flex flex-wrap gap-2">
        {cited.map(({ num, ev }) => (
          <button
            key={ev.id}
            type="button"
            onClick={() => scrollToEvidence(ev.id)}
            className="inline-flex items-center gap-1.5 text-xs px-2.5 py-1 rounded-lg
              bg-surface-overlay border border-surface-border text-slate-400
              hover:border-brand-500/40 hover:bg-brand-500/10 hover:text-slate-300
              cursor-pointer transition-colors"
          >
            <span className="font-bold text-brand-400">[{num}]</span>
            <span className="text-slate-300 max-w-[160px] truncate">{ev.source_title}</span>
          </button>
        ))}
      </div>
    </div>
  );
}
