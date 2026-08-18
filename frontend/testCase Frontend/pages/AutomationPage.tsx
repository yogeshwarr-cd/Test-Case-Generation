'use client';

import { useEffect, useState, type ReactNode } from 'react';
import { useSearchParams } from 'next/navigation';
import Image from 'next/image';
import { CheckCircle2, Download, LoaderCircle, Play, X, XCircle } from 'lucide-react';
import { StatePanel } from '../components/StatePanel';
import { ConfidenceRing, EntityId, StatusBadge, TraceabilityChain } from '../components/TraceabilityUI';
import { automationArtifactPdfUrl, automationArtifactUrl, testCaseApi } from '../services/testCaseApi';
import { loadTestProjectArtifacts, saveAutomationActivity, saveTestProjectArtifacts, useTestCaseWorkflowStore } from '../store/workflowStore';
import type { CrawlAnalysis, DeveloperExecutionReport, ExecutionJob, ExecutionReport, HumanExecutionSession, QaDiagnosticReport, ScriptGeneration, TraceabilityComparisonReport, WorkflowCrawlJob } from '../types';
import { downloadFile, friendlyError, friendlyId, registerFriendlyIds, setActiveProjectId } from '../utils';

export function AutomationPage() {
  const historyMode = useSearchParams().get('view') === 'history';
  const { workflowId, hydrate } = useTestCaseWorkflowStore();
  const [applicationUrl, setApplicationUrl] = useState('');
  const [authenticationEmail, setAuthenticationEmail] = useState('');
  const [authenticationPassword, setAuthenticationPassword] = useState('');
  const [generation, setGeneration] = useState<ScriptGeneration | null>(null);
  const [crawl, setCrawl] = useState<CrawlAnalysis | null>(null);
  const [report, setReport] = useState<ExecutionReport | null>(null);
  const [mode, setMode] = useState<'automated' | 'manual'>('automated');
  const [testingScope, setTestingScope] = useState<'full_application' | 'specific_page'>('full_application');
  const [targetPageUrl, setTargetPageUrl] = useState('');
  const [authMode, setAuthMode] = useState<'no_auth' | 'credentials' | 'existing_session'>('no_auth');
  const [sessionState, setSessionState] = useState('');
  const [executionProfile, setExecutionProfile] = useState<'fast' | 'standard' | 'diagnostic'>('fast');
  const [selectedScript, setSelectedScript] = useState(0);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [showTestReport, setShowTestReport] = useState(false);
  const [showDeveloperReport, setShowDeveloperReport] = useState(false);
  const [comparison, setComparison] = useState<TraceabilityComparisonReport | null>(null);
  const [humanSession, setHumanSession] = useState<HumanExecutionSession | null>(null);
  const [crawlJob, setCrawlJob] = useState<WorkflowCrawlJob | null>(null);
  const [executionJob, setExecutionJob] = useState<ExecutionJob | null>(null);
  const humanSessionId = humanSession?.session_id;
  const humanSessionState = humanSession?.state;
  const crawlRunning = Boolean(
    crawlJob && ['queued', 'running', 'stopping'].includes(crawlJob.status),
  );
  const executionRunning = Boolean(
    executionJob && ['queued', 'running'].includes(executionJob.status),
  );

  useEffect(() => {
    if (workflowId) {
      setActiveProjectId(workflowId);
    }
    const scripts = generation?.scripts ?? [];
    registerFriendlyIds('script', scripts.map((script) => script.script_id), workflowId);
    registerFriendlyIds('scenario', scripts.map((script) => script.scenario_id), workflowId);
    registerFriendlyIds('case', scripts.map((script) => script.test_case_id), workflowId);
  }, [generation, workflowId]);

  useEffect(() => {
    if (workflowId) saveTestProjectArtifacts(workflowId, generation, report, comparison, crawl);
  }, [comparison, crawl, generation, report, workflowId]);

  useEffect(() => {
    if (!workflowId) return;
    saveAutomationActivity(workflowId, {
      applicationUrl,
      crawlJobId: crawlJob?.job_id,
      executionJobId: executionJob?.job_id,
      humanSessionId: humanSession?.session_id,
    });
  }, [applicationUrl, crawlJob?.job_id, executionJob?.job_id, humanSession?.session_id, workflowId]);

  useEffect(() => hydrate(), [hydrate]);
  useEffect(() => {
    if (!workflowId) return;
    const saved = loadTestProjectArtifacts(workflowId);
    if (!saved) return;
    queueMicrotask(() => {
      if (saved.applicationUrl) setApplicationUrl(saved.applicationUrl);
      if (saved.crawl) setCrawl(saved.crawl);
      if (saved.generation) { setGeneration(saved.generation); setApplicationUrl(saved.generation.application_url); }
      if (saved.report) { setReport(saved.report); if (historyMode) setShowTestReport(true); }
      if (saved.comparison) setComparison(saved.comparison);
      if (saved.crawlJobId) void testCaseApi.getWorkflowCrawlJob(saved.crawlJobId).then((current) => {
        setCrawlJob(current);
        if (current.crawl) setCrawl(current.crawl);
        if (current.generation) setGeneration(current.generation);
      }).catch(() => undefined);
      if (saved.executionJobId) void testCaseApi.getExecutionJob(saved.executionJobId).then((current) => {
        setExecutionJob(current);
        if (current.report) setReport(current.report);
      }).catch(() => undefined);
      if (saved.humanSessionId) void testCaseApi.getHumanExecution(saved.humanSessionId).then(setHumanSession).catch(() => undefined);
    });
  }, [historyMode, workflowId]);
  useEffect(() => {
    if (!humanSessionId || !humanSessionState || !['waiting_for_human', 'recording', 'generating_scripts', 'validating_scripts', 'executing_scripts'].includes(humanSessionState)) return;
    const timer = window.setInterval(async () => {
      try {
        const current = await testCaseApi.getHumanExecution(humanSessionId);
        setHumanSession(current);
        if (current.state === 'completed' && current.execution_id) {
          setReport(await testCaseApi.getExecutionReport(current.execution_id));
          if (current.comparison) setComparison(current.comparison);
        }
        if (current.state === 'failed') setError(current.error || 'Manual execution failed.');
      } catch (requestError) {
        setError(friendlyError(requestError));
      }
    }, 1000);
    return () => window.clearInterval(timer);
  }, [humanSessionId, humanSessionState]);
  useEffect(() => {
    if (!crawlJob?.job_id || !crawlRunning) return;
    let disposed = false;
    let consecutiveFailures = 0;
    let pollingErrorVisible = false;
    let timer: number | undefined;
    const poll = async () => {
      try {
        const current = await testCaseApi.getWorkflowCrawlJob(crawlJob.job_id);
        if (disposed) return;
        consecutiveFailures = 0;
        if (pollingErrorVisible) {
          setError('');
          pollingErrorVisible = false;
        }
        setCrawlJob(current);
        if (current.status === 'completed') {
          if (current.crawl) setCrawl(current.crawl);
          if (current.generation) {
            setGeneration(current.generation);
            setSelectedScript(0);
          }
        } else if (current.status === 'failed') {
          setError(current.error || 'The application crawl failed.');
        }
      } catch (requestError) {
        if (disposed) return;
        consecutiveFailures += 1;
        if (consecutiveFailures >= 3) {
          pollingErrorVisible = true;
          setError(`Crawl status updates were interrupted. The crawl is still running and reconnection will continue automatically. ${friendlyError(requestError)}`);
        }
      } finally {
        if (!disposed) timer = window.setTimeout(poll, 1500);
      }
    };
    void poll();
    return () => {
      disposed = true;
      if (timer !== undefined) window.clearTimeout(timer);
    };
  }, [crawlJob?.job_id, crawlRunning]);

  useEffect(() => {
    if (!executionJob?.job_id || !executionRunning) return;
    let disposed = false;
    let timer: number | undefined;
    const poll = async () => {
      try {
        const current = await testCaseApi.getExecutionJob(executionJob.job_id);
        if (disposed) return;
        setExecutionJob(current);
        if (current.status === 'completed' && current.report) {
          setReport(current.report);
          setShowTestReport(true);
        } else if (current.status === 'failed') {
          setError(current.error || 'The Playwright execution failed.');
        }
      } catch (requestError) {
        if (!disposed) setError(`Execution status updates were interrupted. The execution is still running and reconnection will continue automatically. ${friendlyError(requestError)}`);
      } finally {
        if (!disposed) timer = window.setTimeout(poll, 1500);
      }
    };
    void poll();
    return () => {
      disposed = true;
      if (timer !== undefined) window.clearTimeout(timer);
    };
  }, [executionJob?.job_id, executionRunning]);

  const crawlApplication = async () => {
    if (crawlRunning && crawlJob) {
      if (busy) return;
      setBusy(true); setError('');
      try {
        setCrawlJob(await testCaseApi.stopWorkflowCrawlJob(crawlJob.job_id));
      } catch (requestError) {
        setError(friendlyError(requestError));
      } finally {
        setBusy(false);
      }
      return;
    }
    if (!workflowId || !applicationUrl.trim() || busy) return;
    const targetUrl = (testingScope === 'specific_page' && targetPageUrl.trim())
      ? targetPageUrl.trim()
      : applicationUrl.trim();
    setBusy(true); setError(''); setReport(null); setComparison(null); setShowTestReport(false); setShowDeveloperReport(false);
    try {
      setCrawl(null);
      setGeneration(null);
      const authentication = authMode === 'credentials' && authenticationEmail.trim() && authenticationPassword
        ? { email: authenticationEmail.trim(), password: authenticationPassword }
        : undefined;
      const startedJob = await testCaseApi.startWorkflowCrawlJob(
        workflowId, targetUrl, { testing_scope: testingScope, authentication }
      );
      setCrawlJob(startedJob);
      saveAutomationActivity(workflowId, { applicationUrl: targetUrl, crawlJobId: startedJob.job_id });
    } catch (requestError) { setError(friendlyError(requestError)); }
    finally { setBusy(false); }
  };

  const generate = async () => {
    if (
      !workflowId
      || !crawl
      || crawl.crawl_status === 'crawl_blocked'
      || (crawl.pages_crawled === 0 && crawl.discovered_elements.length === 0)
    ) return;
    setBusy(true); setError('');
    try {
      const generated = await testCaseApi.generateScripts(
        workflowId, applicationUrl.trim(), crawl.crawl_id,
      );
      setGeneration(generated);
      saveTestProjectArtifacts(workflowId, generated, report, comparison, crawl);
      setSelectedScript(0);
    } catch (requestError) { setError(friendlyError(requestError)); }
    finally { setBusy(false); }
  };

  const execute = async () => {
    if (!generation || !script) return;
    if (mode === 'manual') {
      if (!workflowId || !applicationUrl.trim()) return;
      setBusy(true); setError(''); setReport(null); setComparison(null); setShowTestReport(false); setShowDeveloperReport(false);
      try {
        const startedSession = await testCaseApi.startHumanExecution({
          workflow_id: workflowId,
          scenario_id: script.scenario_id,
          test_case_id: script.test_case_id,
          application_url: applicationUrl.trim(),
        });
        setHumanSession(startedSession);
        saveAutomationActivity(workflowId, { applicationUrl: applicationUrl.trim(), humanSessionId: startedSession.session_id });
      } catch (requestError) {
        setError(friendlyError(requestError));
      } finally {
        setBusy(false);
      }
      return;
    }
    if (Boolean(authenticationEmail.trim()) !== Boolean(authenticationPassword)) {
      setError('Enter both Email and Password, or leave both fields empty.');
      return;
    }
    const authentication = authenticationEmail.trim() && authenticationPassword
      ? { email: authenticationEmail.trim(), password: authenticationPassword }
      : undefined;
    setBusy(true); setError(''); setShowTestReport(false); setShowDeveloperReport(false);
    try {
      const startedJob = await testCaseApi.startExecutionJob(generation.generation_id, 'automated', authentication, executionProfile, testingScope);
      setExecutionJob(startedJob);
      if (workflowId) {
        saveTestProjectArtifacts(workflowId, generation, report, comparison, crawl);
        saveAutomationActivity(workflowId, { applicationUrl: applicationUrl.trim(), executionJobId: startedJob.job_id });
      }
    }
    catch (requestError) {
      if (requestError instanceof Error && requestError.message.includes('(404)') && workflowId && applicationUrl.trim()) {
        try {
          if (
            !crawl
            || crawl.crawl_status === 'crawl_blocked'
            || (crawl.pages_crawled === 0 && crawl.discovered_elements.length === 0)
          ) {
            throw new Error('At least one successfully crawled page is required before regenerating scripts.');
          }
          const refreshed = await testCaseApi.generateScripts(
            workflowId, applicationUrl.trim(), crawl.crawl_id,
          );
          setGeneration(refreshed);
          setSelectedScript(0);
          const startedJob = await testCaseApi.startExecutionJob(refreshed.generation_id, 'automated', authentication, executionProfile, testingScope);
          setExecutionJob(startedJob);
          saveTestProjectArtifacts(workflowId, refreshed, report, comparison, crawl);
          saveAutomationActivity(workflowId, { applicationUrl: applicationUrl.trim(), executionJobId: startedJob.job_id });
        } catch (retryError) { setError(friendlyError(retryError)); }
      } else { setError(friendlyError(requestError)); }
    }
    finally { setBusy(false); }
  };

  const finishHumanExecution = async () => {
    if (!humanSession) return;
    setBusy(true); setError('');
    try { setHumanSession(await testCaseApi.finishHumanExecution(humanSession.session_id)); }
    catch (requestError) { setError(friendlyError(requestError)); }
    finally { setBusy(false); }
  };

  const cancelHumanExecution = async () => {
    if (!humanSession) return;
    setBusy(true); setError('');
    try { setHumanSession(await testCaseApi.cancelHumanExecution(humanSession.session_id)); }
    catch (requestError) { setError(friendlyError(requestError)); }
    finally { setBusy(false); }
  };

  const executeGeneratedHumanScripts = async () => {
    if (!humanSession?.generation_id) return;
    if (Boolean(authenticationEmail.trim()) !== Boolean(authenticationPassword)) {
      setError('Enter both Email and Password, or leave both fields empty.');
      return;
    }
    const authentication = authenticationEmail.trim() && authenticationPassword
      ? { email: authenticationEmail.trim(), password: authenticationPassword }
      : undefined;
    setBusy(true); setError(''); setReport(null); setComparison(null); setShowTestReport(false); setShowDeveloperReport(false);
    try {
      const startedJob = await testCaseApi.startExecutionJob(
        humanSession.generation_id,
        'automated',
        authentication,
        executionProfile,
      );
      setExecutionJob(startedJob);
      if (workflowId) {
        saveTestProjectArtifacts(workflowId, generation, report, comparison, crawl);
        saveAutomationActivity(workflowId, { applicationUrl: applicationUrl.trim(), executionJobId: startedJob.job_id, humanSessionId: humanSession.session_id });
      }
    } catch (requestError) {
      setError(friendlyError(requestError));
    } finally {
      setBusy(false);
    }
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
  const hasUsableCrawl = Boolean(
    crawl
    && crawl.crawl_status !== 'crawl_blocked'
    && (crawl.pages_crawled > 0 || crawl.discovered_elements.length > 0),
  );
  const partialGeneration = generation?.crawl_report.status === 'crawl_incomplete';
  const skippedPages = (crawl?.crawl_report.pages_skipped ?? []).filter(
    (item) => /^https?:\/\//i.test(item.url),
  );
  return (
    <div className="space-y-6">
      <div>
        <p className="text-xs font-bold uppercase tracking-[0.2em] text-primary">Playwright automation</p>
        <h1 className="mt-2 text-2xl font-bold">{historyMode ? 'Saved scripts and execution results' : 'Generate and execute test scripts'}</h1>
        <p className="mt-1 text-sm text-muted-foreground">{historyMode ? 'Read-only output from the previously completed run. This view cannot start a crawl or execution.' : 'Playwright remains the primary engine. Optional Seacrawl recovery is limited to failed locator actions.'}</p>
      </div>

      {error && <div role="alert" className="rounded-xl border border-red-500/30 bg-red-500/10 p-4 text-sm text-red-600">{error}</div>}

      {!historyMode && (
        <section className="rounded-2xl border border-border bg-card p-5 space-y-5">

          {/* Application URL + action buttons */}
          <div>
            <label htmlFor="application-url" className="text-sm font-semibold">Deployed application URL</label>
            <div className="mt-2 flex flex-col gap-3 sm:flex-row">
              <input
                id="application-url"
                type="url"
                value={applicationUrl}
                onChange={(event) => { setApplicationUrl(event.target.value); setCrawl(null); setGeneration(null); }}
                placeholder="https://app.example.com"
                className="min-w-0 flex-1 rounded-lg border border-input bg-background px-3 py-2 text-sm outline-none focus:border-primary"
              />
              <button
                disabled={busy || (!crawlRunning && !applicationUrl.trim())}
                onClick={crawlApplication}
                className={`inline-flex items-center justify-center gap-2 rounded-lg px-4 py-2 text-sm font-semibold text-white disabled:opacity-50 ${crawlRunning ? 'bg-red-600 hover:bg-red-700' : 'bg-primary text-primary-foreground'}`}
              >
                {busy || crawlJob?.status === 'stopping' ? <LoaderCircle className="h-4 w-4 animate-spin" /> : <Play className="h-4 w-4" />}
                {crawlRunning ? 'Stop Crawling' : 'Crawl Application'}
              </button>
              <button
                disabled={busy || !hasUsableCrawl}
                onClick={generate}
                className="inline-flex items-center justify-center gap-2 rounded-lg bg-green-600 px-4 py-2 text-sm font-semibold text-white disabled:opacity-50"
              >
                <Play className="h-4 w-4" /> Generate Test Scripts
              </button>
            </div>
          </div>

          {/* Testing Scope */}
          <div className="grid gap-4 sm:grid-cols-2">
            <div className="space-y-1.5">
              <label htmlFor="testing-scope-select" className="text-sm font-semibold">Testing Scope</label>
              <select
                id="testing-scope-select"
                value={testingScope}
                onChange={(e) => setTestingScope(e.target.value as 'full_application' | 'specific_page')}
                className="w-full rounded-lg border border-input bg-background px-3 py-2 text-sm outline-none focus:border-primary"
              >
                <option value="full_application">Full Application — discover &amp; crawl all sub-links</option>
                <option value="specific_page">Specific Page — single target URL only</option>
              </select>
            </div>
            {testingScope === 'specific_page' && (
              <div className="space-y-1.5">
                <label htmlFor="target-page-url" className="text-sm font-semibold">
                  Target Page URL <span className="text-red-500">*</span>
                </label>
                <input
                  id="target-page-url"
                  type="url"
                  placeholder="https://app.example.com/dashboard"
                  value={targetPageUrl}
                  onChange={(e) => setTargetPageUrl(e.target.value)}
                  className="w-full rounded-lg border border-input bg-background px-3 py-2 text-sm outline-none focus:border-primary"
                />
                <p className="text-xs text-muted-foreground">Only this page will be crawled — no link-following.</p>
              </div>
            )}
          </div>

          {/* Authentication */}
          <div className="space-y-3">
            <div className="space-y-1.5">
              <label htmlFor="auth-mode-select" className="text-sm font-semibold">Authentication</label>
              <select
                id="auth-mode-select"
                value={authMode}
                onChange={(e) => setAuthMode(e.target.value as 'no_auth' | 'credentials' | 'existing_session')}
                className="w-full rounded-lg border border-input bg-background px-3 py-2 text-sm outline-none focus:border-primary sm:max-w-sm"
              >
                <option value="no_auth">No Authentication Required</option>
                <option value="credentials">Credentials — Identifier + Password</option>
                <option value="existing_session">Existing Session State</option>
              </select>
            </div>
            {authMode === 'credentials' && (
              <div className="grid gap-4 rounded-xl border border-border bg-muted/20 p-4 sm:grid-cols-2">
                <div className="space-y-1.5">
                  <label htmlFor="playwright-email" className="text-xs font-semibold">
                    Generic Identifier <span className="font-normal text-muted-foreground">(Email, Username, Employee ID…)</span>
                  </label>
                  <input
                    id="playwright-email"
                    type="text"
                    autoComplete="username"
                    placeholder="e.g. user@example.com or admin"
                    value={authenticationEmail}
                    onChange={(event) => setAuthenticationEmail(event.target.value)}
                    className="w-full rounded-lg border border-input bg-background px-3 py-2 text-sm outline-none focus:border-primary"
                  />
                </div>
                <div className="space-y-1.5">
                  <label htmlFor="playwright-password" className="text-xs font-semibold">Password</label>
                  <input
                    id="playwright-password"
                    type="password"
                    autoComplete="current-password"
                    placeholder="••••••••"
                    value={authenticationPassword}
                    onChange={(event) => setAuthenticationPassword(event.target.value)}
                    className="w-full rounded-lg border border-input bg-background px-3 py-2 text-sm outline-none focus:border-primary"
                  />
                </div>
                <p className="col-span-full text-xs text-muted-foreground">
                  Credentials are used only at runtime and are never stored in generated scripts or reports.
                </p>
              </div>
            )}
            {authMode === 'existing_session' && (
              <div className="space-y-1.5 rounded-xl border border-border bg-muted/20 p-4">
                <label htmlFor="auth-session" className="text-xs font-semibold">Session Storage State JSON</label>
                <textarea
                  id="auth-session"
                  rows={3}
                  placeholder='{"cookies": [...], "origins": [...]}'
                  value={sessionState}
                  onChange={(e) => setSessionState(e.target.value)}
                  className="w-full rounded-lg border border-input bg-background px-3 py-2 font-mono text-xs outline-none focus:border-primary"
                />
                <p className="text-xs text-muted-foreground">Paste a Playwright storage state JSON to reuse an existing authenticated session.</p>
              </div>
            )}
            {authMode === 'no_auth' && (
              <p className="text-xs text-muted-foreground">The application will be crawled without authentication. If a login wall is detected the crawl will be marked as blocked.</p>
            )}
          </div>

          {/* Execution profile */}
          <div className="space-y-1.5">
            <label htmlFor="execution-profile" className="text-sm font-semibold">Execution profile</label>
            <select
              id="execution-profile"
              value={executionProfile}
              onChange={(event) => setExecutionProfile(event.target.value as 'fast' | 'standard' | 'diagnostic')}
              className="w-full rounded-lg border border-input bg-background px-3 py-2 text-sm outline-none focus:border-primary sm:max-w-md"
            >
              <option value="fast">Fast — functional checks and failure screenshots</option>
              <option value="standard">Standard — visual checks and failure traces</option>
              <option value="diagnostic">Diagnostic — complete trace and evidence collection</option>
            </select>
            <p className="text-xs text-muted-foreground">Fast is recommended for routine runs. Use Diagnostic when investigating a failure.</p>
          </div>

        </section>
      )}

      {crawlRunning && <section className="rounded-2xl border border-primary/20 bg-primary/5 p-5">
        <div className="flex items-center gap-2 font-semibold text-primary"><LoaderCircle className="h-5 w-5 animate-spin" /> Crawling application</div>
        <p className="mt-2 text-sm text-muted-foreground">
          {crawlJob?.progress?.pages_completed ?? 0} pages scanned &middot;{' '}
          {crawlJob?.progress?.pages_remaining ?? 0} pages remaining &middot;{' '}
          {crawlJob?.progress?.elapsed_seconds ?? 0}s elapsed
        </p>
        <p className="mt-1 text-xs text-muted-foreground">Click Stop Crawling to preserve scanned pages and generate scripts immediately.</p>
      </section>}

      {executionRunning && <section className="rounded-2xl border border-green-500/20 bg-green-500/5 p-5">
        <div className="flex items-center gap-2 font-semibold text-green-700"><LoaderCircle className="h-5 w-5 animate-spin" /> Playwright execution running in the background</div>
        <p className="mt-2 text-sm text-muted-foreground">You can navigate to Generated Tests or any other page. Return here to view the same run and its completed report.</p>
      </section>}

      {crawl && (
        <section className={`rounded-2xl border p-5 ${crawl.crawl_status === 'crawl_blocked' ? 'border-red-500/30 bg-red-500/5' : 'border-green-500/30 bg-green-500/5'}`}>
          <div className={`flex items-center gap-2 font-semibold ${crawl.crawl_status === 'crawl_blocked' ? 'text-red-600' : 'text-green-600'}`}>
            {crawl.crawl_status === 'crawl_blocked' ? <XCircle className="h-5 w-5" /> : <CheckCircle2 className="h-5 w-5" />}
            {crawl.crawl_status.replaceAll('_', ' ')}
          </div>
          <p className="mt-2 text-sm text-muted-foreground">{crawl.pages_crawled} pages scanned · {crawl.elements_found} verified elements · {skippedPages.length} pages skipped</p>
          {crawl.crawl_report.failure_reason && <p className="mt-3 text-sm font-medium text-amber-700">{crawl.crawl_report.failure_reason}</p>}
          {crawl.crawl_status === 'crawl_incomplete' && hasUsableCrawl && <p className="mt-3 text-sm font-medium text-amber-700">The crawl stopped early, but scripts can still be generated from the successfully scanned pages.</p>}
          {crawl.crawl_report.blocked_url && <p className="mt-1 break-all text-xs text-muted-foreground">Blocked URL: {crawl.crawl_report.blocked_url}</p>}
          {crawl.crawl_report.recommended_corrective_action && <p className="mt-2 text-sm text-muted-foreground">Recommended action: {crawl.crawl_report.recommended_corrective_action}</p>}
          {skippedPages.length > 0 && <div className="mt-4 rounded-lg border border-amber-500/20 bg-background/50 p-3">
            <p className="text-sm font-semibold text-amber-700">Skipped pages ({skippedPages.length})</p>
            <ul className="mt-2 max-h-40 space-y-1 overflow-auto text-xs text-muted-foreground">
              {skippedPages.map((item, index) => <li key={`${item.url}-${index}`} className="break-all"><span className="font-medium text-foreground">{item.url}</span> — {item.reason}</li>)}
            </ul>
          </div>}
        </section>
      )}

      {generation && (
        <>
          <section className={`rounded-2xl border p-5 ${partialGeneration ? 'border-amber-500/30 bg-amber-500/5' : 'border-green-500/30 bg-green-500/5'}`}>
            <div className={`flex items-center gap-2 font-semibold ${partialGeneration ? 'text-amber-700' : 'text-green-600'}`}><CheckCircle2 className="h-5 w-5" /> {partialGeneration ? 'Scripts Generated from Successfully Crawled Pages' : 'Generated Test Scripts'}</div>
            <p className="mt-2 text-sm text-muted-foreground">{generation.page_title || generation.application_url} · {generation.application_map?.page_count ?? 1} pages · {generation.discovered_elements.length} verified interactive elements · {generation.scripts.length} scripts generated</p>
            {partialGeneration && <p className="mt-2 text-sm text-amber-700">These scripts use the pages and elements preserved before the crawl stopped.</p>}
          </section>

          {generation.scripts.length === 0
            ? <section className="rounded-2xl border border-border bg-card p-5 text-sm text-muted-foreground">No scripts available</section>
            : <div className="grid items-start gap-6 lg:grid-cols-[20rem_minmax(0,1fr)]">
            <aside className="flex max-h-[42rem] flex-col overflow-hidden rounded-2xl border border-border bg-card">
              <div className="shrink-0 border-b border-border px-4 py-3">
                <h2 className="font-semibold">Generated scripts</h2>
                <p className="mt-1 text-xs text-muted-foreground">{generation.scripts.length} scripts · Select one to view its code</p>
              </div>
              <div className="space-y-2 overflow-y-auto p-3">
                {generation.scripts.map((item, index) => <button key={item.script_id} onClick={() => setSelectedScript(index)} className={`w-full rounded-xl border p-3 text-left text-sm shadow-sm transition-all ${selectedScript === index ? 'border-primary/40 bg-primary/10 ring-1 ring-primary/20' : 'border-transparent hover:-translate-y-0.5 hover:border-border hover:bg-muted/60 hover:shadow-md'}`}><span className="block font-semibold">{item.name}</span><span className="mt-1 block truncate text-xs text-muted-foreground">{item.page_url || item.application_url}</span><span className="mt-2 block truncate font-mono text-[10px] text-primary">Script · {friendlyId('script', item.script_id)}</span></button>)}
              </div>
            </aside>
            {script && <section className="min-w-0 rounded-2xl border border-border bg-card">
              <div className="flex flex-wrap items-start justify-between gap-4 border-b border-border p-4"><div className="min-w-0"><h2 className="font-semibold">{script.name}</h2><p className="mt-1 break-all text-xs text-muted-foreground">{script.page_url || script.application_url}</p><TraceabilityChain className="mt-3" scenarioId={script.scenario_id} testCaseId={script.test_case_id} scriptId={script.script_id} /></div><button onClick={() => downloadFile(`${script.script_id}.py`, script.source, 'text/x-python')} className="inline-flex items-center gap-2 rounded-lg border border-border bg-background px-3 py-2 text-sm font-semibold shadow-sm transition hover:-translate-y-0.5 hover:bg-muted hover:shadow-md"><Download className="h-4 w-4" /> Download</button></div>
              <pre className="max-h-[36rem] overflow-auto p-4 text-xs">{script.source}</pre>
            </section>}
          </div>}

          {!historyMode && <section className="rounded-2xl border border-border bg-card p-5">
            <h2 className="font-semibold">Execution mode</h2>
            <div className="mt-3 flex flex-wrap gap-3">
              <label className="flex cursor-pointer items-center gap-2 rounded-lg border border-border px-4 py-3"><input type="radio" checked={mode === 'automated'} onChange={() => setMode('automated')} /> Automated execution (default)</label>
              <label className="flex cursor-pointer items-center gap-2 rounded-lg border border-border px-4 py-3"><input type="radio" checked={mode === 'manual'} onChange={() => setMode('manual')} /> Manual execution</label>
              <button disabled={busy || executionRunning || !script || Boolean(humanSession && ['waiting_for_human', 'recording', 'generating_scripts', 'validating_scripts', 'executing_scripts'].includes(humanSession.state))} onClick={execute} className="inline-flex items-center gap-2 rounded-lg bg-green-600 px-4 py-2 text-sm font-semibold text-white disabled:opacity-50">{busy || executionRunning ? <LoaderCircle className="h-4 w-4 animate-spin" /> : <Play className="h-4 w-4" />} {executionRunning ? 'Execution Running' : mode === 'automated' ? 'Execute with Playwright' : 'Start Manual Execution'}</button>
            </div>
            {humanSession && <div className="mt-4 rounded-xl border border-primary/20 bg-primary/5 p-4">
              <div className="grid gap-3 text-sm sm:grid-cols-3">
                <div><p className="text-xs text-muted-foreground">Session state</p><p className="mt-1 font-semibold capitalize">{humanSession.state.replaceAll('_', ' ')}</p></div>
                <div><p className="text-xs text-muted-foreground">Browser status</p><p className="mt-1 font-semibold capitalize">{humanSession.browser_status}</p></div>
                <div><p className="text-xs text-muted-foreground">Recorded actions</p><p className="mt-1 font-semibold">{humanSession.recorded_action_count}</p></div>
              </div>
              {humanSession.error && <p className="mt-3 text-sm text-red-600">{humanSession.error}</p>}
              <div className="mt-4 flex flex-wrap gap-3">
                <button disabled={busy || humanSession.state !== 'recording'} onClick={finishHumanExecution} className="rounded-lg bg-primary px-4 py-2 text-sm font-semibold text-primary-foreground disabled:opacity-50">Finish Recording</button>
                <button disabled={busy || !['waiting_for_human', 'recording'].includes(humanSession.state)} onClick={cancelHumanExecution} className="rounded-lg border border-red-500/30 px-4 py-2 text-sm font-semibold text-red-600 disabled:opacity-50">Cancel Session</button>
              </div>
            </div>}
          </section>}
          {humanSession?.generated_scripts?.length ? <section className="space-y-4 rounded-2xl border border-green-500/30 bg-green-500/5 p-5">
            <div className="flex flex-wrap items-start justify-between gap-3">
              <div>
                <p className="text-xs font-bold uppercase tracking-[0.2em] text-green-600">Human-recorded automation</p>
                <h2 className="mt-2 text-lg font-bold">Generated Manual Test Scripts</h2>
                <p className="mt-1 text-sm text-muted-foreground">{humanSession.generated_scripts.length} validated Playwright script{humanSession.generated_scripts.length === 1 ? '' : 's'} generated from {humanSession.recorded_action_count} recorded actions.</p>
              </div>
              <button disabled={busy || executionRunning || !humanSession.generation_id} onClick={executeGeneratedHumanScripts} className="inline-flex items-center gap-2 rounded-lg bg-green-600 px-4 py-2 text-sm font-semibold text-white disabled:opacity-50">{busy || executionRunning ? <LoaderCircle className="h-4 w-4 animate-spin" /> : <Play className="h-4 w-4" />} {executionRunning ? 'Execution Running' : 'Execute with Playwright'}</button>
            </div>
            {humanSession.generated_scripts.map((generatedScript, index) => <article key={`${generatedScript.script_id}-${index}`} className="overflow-hidden rounded-xl border border-border bg-card">
              <div className="flex flex-wrap items-center justify-between gap-3 border-b border-border p-4">
                <div className="min-w-0"><h3 className="font-semibold">{generatedScript.name}</h3><p className="mt-1 text-xs text-muted-foreground">{generatedScript.action_count} recorded actions</p><TraceabilityChain className="mt-3" scenarioId={generatedScript.scenario_id} testCaseId={generatedScript.test_case_id} scriptId={generatedScript.script_id} /></div>
                <button onClick={() => downloadFile(`${generatedScript.script_id}.py`, generatedScript.source, 'text/x-python')} className="inline-flex items-center gap-2 rounded-lg border border-border px-3 py-2 text-sm font-semibold hover:bg-muted"><Download className="h-4 w-4" /> Download script</button>
              </div>
              <pre className="max-h-[36rem] overflow-auto whitespace-pre p-4 text-xs">{generatedScript.source}</pre>
            </article>)}
          </section> : null}
        </>
      )}

      {report && <><ExecutionDashboard report={report} generation={generation} /><div className="flex flex-wrap justify-end gap-3">{report.mode === 'automated' && <button disabled={busy} onClick={compare} className="rounded-lg bg-primary px-5 py-3 text-sm font-bold text-primary-foreground disabled:opacity-50">Compare with Test Cases &amp; Scenarios</button>}<button onClick={() => setShowDeveloperReport((visible) => !visible)} className="inline-flex items-center gap-2 rounded-lg border border-primary/30 bg-primary/5 px-5 py-3 text-sm font-bold text-primary">{showDeveloperReport ? 'Hide Developer Report' : 'Developer Report'}</button><button onClick={() => setShowTestReport((visible) => !visible)} className="inline-flex items-center gap-2 rounded-lg border border-primary/30 bg-primary/5 px-5 py-3 text-sm font-bold text-primary">{showTestReport ? 'Hide QA Report' : 'QA Report'}</button></div>{showDeveloperReport && <DeveloperReports report={report} />}{showTestReport && <DetailedTestReport report={report} />}{comparison && <TraceabilityComparisonSection comparison={comparison} />}</>}
    </div>
  );
}

function ExecutionDashboard({ report, generation }: { report: ExecutionReport; generation: ScriptGeneration | null }) {
  const [preview, setPreview] = useState<{ path: string; name: string } | null>(null);
  return <section className="space-y-5">
    <div><p className="text-xs font-bold uppercase tracking-[0.2em] text-primary">Execution dashboard</p><h2 className="mt-2 text-xl font-bold">Run results</h2></div>
    <div className="grid gap-3 sm:grid-cols-3 lg:grid-cols-6">
      <Metric label="Total" value={report.total_scripts} /><Metric label="Passed" value={report.passed_scripts} /><Metric label="Failed" value={report.failed_scripts} /><Metric label="Skipped" value={report.skipped_scripts} /><Metric label="Seconds" value={report.execution_time_seconds} /><Metric label="Success" value={`${report.success_percentage}%`} />
    </div>
    <div className="space-y-3">{report.results.map((result, index) => {
      const failure = result.failure;
      const generatedScript = generation?.scripts.find((item) => item.script_id === result.script_id);
      const performedSteps = generatedScript?.executable_steps ?? [];
      const importantMessage = result.status === 'passed'
        ? `Completed successfully in ${result.duration_seconds}s.`
        : failure?.failure_reason || result.error_message || (result.status === 'skipped' ? 'Execution was skipped.' : 'Execution failed.');
      const evidence = [failure?.screenshot, failure?.dom_snapshot, failure?.trace_path, failure?.intelligence?.evidence?.screenshot, failure?.intelligence?.evidence?.dom_snapshot, failure?.intelligence?.evidence?.playwright_trace].filter((value): value is string => Boolean(value));
      return <details key={`${result.script_id}-${index}`} className="group overflow-hidden rounded-xl border border-border/80 bg-card shadow-sm transition open:border-primary/25 open:shadow-md">
        <summary className="flex cursor-pointer list-none items-start justify-between gap-4 p-4 marker:hidden sm:p-5">
          <div className="flex min-w-0 gap-3">
            <span className="mt-0.5 shrink-0">{result.status === 'passed' ? <CheckCircle2 className="h-5 w-5 text-green-500" /> : result.status === 'failed' ? <XCircle className="h-5 w-5 text-red-500" /> : <Play className="h-5 w-5 text-amber-500" />}</span>
            <div className="min-w-0"><h3 className="truncate font-semibold">{result.script_name}</h3><p className={`mt-1 line-clamp-2 text-sm ${result.status === 'failed' ? 'text-red-600 dark:text-red-300' : 'text-muted-foreground'}`}>{importantMessage}</p></div>
          </div>
          <div className="flex shrink-0 items-center gap-2"><StatusBadge status={result.status} /><span className="hidden text-xs font-semibold text-muted-foreground sm:inline">{result.duration_seconds}s</span><span aria-hidden className="text-lg text-muted-foreground transition-transform group-open:rotate-180">⌄</span></div>
        </summary>
        <div className="space-y-5 border-t border-border bg-muted/10 p-4 sm:p-5">
          <section><h4 className="text-sm font-semibold">Execution identity</h4><TraceabilityChain className="mt-3" scenarioId={result.scenario_id} testCaseId={result.test_case_id} scriptId={result.script_id} /></section>
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
            <Detail label="Execution status" value={result.status} />
            <Detail label="Duration" value={`${result.duration_seconds}s`} />
            <Detail label="Test case / script ID" value={`${friendlyId('case', result.test_case_id)} / ${friendlyId('script', result.script_id)}`} />
            <Detail label="Page URL" value={failure?.page_url} />
            <Detail label="Expected page URL" value={failure?.expected_page_url} />
            <Detail label="Page title" value={failure?.page_title} />
            <Detail label="Locator / XPath" value={failure?.exact_locator || failure?.intelligence?.evidence?.failed_locator} />
            <Detail label="Expected result" value={failure?.expected_result || failure?.intelligence?.expected_behavior} />
            <Detail label="Actual result" value={failure?.actual_result || failure?.intelligence?.actual_behavior} />
            <Detail label="Failure reason" value={failure?.failure_reason} />
            <Detail label="Error message" value={result.error_message} />
            <Detail label="HTTP response" value={failure?.http_response_status != null ? String(failure.http_response_status) : undefined} />
          </div>
          <section><h4 className="text-sm font-semibold">Steps performed</h4>{failure?.failed_action && <p className="mt-2 rounded-lg border border-border bg-background p-3 text-sm"><span className="font-medium">Failed action:</span> {failure.failed_action}</p>}{performedSteps.length ? <ol className="mt-2 list-decimal space-y-2 pl-5 text-sm text-muted-foreground">{performedSteps.map((step, stepIndex) => <li key={stepIndex} className="pl-1"><pre className="whitespace-pre-wrap break-words font-sans">{typeof step === 'string' ? step : JSON.stringify(step, null, 2)}</pre></li>)}</ol> : failure?.reproduction_steps?.length ? <ol className="mt-2 list-decimal space-y-1 pl-5 text-sm text-muted-foreground">{failure.reproduction_steps.map((step, stepIndex) => <li key={`${step}-${stepIndex}`}>{step}</li>)}</ol> : <p className="mt-2 text-sm text-muted-foreground">No step-level execution data was captured.</p>}</section>
          {evidence.length > 0 && <section><h4 className="text-sm font-semibold">Screenshots and evidence</h4><div className="mt-2 flex flex-wrap gap-2">{Array.from(new Set(evidence)).map((path, evidenceIndex) => { const name = path.split(/[\\/]/).pop() || `Evidence ${evidenceIndex + 1}`; const isImage = /\.(png|jpe?g|webp|gif)$/i.test(path); return isImage ? <button type="button" key={`${path}-${evidenceIndex}`} onClick={() => setPreview({ path, name })} className="max-w-full truncate rounded-lg border border-primary/30 bg-background px-3 py-2 text-xs font-medium text-primary hover:bg-primary/5">{name}</button> : <a key={`${path}-${evidenceIndex}`} href={automationArtifactUrl(path)} target="_blank" rel="noreferrer" className="max-w-full truncate rounded-lg border border-border bg-background px-3 py-2 text-xs font-medium text-primary hover:bg-muted">{name}</a>; })}</div></section>}
          {failure && <section><h4 className="text-sm font-semibold">Additional execution information</h4><pre className="mt-2 max-h-80 overflow-auto whitespace-pre-wrap break-words rounded-lg border border-border bg-background p-3 text-xs">{JSON.stringify({ failure_stage: failure.failure_stage, failure_category: failure.failure_category, locator_details: failure.locator_details, alternate_locators_attempted: failure.alternate_locators_attempted, locator_diagnosis: failure.locator_diagnosis, assertion_details: failure.assertion_details, navigation_details: failure.navigation_details, input_details: failure.input_details, application_state_details: failure.application_state_details, console_logs: failure.console_logs, network_errors: failure.network_errors, stack_trace: failure.stack_trace, traceability: result.traceability }, null, 2)}</pre></section>}
          {!failure && Object.keys(result.traceability ?? {}).length > 0 && <section><h4 className="text-sm font-semibold">Traceability details</h4><pre className="mt-2 max-h-64 overflow-auto whitespace-pre-wrap break-words rounded-lg border border-border bg-background p-3 text-xs">{JSON.stringify(result.traceability, null, 2)}</pre></section>}
        </div>
      </details>;
    })}</div>
    {preview && <div role="dialog" aria-modal="true" aria-label={`Screenshot preview: ${preview.name}`} className="fixed inset-0 z-[100] flex items-center justify-center bg-black/75 p-4" onClick={() => setPreview(null)}>
      <div className="relative flex max-h-[92vh] w-full max-w-6xl flex-col overflow-hidden rounded-2xl border border-white/20 bg-background shadow-2xl" onClick={(event) => event.stopPropagation()}>
        <div className="flex items-center justify-between gap-3 border-b border-border px-4 py-3"><p className="min-w-0 truncate text-sm font-semibold">{preview.name}</p><div className="flex shrink-0 items-center gap-2"><a href={automationArtifactPdfUrl(preview.path)} download className="inline-flex items-center gap-2 rounded-lg border border-border px-3 py-2 text-sm font-semibold text-primary hover:bg-muted"><Download className="h-4 w-4" /><span className="hidden sm:inline">Download as PDF</span></a><button type="button" onClick={() => setPreview(null)} aria-label="Close screenshot preview" className="rounded-lg border border-border p-2 text-muted-foreground hover:bg-muted hover:text-foreground"><X className="h-5 w-5" /></button></div></div>
        <div className="overflow-auto bg-black/5 p-3"><Image src={automationArtifactUrl(preview.path)} loader={({ src }) => src} alt={preview.name} width={1600} height={1000} unoptimized className="mx-auto h-auto max-h-[80vh] w-auto max-w-full object-contain" /></div>
      </div>
    </div>}
  </section>;
}

function Detail({ label, value }: { label: string; value?: string }) {
  return <div className="min-w-0 rounded-lg border border-border/70 bg-background p-3"><p className="text-xs font-medium text-muted-foreground">{label}</p><p className="mt-1 break-words text-sm font-medium capitalize">{value || 'Not available'}</p></div>;
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
    {report.classification && <ReportSection title="Evidence Classification"><div className="flex flex-wrap items-center gap-4"><ConfidenceRing value={report.confidence} label="Evidence confidence" size="sm" /><p className="font-semibold">{report.classification}{report.developer_issue_created ? ' · developer issue created' : ' · no developer issue created'}</p></div></ReportSection>}
    {failure && <ReportSection title="Failure Summary"><div className="grid gap-2 md:grid-cols-2">
      <p><strong>Category:</strong> {failure.failure_category}</p><p><strong>Stage:</strong> {failure.failure_stage ?? 'Unknown'}</p>
      <p><strong>Test case:</strong> {friendlyId('case', failure.test_case_id)} · {failure.test_case_title}</p><p><strong>Scenario:</strong> {String(failure.test_scenario?.title ?? (friendlyId('scenario', String(failure.test_scenario?.scenario_id ?? '')) || 'Not mapped'))}</p>
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

function DeveloperReports({ report }: { report: ExecutionReport }) {
  const developerReports = report.developer_execution_reports ?? [];
  return <section className="space-y-5 rounded-2xl border border-primary/25 bg-card p-5">
    <div className="flex flex-wrap items-center justify-between gap-3"><div><p className="text-xs font-bold uppercase tracking-[0.2em] text-primary">Developer implementation report</p><h2 className="mt-1 text-xl font-bold">Evidence-gated application behavior</h2></div><button onClick={() => downloadFile(`developer-report-${report.execution_id}.json`, JSON.stringify(developerReports, null, 2), 'application/json')} className="inline-flex items-center gap-2 rounded-lg border border-border px-4 py-2 text-sm font-semibold"><Download className="h-4 w-4" /> Download developer report</button></div>
    {developerReports.length ? developerReports.map((item, index) => <DeveloperReportCard key={`${item.issue_title}-${index}`} report={item} />) : <p className="rounded-lg border border-dashed border-border p-4 text-sm text-muted-foreground">No developer reports are available for this execution.</p>}
  </section>;
}

function DetailedTestReport({ report }: { report: ExecutionReport }) {
  const qaReports = report.qa_diagnostic_reports ?? [];
  return <section className="space-y-5 rounded-2xl border border-border bg-card p-5">
    <div className="flex flex-wrap items-center justify-between gap-3"><div><p className="text-xs font-bold uppercase tracking-[0.2em] text-primary">QA diagnostic report</p><h2 className="mt-1 text-xl font-bold">Automation and technical evidence</h2></div><button onClick={() => downloadFile(`qa-diagnostic-${report.execution_id}.json`, JSON.stringify(qaReports, null, 2), 'application/json')} className="inline-flex items-center gap-2 rounded-lg border border-border px-4 py-2 text-sm font-semibold"><Download className="h-4 w-4" /> Download QA report</button></div>
    {qaReports.map((item, index) => <QaDiagnosticCard key={`${item.script_id}-${index}`} report={item} />)}
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
  return <article className="space-y-3 rounded-xl border border-border bg-muted/20 p-4 text-sm shadow-sm">
    <div className="flex flex-wrap items-center justify-between gap-2"><EntityId kind="script" value={report.script_id} /><StatusBadge status={report.status} /></div>
    {report.classification && <p className="text-xs font-semibold text-muted-foreground">Classification: {report.classification}</p>}
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
  matched_scripts?: string[];
};

function TraceabilityComparisonSection({ comparison }: { comparison: TraceabilityComparisonReport }) {
  const [filter, setFilter] = useState<'missing' | 'partial' | 'covered' | 'all'>('missing');

  const allArtifacts: ComparisonDisplayItem[] = [
    ...(comparison.scenario_coverage || []),
    ...(comparison.test_case_coverage || []),
  ];

  const getStatus = (item: { status?: string; gap_type?: string; coverage_percentage?: number }) => {
    if (item.status) return item.status;
    if (item.gap_type === 'uncovered') return 'missing';
    if (item.gap_type === 'partially covered' || item.gap_type === 'partially_covered') return 'partial';
    const percentage = item.coverage_percentage ?? 0;
    if (percentage > (comparison.summary.thresholds?.covered_above ?? 60)) return 'covered';
    if (percentage >= (comparison.summary.thresholds?.missing_below ?? 20)) return 'partial';
    return 'missing';
  };
  const totalArtifacts = allArtifacts.length || comparison.summary.total_artifacts;
  const coveredCount = allArtifacts.length
    ? allArtifacts.filter((item) => getStatus(item) === 'covered').length
    : comparison.summary.covered;
  const partialCount = allArtifacts.length
    ? allArtifacts.filter((item) => getStatus(item) === 'partial').length
    : (comparison.summary.partial ?? 0);
  const missingCount = allArtifacts.length
    ? allArtifacts.filter((item) => getStatus(item) === 'missing').length
    : comparison.summary.missing;
  const coveragePercentage = comparison.summary.coverage_percentage;

  const getFilteredItems = () => {
    if (filter === 'missing') {
      return comparison.gaps.filter((g) => getStatus(g) === 'missing');
    }
    if (filter === 'covered') {
      return allArtifacts.filter((a) => getStatus(a) === 'covered');
    }
    if (filter === 'partial') {
      return allArtifacts.filter((a) => getStatus(a) === 'partial');
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
          <p className="mt-1 text-xs text-muted-foreground">
            Covered &gt; {comparison.summary.thresholds?.covered_above ?? 60}% · Partially Covered {comparison.summary.thresholds?.missing_below ?? 20}–{comparison.summary.thresholds?.covered_above ?? 60}% · Missing Evidence &lt; {comparison.summary.thresholds?.missing_below ?? 20}%
          </p>
        </div>
        <div className="flex items-center gap-2">
          <span className="rounded-xl border border-primary/20 bg-primary/10 px-4 py-2 text-sm font-bold text-primary">
            Overall Coverage: {coveragePercentage}%
          </span>
        </div>
      </div>

      {/* KPI Cards */}
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-4">
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
          onClick={() => setFilter('partial')}
          className={`rounded-xl border p-4 text-left transition ${
            filter === 'partial' ? 'border-amber-500 bg-amber-500/10 ring-1 ring-amber-500' : 'border-border bg-background hover:bg-muted'
          }`}
        >
          <p className="text-xs font-semibold uppercase text-amber-600 dark:text-amber-400">Partially Covered</p>
          <p className="mt-1 text-2xl font-bold text-amber-600 dark:text-amber-400">{partialCount}</p>
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
          { key: 'partial', label: `Partially Covered (${partialCount})` },
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
            const isTestCase = comparison.test_case_coverage.some((artifact) => artifact.id === id);

            return (
              <article
                key={id}
                className={`rounded-xl border p-4 text-sm shadow-sm transition ${
                  status === 'missing'
                    ? 'border-red-500/40 bg-red-500/5'
                    : status === 'partial'
                      ? 'border-amber-500/40 bg-amber-500/5'
                      : 'border-green-500/40 bg-green-500/5'
                }`}
              >
                <div className="flex flex-wrap items-center justify-between gap-2 border-b border-border/40 pb-2">
                  <div className="flex items-center gap-2">
                    {status === 'missing' && (
                      <span className="inline-flex items-center gap-1.5 rounded-full border border-red-500/40 bg-red-500/15 px-3 py-1 text-xs font-bold text-red-700 dark:text-red-300">
                        <XCircle className="h-3.5 w-3.5" /> MISSING EVIDENCE ({coveragePct}%)
                      </span>
                    )}
                    {status === 'covered' && (
                      <span className="inline-flex items-center gap-1.5 rounded-full border border-green-500/40 bg-green-500/15 px-3 py-1 text-xs font-bold text-green-700 dark:text-green-300">
                        <CheckCircle2 className="h-3.5 w-3.5" /> COVERED ({coveragePct}%)
                      </span>
                    )}
                    {status === 'partial' && (
                      <span className="inline-flex items-center gap-1.5 rounded-full border border-amber-500/40 bg-amber-500/15 px-3 py-1 text-xs font-bold text-amber-700 dark:text-amber-300">
                        PARTIALLY COVERED ({coveragePct}%)
                      </span>
                    )}

                    <EntityId kind={isTestCase ? 'case' : 'scenario'} value={id} compact />
                  </div>

                  <span className="text-xs font-bold uppercase tracking-wider">
                    Label: <strong className={status === 'missing' ? 'text-red-600 dark:text-red-400' : status === 'partial' ? 'text-amber-600 dark:text-amber-400' : 'text-green-600 dark:text-green-400'}>{status}</strong>
                  </span>
                </div>

                <h3 className="mt-3 font-bold text-base">{title}</h3>

                <div className="mt-2 text-xs text-muted-foreground">
                  {(item.classification || item.gap_type) && status !== 'covered' && (
                    <p className={`mb-1 font-semibold ${status === 'partial' ? 'text-amber-600' : 'text-red-600'}`}>
                      Classification: {(item.classification || item.gap_type || '').replaceAll('_', ' ')}
                    </p>
                  )}
                  <p className="font-medium">{details}</p>
                  {item.matched_scripts?.length ? <div className="mt-3"><p className="mb-2 font-semibold uppercase tracking-wide">Matched test scripts</p><div className="flex flex-wrap gap-2">{item.matched_scripts.map((scriptId, scriptIndex) => <EntityId key={`${scriptId}-${scriptIndex}`} kind="script" value={scriptId} compact />)}</div></div> : null}
                </div>
              </article>
            );
          })
        )}
      </div>
    </section>
  );
}
