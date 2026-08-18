'use client';

import { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import { Check, ChevronDown, ChevronUp, Clipboard, Download, RefreshCw, X } from 'lucide-react';
import { StatePanel } from '../components/StatePanel';
import { Modal } from '@/components/common/Modal';
import { ConfidenceBadge, ConfidenceRing, EntityId, StatusBadge, TraceabilityChain } from '../components/TraceabilityUI';
import { testCaseApi } from '../services/testCaseApi';
import { useTestCaseWorkflowStore } from '../store/workflowStore';
import type { Scenario, TestCase, WorkflowResult } from '../types';
import { confidencePercent, downloadFile, friendlyError, friendlyId, registerFriendlyIds, setActiveProjectId, testCaseText } from '../utils';

type Tab = 'scenarios' | 'testCases' | 'validation' | 'traceability';

export function ResultsPage() {
  const router = useRouter();
  const { workflowId, result, hydrate, setResult, clear } = useTestCaseWorkflowStore();
  const [data, setData] = useState<WorkflowResult | null>(result);
  const [loading, setLoading] = useState(!result);
  const [error, setError] = useState('');
  const [tab, setTab] = useState<Tab>('scenarios');
  const [page, setPage] = useState(1);
  const [copied, setCopied] = useState('');
  const [regenerating, setRegenerating] = useState('');
  const [notice, setNotice] = useState('');
  const [regenerationTarget, setRegenerationTarget] = useState<{ kind: 'scenario' | 'testCase'; id: string; title: string } | null>(null);
  const [improvements, setImprovements] = useState('');
  const [regenerationError, setRegenerationError] = useState('');
  const [decisions, setDecisions] = useState<Record<string, 'approved' | 'rejected'>>({});
  const pageSize = 10;

  useEffect(() => hydrate(), [hydrate]);
  useEffect(() => {
    if (!workflowId || data) return;
    testCaseApi.getWorkflowResult(workflowId).then((response) => {
      setData(response);
      setResult(response);
    }).catch((requestError) => setError(friendlyError(requestError))).finally(() => setLoading(false));
  }, [data, setResult, workflowId]);
  const scenarios = data?.scenarios ?? [];
  const testCases = data?.test_cases ?? [];
  useEffect(() => {
    if (workflowId) {
      setActiveProjectId(workflowId);
    }
    registerFriendlyIds('scenario', scenarios.map((scenario) => scenario.scenario_id), workflowId);
    registerFriendlyIds('case', testCases.map((testCase) => testCase.test_case_id), workflowId);
    registerFriendlyIds('requirement', [...scenarios.flatMap((scenario) => scenario.requirement_ids ?? []), ...testCases.flatMap((testCase) => testCase.requirement_ids ?? [])], workflowId);
    registerFriendlyIds('userStory', scenarios.flatMap((scenario) => scenario.user_story_ids ?? []), workflowId);
    registerFriendlyIds('acceptanceCriteria', [...scenarios.flatMap((scenario) => scenario.acceptance_criteria_ids ?? []), ...testCases.flatMap((testCase) => testCase.acceptance_criteria_ids ?? [])], workflowId);
  }, [scenarios, testCases, workflowId]);
  const activeItems = tab === 'scenarios' ? scenarios : testCases;
  const pageCount = Math.max(1, Math.ceil(activeItems.length / pageSize));
  const visible = activeItems.slice((page - 1) * pageSize, page * pageSize);

  const copy = async (text: string, label: string) => {
    await navigator.clipboard.writeText(text);
    setCopied(label);
    window.setTimeout(() => setCopied(''), 1500);
  };
  const startAnother = () => {
    clear();
    router.push('/test-case-generation');
  };
  const regenerate = async () => {
    const feedback = improvements.trim();
    if (!regenerationTarget || feedback.length < 10) {
      setRegenerationError('Please provide at least 10 characters describing what should be improved.');
      return;
    }
    const { kind, id } = regenerationTarget;
    setRegenerating(id);
    setNotice('');
    setRegenerationError('');
    try {
      if (!activeWorkflowId) throw new Error('Workflow is unavailable.');
      const response = await testCaseApi.regenerateWorkflowItem(activeWorkflowId, kind, id, feedback);
      const nextData = data ? { ...data, ...response.result } : null;
      setData(nextData);
      setResult(nextData);
      setNotice(`${kind === 'scenario' ? 'Scenario' : 'Test case'} regenerated and revalidated successfully.`);
      setRegenerationTarget(null);
      setImprovements('');
    } catch (requestError) {
      setRegenerationError(friendlyError(requestError));
    } finally {
      setRegenerating('');
    }
  };
  const requestRegeneration = (kind: 'scenario' | 'testCase', id: string, title: string) => {
    setRegenerationTarget({ kind, id, title });
    setImprovements('');
    setRegenerationError('');
  };
  const closeRegeneration = () => {
    if (regenerating) return;
    setRegenerationTarget(null);
    setImprovements('');
    setRegenerationError('');
  };
  const decide = async (id: string, decision: 'approved' | 'rejected') => {
    if (!activeWorkflowId) return;
    try {
      await testCaseApi.saveDecision(activeWorkflowId, tab === 'scenarios' ? 'scenario' : 'testCase', id, decision);
      setDecisions((current) => ({ ...current, [id]: decision }));
      setNotice(`Item ${decision}.`);
    } catch (requestError) { setNotice(friendlyError(requestError)); }
  };
  const acceptAll = async () => {
    if (!activeWorkflowId) return;
    try {
      await testCaseApi.saveAllDecisions(activeWorkflowId, tab === 'scenarios' ? 'scenario' : 'testCase');
    const items = tab === 'scenarios' ? data?.scenarios ?? [] : data?.test_cases ?? [];
    setDecisions((current) => ({
      ...current,
      ...Object.fromEntries(items.map((item) => [
        'test_case_id' in item ? item.test_case_id : item.scenario_id,
        'approved' as const,
      ])),
    }));
    setPage(1);
    if (tab === 'scenarios') {
      setTab('testCases');
      setNotice('All scenarios accepted. Moved to Test Cases.');
    } else {
      setTab('validation');
      setNotice('All test cases accepted. Moved to the Validation Report.');
    }
    } catch (requestError) { setNotice(friendlyError(requestError)); }
  };

  const activeWorkflowId = workflowId;
  if (!activeWorkflowId) return <StatePanel type="error" title="No workflow result selected" message="Complete a workflow to view its results dashboard." />;
  if (loading) return <StatePanel type="loading" title="Loading results" message="Fetching generated scenarios, test cases, and validation data." />;
  if (error) return <StatePanel type="error" title="Results unavailable" message={error} />;
  if (!data || (!data.scenarios.length && !data.test_cases.length)) return <StatePanel type="empty" title="No generated results" message="The workflow completed without returning scenarios or test cases." />;

  return (
    <div className="space-y-6">
      <div className="flex flex-col justify-between gap-4 lg:flex-row lg:items-end">
        <div>
          <p className="text-xs font-bold uppercase tracking-[0.2em] text-green-500">Workflow completed</p>
          <h1 className="mt-2 text-2xl font-bold">Test Case Generation results</h1>
          <p className="mt-1 text-sm text-muted-foreground">{data.scenarios.length} scenarios · {data.test_cases.length} test cases</p>
          <p className="mt-1 text-sm text-muted-foreground">Review generated assets and their threshold-based validation results.</p>
        </div>
        <div className="flex flex-wrap gap-2">
          <button onClick={() => router.push('/test-case-generation/automation')} className="rounded-lg bg-green-600 px-4 py-2 text-sm font-semibold text-white hover:bg-green-700">Proceed to Test Scripts</button>
          <button onClick={() => downloadFile(`testcase-results-${activeWorkflowId}.json`, JSON.stringify(data, null, 2), 'application/json')} className="inline-flex items-center gap-2 rounded-lg border border-border px-4 py-2 text-sm font-semibold hover:bg-muted"><Download className="h-4 w-4" /> Export JSON</button>
          <button onClick={startAnother} className="rounded-lg bg-primary px-4 py-2 text-sm font-semibold text-primary-foreground">Start another generation</button>
        </div>
      </div>

      <div className="flex gap-1 overflow-x-auto rounded-xl border border-border bg-card p-1">
        {([['scenarios', 'Scenarios'], ['testCases', 'Test Cases'], ['validation', 'Validation Report'], ['traceability', 'Traceability']] as Array<[Tab, string]>).map(([key, label]) => (
          <button key={key} onClick={() => {
            setTab(key);
            setPage(1);
          }} className={`whitespace-nowrap rounded-lg px-4 py-2 text-sm font-semibold ${tab === key ? 'bg-primary text-primary-foreground' : 'text-muted-foreground hover:bg-muted hover:text-foreground'}`}>{label}</button>
        ))}
      </div>
      {notice && <div role="status" className="rounded-lg border border-primary/20 bg-primary/10 px-4 py-3 text-sm text-primary">{notice}</div>}
      {regenerationTarget && (
        <Modal isOpen onClose={closeRegeneration} title={`Regenerate ${regenerationTarget.kind === 'scenario' ? 'scenario' : 'test case'}`}>
          <form onSubmit={(event) => { event.preventDefault(); void regenerate(); }}>
            <p className="mt-1 text-sm text-muted-foreground">{regenerationTarget.title}</p>
            <label className="mt-5 block text-sm font-semibold" htmlFor="regeneration-improvements">What should be improved?</label>
            <textarea id="regeneration-improvements" autoFocus required minLength={10} disabled={Boolean(regenerating)} value={improvements} onChange={(event) => { setImprovements(event.target.value); setRegenerationError(''); }} placeholder="Example: Add boundary conditions, clearer expected results, and invalid input coverage." rows={5} aria-describedby="regeneration-help regeneration-error" aria-invalid={Boolean(regenerationError)} className="mt-2 w-full resize-y rounded-lg border border-input bg-background p-3 text-sm outline-none focus:border-primary focus:ring-2 focus:ring-primary/20 disabled:cursor-wait disabled:opacity-60" />
            <div className="mt-2 flex items-start justify-between gap-3 text-xs">
              <p id="regeneration-help" className="text-muted-foreground">The selected item will be completely regenerated and revalidated using this feedback.</p>
              <span className={improvements.trim().length < 10 ? 'text-muted-foreground' : 'text-green-600'}>{improvements.trim().length}/10 minimum</span>
            </div>
            {regenerationError && <p id="regeneration-error" role="alert" className="mt-3 rounded-lg border border-red-500/30 bg-red-500/10 p-3 text-sm text-red-600">{regenerationError}</p>}
            <div className="mt-5 flex justify-end gap-2">
              <button type="button" disabled={Boolean(regenerating)} onClick={closeRegeneration} className="rounded-lg border border-border px-4 py-2 text-sm font-semibold hover:bg-muted disabled:opacity-50">Cancel</button>
              <button type="submit" disabled={improvements.trim().length < 10 || Boolean(regenerating)} className="inline-flex items-center gap-2 rounded-lg bg-primary px-4 py-2 text-sm font-semibold text-primary-foreground disabled:cursor-not-allowed disabled:opacity-50"><RefreshCw className={`h-4 w-4 ${regenerating ? 'animate-spin' : ''}`} /> {regenerating ? 'Regenerating…' : 'Regenerate completely'}</button>
            </div>
          </form>
        </Modal>
      )}

      {(tab === 'scenarios' || tab === 'testCases') && (
        <>
          <div className="flex justify-end">
            <button onClick={acceptAll} className="inline-flex items-center gap-2 rounded-lg bg-green-600 px-4 py-2 text-sm font-semibold text-white hover:bg-green-700"><Check className="h-4 w-4" /> Accept all {tab === 'scenarios' ? 'scenarios' : 'test cases'}</button>
          </div>
          <section className="flex flex-wrap items-center justify-between gap-6 rounded-2xl border border-border bg-card p-5">
            <div><p className="text-sm font-semibold">Overall {tab === 'scenarios' ? 'scenario' : 'test-case'} confidence</p><p className="mt-1 text-xs text-muted-foreground">Calculated across all generated {tab === 'scenarios' ? 'scenarios' : 'test cases'}.</p></div>
            <ConfidenceRing value={tab === 'scenarios' ? data.scenario_validation?.confidence_score : data.testcase_validation?.confidence_score} threshold={data.confidence_threshold ?? .95} label={tab === 'scenarios' ? 'Scenario confidence' : 'Test-case confidence'} size="lg" />
          </section>
          <div className="flex items-center justify-between text-sm text-muted-foreground">
            <span>{activeItems.length} result{activeItems.length === 1 ? '' : 's'}</span>
            <button onClick={() => copy(tab === 'scenarios' ? JSON.stringify(visible, null, 2) : (visible as TestCase[]).map(testCaseText).join('\n\n---\n\n'), 'all')} className="inline-flex items-center gap-2 font-semibold text-primary hover:underline">
              {copied === 'all' ? <Check className="h-4 w-4" /> : <Clipboard className="h-4 w-4" />} Copy visible results
            </button>
          </div>
          <div className="space-y-3">
            {!visible.length ? <StatePanel type="empty" title="No generated results" message="No generated items are available in this section." /> :
              tab === 'scenarios'
                ? (visible as Scenario[]).map((scenario, index) => <div key={`${scenario.scenario_id}-${index}`} className={`rounded-xl ${decisions[scenario.scenario_id] === 'approved' ? 'ring-2 ring-green-500/50' : decisions[scenario.scenario_id] === 'rejected' ? 'ring-2 ring-red-500/50' : ''}`}><DecisionButtons id={scenario.scenario_id} title={scenario.title} decision={decisions[scenario.scenario_id]} decide={decide} /><ScenarioCard scenario={scenario} confidence={itemConfidence(scenario, data.scenario_validation?.entity_scores, data.scenario_validation?.confidence_score)} regenerating={regenerating === scenario.scenario_id} requestRegeneration={requestRegeneration} /></div>)
                : (visible as TestCase[]).map((testCase, index) => <div key={`${testCase.test_case_id}-${index}`} className={`rounded-xl ${decisions[testCase.test_case_id] === 'approved' ? 'ring-2 ring-green-500/50' : decisions[testCase.test_case_id] === 'rejected' ? 'ring-2 ring-red-500/50' : ''}`}><DecisionButtons id={testCase.test_case_id} title={testCase.title} decision={decisions[testCase.test_case_id]} decide={decide} /><TestCaseCard testCase={testCase} confidence={itemConfidence(testCase, data.testcase_validation?.entity_scores, data.testcase_validation?.confidence_score)} regenerating={regenerating === testCase.test_case_id} requestRegeneration={requestRegeneration} copied={copied} copy={copy} /></div>)}
          </div>
          {pageCount > 1 && <div className="flex items-center justify-center gap-3"><button disabled={page === 1} onClick={() => setPage((value) => value - 1)} className="rounded-lg border border-border px-3 py-2 text-sm disabled:opacity-40">Previous</button><span className="text-sm text-muted-foreground">Page {page} of {pageCount}</span><button disabled={page === pageCount} onClick={() => setPage((value) => value + 1)} className="rounded-lg border border-border px-3 py-2 text-sm disabled:opacity-40">Next</button></div>}
        </>
      )}

      {tab === 'validation' && <ValidationView data={data} />}
      {tab === 'traceability' && <TraceabilityView data={data} />}
    </div>
  );
}

function DecisionButtons({ id, title, decision, decide }: { id: string; title: string; decision?: 'approved' | 'rejected'; decide: (id: string, decision: 'approved' | 'rejected') => void }) {
  return <div className="flex justify-end gap-2 rounded-t-xl border border-b-0 border-border bg-card px-4 pt-3"><button onClick={() => decide(id, 'approved')} className={`rounded-lg border p-2 ${decision === 'approved' ? 'border-green-600 bg-green-600 text-white' : 'border-border hover:bg-green-500/10 hover:text-green-600'}`} aria-label={`Accept ${title}`} title="Accept"><Check className="h-4 w-4" /></button><button onClick={() => decide(id, 'rejected')} className={`rounded-lg border p-2 ${decision === 'rejected' ? 'border-red-600 bg-red-600 text-white' : 'border-border hover:bg-red-500/10 hover:text-red-600'}`} aria-label={`Reject ${title}`} title="Reject"><X className="h-4 w-4" /></button></div>;
}

function ScenarioCard({ scenario, confidence, regenerating, requestRegeneration }: { scenario: Scenario; confidence: number; regenerating: boolean; requestRegeneration: (kind: 'scenario' | 'testCase', id: string, title: string) => void }) {
  return <article className="rounded-xl border border-border/80 bg-card p-5 shadow-sm transition-all duration-200 hover:-translate-y-0.5 hover:border-primary/25 hover:shadow-md"><div className="flex flex-wrap items-start justify-between gap-4"><div className="min-w-0 space-y-2"><EntityId kind="scenario" value={scenario.scenario_id} /><h2 className="text-base font-semibold leading-snug">{scenario.title}</h2></div><div className="flex flex-wrap items-center justify-end gap-3"><ConfidenceBadge value={confidence} />{scenario.validation_status && <StatusBadge status={scenario.validation_status} />}<Pills values={[scenario.priority, scenario.scenario_type]} /><button disabled={regenerating} onClick={() => requestRegeneration('scenario', scenario.scenario_id, scenario.title)} className="rounded-lg border border-border bg-background p-2 shadow-sm transition hover:bg-muted hover:text-primary disabled:cursor-not-allowed disabled:opacity-50" aria-label={`Regenerate ${scenario.title}`} title="Regenerate scenario"><RefreshCw className={`h-4 w-4 ${regenerating ? 'animate-spin' : ''}`} /></button></div></div><p className="mt-4 text-sm leading-6 text-muted-foreground">{scenario.description}</p><div className="mt-5 grid gap-3 rounded-xl border border-border/60 bg-muted/20 p-4 text-sm sm:grid-cols-2"><Info label="Related requirements" value={scenario.requirement_ids?.join(', ')} /><Info label="Related user stories" value={scenario.user_story_ids?.join(', ')} /><Info label="Preconditions" value={scenario.preconditions?.join('; ')} /><Info label="Expected outcome" value={scenario.expected_business_outcome} /></div></article>;
}

function TestCaseCard({ testCase, confidence, regenerating, requestRegeneration, copied, copy }: { testCase: TestCase; confidence: number; regenerating: boolean; requestRegeneration: (kind: 'scenario' | 'testCase', id: string, title: string) => void; copied: string; copy: (text: string, label: string) => Promise<void> }) {
  const [open, setOpen] = useState(false);
  return <article className="overflow-hidden rounded-xl border border-border/80 bg-card shadow-sm transition-all duration-200 hover:border-primary/25 hover:shadow-md"><div className="flex items-start gap-3 p-5"><button onClick={() => setOpen((value) => !value)} aria-label={`${open ? 'Collapse' : 'Expand'} ${testCase.title}`} className="mt-1 rounded-lg border border-transparent p-1.5 transition hover:border-border hover:bg-muted">{open ? <ChevronUp className="h-4 w-4" /> : <ChevronDown className="h-4 w-4" />}</button><div className="min-w-0 flex-1"><TraceabilityChain scenarioId={testCase.scenario_id} testCaseId={testCase.test_case_id} /><h2 className="mt-3 font-semibold">{testCase.title}</h2><p className="mt-2 text-sm leading-6 text-muted-foreground">{testCase.description}</p><div className="mt-3 flex flex-wrap items-center gap-2"><ConfidenceBadge value={confidence} />{testCase.validation_status && <StatusBadge status={testCase.validation_status} />}<Pills values={[testCase.priority, testCase.test_case_type, testCase.automation_candidate ? 'Automation candidate' : undefined]} /></div></div><div className="flex gap-2"><button disabled={regenerating} onClick={() => requestRegeneration('testCase', testCase.test_case_id, testCase.title)} className="rounded-lg border border-border bg-background p-2 shadow-sm transition hover:bg-muted hover:text-primary disabled:cursor-not-allowed disabled:opacity-50" aria-label={`Regenerate ${testCase.title}`} title="Regenerate test case"><RefreshCw className={`h-4 w-4 ${regenerating ? 'animate-spin' : ''}`} /></button><button onClick={() => copy(testCaseText(testCase), testCase.test_case_id)} className="rounded-lg border border-border bg-background p-2 shadow-sm transition hover:bg-muted hover:text-primary" aria-label={`Copy ${testCase.title}`}>{copied === testCase.test_case_id ? <Check className="h-4 w-4 text-green-500" /> : <Clipboard className="h-4 w-4" />}</button></div></div>{open && <div className="space-y-5 border-t border-border bg-muted/10 p-5"><Info label="Preconditions" value={testCase.preconditions?.join('; ')} /><div><h3 className="text-sm font-semibold">Test steps</h3><ol className="mt-3 space-y-3">{testCase.steps?.map((step, index) => <li key={`${step.step_number}-${index}`} className="grid gap-3 rounded-xl border border-border/60 bg-background p-4 text-sm sm:grid-cols-[2rem_1fr_1fr]"><span className="flex h-7 w-7 items-center justify-center rounded-full bg-primary/10 font-bold text-primary">{step.step_number}</span><div><p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">Action</p><p className="mt-1">{step.action}</p></div><div><p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">Expected result</p><p className="mt-1">{step.expected_result}</p></div></li>)}</ol></div><div className="grid gap-3 sm:grid-cols-2"><Info label="Requirement mapping" value={testCase.requirement_ids?.join(', ')} /><Info label="Acceptance criteria" value={testCase.acceptance_criteria_ids?.join(', ')} /><Info label="Test data" value={JSON.stringify(testCase.test_data ?? {})} /><Info label="Confidence" value={`${confidence}%`} /></div></div>}</article>;
}

function ValidationView({ data }: { data: WorkflowResult }) {
  const validations = [['Scenario validation', data.scenario_validation], ['Test-case validation', data.testcase_validation]] as const;
  return <div className="grid gap-6 lg:grid-cols-2">{validations.map(([label, validation]) => <section key={label} className="rounded-2xl border border-border bg-card p-5 sm:p-6"><div className="flex items-start justify-between gap-4"><h2 className="font-semibold">{label}</h2><ConfidenceRing value={validation?.confidence_score} threshold={data.confidence_threshold ?? .95} label={label} /></div><div className="mt-5 grid gap-3 sm:grid-cols-2">{Object.entries(validation?.score_breakdown ?? {}).map(([key, value]) => <MetricBar key={key} label={key.replaceAll('_', ' ')} value={confidencePercent(value)} />)}</div><h3 className="mt-6 text-sm font-semibold">Validation issues</h3><div className="mt-3 space-y-2">{validation?.issues?.length ? validation.issues.map((issue, index) => <div key={index} className="rounded-lg border border-border p-3 text-sm"><p className="font-medium">{issue.description}</p>{issue.recommendation && <p className="mt-1 text-xs text-muted-foreground">{issue.recommendation}</p>}</div>) : <p className="text-sm text-muted-foreground">No validation issues reported.</p>}</div><p className="mt-5 text-sm"><span className="text-muted-foreground">Final approval status:</span> <span className="font-semibold capitalize">{validation?.status ?? 'Not provided'}</span></p></section>)}</div>;
}

function TraceabilityView({ data }: { data: WorkflowResult }) {
  const rows = data.test_cases.map((testCase) => {
    const sourceScenario = data.scenarios.find((scenario) => scenario.scenario_id === testCase.scenario_id);
    return {
      testCase,
      scenario: sourceScenario && {
        ...sourceScenario,
        user_story_ids: sourceScenario.user_story_ids?.map((id) => friendlyId('userStory', id)),
      },
    };
  });
  return <section className="overflow-hidden rounded-2xl border border-border/80 bg-card shadow-sm"><div className="border-b border-border p-5"><h2 className="font-semibold">User Story → Test Scenario ID → Test Case ID</h2><p className="mt-1 text-sm text-muted-foreground">Every row preserves the identifiers returned by the generation workflow.</p></div><div className="overflow-x-auto"><table className="w-full min-w-[1000px] text-left text-sm"><thead className="bg-muted/60 text-xs uppercase tracking-wide text-muted-foreground"><tr><th className="p-4">User story</th><th className="p-4">Traceability chain</th><th className="p-4">Generated asset</th></tr></thead><tbody>{rows.map(({ testCase, scenario }, index) => <tr key={`${testCase.test_case_id}-${index}`} className="border-t border-border transition-colors hover:bg-muted/30"><td className="p-4">{scenario?.user_story_ids?.join(', ') || 'Unmapped'}</td><td className="p-4"><TraceabilityChain scenarioId={testCase.scenario_id} testCaseId={testCase.test_case_id} /></td><td className="p-4"><p className="font-medium">{testCase.title}</p><p className="mt-1 text-xs text-muted-foreground">{scenario?.title || 'Scenario record unavailable'}</p></td></tr>)}</tbody></table></div></section>;
}

function itemConfidence(item: Scenario | TestCase, entityScores?: Record<string, number>, fallback?: number): number {
  const id = 'test_case_id' in item ? item.test_case_id : item.scenario_id;
  return confidencePercent(item.confidence_score ?? entityScores?.[id] ?? fallback);
}

function Pills({ values }: { values: Array<string | undefined> }) { return <div className="flex flex-wrap gap-2">{values.filter(Boolean).map((value) => <span key={value} className="rounded-full bg-muted px-2.5 py-1 text-xs font-medium capitalize">{value?.replaceAll('_', ' ')}</span>)}</div>; }
function Info({ label, value }: { label: string; value?: string }) {
  const kind = label === 'Related requirements' || label === 'Requirement mapping'
    ? 'requirement'
    : label === 'Related user stories'
      ? 'userStory'
      : label === 'Acceptance criteria'
        ? 'acceptanceCriteria'
        : null;
  const displayValue = kind && value ? value.split(', ').map((id) => friendlyId(kind, id)).join(', ') : value;
  return <div><p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">{label}</p><p className="mt-1 break-words">{displayValue || 'Not provided'}</p></div>;
}
function MetricBar({ label, value }: { label: string; value: number }) { return <div className="rounded-lg bg-muted/60 p-3"><div className="flex justify-between text-xs"><span className="capitalize">{label}</span><span>{value}%</span></div><div className="mt-2 h-1.5 rounded-full bg-background"><div className="h-full rounded-full bg-primary" style={{ width: `${value}%` }} /></div></div>; }
