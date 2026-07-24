'use client';

import { useEffect, useState, type ReactNode } from 'react';
import { CheckCircle2, Download, LoaderCircle, Play } from 'lucide-react';
import { StatePanel } from '../components/StatePanel';
import { testCaseApi } from '../services/testCaseApi';
import { useTestCaseWorkflowStore } from '../store/workflowStore';
import type { DeveloperExecutionReport, ExecutionReport, QaDiagnosticReport, ScriptGeneration, TraceabilityComparisonReport } from '../types';
import { downloadFile, friendlyError } from '../utils';

export function AutomationPage() {
  const { workflowId, hydrate } = useTestCaseWorkflowStore();
  const [applicationUrl, setApplicationUrl] = useState('');
  const [generation, setGeneration] = useState<ScriptGeneration | null>(null);
  const [report, setReport] = useState<ExecutionReport | null>(null);
  const [mode, setMode] = useState<'automated' | 'manual'>('automated');
  const [selectedScript, setSelectedScript] = useState(0);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [showTestReport, setShowTestReport] = useState(false);
  const [comparison, setComparison] = useState<TraceabilityComparisonReport | null>(null);

  useEffect(() => hydrate(), [hydrate]);

  const generate = async () => {
    if (!workflowId || !applicationUrl.trim()) return;
    setBusy(true); setError(''); setReport(null); setComparison(null); setShowTestReport(false);
    try {
      setGeneration(await testCaseApi.generateScripts(workflowId, applicationUrl.trim()));
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
          const refreshed = await testCaseApi.generateScripts(workflowId, applicationUrl.trim());
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
        <p className="mt-1 text-sm text-muted-foreground">Playwright remains the primary engine. Optional Skyvern recovery is limited to failed locator actions.</p>
      </div>

      {error && <div role="alert" className="rounded-xl border border-red-500/30 bg-red-500/10 p-4 text-sm text-red-600">{error}</div>}
      <section className="rounded-2xl border border-border bg-card p-5">
        <label htmlFor="application-url" className="text-sm font-semibold">Deployed application URL</label>
        <div className="mt-2 flex flex-col gap-3 sm:flex-row">
          <input id="application-url" type="url" value={applicationUrl} onChange={(event) => setApplicationUrl(event.target.value)} placeholder="https://app.example.com" className="min-w-0 flex-1 rounded-lg border border-input bg-background px-3 py-2 text-sm outline-none focus:border-primary" />
          <button disabled={busy || !applicationUrl.trim()} onClick={generate} className="inline-flex items-center justify-center gap-2 rounded-lg bg-primary px-4 py-2 text-sm font-semibold text-primary-foreground disabled:opacity-50">{busy ? <LoaderCircle className="h-4 w-4 animate-spin" /> : <Play className="h-4 w-4" />} Validate URL &amp; generate</button>
        </div>
      </section>

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

      {report && <><ExecutionDashboard report={report} /><div className="flex flex-wrap justify-end gap-3">{report.mode === 'automated' && <button disabled={busy} onClick={compare} className="rounded-lg bg-primary px-5 py-3 text-sm font-bold text-primary-foreground disabled:opacity-50">Compare with Test Cases &amp; Scenarios</button>}<button onClick={() => setShowTestReport(true)} className="inline-flex items-center gap-2 rounded-lg border border-border px-5 py-3 text-sm font-bold"><Download className="h-4 w-4" /> Generate Test Report</button></div>{comparison && <section className="space-y-3 rounded-2xl border border-primary/30 bg-card p-5"><h2 className="text-xl font-bold">Post-execution traceability</h2><p className="text-sm">Coverage: {comparison.summary.coverage_percentage}% · Covered {comparison.summary.covered} · Partial {comparison.summary.partial} · Missing {comparison.summary.missing}</p>{comparison.gaps.map((gap) => <article key={gap.artifact_id} className="rounded-lg border border-border p-4 text-sm"><strong>{gap.artifact_id} · {gap.artifact_title}</strong><p className="mt-2 text-muted-foreground">{gap.details}</p></article>)}</section>}{showTestReport && <DetailedTestReport report={report} />}</>}
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
  const requirements = [
    ...report.developer_implementation_requirements.ui.map((value) => `UI: ${value}`),
    ...report.developer_implementation_requirements.backend_api.map((value) => `Backend/API: ${value}`),
    ...report.developer_implementation_requirements.validation.map((value) => `Validation: ${value}`),
    ...report.developer_implementation_requirements.database.map((value) => `Database: ${value}`),
  ];
  return <div className="mt-4 space-y-4 rounded-xl border border-primary/20 bg-primary/5 p-4 text-sm">
    <ReportSection title="Issue Title"><h4 className="text-base font-semibold">{report.issue_title}</h4></ReportSection>
    {report.classification && <ReportSection title="Evidence Classification"><p className="font-semibold">{report.classification} · {Math.round((report.confidence ?? 0) * 100)}% confidence{report.developer_issue_created ? ' · developer issue created' : ' · no developer issue created'}</p></ReportSection>}
    <ReportSection title="Affected Feature/User Story"><p><strong>{report.affected_feature_user_story.feature}</strong></p><TextList values={report.affected_feature_user_story.user_stories} empty="No mapped user story was found." /></ReportSection>
    <ReportSection title="Problem Description"><p>{report.problem_description}</p></ReportSection>
    <ReportSection title="Expected vs Actual Application Behavior"><p><strong>Expected:</strong> {report.expected_vs_actual_application_behavior.expected}</p><p className="mt-2"><strong>Actual:</strong> {report.expected_vs_actual_application_behavior.actual}</p></ReportSection>
    <ReportSection title="Missing Functionality"><p>{report.missing_functionality}</p></ReportSection>
    <ReportSection title="Developer Implementation Requirements"><TextList values={requirements} /></ReportSection>
    <ReportSection title="Acceptance Criteria"><TextList values={report.acceptance_criteria.map((item) => `${item.id}: ${item.title}`)} empty="No acceptance criteria were mapped." /></ReportSection>
    <ReportSection title="Priority"><p className="font-semibold">{report.priority}</p></ReportSection>
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
