'use client';

import { useEffect, useState, type ReactNode } from 'react';
import { CheckCircle2, Download, LoaderCircle, Play, XCircle } from 'lucide-react';
import { StatePanel } from '../components/StatePanel';
import { testCaseApi } from '../services/testCaseApi';
import { useTestCaseWorkflowStore } from '../store/workflowStore';
import type { CrawlAnalysis, DeveloperExecutionReport, ExecutionReport, QaDiagnosticReport, ScriptGeneration, TraceabilityComparisonReport } from '../types';
import { downloadFile, friendlyError } from '../utils';

export function AutomationPage() {
  const { workflowId, hydrate } = useTestCaseWorkflowStore();
  const [applicationUrl, setApplicationUrl] = useState('');
  const [generation, setGeneration] = useState<ScriptGeneration | null>(null);
  const [crawl, setCrawl] = useState<CrawlAnalysis | null>(null);
  const [report, setReport] = useState<ExecutionReport | null>(null);
  const [mode, setMode] = useState<'automated' | 'manual'>('automated');
  const [selectedScript, setSelectedScript] = useState(0);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [showTestReport, setShowTestReport] = useState(false);
  const [comparison, setComparison] = useState<TraceabilityComparisonReport | null>(null);

  useEffect(() => hydrate(), [hydrate]);

  const crawlApplication = async () => {
    if (!workflowId || !applicationUrl.trim()) return;
    setBusy(true); setError(''); setReport(null); setComparison(null); setShowTestReport(false);
    try {
      setGeneration(null);
      setCrawl(await testCaseApi.crawlApplication(workflowId, applicationUrl.trim()));
    } catch (requestError) { setError(friendlyError(requestError)); }
    finally { setBusy(false); }
  };

  const generate = async () => {
    if (!workflowId || !crawl || crawl.crawl_status !== 'crawl_completed') return;
    setBusy(true); setError('');
    try {
      setGeneration(await testCaseApi.generateScripts(
        workflowId, applicationUrl.trim(), crawl.crawl_id,
      ));
      setSelectedScript(0);
    } catch (requestError) { setError(friendlyError(requestError)); }
    finally { setBusy(false); }
  };

  const execute = async () => {
    if (!generation) return;
    setBusy(true); setError(''); setShowTestReport(false);
    try { setReport(await testCaseApi.executeScripts(generation.generation_id, mode)); }
    catch (requestError) {
      if (requestError instanceof Error && requestError.message.includes('(404)') && workflowId && applicationUrl.trim()) {
        try {
          if (!crawl || crawl.crawl_status !== 'crawl_completed') {
            throw new Error('A completed crawl is required before regenerating scripts.');
          }
          const refreshed = await testCaseApi.generateScripts(
            workflowId, applicationUrl.trim(), crawl.crawl_id,
          );
          setGeneration(refreshed);
          setSelectedScript(0);
          setReport(await testCaseApi.executeScripts(refreshed.generation_id, mode));
        } catch (retryError) { setError(friendlyError(retryError)); }
      } else { setError(friendlyError(requestError)); }
    }
    finally { setBusy(false); }
  };

  const compare = async () => {
    if (!report) return;
    setBusy(true); setError('');
    try { setComparison(await testCaseApi.compareExecution(report.execution_id)); }
    catch (requestError) { setError(friendlyError(requestError)); }
    finally { setBusy(false); }
  };

  if (!workflowId) return <StatePanel type="error" title="No completed workflow selected" message="Return to results and choose Proceed to Test Scripts." />;

  const script = generation?.scripts[selectedScript];
  return (
    <div className="space-y-6">
      <div>
        <p className="text-xs font-bold uppercase tracking-[0.2em] text-primary">Playwright automation</p>
        <h1 className="mt-2 text-2xl font-bold">Generate and execute test scripts</h1>
        <p className="mt-1 text-sm text-muted-foreground">Playwright remains the primary engine. Optional Seacrawl recovery is limited to failed locator actions.</p>
      </div>

      {error && <div role="alert" className="rounded-xl border border-red-500/30 bg-red-500/10 p-4 text-sm text-red-600">{error}</div>}
      <section className="rounded-2xl border border-border bg-card p-5">
        <label htmlFor="application-url" className="text-sm font-semibold">Deployed application URL</label>
        <div className="mt-2 flex flex-col gap-3 sm:flex-row">
          <input id="application-url" type="url" value={applicationUrl} onChange={(event) => { setApplicationUrl(event.target.value); setCrawl(null); setGeneration(null); }} placeholder="https://app.example.com" className="min-w-0 flex-1 rounded-lg border border-input bg-background px-3 py-2 text-sm outline-none focus:border-primary" />
          <button disabled={busy || !applicationUrl.trim()} onClick={crawlApplication} className="inline-flex items-center justify-center gap-2 rounded-lg bg-primary px-4 py-2 text-sm font-semibold text-primary-foreground disabled:opacity-50">{busy ? <LoaderCircle className="h-4 w-4 animate-spin" /> : <Play className="h-4 w-4" />} Crawl application</button>
          <button disabled={busy || crawl?.crawl_status !== 'crawl_completed'} onClick={generate} className="inline-flex items-center justify-center gap-2 rounded-lg bg-green-600 px-4 py-2 text-sm font-semibold text-white disabled:opacity-50"><Play className="h-4 w-4" /> Generate Test Scripts</button>
        </div>
      </section>

      {crawl && (
        <section className={`rounded-2xl border p-5 ${crawl.crawl_status === 'crawl_completed' ? 'border-green-500/30 bg-green-500/5' : 'border-red-500/30 bg-red-500/5'}`}>
          <div className={`flex items-center gap-2 font-semibold ${crawl.crawl_status === 'crawl_completed' ? 'text-green-600' : 'text-red-600'}`}>
            {crawl.crawl_status === 'crawl_completed' ? <CheckCircle2 className="h-5 w-5" /> : <XCircle className="h-5 w-5" />}
            {crawl.crawl_status.replaceAll('_', ' ')}
          </div>
          <p className="mt-2 text-sm text-muted-foreground">{crawl.pages_crawled} pages scanned · {crawl.elements_found} verified elements · {crawl.crawl_report.pages_skipped.length} pages skipped</p>
          {crawl.crawl_report.failure_reason && <p className="mt-3 text-sm font-medium text-red-600">{crawl.crawl_report.failure_reason}</p>}
          {crawl.crawl_report.blocked_url && <p className="mt-1 break-all text-xs text-muted-foreground">Blocked URL: {crawl.crawl_report.blocked_url}</p>}
          {crawl.crawl_report.recommended_corrective_action && <p className="mt-2 text-sm text-muted-foreground">Recommended action: {crawl.crawl_report.recommended_corrective_action}</p>}
        </section>
      )}

      {generation && (
        <>
          <section className="rounded-2xl border border-green-500/30 bg-green-500/5 p-5">
            <div className="flex items-center gap-2 font-semibold text-green-600"><CheckCircle2 className="h-5 w-5" /> Application reachable</div>
            <p className="mt-2 text-sm text-muted-foreground">{generation.page_title || generation.application_url} · {generation.application_map?.page_count ?? 1} pages · {generation.discovered_elements.length} verified interactive elements · {generation.scripts.length} scripts generated</p>
          </section>

          <div className="grid gap-6 lg:grid-cols-[18rem_1fr]">
            <aside className="space-y-2 rounded-2xl border border-border bg-card p-3">
              {generation.scripts.map((item, index) => <button key={item.script_id} onClick={() => setSelectedScript(index)} className={`w-full rounded-lg p-3 text-left text-sm ${selectedScript === index ? 'bg-primary text-primary-foreground' : 'hover:bg-muted'}`}><span className="block font-semibold">{item.name}</span><span className="mt-1 block truncate text-xs opacity-70">{item.test_case_id}</span></button>)}
            </aside>
            {script && <section className="min-w-0 rounded-2xl border border-border bg-card">
              <div className="flex items-center justify-between gap-3 border-b border-border p-4"><div><h2 className="font-semibold">{script.name}</h2><p className="text-xs text-muted-foreground">{script.test_case_id} → {script.script_id}</p></div><button onClick={() => downloadFile(`${script.script_id}.py`, script.source, 'text/x-python')} className="inline-flex items-center gap-2 rounded-lg border border-border px-3 py-2 text-sm font-semibold hover:bg-muted"><Download className="h-4 w-4" /> Download</button></div>
              <pre className="max-h-[36rem] overflow-auto p-4 text-xs">{script.source}</pre>
            </section>}
          </div>

          <section className="rounded-2xl border border-border bg-card p-5">
            <h2 className="font-semibold">Execution mode</h2>
            <div className="mt-3 flex flex-wrap gap-3">
              <label className="flex cursor-pointer items-center gap-2 rounded-lg border border-border px-4 py-3"><input type="radio" checked={mode === 'automated'} onChange={() => setMode('automated')} /> Automated execution (default)</label>
              <label className="flex cursor-pointer items-center gap-2 rounded-lg border border-border px-4 py-3"><input type="radio" checked={mode === 'manual'} onChange={() => setMode('manual')} /> Manual execution</label>
              <button disabled={busy} onClick={execute} className="inline-flex items-center gap-2 rounded-lg bg-green-600 px-4 py-2 text-sm font-semibold text-white disabled:opacity-50">{busy ? <LoaderCircle className="h-4 w-4 animate-spin" /> : <Play className="h-4 w-4" />} {mode === 'automated' ? 'Execute with Playwright' : 'Prepare manual package'}</button>
            </div>
          </section>
        </>
      )}

      {report && <><ExecutionDashboard report={report} /><div className="flex flex-wrap justify-end gap-3">{report.mode === 'automated' && <button disabled={busy} onClick={compare} className="rounded-lg bg-primary px-5 py-3 text-sm font-bold text-primary-foreground disabled:opacity-50">Compare with Test Cases &amp; Scenarios</button>}<button onClick={() => setShowTestReport(true)} className="inline-flex items-center gap-2 rounded-lg border border-border px-5 py-3 text-sm font-bold"><Download className="h-4 w-4" /> Generate Test Report</button></div>{comparison && <TraceabilityComparisonSection comparison={comparison} />}{showTestReport && <DetailedTestReport report={report} />}</>}
    </div>
  );
}

function ExecutionDashboard({ report }: { report: ExecutionReport }) {
  return <section className="space-y-5">
    <div><p className="text-xs font-bold uppercase tracking-[0.2em] text-primary">Execution dashboard</p><h2 className="mt-2 text-xl font-bold">Run results</h2></div>
    <div className="grid gap-3 sm:grid-cols-3 lg:grid-cols-6">
      <Metric label="Total" value={report.total_scripts} /><Metric label="Passed" value={report.passed_scripts} /><Metric label="Failed" value={report.failed_scripts} /><Metric label="Skipped" value={report.skipped_scripts} /><Metric label="Seconds" value={report.execution_time_seconds} /><Metric label="Success" value={`${report.success_percentage}%`} />
    </div>
    <div className="space-y-3">{report.results.map((result, index) => <article key={result.script_id} className="rounded-xl border border-border bg-card p-5">
      {result.status !== 'failed' && <div className="flex flex-wrap items-start justify-between gap-3"><div className="flex gap-3">{result.status === 'passed' ? <CheckCircle2 className="h-5 w-5 text-green-500" /> : <Play className="h-5 w-5 text-amber-500" />}<div><h3 className="font-semibold">{result.script_name}</h3></div></div><span className="text-sm font-semibold capitalize">{result.status} · {result.duration_seconds}s</span></div>}
      {report.developer_execution_reports?.[index] && <DeveloperReportCard report={report.developer_execution_reports[index]} />}
    </article>)}</div>
  </section>;
}

function DeveloperReportCard({ report }: { report: DeveloperExecutionReport }) {
  const failure = report.technical_failure_details;
  const requirements = [
    ...report.developer_implementation_requirements.ui.map((value) => `UI: ${value}`),
    ...report.developer_implementation_requirements.backend_api.map((value) => `Backend/API: ${value}`),
    ...report.developer_implementation_requirements.validation.map((value) => `Validation: ${value}`),
    ...report.developer_implementation_requirements.database.map((value) => `Database: ${value}`),
  ];
  return <div className="mt-4 space-y-4 rounded-xl border border-primary/20 bg-primary/5 p-4 text-sm">
    <ReportSection title="Issue Title"><h4 className="text-base font-semibold">{report.issue_title}</h4></ReportSection>
    {report.classification && <ReportSection title="Evidence Classification"><p className="font-semibold">{report.classification} · {Math.round((report.confidence ?? 0) * 100)}% confidence{report.developer_issue_created ? ' · developer issue created' : ' · no developer issue created'}</p></ReportSection>}
    {failure && <ReportSection title="Failure Summary"><div className="grid gap-2 md:grid-cols-2">
      <p><strong>Category:</strong> {failure.failure_category}</p><p><strong>Stage:</strong> {failure.failure_stage ?? 'Unknown'}</p>
      <p><strong>Test case:</strong> {failure.test_case_id} · {failure.test_case_title}</p><p><strong>Scenario:</strong> {String(failure.test_scenario?.title ?? failure.test_scenario?.scenario_id ?? 'Not mapped')}</p>
      <p><strong>Failed step:</strong> {failure.failed_step ?? 'Unknown'}</p><p><strong>Action:</strong> {failure.failed_action ?? 'No executable action'}</p>
      <p><strong>Current URL:</strong> {failure.page_url ?? 'Unavailable'}</p><p><strong>Expected URL:</strong> {failure.expected_page_url ?? 'Unavailable'}</p>
      <p><strong>Page title:</strong> {failure.page_title ?? 'Unavailable'}</p><p><strong>HTTP status:</strong> {failure.http_response_status ?? 'Unavailable'}</p>
      <p><strong>Executed:</strong> {failure.execution_timestamp}</p><p><strong>Developer issue:</strong> {failure.developer_issue_recommended ? 'Recommended' : 'Not recommended'}</p>
    </div></ReportSection>}
    <ReportSection title="Affected Feature/User Story"><p><strong>{report.affected_feature_user_story.feature}</strong></p><TextList values={report.affected_feature_user_story.user_stories} empty="No mapped user story was found." /></ReportSection>
    {report.mapping_explanation && <ReportSection title="Mapping Status"><p>{report.mapping_explanation}</p></ReportSection>}
    <ReportSection title="Problem Description"><p>{report.problem_description}</p></ReportSection>
    <ReportSection title="Expected vs Actual Application Behavior"><p><strong>Expected:</strong> {report.expected_vs_actual_application_behavior.expected}</p><p className="mt-2"><strong>Actual:</strong> {report.expected_vs_actual_application_behavior.actual}</p></ReportSection>
    <ReportSection title="Missing Functionality"><p>{report.missing_functionality}</p></ReportSection>
    {failure && <ReportSection title="Playwright Locator Evidence">
      <p><strong>Exact locator:</strong> {failure.exact_locator ?? 'No valid locator was produced.'}</p>
      {failure.locator_diagnosis && <p className="mt-2"><strong>Diagnosis:</strong> {failure.locator_diagnosis}</p>}
      <pre className="mt-2 max-h-72 overflow-auto whitespace-pre-wrap rounded-lg bg-background p-3 text-xs">{JSON.stringify({ locator: failure.locator_details, alternatives: failure.alternate_locators_attempted }, null, 2)}</pre>
    </ReportSection>}
    {failure && Object.keys(failure.input_details).length > 0 && <ReportSection title="Input Evidence"><pre className="max-h-72 overflow-auto whitespace-pre-wrap rounded-lg bg-background p-3 text-xs">{JSON.stringify(failure.input_details, null, 2)}</pre></ReportSection>}
    {failure && Object.keys(failure.navigation_details).length > 0 && <ReportSection title="Navigation Evidence"><pre className="max-h-72 overflow-auto whitespace-pre-wrap rounded-lg bg-background p-3 text-xs">{JSON.stringify(failure.navigation_details, null, 2)}</pre></ReportSection>}
    {failure && Object.keys(failure.assertion_details).length > 0 && <ReportSection title="Assertion Evidence"><pre className="max-h-72 overflow-auto whitespace-pre-wrap rounded-lg bg-background p-3 text-xs">{JSON.stringify(failure.assertion_details, null, 2)}</pre></ReportSection>}
    {failure && <ReportSection title="Execution Evidence"><TextList values={[
      failure.screenshot ? `Screenshot: ${failure.screenshot}` : '',
      failure.trace_path ? `Trace: ${failure.trace_path}` : '',
      failure.dom_snapshot ? `DOM snapshot: ${failure.dom_snapshot}` : '',
      ...failure.console_logs.map((value) => `Console: ${value}`),
      ...failure.network_errors.map((value) => `Network: ${value}`),
    ].filter(Boolean)} empty="No execution evidence was captured." /></ReportSection>}
    {report.root_cause_analysis && <ReportSection title="Root Cause Analysis"><p>{report.root_cause_analysis}</p></ReportSection>}
    <ReportSection title="Reproduction Steps"><TextList values={report.reproduction_steps ?? []} ordered /></ReportSection>
    <ReportSection title="Recommended Script Correction"><TextList values={report.recommended_script_correction ?? []} /></ReportSection>
    <ReportSection title="Recommended Application Fix"><TextList values={report.recommended_application_fix ?? []} /></ReportSection>
    <ReportSection title="Developer Implementation Requirements"><TextList values={requirements} /></ReportSection>
    <ReportSection title="Acceptance Criteria"><TextList values={report.acceptance_criteria.map((item) => `${item.id}: ${item.title}`)} empty="No acceptance criteria were mapped." /></ReportSection>
    <ReportSection title="Severity / Priority"><p className="font-semibold">{report.severity ?? report.priority} / {report.priority}</p></ReportSection>
  </div>;
}

function ReportSection({ title, children }: { title: string; children: ReactNode }) { return <section className="mt-3"><h5 className="text-xs font-bold uppercase text-muted-foreground">{title}</h5><div className="mt-2">{children}</div></section>; }
function TextList({ values, empty = 'No changes identified.', ordered = false }: { values: string[]; empty?: string; ordered?: boolean }) { if (!values.length) return <p className="text-muted-foreground">{empty}</p>; const Tag = ordered ? 'ol' : 'ul'; return <Tag className={`space-y-1 pl-5 ${ordered ? 'list-decimal' : 'list-disc'}`}>{values.map((value, index) => <li key={`${value}-${index}`}>{value}</li>)}</Tag>; }

function DetailedTestReport({ report }: { report: ExecutionReport }) {
  const developerReports = report.developer_execution_reports ?? [];
  const qaReports = report.qa_diagnostic_reports ?? [];
  return <section className="space-y-5 rounded-2xl border border-border bg-card p-5">
    <div className="flex flex-wrap items-center justify-between gap-3"><div><p className="text-xs font-bold uppercase tracking-[0.2em] text-primary">Developer implementation report</p><h2 className="mt-1 text-xl font-bold">Evidence-gated application behavior</h2></div><button onClick={() => downloadFile(`developer-report-${report.execution_id}.json`, JSON.stringify(developerReports, null, 2), 'application/json')} className="inline-flex items-center gap-2 rounded-lg border border-border px-4 py-2 text-sm font-semibold"><Download className="h-4 w-4" /> Download developer report</button></div>
    {developerReports.length ? developerReports.map((item, index) => <DeveloperReportCard key={`${item.issue_title}-${index}`} report={item} />) : <p className="rounded-lg border border-dashed border-border p-4 text-sm text-muted-foreground">No execution results are available.</p>}
    <div className="flex flex-wrap items-center justify-between gap-3 border-t border-border pt-5"><div><p className="text-xs font-bold uppercase tracking-[0.2em] text-primary">QA diagnostic report</p><h2 className="mt-1 text-xl font-bold">Automation and technical evidence</h2></div><button onClick={() => downloadFile(`qa-diagnostic-${report.execution_id}.json`, JSON.stringify(qaReports, null, 2), 'application/json')} className="inline-flex items-center gap-2 rounded-lg border border-border px-4 py-2 text-sm font-semibold"><Download className="h-4 w-4" /> Download QA report</button></div>
    {qaReports.map((item) => <QaDiagnosticCard key={item.script_id} report={item} />)}
  </section>;
}

function QaDiagnosticCard({ report }: { report: QaDiagnosticReport }) {
  const checks = Object.entries(report.confidence_gate?.checks ?? {}).map(([key, passed]) => `${passed ? 'PASS' : 'FAIL'}: ${key.replaceAll('_', ' ')}`);
  const recommendations = Object.values(report.automation_recommendations ?? {}).flat();
  const evidence = [
    report.locator ? `Locator: ${report.locator}` : '',
    report.playwright_trace ? `Trace: ${report.playwright_trace}` : '',
    report.dom_snapshot ? `DOM: ${report.dom_snapshot}` : '',
    ...report.screenshots.map((value) => `Screenshot: ${value}`),
    ...report.network_errors.map((value) => `Network: ${value}`),
    ...report.console_logs.map((value) => `Console: ${value}`),
    report.stack_trace ? `Stack trace: ${report.stack_trace}` : '',
  ].filter(Boolean);
  return <article className="space-y-3 rounded-xl border border-border bg-muted/20 p-4 text-sm">
    <h3 className="font-semibold">{report.script_id} · {report.status}{report.classification ? ` · ${report.classification}` : ''}</h3>
    <ReportSection title="Confidence Gate"><TextList values={checks} empty="Not applicable for this result." /></ReportSection>
    <ReportSection title="Technical Evidence"><TextList values={evidence} empty="No failure evidence was produced." /></ReportSection>
    <ReportSection title="Automation Recommendations"><TextList values={recommendations} /></ReportSection>
  </article>;
}

function Metric({ label, value }: { label: string; value: string | number }) { return <div className="rounded-xl border border-border bg-card p-4"><p className="text-xs text-muted-foreground">{label}</p><p className="mt-1 text-xl font-bold">{value}</p></div>; }

type ComparisonDisplayItem = {
  id?: string;
  artifact_id?: string;
  title?: string;
  artifact_title?: string;
  status?: string;
  gap_type?: string;
  classification?: string;
  coverage_percentage?: number;
  details?: string;
  missing_terms?: string[];
};

function TraceabilityComparisonSection({ comparison }: { comparison: TraceabilityComparisonReport }) {
  const [filter, setFilter] = useState<'missing' | 'covered' | 'all'>('missing');

  const allArtifacts: ComparisonDisplayItem[] = [
    ...(comparison.scenario_coverage || []),
    ...(comparison.test_case_coverage || []),
  ];

  const getStatus = (item: { status?: string; gap_type?: string; coverage_percentage?: number }) => {
    if (item.status === 'partial') return 'covered';
    if (item.status) return item.status;
    if (item.gap_type === 'uncovered') return 'missing';
    if (item.gap_type === 'partially covered') return 'covered';
    if ((item.coverage_percentage ?? 0) > 0) return 'covered';
    return 'missing';
  };
  const totalArtifacts = allArtifacts.length || comparison.summary.total_artifacts;
  const coveredCount = allArtifacts.length
    ? allArtifacts.filter((item) => getStatus(item) === 'covered').length
    : comparison.summary.covered;
  const missingCount = Math.max(totalArtifacts - coveredCount, 0);
  const coveragePercentage = totalArtifacts ? Math.round((coveredCount / totalArtifacts) * 10000) / 100 : 0;

  const getFilteredItems = () => {
    if (filter === 'missing') {
      return comparison.gaps.filter((g) => getStatus(g) === 'missing');
    }
    if (filter === 'covered') {
      return allArtifacts.filter((a) => getStatus(a) === 'covered');
    }
    if (filter === 'all') {
      return allArtifacts.length > 0 ? allArtifacts : comparison.gaps;
    }
    return allArtifacts;
  };

  const filteredItems = getFilteredItems();

  return (
    <section className="space-y-5 rounded-2xl border border-primary/30 bg-card p-6 shadow-sm">
      <div className="flex flex-wrap items-center justify-between gap-4 border-b border-border pb-4">
        <div>
          <p className="text-xs font-bold uppercase tracking-[0.2em] text-primary">Post-execution traceability</p>
          <h2 className="mt-1 text-xl font-bold">Coverage &amp; Gap Analysis</h2>
          <p className="mt-1 text-xs text-muted-foreground">
            DOM UI evidence comparison against test scenarios and test cases.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <span className="rounded-xl border border-primary/20 bg-primary/10 px-4 py-2 text-sm font-bold text-primary">
            Overall Coverage: {coveragePercentage}%
          </span>
        </div>
      </div>

      {/* KPI Cards */}
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
        <button
          type="button"
          onClick={() => setFilter('all')}
          className={`rounded-xl border p-4 text-left transition ${
            filter === 'all' ? 'border-primary bg-primary/5 ring-1 ring-primary' : 'border-border bg-background hover:bg-muted'
          }`}
        >
          <p className="text-xs font-semibold uppercase text-muted-foreground">Total Artifacts</p>
          <p className="mt-1 text-2xl font-bold">{totalArtifacts}</p>
        </button>

        <button
          type="button"
          onClick={() => setFilter('covered')}
          className={`rounded-xl border p-4 text-left transition ${
            filter === 'covered' ? 'border-green-500 bg-green-500/10 ring-1 ring-green-500' : 'border-border bg-background hover:bg-muted'
          }`}
        >
          <p className="text-xs font-semibold uppercase text-green-600 dark:text-green-400">Covered</p>
          <p className="mt-1 text-2xl font-bold text-green-600 dark:text-green-400">{coveredCount}</p>
          <p className="mt-1 text-xs font-semibold text-green-600/80 dark:text-green-400/80">{coveragePercentage}% coverage</p>
        </button>

        <button
          type="button"
          onClick={() => setFilter('missing')}
          className={`rounded-xl border p-4 text-left transition ${
            filter === 'missing' ? 'border-red-500 bg-red-500/10 ring-1 ring-red-500' : 'border-border bg-background hover:bg-muted'
          }`}
        >
          <p className="text-xs font-semibold uppercase text-red-600 dark:text-red-400">Missing Evidence</p>
          <p className="mt-1 text-2xl font-bold text-red-600 dark:text-red-400">{missingCount}</p>
        </button>
      </div>

      {/* Filter Tabs */}
      <div className="flex flex-wrap items-center gap-2 border-b border-border pb-3">
        <span className="mr-2 text-xs font-semibold text-muted-foreground">Filter view:</span>
        {([
          { key: 'missing', label: `Missing Only (${missingCount})` },
          { key: 'covered', label: `Covered Only (${coveredCount})` },
          { key: 'all', label: `All Artifacts (${totalArtifacts})` },
        ] as const).map((tab) => (
          <button
            key={tab.key}
            type="button"
            onClick={() => setFilter(tab.key)}
            className={`rounded-lg px-3.5 py-1.5 text-xs font-bold transition ${
              filter === tab.key
                ? 'bg-primary text-primary-foreground shadow-sm'
                : 'bg-muted/60 text-muted-foreground hover:bg-muted hover:text-foreground'
            }`}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {/* Item List */}
      <div className="space-y-3">
        {filteredItems.length === 0 ? (
          <div className="rounded-xl border border-dashed border-border p-8 text-center text-sm text-muted-foreground">
            No items match the selected filter.
          </div>
        ) : (
          filteredItems.map((item: ComparisonDisplayItem, idx: number) => {
            const id = item.artifact_id || item.id || `item-${idx}`;
            const title = item.artifact_title || item.title || 'Untitled Artifact';
            const status = getStatus(item);
            const coveragePct = item.coverage_percentage ?? (status === 'covered' ? 100 : 0);
            const details = item.details || (item.missing_terms?.length ? `Missing UI evidence: ${item.missing_terms.join(', ')}` : 'All UI evidence verified');

            return (
              <article
                key={id}
                className={`rounded-xl border p-4 text-sm shadow-sm transition ${
                  status === 'missing'
                    ? 'border-red-500/40 bg-red-500/5'
                    : 'border-green-500/40 bg-green-500/5'
                }`}
              >
                <div className="flex flex-wrap items-center justify-between gap-2 border-b border-border/40 pb-2">
                  <div className="flex items-center gap-2">
                    {status === 'missing' && (
                      <span className="inline-flex items-center gap-1.5 rounded-full border border-red-500/40 bg-red-500/15 px-3 py-1 text-xs font-bold text-red-700 dark:text-red-300">
                        <XCircle className="h-3.5 w-3.5" /> MISSING (0%)
                      </span>
                    )}
                    {status === 'covered' && (
                      <span className="inline-flex items-center gap-1.5 rounded-full border border-green-500/40 bg-green-500/15 px-3 py-1 text-xs font-bold text-green-700 dark:text-green-300">
                        <CheckCircle2 className="h-3.5 w-3.5" /> COVERED ({coveragePct}%)
                      </span>
                    )}

                    <span className="font-mono text-xs font-semibold text-muted-foreground">{id}</span>
                  </div>

                  <span className="text-xs font-bold uppercase tracking-wider">
                    Label: <strong className={status === 'missing' ? 'text-red-600 dark:text-red-400' : 'text-green-600 dark:text-green-400'}>{status}</strong>
                  </span>
                </div>

                <h3 className="mt-3 font-bold text-base">{title}</h3>

                <div className="mt-2 text-xs text-muted-foreground">
                  {(item.classification || item.gap_type) && status === 'missing' && (
                    <p className="mb-1 font-semibold text-red-600">
                      Classification: {(item.classification || item.gap_type || '').replaceAll('_', ' ')}
                    </p>
                  )}
                  <p className="font-medium">{details}</p>
                </div>
              </article>
            );
          })
        )}
      </div>
    </section>
  );
}
