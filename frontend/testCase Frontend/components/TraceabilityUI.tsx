import { CheckCircle2, CircleAlert, CircleX, Clock3, MinusCircle } from 'lucide-react';

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
    <span className={`inline-flex min-w-0 items-center gap-2 rounded-lg border px-2.5 py-1.5 ${tones[kind]}`} title={`${labels[kind]}: ${value}`}>
      <span className="shrink-0 text-[10px] font-bold uppercase tracking-wider opacity-70">{compact ? labels[kind].replace('Test ', '').replace(' ID', '') : labels[kind]}</span>
      <code className="truncate text-[11px] font-semibold">{value}</code>
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

export function ConfidenceBadge({ value }: { value?: number | null }) {
  const percent = Math.max(0, Math.min(100, Math.round((value ?? 0) <= 1 ? (value ?? 0) * 100 : (value ?? 0))));
  const tone = percent >= 95 ? 'text-green-700 dark:text-green-300' : percent >= 75 ? 'text-amber-700 dark:text-amber-300' : 'text-red-700 dark:text-red-300';
  return <span className={`inline-flex items-center gap-2 rounded-full border border-border bg-background px-2.5 py-1 text-xs font-semibold ${tone}`}><span className="h-1.5 w-12 overflow-hidden rounded-full bg-muted"><span className="block h-full rounded-full bg-current" style={{ width: `${percent}%` }} /></span>{percent}% confidence</span>;
}
