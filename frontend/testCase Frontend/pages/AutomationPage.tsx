'use client';

import { useEffect, useState } from 'react';
import { CheckCircle2, Download, LoaderCircle, Play, XCircle } from 'lucide-react';
import { StatePanel } from '../components/StatePanel';
import { testCaseApi } from '../services/testCaseApi';
import { useTestCaseWorkflowStore } from '../store/workflowStore';
import type { ExecutionReport, FailureAnalysis, ScriptGeneration } from '../types';
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

  useEffect(() => hydrate(), [hydrate]);

  const generate = async () => {
    if (!workflowId || !applicationUrl.trim()) return;
    setBusy(true); setError(''); setReport(null); setShowTestReport(false);
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
            <p className="mt-2 text-sm text-muted-foreground">{generation.page_title || generation.application_url} · {generation.discovered_elements.length} interactive elements discovered · {generation.scripts.length} scripts generated</p>
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

      {report && <><ExecutionDashboard report={report} /><div className="flex justify-end"><button onClick={() => setShowTestReport(true)} className="inline-flex items-center gap-2 rounded-lg bg-primary px-5 py-3 text-sm font-bold text-primary-foreground"><Download className="h-4 w-4" /> Generate Test Report</button></div>{showTestReport && <DetailedTestReport report={report} />}</>}
    </div>
  );
}

function ExecutionDashboard({ report }: { report: ExecutionReport }) {
  return <section className="space-y-5">
    <div><p className="text-xs font-bold uppercase tracking-[0.2em] text-primary">Execution dashboard</p><h2 className="mt-2 text-xl font-bold">Run results</h2></div>
    <div className="grid gap-3 sm:grid-cols-3 lg:grid-cols-6">
      <Metric label="Total" value={report.total_scripts} /><Metric label="Passed" value={report.passed_scripts} /><Metric label="Failed" value={report.failed_scripts} /><Metric label="Skipped" value={report.skipped_scripts} /><Metric label="Seconds" value={report.execution_time_seconds} /><Metric label="Success" value={`${report.success_percentage}%`} />
    </div>
    <div className="space-y-3">{report.results.map((result) => <article key={result.script_id} className="rounded-xl border border-border bg-card p-5">
      <div className="flex flex-wrap items-start justify-between gap-3"><div className="flex gap-3">{result.status === 'passed' ? <CheckCircle2 className="h-5 w-5 text-green-500" /> : result.status === 'failed' ? <XCircle className="h-5 w-5 text-red-500" /> : <Play className="h-5 w-5 text-amber-500" />}<div><h3 className="font-semibold">{result.script_name}</h3><p className="text-xs text-muted-foreground">{result.test_case_id} → {result.scenario_id} → {result.script_id}</p></div></div><span className="text-sm font-semibold capitalize">{result.status} · {result.duration_seconds}s</span></div>
      {result.status === 'failed' && <p className="mt-3 rounded-lg bg-red-500/10 p-3 text-sm text-red-600">{friendlyFailureMessage(result.error_message, result.failure)}</p>}
      {result.failure && <details className="mt-3 rounded-lg border border-border"><summary className="cursor-pointer p-3 text-sm font-semibold">Failure analysis · {result.failure.failure_category}</summary><div className="grid gap-3 border-t border-border p-3 text-sm sm:grid-cols-2"><Info label="Category" value={result.failure.failure_category} /><Info label="Failed step" value={String(result.failure.failed_step ?? 'Unknown')} /><Info label="Reason" value={result.failure.failure_reason} /><Info label="Expected" value={result.failure.expected_result} /><Info label="Actual" value={result.failure.actual_result} /><Info label="Page URL" value={result.failure.page_url} /><Info label="Failed UI element" value={result.failure.ui_element} /><Info label="Skyvern attempted" value={result.failure.skyvern_attempted ? 'Yes' : 'No'} /><Info label="Skyvern succeeded" value={result.failure.skyvern_succeeded ? 'Yes' : 'No'} /><Info label="Console logs" value={result.failure.console_logs.join('\n')} /><Info label="Network errors" value={result.failure.network_errors.join('\n')} /></div></details>}
    </article>)}</div>
  </section>;
}

function DetailedTestReport({ report }: { report: ExecutionReport }) {
  const passed = report.results.filter((item) => item.status === 'passed');
  const failed = report.results.filter((item) => item.status === 'failed');
  const rejected = report.rejected_results ?? [];
  const summary = report.overall_summary ?? {
    total_tests: report.total_scripts + rejected.length,
    executed_tests: report.total_scripts,
    passed: report.passed_scripts,
    failed: report.failed_scripts,
    skipped: report.skipped_scripts,
    rejected: rejected.length,
    pass_rate: report.total_scripts + rejected.length ? Math.round(report.passed_scripts / (report.total_scripts + rejected.length) * 10000) / 100 : 0,
  };
  return <section className="space-y-5 rounded-2xl border border-border bg-card p-5">
    <div className="flex flex-wrap items-center justify-between gap-3"><div><p className="text-xs font-bold uppercase tracking-[0.2em] text-primary">Final automation report</p><h2 className="mt-1 text-xl font-bold">Detailed test report</h2></div><button onClick={() => downloadFile(`test-report-${report.execution_id}.json`, JSON.stringify(report, null, 2), 'application/json')} className="inline-flex items-center gap-2 rounded-lg border border-border px-4 py-2 text-sm font-semibold"><Download className="h-4 w-4" /> Download report</button></div>
    <div className="grid gap-3 sm:grid-cols-3 lg:grid-cols-6"><Metric label="Total" value={summary.total_tests} /><Metric label="Passed" value={summary.passed} /><Metric label="Failed" value={summary.failed} /><Metric label="Rejected" value={summary.rejected} /><Metric label="Pass rate" value={`${summary.pass_rate}%`} /><Metric label="Seconds" value={report.execution_time_seconds} /></div>
    <ReportGroup title="Passed" tone="green" items={passed.map((item) => ({ id: item.test_case_id, name: item.script_name, status: item.status, reason: 'All assertions passed', duration: item.duration_seconds }))} />
    <ReportGroup title="Failed" tone="red" items={failed.map((item) => ({ id: item.test_case_id, name: item.script_name, status: item.status, reason: friendlyFailureMessage(item.error_message, item.failure), duration: item.duration_seconds, screenshot: item.failure?.screenshot, logs: [...(item.failure?.console_logs ?? []), ...(item.failure?.network_errors ?? [])] }))} />
    <ReportGroup title="Rejected / Unsupported" tone="amber" items={rejected.map((item) => ({ id: item.test_case_id, name: item.test_case_name, status: item.status, reason: item.reason, duration: item.duration_seconds, screenshot: item.screenshot, logs: item.logs }))} />
  </section>;
}

function ReportGroup({ title, tone, items }: { title: string; tone: 'green' | 'red' | 'amber'; items: Array<{ id: string; name: string; status: string; reason: string; duration: number; screenshot?: string; logs?: string[] }> }) {
  const colors = tone === 'green' ? 'border-green-500/30 bg-green-500/5' : tone === 'red' ? 'border-red-500/30 bg-red-500/5' : 'border-amber-500/30 bg-amber-500/5';
  return <div><h3 className="font-semibold">{title} ({items.length})</h3><div className="mt-3 space-y-2">{items.length ? items.map((item) => <article key={item.id} className={`rounded-xl border p-4 ${colors}`}><div className="flex flex-wrap justify-between gap-2"><div><p className="font-semibold">{item.name}</p><p className="text-xs text-muted-foreground">{item.id} · {item.status}</p></div><span className="text-sm font-semibold">{item.duration}s</span></div><p className="mt-2 text-sm">{item.reason}</p>{item.screenshot && <p className="mt-2 break-all text-xs text-muted-foreground">Screenshot: {item.screenshot}</p>}{item.logs?.length ? <details className="mt-2 text-xs"><summary className="cursor-pointer font-semibold">Logs ({item.logs.length})</summary><pre className="mt-2 overflow-auto whitespace-pre-wrap">{item.logs.join('\n')}</pre></details> : null}</article>) : <p className="rounded-lg border border-dashed border-border p-4 text-sm text-muted-foreground">No {title.toLowerCase()} test cases.</p>}</div></div>;
}

function Metric({ label, value }: { label: string; value: string | number }) { return <div className="rounded-xl border border-border bg-card p-4"><p className="text-xs text-muted-foreground">{label}</p><p className="mt-1 text-xl font-bold">{value}</p></div>; }
function Info({ label, value }: { label: string; value?: string }) { return <div><p className="text-xs font-semibold uppercase text-muted-foreground">{label}</p><p className="mt-1 whitespace-pre-wrap break-words">{value || 'Not available'}</p></div>; }

function friendlyFailureMessage(errorMessage?: string, failure?: FailureAnalysis) {
  const technicalMessage = `${errorMessage ?? ''} ${failure?.failure_reason ?? ''} ${failure?.actual_result ?? ''}`.toLowerCase();

  if (technicalMessage.includes('invalidselector') || technicalMessage.includes('parsing selector')) {
    return 'The test could not continue because the generated element selector was invalid.';
  }
  if (technicalMessage.includes('timeout') || technicalMessage.includes('timed out')) {
    return 'The test timed out while waiting for the application to complete the expected action.';
  }
  if (technicalMessage.includes('assert') || technicalMessage.includes('expected')) {
    return 'The application result did not match what this test expected.';
  }

  switch (failure?.failure_category) {
    case 'Locator':
      return 'The test could not find or interact with the expected page element.';
    case 'Navigation':
      return 'The test could not open or navigate to the expected page.';
    case 'Application':
      return 'The application did not respond as expected during this test.';
    case 'Script Generation':
      return 'The generated automation steps could not be executed successfully.';
    default:
      return 'The test could not be completed as expected. Open the failure analysis for more details.';
  }
}
