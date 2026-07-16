'use client';

import { useEffect, useMemo, useState } from 'react';
import { useRouter } from 'next/navigation';
import { Check, ChevronDown, ChevronUp, Clipboard, Download, FilterX, Search } from 'lucide-react';
import { StatePanel } from '../components/StatePanel';
import { testCaseApi } from '../services/testCaseApi';
import { useTestCaseWorkflowStore } from '../store/workflowStore';
import type { ResultFilters, Scenario, TestCase, WorkflowResult } from '../types';
import { confidencePercent, downloadFile, friendlyError, testCaseText } from '../utils';

type Tab = 'scenarios' | 'testCases' | 'validation' | 'traceability';
const EMPTY_FILTERS: ResultFilters = { search: '', priority: '', testType: '', validationStatus: '', requirement: '', minConfidence: 0 };

export function ResultsPage() {
  const router = useRouter();
  const { workflowId, result, hydrate, setResult, clear } = useTestCaseWorkflowStore();
  const [data, setData] = useState<WorkflowResult | null>(result);
  const [loading, setLoading] = useState(!result);
  const [error, setError] = useState('');
  const [tab, setTab] = useState<Tab>('scenarios');
  const [filters, setFilters] = useState<ResultFilters>(EMPTY_FILTERS);
  const [sort, setSort] = useState<'title' | 'priority' | 'confidence'>('title');
  const [page, setPage] = useState(1);
  const [copied, setCopied] = useState('');
  const pageSize = 10;

  useEffect(() => hydrate(), [hydrate]);
  useEffect(() => {
    if (!workflowId || data) return;
    testCaseApi.getWorkflowResult(workflowId).then((response) => {
      setData(response);
      setResult(response);
    }).catch((requestError) => setError(friendlyError(requestError))).finally(() => setLoading(false));
  }, [data, setResult, workflowId]);

  const scenarios = useMemo(() => filterAndSort(data?.scenarios ?? [], filters, sort), [data, filters, sort]);
  const testCases = useMemo(() => filterAndSort(data?.test_cases ?? [], filters, sort), [data, filters, sort]);
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

  if (!workflowId) return <StatePanel type="error" title="No workflow result selected" message="Complete a workflow to view its results dashboard." />;
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
        </div>
        <div className="flex flex-wrap gap-2">
          <button onClick={() => downloadFile(`testcase-results-${workflowId}.json`, JSON.stringify(data, null, 2), 'application/json')} className="inline-flex items-center gap-2 rounded-lg border border-border px-4 py-2 text-sm font-semibold hover:bg-muted"><Download className="h-4 w-4" /> Export JSON</button>
          <button onClick={startAnother} className="rounded-lg bg-primary px-4 py-2 text-sm font-semibold text-primary-foreground">Start another generation</button>
        </div>
      </div>

      <div className="flex gap-1 overflow-x-auto rounded-xl border border-border bg-card p-1">
        {([['scenarios', 'Scenarios'], ['testCases', 'Test Cases'], ['validation', 'Validation Report'], ['traceability', 'Traceability']] as Array<[Tab, string]>).map(([key, label]) => (
          <button key={key} onClick={() => { setTab(key); setPage(1); }} className={`whitespace-nowrap rounded-lg px-4 py-2 text-sm font-semibold ${tab === key ? 'bg-primary text-primary-foreground' : 'text-muted-foreground hover:bg-muted hover:text-foreground'}`}>{label}</button>
        ))}
      </div>

      {(tab === 'scenarios' || tab === 'testCases') && (
        <>
          <FilterBar filters={filters} setFilters={(next) => { setFilters(next); setPage(1); }} sort={sort} setSort={setSort} items={tab === 'scenarios' ? data.scenarios : data.test_cases} />
          <div className="flex items-center justify-between text-sm text-muted-foreground">
            <span>{activeItems.length} result{activeItems.length === 1 ? '' : 's'}</span>
            <button onClick={() => copy(tab === 'scenarios' ? JSON.stringify(visible, null, 2) : (visible as TestCase[]).map(testCaseText).join('\n\n---\n\n'), 'all')} className="inline-flex items-center gap-2 font-semibold text-primary hover:underline">
              {copied === 'all' ? <Check className="h-4 w-4" /> : <Clipboard className="h-4 w-4" />} Copy visible results
            </button>
          </div>
          <div className="space-y-3">
            {!visible.length ? <StatePanel type="empty" title="No matching results" message="Clear or adjust the filters to see generated items." /> :
              tab === 'scenarios'
                ? (visible as Scenario[]).map((scenario) => <ScenarioCard key={scenario.scenario_id} scenario={scenario} />)
                : (visible as TestCase[]).map((testCase) => <TestCaseCard key={testCase.test_case_id} testCase={testCase} copied={copied} copy={copy} />)}
          </div>
          {pageCount > 1 && <div className="flex items-center justify-center gap-3"><button disabled={page === 1} onClick={() => setPage((value) => value - 1)} className="rounded-lg border border-border px-3 py-2 text-sm disabled:opacity-40">Previous</button><span className="text-sm text-muted-foreground">Page {page} of {pageCount}</span><button disabled={page === pageCount} onClick={() => setPage((value) => value + 1)} className="rounded-lg border border-border px-3 py-2 text-sm disabled:opacity-40">Next</button></div>}
        </>
      )}

      {tab === 'validation' && <ValidationView data={data} />}
      {tab === 'traceability' && <TraceabilityView data={data} />}
    </div>
  );
}

function FilterBar({ filters, setFilters, sort, setSort, items }: { filters: ResultFilters; setFilters: (filters: ResultFilters) => void; sort: 'title' | 'priority' | 'confidence'; setSort: (sort: 'title' | 'priority' | 'confidence') => void; items: Array<Scenario | TestCase> }) {
  const priorities = unique(items.map((item) => item.priority));
  const types = unique(items.map((item) => 'test_case_id' in item ? item.test_case_type : item.scenario_type));
  const statuses = unique(items.map((item) => item.validation_status));
  return (
    <section className="grid gap-3 rounded-2xl border border-border bg-card p-4 sm:grid-cols-2 lg:grid-cols-6">
      <label className="relative sm:col-span-2"><Search className="absolute left-3 top-3 h-4 w-4 text-muted-foreground" /><input aria-label="Search results" value={filters.search} onChange={(event) => setFilters({ ...filters, search: event.target.value })} placeholder="Search title, description, ID…" className="h-10 w-full rounded-lg border border-input bg-background pl-9 pr-3 text-sm outline-none focus:border-primary" /></label>
      <Select label="Priority" value={filters.priority} options={priorities} onChange={(value) => setFilters({ ...filters, priority: value })} />
      <Select label="Type" value={filters.testType} options={types} onChange={(value) => setFilters({ ...filters, testType: value })} />
      <Select label="Validation" value={filters.validationStatus} options={statuses} onChange={(value) => setFilters({ ...filters, validationStatus: value })} />
      <select aria-label="Sort results" value={sort} onChange={(event) => setSort(event.target.value as typeof sort)} className="h-10 rounded-lg border border-input bg-background px-3 text-sm"><option value="title">Sort: Title</option><option value="priority">Sort: Priority</option><option value="confidence">Sort: Confidence</option></select>
      <input aria-label="Filter by requirement" value={filters.requirement} onChange={(event) => setFilters({ ...filters, requirement: event.target.value })} placeholder="Requirement ID" className="h-10 rounded-lg border border-input bg-background px-3 text-sm outline-none focus:border-primary" />
      <label className="flex items-center gap-3 rounded-lg border border-input px-3 text-xs text-muted-foreground">Confidence ≥ {filters.minConfidence}%<input type="range" min="0" max="100" step="10" value={filters.minConfidence} onChange={(event) => setFilters({ ...filters, minConfidence: Number(event.target.value) })} className="min-w-0 flex-1" /></label>
      <button onClick={() => setFilters(EMPTY_FILTERS)} className="inline-flex h-10 items-center justify-center gap-2 rounded-lg border border-border text-sm font-semibold hover:bg-muted"><FilterX className="h-4 w-4" /> Clear filters</button>
    </section>
  );
}

function Select({ label, value, options, onChange }: { label: string; value: string; options: string[]; onChange: (value: string) => void }) {
  return <select aria-label={`Filter by ${label}`} value={value} onChange={(event) => onChange(event.target.value)} className="h-10 rounded-lg border border-input bg-background px-3 text-sm"><option value="">{label}: All</option>{options.map((option) => <option key={option} value={option}>{option}</option>)}</select>;
}

function ScenarioCard({ scenario }: { scenario: Scenario }) {
  return <article className="rounded-xl border border-border bg-card p-5"><div className="flex flex-wrap items-start justify-between gap-3"><div><p className="text-xs font-semibold text-primary">{scenario.scenario_id}</p><h2 className="mt-1 font-semibold">{scenario.title}</h2></div><Pills values={[scenario.priority, scenario.scenario_type, scenario.validation_status]} /></div><p className="mt-3 text-sm text-muted-foreground">{scenario.description}</p><div className="mt-4 grid gap-3 text-sm sm:grid-cols-2"><Info label="Requirements" value={scenario.requirement_ids?.join(', ')} /><Info label="User stories" value={scenario.user_story_ids?.join(', ')} /><Info label="Preconditions" value={scenario.preconditions?.join('; ')} /><Info label="Expected coverage" value={scenario.expected_business_outcome} /></div></article>;
}

function TestCaseCard({ testCase, copied, copy }: { testCase: TestCase; copied: string; copy: (text: string, label: string) => Promise<void> }) {
  const [open, setOpen] = useState(false);
  return <article className="rounded-xl border border-border bg-card"><div className="flex items-start gap-3 p-5"><button onClick={() => setOpen((value) => !value)} aria-label={`${open ? 'Collapse' : 'Expand'} ${testCase.title}`} className="mt-1 rounded p-1 hover:bg-muted">{open ? <ChevronUp className="h-4 w-4" /> : <ChevronDown className="h-4 w-4" />}</button><div className="min-w-0 flex-1"><p className="text-xs font-semibold text-primary">{testCase.test_case_id}</p><h2 className="mt-1 font-semibold">{testCase.title}</h2><p className="mt-2 text-sm text-muted-foreground">{testCase.description}</p><div className="mt-3"><Pills values={[testCase.priority, testCase.test_case_type, testCase.validation_status, testCase.automation_candidate ? 'Automation candidate' : undefined]} /></div></div><button onClick={() => copy(testCaseText(testCase), testCase.test_case_id)} className="rounded-lg border border-border p-2 hover:bg-muted" aria-label={`Copy ${testCase.title}`}>{copied === testCase.test_case_id ? <Check className="h-4 w-4 text-green-500" /> : <Clipboard className="h-4 w-4" />}</button></div>{open && <div className="space-y-5 border-t border-border p-5"><Info label="Preconditions" value={testCase.preconditions?.join('; ')} /><div><h3 className="text-sm font-semibold">Test steps</h3><ol className="mt-3 space-y-3">{testCase.steps?.map((step) => <li key={step.step_number} className="grid gap-2 rounded-lg bg-muted/60 p-3 text-sm sm:grid-cols-[2rem_1fr_1fr]"><span className="font-bold text-primary">{step.step_number}</span><div><p className="text-xs text-muted-foreground">Action</p><p>{step.action}</p></div><div><p className="text-xs text-muted-foreground">Expected result</p><p>{step.expected_result}</p></div></li>)}</ol></div><div className="grid gap-3 sm:grid-cols-2"><Info label="Requirement mapping" value={testCase.requirement_ids?.join(', ')} /><Info label="Acceptance criteria" value={testCase.acceptance_criteria_ids?.join(', ')} /><Info label="Test data" value={JSON.stringify(testCase.test_data ?? {})} /><Info label="Confidence" value={`${confidencePercent(testCase.confidence_score)}%`} /></div></div>}</article>;
}

function ValidationView({ data }: { data: WorkflowResult }) {
  const validations = [['Scenario validation', data.scenario_validation], ['Test-case validation', data.testcase_validation]] as const;
  return <div className="grid gap-6 lg:grid-cols-2">{validations.map(([label, validation]) => <section key={label} className="rounded-2xl border border-border bg-card p-5 sm:p-6"><div className="flex items-center justify-between"><h2 className="font-semibold">{label}</h2><span className="text-2xl font-bold text-primary">{confidencePercent(validation?.confidence_score)}%</span></div><div className="mt-5 grid gap-3 sm:grid-cols-2">{Object.entries(validation?.score_breakdown ?? {}).map(([key, value]) => <MetricBar key={key} label={key.replaceAll('_', ' ')} value={confidencePercent(value)} />)}</div><h3 className="mt-6 text-sm font-semibold">Validation issues</h3><div className="mt-3 space-y-2">{validation?.issues?.length ? validation.issues.map((issue, index) => <div key={index} className="rounded-lg border border-border p-3 text-sm"><p className="font-medium">{issue.description}</p>{issue.recommendation && <p className="mt-1 text-xs text-muted-foreground">{issue.recommendation}</p>}</div>) : <p className="text-sm text-muted-foreground">No validation issues reported.</p>}</div><p className="mt-5 text-sm"><span className="text-muted-foreground">Final approval status:</span> <span className="font-semibold capitalize">{validation?.status ?? 'Not provided'}</span></p></section>)}</div>;
}

function TraceabilityView({ data }: { data: WorkflowResult }) {
  const rows = data.test_cases.map((testCase) => ({ testCase, scenario: data.scenarios.find((scenario) => scenario.scenario_id === testCase.scenario_id) }));
  return <section className="overflow-hidden rounded-2xl border border-border bg-card"><div className="border-b border-border p-5"><h2 className="font-semibold">Requirement → User Story → Scenario → Test Case</h2><p className="mt-1 text-sm text-muted-foreground">Coverage is derived from the traceability IDs returned with generated assets.</p></div><div className="overflow-x-auto"><table className="w-full min-w-[900px] text-left text-sm"><thead className="bg-muted/60 text-xs uppercase text-muted-foreground"><tr><th className="p-4">Coverage</th><th className="p-4">Requirement</th><th className="p-4">User story</th><th className="p-4">Scenario</th><th className="p-4">Test case</th></tr></thead><tbody>{rows.map(({ testCase, scenario }) => { const covered = Boolean(testCase.requirement_ids?.length && scenario); return <tr key={testCase.test_case_id} className="border-t border-border"><td className="p-4"><span className={`rounded-full px-2 py-1 text-xs font-semibold ${covered ? 'bg-green-500/10 text-green-600' : 'bg-amber-500/10 text-amber-600'}`}>{covered ? 'Fully covered' : 'Partial / orphan'}</span></td><td className="p-4">{testCase.requirement_ids?.join(', ') || 'Unmapped'}</td><td className="p-4">{scenario?.user_story_ids?.join(', ') || 'Unmapped'}</td><td className="p-4">{scenario?.title || `Orphan scenario: ${testCase.scenario_id}`}</td><td className="p-4 font-medium">{testCase.title}</td></tr>; })}</tbody></table></div></section>;
}

function filterAndSort<T extends Scenario | TestCase>(items: T[], filters: ResultFilters, sort: 'title' | 'priority' | 'confidence'): T[] {
  const query = filters.search.toLowerCase();
  return items.filter((item) => {
    const type = 'test_case_id' in item ? item.test_case_type : item.scenario_type;
    return (!query || `${item.title} ${item.description} ${'test_case_id' in item ? item.test_case_id : item.scenario_id}`.toLowerCase().includes(query))
      && (!filters.priority || item.priority === filters.priority)
      && (!filters.testType || type === filters.testType)
      && (!filters.validationStatus || item.validation_status === filters.validationStatus)
      && (!filters.requirement || item.requirement_ids?.some((id) => id.toLowerCase().includes(filters.requirement.toLowerCase())))
      && confidencePercent(item.confidence_score) >= filters.minConfidence;
  }).sort((a, b) => sort === 'confidence' ? confidencePercent(b.confidence_score) - confidencePercent(a.confidence_score) : String(a[sort] ?? '').localeCompare(String(b[sort] ?? '')));
}

function unique(values: Array<string | undefined>): string[] { return [...new Set(values.filter((value): value is string => Boolean(value)))]; }
function Pills({ values }: { values: Array<string | undefined> }) { return <div className="flex flex-wrap gap-2">{values.filter(Boolean).map((value) => <span key={value} className="rounded-full bg-muted px-2.5 py-1 text-xs font-medium capitalize">{value?.replaceAll('_', ' ')}</span>)}</div>; }
function Info({ label, value }: { label: string; value?: string }) { return <div><p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">{label}</p><p className="mt-1 break-words">{value || 'Not provided'}</p></div>; }
function MetricBar({ label, value }: { label: string; value: number }) { return <div className="rounded-lg bg-muted/60 p-3"><div className="flex justify-between text-xs"><span className="capitalize">{label}</span><span>{value}%</span></div><div className="mt-2 h-1.5 rounded-full bg-background"><div className="h-full rounded-full bg-primary" style={{ width: `${value}%` }} /></div></div>; }
