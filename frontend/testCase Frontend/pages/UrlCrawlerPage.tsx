'use client';

import { useEffect, useState } from 'react';
import {
  ArrowRight,
  CheckCircle2,
  ChevronDown,
  ChevronRight,
  Download,
  FileCode2,
  Globe,
  LoaderCircle,
  Map,
  Sparkles,
  Square,
  Layers,
} from 'lucide-react';
import { testCaseApi } from '../services/testCaseApi';
import { EntityId } from '../components/TraceabilityUI';
import type { CrawlGenerationResponse, CrawlJob } from '../types';
import { downloadFile, friendlyError, friendlyId, registerFriendlyIds, setActiveProjectId } from '../utils';

function downloadAllAsZip(result: CrawlGenerationResponse) {
  const combined = result.scripts
    .map((s) => `# ===== ${s.script_id}.py =====\n\n${s.source}`)
    .join('\n\n\n');
  downloadFile('all_crawl_scripts.py', combined, 'text/x-python');
}

export function UrlCrawlerPage() {
  const [url, setUrl] = useState('');
  const [pageLimit, setPageLimit] = useState(250);
  const [depthLimit, setDepthLimit] = useState(15);
  const [maxExecutionTime, setMaxExecutionTime] = useState(300);
  const [showAdvanced, setShowAdvanced] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [result, setResult] = useState<CrawlGenerationResponse | null>(null);
  const [crawlJob, setCrawlJob] = useState<CrawlJob | null>(null);
  const [selectedScript, setSelectedScript] = useState(0);
  const isCrawling = Boolean(
    crawlJob && ['queued', 'running', 'stopping'].includes(crawlJob.status),
  );

  useEffect(() => {
    if (!crawlJob?.job_id || !isCrawling) return;
    let disposed = false;
    let consecutiveFailures = 0;
    let pollingErrorVisible = false;
    let timer: number | undefined;
    const poll = async () => {
      try {
        const current = await testCaseApi.getCrawlJob(crawlJob.job_id);
        if (disposed) return;
        consecutiveFailures = 0;
        if (pollingErrorVisible) {
          setError('');
          pollingErrorVisible = false;
        }
        setCrawlJob(current);
        if (current.status === 'completed' && current.result) {
          setResult(current.result);
          setSelectedScript(0);
        } else if (current.status === 'failed') {
          setError(current.error || 'The crawl could not be completed.');
        }
      } catch (err) {
        if (disposed) return;
        consecutiveFailures += 1;
        if (consecutiveFailures >= 3) {
          pollingErrorVisible = true;
          setError(`Crawl status updates were interrupted. The crawl is still running and reconnection will continue automatically. ${friendlyError(err)}`);
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
  }, [crawlJob?.job_id, isCrawling]);

  const [testingScope, setTestingScope] = useState<'full_application' | 'specific_page'>('full_application');
  const [authMode, setAuthMode] = useState<'no_auth' | 'credentials' | 'existing_session'>('no_auth');
  const [identifier, setIdentifier] = useState('');
  const [password, setPassword] = useState('');
  const [sessionState, setSessionState] = useState('');

  const handleCrawl = async (event: React.FormEvent) => {
    event.preventDefault();
    if (isCrawling && crawlJob) {
      if (busy) return;
      setBusy(true);
      setError('');
      try {
        setCrawlJob(await testCaseApi.stopCrawlJob(crawlJob.job_id));
      } catch (err) {
        setError(friendlyError(err));
      } finally {
        setBusy(false);
      }
      return;
    }
    const trimmed = url.trim();
    if (!trimmed || busy) return;
    setBusy(true);
    setError('');
    setResult(null);
    setSelectedScript(0);

    let authPayload: any = undefined;
    if (authMode === 'credentials') {
      authPayload = {
        auth_mode: 'credentials',
        identifier: identifier.trim() || undefined,
        password: password || undefined,
      };
    } else if (authMode === 'existing_session') {
      let parsedSess: any = sessionState;
      try { parsedSess = JSON.parse(sessionState); } catch {}
      authPayload = {
        auth_mode: 'existing_session',
        session_state: parsedSess,
      };
    }

    try {
      const job = await testCaseApi.startCrawlJob(trimmed, {
        page_limit: pageLimit,
        depth_limit: depthLimit,
        max_execution_time_seconds: maxExecutionTime,
        testing_scope: testingScope,
        authentication: authPayload,
      });
      setCrawlJob(job);
    } catch (err) {
      setError(friendlyError(err));
    } finally {
      setBusy(false);
    }
  };

  const script = result?.scripts[selectedScript];
  const partialResult = result?.crawl_status === 'crawl_incomplete';
  useEffect(() => {
    const scope = result?.crawl_id || 'crawler';
    setActiveProjectId(scope);
    const scripts = result?.scripts ?? [];
    registerFriendlyIds('script', scripts.map((script) => script.script_id), scope);
    registerFriendlyIds('scenario', scripts.map((script) => script.scenario_id), scope);
    registerFriendlyIds('case', scripts.map((script) => script.test_case_id), scope);
  }, [result]);

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="rounded-2xl border border-primary/20 bg-gradient-to-br from-primary/10 via-card to-card p-6 sm:p-8">
        <div className="flex items-start gap-4">
          <div className="rounded-xl bg-primary p-3 text-primary-foreground">
            <Globe className="h-6 w-6" />
          </div>
          <div>
            <p className="text-xs font-bold uppercase tracking-[0.2em] text-primary">
              URL Crawler
            </p>
            <h1 className="mt-2 text-2xl font-bold sm:text-3xl">
              Crawl any URL &middot; Generate test scripts
            </h1>
            <p className="mt-2 max-w-3xl text-sm text-muted-foreground">
              Enter a deployed application URL. The crawler will visit every reachable page,
              discover interactive elements, and generate a Playwright test script for each page
              &mdash; no user stories or workflow required.
            </p>
          </div>
        </div>
      </div>

      {/* Crawl Form */}
      <form onSubmit={handleCrawl} className="space-y-4">
        {error && (
          <div role="alert" className="rounded-xl border border-red-500/30 bg-red-500/10 p-4 text-sm text-red-600 dark:text-red-300">
            {error}
          </div>
        )}

        <div className="rounded-2xl border border-border bg-card p-5 shadow-sm sm:p-6 space-y-4">
          <div className="space-y-2">
            <label htmlFor="crawl-url" className="text-sm font-semibold">
              Application URL <span className="text-red-500">*</span>
            </label>
            <div className="flex flex-col gap-3 sm:flex-row">
              <input
                id="crawl-url"
                type="url"
                required
                value={url}
                onChange={(e) => setUrl(e.target.value)}
                placeholder="https://your-app.example.com"
                className="min-w-0 flex-1 rounded-xl border border-input bg-background px-4 py-3 text-sm outline-none focus:border-primary focus:ring-2 focus:ring-primary/20 transition"
              />
              <button
                type="submit"
                disabled={busy || (!isCrawling && !url.trim())}
                id="crawl-submit-btn"
                className={`inline-flex min-w-52 items-center justify-center gap-2 rounded-xl px-6 py-3 text-sm font-bold text-white shadow-lg transition disabled:cursor-not-allowed disabled:opacity-60 ${isCrawling ? 'bg-red-600 shadow-red-600/20 hover:bg-red-700' : 'bg-primary text-primary-foreground shadow-primary/20 hover:bg-primary/90'}`}
              >
                {isCrawling ? (
                  <>
                    {busy || crawlJob?.status === 'stopping'
                      ? <LoaderCircle className="h-4 w-4 animate-spin" />
                      : <Square className="h-4 w-4" />}
                    {crawlJob?.status === 'stopping' ? 'Stopping&hellip;' : 'Stop Crawling'}
                  </>
                ) : (
                  <>
                    <Sparkles className="h-4 w-4" />
                    Start Crawling
                    <ArrowRight className="h-4 w-4" />
                  </>
                )}
              </button>
            </div>
          </div>
          <div className="grid gap-4 sm:grid-cols-2">
            <div className="space-y-2">
              <label htmlFor="testing-scope-select" className="text-sm font-semibold">
                Testing Scope
              </label>
              <select
                id="testing-scope-select"
                value={testingScope}
                onChange={(e) => setTestingScope(e.target.value as any)}
                className="w-full rounded-xl border border-input bg-background px-3 py-2.5 text-sm outline-none focus:border-primary transition"
              >
                <option value="full_application">Full Application (Discover & Crawl Sub-links)</option>
                <option value="specific_page">Specific Page Only (Single Target URL)</option>
              </select>
            </div>

            <div className="space-y-2">
              <label htmlFor="auth-mode-select" className="text-sm font-semibold">
                Authentication Option
              </label>
              <select
                id="auth-mode-select"
                value={authMode}
                onChange={(e) => setAuthMode(e.target.value as any)}
                className="w-full rounded-xl border border-input bg-background px-3 py-2.5 text-sm outline-none focus:border-primary transition"
              >
                <option value="no_auth">No Authentication Required</option>
                <option value="credentials">Credentials (Identifier + Password)</option>
                <option value="existing_session">Existing Session State</option>
              </select>
            </div>
          </div>

          {authMode === 'credentials' && (
            <div className="grid gap-4 rounded-xl border border-border bg-muted/20 p-4 sm:grid-cols-2">
              <div className="space-y-1.5">
                <label htmlFor="auth-identifier" className="text-xs font-semibold">
                  Generic Identifier <span className="text-muted-foreground font-normal">(Email, Username, Employee ID, etc.)</span>
                </label>
                <input
                  id="auth-identifier"
                  type="text"
                  placeholder="e.g. user@example.com or admin"
                  value={identifier}
                  onChange={(e) => setIdentifier(e.target.value)}
                  className="w-full rounded-lg border border-input bg-background px-3 py-2 text-sm outline-none focus:border-primary transition"
                />
              </div>
              <div className="space-y-1.5">
                <label htmlFor="auth-password" className="text-xs font-semibold">
                  Password
                </label>
                <input
                  id="auth-password"
                  type="password"
                  placeholder="••••••••"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  className="w-full rounded-lg border border-input bg-background px-3 py-2 text-sm outline-none focus:border-primary transition"
                />
              </div>
            </div>
          )}

          {authMode === 'existing_session' && (
            <div className="space-y-1.5 rounded-xl border border-border bg-muted/20 p-4">
              <label htmlFor="auth-session" className="text-xs font-semibold">
                Session Storage State JSON
              </label>
              <textarea
                id="auth-session"
                rows={3}
                placeholder='{"cookies": [...], "origins": [...]}'
                value={sessionState}
                onChange={(e) => setSessionState(e.target.value)}
                className="w-full rounded-lg border border-input bg-background px-3 py-2 font-mono text-xs outline-none focus:border-primary transition"
              />
            </div>
          )}

          <button
            type="button"
            onClick={() => setShowAdvanced((v) => !v)}
            className="flex items-center gap-2 text-sm text-muted-foreground hover:text-foreground transition"
          >
            {showAdvanced ? <ChevronDown className="h-4 w-4" /> : <ChevronRight className="h-4 w-4" />}
            Advanced options
          </button>

          {showAdvanced && (
            <div className="grid gap-4 rounded-xl border border-border bg-muted/30 p-4 sm:grid-cols-3">
              <div className="space-y-2">
                <label htmlFor="page-limit" className="text-sm font-semibold">
                  Page limit <span className="text-muted-foreground font-normal">(1-500)</span>
                </label>
                <input
                  id="page-limit"
                  type="number"
                  min={1}
                  max={500}
                  value={pageLimit}
                  onChange={(e) => setPageLimit(Number(e.target.value))}
                  className="w-full rounded-lg border border-input bg-background px-3 py-2 text-sm outline-none focus:border-primary transition"
                />
                <p className="text-xs text-muted-foreground">Max pages the crawler will visit</p>
              </div>
              <div className="space-y-2">
                <label htmlFor="depth-limit" className="text-sm font-semibold">
                  Depth limit <span className="text-muted-foreground font-normal">(1-20)</span>
                </label>
                <input
                  id="depth-limit"
                  type="number"
                  min={1}
                  max={20}
                  value={depthLimit}
                  onChange={(e) => setDepthLimit(Number(e.target.value))}
                  className="w-full rounded-lg border border-input bg-background px-3 py-2 text-sm outline-none focus:border-primary transition"
                />
                <p className="text-xs text-muted-foreground">How many navigation levels deep</p>
              </div>
              <div className="space-y-2">
                <label htmlFor="crawl-timeout" className="text-sm font-semibold">
                  Hard timeout <span className="text-muted-foreground font-normal">(30-3600 seconds)</span>
                </label>
                <input
                  id="crawl-timeout"
                  type="number"
                  min={30}
                  max={3600}
                  value={maxExecutionTime}
                  onChange={(e) => setMaxExecutionTime(Number(e.target.value))}
                  className="w-full rounded-lg border border-input bg-background px-3 py-2 text-sm outline-none focus:border-primary transition"
                />
                <p className="text-xs text-muted-foreground">Crawler stops only when this hard limit is reached</p>
              </div>
            </div>
          )}
        </div>
      </form>

      {isCrawling && (
        <div className="rounded-2xl border border-primary/20 bg-primary/5 p-8 text-center space-y-4">
          <LoaderCircle className="mx-auto h-10 w-10 animate-spin text-primary" />
          <div>
            <p className="font-semibold text-primary">Crawling in progress&hellip;</p>
            <p className="mt-1 text-sm text-muted-foreground">
              Playwright is visiting every page, discovering elements, and building test scripts.
              Stop at any time to generate scripts from the pages collected so far.
            </p>
            {crawlJob?.progress && <p className="mt-2 text-xs text-muted-foreground">
              {crawlJob.progress.pages_completed ?? 0} pages completed ·{' '}
              {crawlJob.progress.pages_remaining ?? 0} remaining ·{' '}
              {crawlJob.progress.elapsed_seconds ?? 0}s elapsed
            </p>}
          </div>
          <div className="flex justify-center gap-6 text-xs text-muted-foreground">
            <span>URL validated</span>
            <span className="animate-pulse">Discovering pages</span>
            <span className="opacity-40">Generating scripts</span>
          </div>
        </div>
      )}

      {result && !busy && (
        <div className="space-y-6">
          <div className={`rounded-2xl border p-5 ${partialResult ? 'border-amber-500/30 bg-amber-500/5' : 'border-green-500/30 bg-green-500/5'}`}>
            <div className="flex flex-wrap items-center justify-between gap-4">
              <div className="flex items-center gap-3">
                <CheckCircle2 className={`h-5 w-5 ${partialResult ? 'text-amber-600' : 'text-green-600'}`} />
                <div>
                  <p className={`font-semibold ${partialResult ? 'text-amber-700 dark:text-amber-400' : 'text-green-700 dark:text-green-400'}`}>
                    {partialResult ? 'Scripts generated from available pages' : 'Crawl complete'} &mdash; {result.scripts.length} scripts generated
                  </p>
                  <p className="mt-0.5 text-sm text-muted-foreground">
                    {result.page_title ?? result.url} &middot; {result.pages_crawled} pages &middot; {result.elements_found} elements discovered
                  </p>
                  {partialResult && (
                    <div className="mt-2 space-y-1 text-sm text-amber-700 dark:text-amber-300">
                      <p>Scripts below were generated from all pages successfully crawled.</p>
                      <p>
                        {result.crawl_report.progress?.pages_discovered ?? result.pages_crawled} discovered ·{' '}
                        {result.crawl_report.progress?.pages_completed ?? result.pages_crawled} completed ·{' '}
                        {result.crawl_report.progress?.pages_remaining ?? result.crawl_report.remaining_crawl_queue.length} remaining ·{' '}
                        depth {result.crawl_report.progress?.current_crawl_depth ?? 0} ·{' '}
                        elapsed {result.crawl_report.progress?.elapsed_seconds ?? 0}s
                        {result.crawl_report.progress?.estimated_completion_seconds != null
                          ? ` · estimated ${result.crawl_report.progress.estimated_completion_seconds}s remaining`
                          : ''}
                      </p>
                    </div>
                  )}
                </div>
              </div>
              {result.scripts.length > 0 && <button
                onClick={() => downloadAllAsZip(result)}
                id="download-all-btn"
                className="inline-flex items-center gap-2 rounded-xl border border-border bg-card px-4 py-2 text-sm font-semibold shadow-sm hover:bg-muted transition"
              >
                <Download className="h-4 w-4" />
                Download all scripts
              </button>}
            </div>
          </div>

          <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
            {[
              { label: 'Pages crawled', value: result.pages_crawled, icon: <Map className="h-4 w-4" /> },
              { label: 'Elements found', value: result.elements_found, icon: <Layers className="h-4 w-4" /> },
              { label: 'Scripts generated', value: result.scripts.length, icon: <FileCode2 className="h-4 w-4" /> },
              { label: 'Depth limit', value: depthLimit, icon: <Globe className="h-4 w-4" /> },
            ].map((stat) => (
              <div key={stat.label} className="rounded-xl border border-border bg-card p-4 text-center shadow-sm">
                <div className="flex justify-center text-primary mb-1">{stat.icon}</div>
                <p className="text-2xl font-bold">{stat.value}</p>
                <p className="text-xs text-muted-foreground mt-1">{stat.label}</p>
              </div>
            ))}
          </div>

          <div className="grid gap-6 lg:grid-cols-[18rem_1fr]">
            <aside className="space-y-1 rounded-2xl border border-border bg-card p-3 max-h-[40rem] overflow-y-auto">
              <p className="px-2 py-1 text-xs font-bold uppercase tracking-widest text-muted-foreground">
                Generated scripts
              </p>
              {result.scripts.map((item, index) => (
                <button
                  key={item.script_id}
                  id={`script-btn-${index}`}
                  onClick={() => setSelectedScript(index)}
                  className={`w-full rounded-xl p-3 text-left text-sm transition ${
                    selectedScript === index
                      ? 'bg-primary text-primary-foreground shadow-md'
                      : 'hover:bg-muted'
                  }`}
                >
                  <span className="flex items-center gap-2 font-semibold">
                    <FileCode2 className="h-3.5 w-3.5 shrink-0" />
                    {item.name}
                  </span>
                  <span className="mt-1 block truncate text-xs opacity-70">
                    {item.page_url ?? item.test_case_id}
                  </span>
                  <span className="mt-2 block truncate font-mono text-[10px] opacity-80">Test Script ID · {friendlyId('script', item.script_id)}</span>
                </button>
              ))}
            </aside>

            {script && (
              <section className="min-w-0 rounded-2xl border border-border bg-card overflow-hidden">
                <div className="flex items-center justify-between gap-3 border-b border-border bg-muted/30 p-4">
                  <div className="min-w-0">
                    <h2 className="font-semibold">{script.name}</h2>
                    <p className="mt-0.5 truncate text-xs text-muted-foreground">{script.page_url}</p>
                    <div className="mt-2"><EntityId kind="script" value={script.script_id} /></div>
                  </div>
                  <button
                    id={`download-script-${script.script_id}`}
                    onClick={() => downloadFile(`${script.script_id}.py`, script.source, 'text/x-python')}
                    className="inline-flex items-center gap-2 rounded-lg border border-border bg-background px-3 py-2 text-sm font-semibold hover:bg-muted transition"
                  >
                    <Download className="h-4 w-4" />
                    Download
                  </button>
                </div>
                <pre
                  id="script-preview"
                  className="max-h-[36rem] overflow-auto p-5 text-xs leading-relaxed font-mono bg-background"
                >
                  {script.source}
                </pre>
              </section>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
