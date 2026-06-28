'use client';

import clsx from 'clsx';
import type { ReactNode } from 'react';
import { Loader2 } from 'lucide-react';

export function PageHeader({
  title,
  description,
  action,
}: {
  title: string;
  description?: string;
  action?: ReactNode;
}) {
  return (
    <div className="flex flex-col sm:flex-row sm:items-start sm:justify-between gap-4 mb-8">
      <div>
        <h2 className="section-title">{title}</h2>
        {description && <p className="section-desc mt-1.5 max-w-2xl">{description}</p>}
      </div>
      {action && <div className="shrink-0">{action}</div>}
    </div>
  );
}

export function Card({
  children,
  className,
  hover,
  style,
}: {
  children: ReactNode;
  className?: string;
  hover?: boolean;
  style?: React.CSSProperties;
}) {
  return (
    <div className={clsx(hover ? 'glass-card-hover' : 'glass-card', 'p-6', className)} style={style}>
      {children}
    </div>
  );
}

export function StatCard({
  label,
  value,
  icon,
  accent = 'brand',
  delay = 0,
}: {
  label: string;
  value: string | number;
  icon?: ReactNode;
  accent?: 'brand' | 'emerald' | 'amber' | 'rose' | 'slate';
  delay?: number;
}) {
  const accents = {
    brand: 'text-brand-400 bg-brand-500/10 border-brand-500/20',
    emerald: 'text-emerald-400 bg-emerald-500/10 border-emerald-500/20',
    amber: 'text-amber-400 bg-amber-500/10 border-amber-500/20',
    rose: 'text-rose-400 bg-rose-500/10 border-rose-500/20',
    slate: 'text-slate-400 bg-slate-500/10 border-slate-500/20',
  };

  return (
    <div className="stat-card" style={{ animationDelay: `${delay}ms` }}>
      <div className="flex items-center justify-between">
        <span className="text-xs font-medium text-slate-500 uppercase tracking-wider">{label}</span>
        {icon && (
          <span className={clsx('p-2 rounded-lg border', accents[accent])}>{icon}</span>
        )}
      </div>
      <div className="text-3xl font-bold text-white tabular-nums">{value}</div>
    </div>
  );
}

export function EmptyState({
  icon,
  title,
  description,
  action,
}: {
  icon: ReactNode;
  title: string;
  description: string;
  action?: ReactNode;
}) {
  return (
    <div className="flex flex-col items-center justify-center py-16 px-6 text-center animate-fade-in">
      <div className="p-4 rounded-2xl bg-surface-overlay border border-surface-border text-slate-500 mb-4">
        {icon}
      </div>
      <h3 className="text-base font-semibold text-slate-300">{title}</h3>
      <p className="text-sm text-slate-500 mt-2 max-w-sm">{description}</p>
      {action && <div className="mt-6">{action}</div>}
    </div>
  );
}

export function AlertBanner({
  type = 'info',
  children,
}: {
  type?: 'info' | 'warning' | 'error' | 'success';
  children: ReactNode;
}) {
  const styles = {
    info: 'bg-brand-500/10 border-brand-500/25 text-brand-300',
    warning: 'bg-amber-500/10 border-amber-500/25 text-amber-300',
    error: 'bg-rose-500/10 border-rose-500/25 text-rose-300',
    success: 'bg-emerald-500/10 border-emerald-500/25 text-emerald-300',
  };

  return (
    <div className={clsx('flex items-center gap-3 px-4 py-3 rounded-xl border text-sm animate-slide-up', styles[type])}>
      {children}
    </div>
  );
}

export function StepProgress({ steps, activeIndex }: { steps: string[]; activeIndex: number }) {
  return (
    <div className="flex flex-col gap-2 mt-5">
      {steps.map((step, i) => {
        const done = i < activeIndex;
        const active = i === activeIndex;
        return (
          <div key={step} className="flex items-center gap-3">
            <div
              className={clsx(
                'w-6 h-6 rounded-full flex items-center justify-center text-xs font-bold shrink-0 transition-all',
                done && 'bg-emerald-500/20 text-emerald-400 border border-emerald-500/40',
                active && 'bg-brand-500/20 text-brand-400 border border-brand-500/40 animate-pulse-soft',
                !done && !active && 'bg-surface-overlay text-slate-600 border border-surface-border'
              )}
            >
              {done ? '✓' : i + 1}
            </div>
            <span
              className={clsx(
                'text-sm transition-colors',
                active ? 'text-brand-300 font-medium' : done ? 'text-slate-400' : 'text-slate-600'
              )}
            >
              {step}
            </span>
          </div>
        );
      })}
    </div>
  );
}

export function LoadingButton({
  loading,
  children,
  className,
  ...props
}: React.ButtonHTMLAttributes<HTMLButtonElement> & { loading?: boolean }) {
  return (
    <button className={clsx('btn-primary', className)} disabled={loading || props.disabled} {...props}>
      {loading && <Loader2 size={16} className="animate-spin" />}
      {children}
    </button>
  );
}

export function TabBadge({ count }: { count: number }) {
  if (count <= 0) return null;
  return (
    <span className="ml-auto min-w-[20px] h-5 px-1.5 flex items-center justify-center rounded-full bg-rose-500/20 text-rose-400 text-xs font-bold border border-rose-500/30">
      {count}
    </span>
  );
}
