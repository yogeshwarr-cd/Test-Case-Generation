import { CheckCircle2, CircleAlert, CircleX, Clock3, MinusCircle } from 'lucide-react';
import { friendlyId } from '../utils';

type EntityKind = 'scenario' | 'case' | 'script' | 'workflow' | 'execution';

const labels: Record<EntityKind, string> = {
  scenario: 'Test Scenario ID',
  case: 'Test Case ID',
  script: 'Test Script ID',
  workflow: 'Workflow ID',
  execution: 'Execution ID',
};

const tones: Record<EntityKind, string> = {
  scenario: 'border-violet-500/20 bg-violet-500/5 text-violet-700 dark:text-violet-300',
  case: 'border-blue-500/20 bg-blue-500/5 text-blue-700 dark:text-blue-300',
  script: 'border-cyan-500/20 bg-cyan-500/5 text-cyan-700 dark:text-cyan-300',
  workflow: 'border-border bg-muted/50 text-foreground',
  execution: 'border-border bg-muted/50 text-foreground',
};

export function EntityId({ kind, value, compact = false }: { kind: EntityKind; value?: string | null; compact?: boolean }) {
  if (!value) return null;
  return (
    <span className={`inline-flex min-w-0 items-center gap-2 rounded-lg border px-2.5 py-1.5 ${tones[kind]}`} title={`${labels[kind]}: ${friendlyId(kind, value)}`}>
      <span className="shrink-0 text-[10px] font-bold uppercase tracking-wider opacity-70">{compact ? labels[kind].replace('Test ', '').replace(' ID', '') : labels[kind]}</span>
      <code className="truncate text-[11px] font-semibold">{friendlyId(kind, value)}</code>
    </span>
  );
}

export function TraceabilityChain({ scenarioId, testCaseId, scriptId, className = '' }: { scenarioId?: string | null; testCaseId?: string | null; scriptId?: string | null; className?: string }) {
  const items = [
    scenarioId ? <EntityId key="scenario" kind="scenario" value={scenarioId} compact /> : null,
    testCaseId ? <EntityId key="case" kind="case" value={testCaseId} compact /> : null,
    scriptId ? <EntityId key="script" kind="script" value={scriptId} compact /> : null,
  ].filter(Boolean);
  if (!items.length) return null;
  return <div className={`flex min-w-0 flex-wrap items-center gap-1.5 ${className}`}>{items.map((item, index) => <span key={index} className="contents">{index > 0 && <span className="text-xs font-bold text-muted-foreground" aria-hidden>→</span>}{item}</span>)}</div>;
}

export function StatusBadge({ status }: { status?: string | null }) {
  const normalized = (status || 'unknown').toLowerCase().replaceAll('_', ' ');
  const positive = ['passed', 'approved', 'completed', 'covered', 'valid', 'success'].some((value) => normalized.includes(value));
  const negative = ['failed', 'rejected', 'blocked', 'error', 'obsolete', 'missing'].some((value) => normalized.includes(value));
  const warning = ['warning', 'review', 'partial', 'skipped', 'incomplete', 'pending'].some((value) => normalized.includes(value));
  const Icon = positive ? CheckCircle2 : negative ? CircleX : warning ? Clock3 : normalized === 'unknown' ? MinusCircle : CircleAlert;
  const tone = positive ? 'border-green-500/20 bg-green-500/10 text-green-700 dark:text-green-300' : negative ? 'border-red-500/20 bg-red-500/10 text-red-700 dark:text-red-300' : warning ? 'border-amber-500/20 bg-amber-500/10 text-amber-700 dark:text-amber-300' : 'border-border bg-muted text-muted-foreground';
  return <span className={`inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-xs font-semibold capitalize ${tone}`}><Icon className="h-3.5 w-3.5" />{normalized}</span>;
}

function confidenceValue(value?: number | null) {
  const percent = Math.max(0, Math.min(100, Math.round((value ?? 0) <= 1 ? (value ?? 0) * 100 : (value ?? 0))));
  return percent;
}

export function ConfidenceRing({ value, threshold = 95, label = 'Confidence', size = 'md' }: { value?: number | null; threshold?: number; label?: string; size?: 'sm' | 'md' | 'lg' }) {
  const percent = confidenceValue(value);
  const required = confidenceValue(threshold);
  const passed = percent >= required;
  const dimensions = size === 'sm' ? 'h-20 w-20' : size === 'lg' ? 'h-36 w-36' : 'h-24 w-24';
  const scoreSize = size === 'lg' ? 'text-3xl' : size === 'sm' ? 'text-lg' : 'text-2xl';
  const color = passed ? '#22c55e' : percent >= 70 ? '#f59e0b' : '#ef4444';
  return (
    <div className="group inline-flex flex-col items-center gap-2" role="meter" aria-label={`${label}: ${percent}%`} aria-valuemin={0} aria-valuemax={100} aria-valuenow={percent} title={`${label}: ${percent}% · Required: ${required}%`}>
      <div className={`relative grid shrink-0 place-items-center rounded-full p-[7px] shadow-[0_12px_35px_rgba(2,6,23,.16)] transition-all duration-300 group-hover:-translate-y-1 group-hover:scale-105 group-hover:shadow-xl group-hover:shadow-primary/20 ${dimensions}`} style={{ background: `conic-gradient(${color} 0deg, ${percent >= 60 ? '#84cc16' : color} ${percent * 2.4}deg, ${percent >= 80 ? '#22c55e' : color} ${percent * 3.6}deg, color-mix(in srgb, var(--muted) 80%, transparent) ${percent * 3.6}deg 360deg)` }}>
        <div className="grid h-full w-full place-items-center rounded-full border border-white/20 bg-card/95 shadow-inner backdrop-blur-xl">
          <div className="text-center leading-none"><span className={`${scoreSize} font-black tracking-tight`} style={{ color }}>{percent}%</span><span className="mt-1 block text-[9px] font-bold uppercase tracking-[0.15em] text-muted-foreground">{passed ? 'Target met' : `${required}% required`}</span></div>
        </div>
      </div>
      <span className="text-[10px] font-bold uppercase tracking-[0.16em] text-muted-foreground">{label}</span>
    </div>
  );
}

export function ConfidenceBadge({ value, threshold = 95 }: { value?: number | null; threshold?: number }) {
  return <ConfidenceRing value={value} threshold={threshold} size="sm" />;
}
