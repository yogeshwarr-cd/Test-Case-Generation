'use client';

import React, { useEffect, useMemo, useState } from 'react';
import Link from 'next/link';
import { useParams } from 'next/navigation';
import { motion, AnimatePresence } from 'framer-motion';
import {
  ArrowLeft,
  CheckCircle2,
  Clock3,
  Code2,
  Copy,
  Download,
  FileCheck2,
  FileText,
  GitBranch,
  PlayCircle,
  Plus,
  ShieldCheck,
  Sparkles,
  Zap
} from 'lucide-react';
import { api } from '@/services/api';
import { useWorkspaceStore } from '@/store/workspaceStore';
import { testCaseApi } from '@/testCase Frontend/services/testCaseApi';
import { useTestCaseWorkflowStore, loadTestProjectArtifacts, saveTestProjectArtifacts, type SavedTestProjectArtifacts } from '@/testCase Frontend/store/workflowStore';
import type { WorkflowResult } from '@/testCase Frontend/types';

type ArtifactTab =
  | 'documents'
  | 'scenarios'
  | 'testcases'
  | 'scripts'
  | 'execution'
  | 'traceability'
  | 'history'
  | 'validation';

export default function DedicatedProjectWorkspacePage() {
  const { projectId } = useParams<{ projectId: string }>();
  const workspace = useWorkspaceStore((store) => store.workspaces.find((item) => item.id === projectId));
  const { projects, hydrate } = useTestCaseWorkflowStore();
  const testProject = projects.find((p) => p.projectId === projectId || p.workflowId === projectId);

  const [state, setState] = useState<Record<string, unknown>>({});
  const [workflowResult, setWorkflowResult] = useState<WorkflowResult | null>(null);
  const [savedArtifacts, setSavedArtifacts] = useState<SavedTestProjectArtifacts | null>(null);
  const [executionStatus, setExecutionStatus] = useState('not_run');
  const [activeTab, setActiveTab] = useState<ArtifactTab>('scenarios');
  const [copiedScriptIndex, setCopiedScriptIndex] = useState<number | null>(null);

  useEffect(() => hydrate(), [hydrate]);

  useEffect(() => {
    if (!projectId) return;
    api.getWorkflowState(projectId)
      .then((res) => setState(res.state || {}))
      .catch(() => setState({}));
  }, [projectId]);

  useEffect(() => {
    const workflowId = testProject?.workflowId;
    if (!workflowId) {
      queueMicrotask(() => {
        setWorkflowResult(null);
        setSavedArtifacts(null);
        setExecutionStatus('not_run');
      });
      return;
    }
    let disposed = false;
    const refresh = async () => {
      let artifacts = loadTestProjectArtifacts(workflowId);
      let currentExecutionStatus = artifacts?.report?.execution_status || 'not_run';
      if (artifacts?.crawlJobId) {
        try {
          const crawlJob = await testCaseApi.getWorkflowCrawlJob(artifacts.crawlJobId);
          artifacts = { ...artifacts, crawl: crawlJob.crawl ?? artifacts.crawl, generation: crawlJob.generation ?? artifacts.generation };
        } catch {}
      }
      if (artifacts?.executionJobId) {
        try {
          const executionJob = await testCaseApi.getExecutionJob(artifacts.executionJobId);
          currentExecutionStatus = executionJob.status;
          artifacts = { ...artifacts, report: executionJob.report ?? artifacts.report };
        } catch {}
      }
      if (artifacts) saveTestProjectArtifacts(workflowId, artifacts.generation, artifacts.report, artifacts.comparison, artifacts.crawl);
      if (!disposed) {
        setSavedArtifacts(artifacts);
        setExecutionStatus(currentExecutionStatus);
      }
      try {
        const result = await testCaseApi.getWorkflowResult(workflowId);
        if (!disposed && result.project_id === (testProject.projectId || projectId)) setWorkflowResult(result);
      } catch {
        if (!disposed) setWorkflowResult(null);
      }
    };
    void refresh();
    const timer = window.setInterval(refresh, 3000);
    return () => { disposed = true; window.clearInterval(timer); };
  }, [projectId, testProject?.projectId, testProject?.workflowId]);

  // Every collection below is scoped to the selected project. There are no demo fallbacks.
  const documents = useMemo(() => {
    const raw = (state.documents || state.uploaded_documents || state.source_documents) as Array<Record<string, unknown>> | undefined;
    return raw ?? [];
  }, [state]);

  const testScenarios = useMemo(() => {
    if (workflowResult?.scenarios?.length) return workflowResult.scenarios as unknown as Array<Record<string, unknown>>;
    return ((state.test_scenarios || state.scenarios) as Array<Record<string, unknown>> | undefined) ?? [];
  }, [state, workflowResult]);

  const testCases = useMemo(() => {
    if (workflowResult?.test_cases?.length) return workflowResult.test_cases as unknown as Array<Record<string, unknown>>;
    return ((state.test_cases || state.testcases) as Array<Record<string, unknown>> | undefined) ?? [];
  }, [state, workflowResult]);

  const playwrightScripts = useMemo(() => {
    return (savedArtifacts?.generation?.scripts as unknown as Array<Record<string, unknown>> | undefined) ?? [];
  }, [savedArtifacts]);

  const executionReports = useMemo(() => {
    if (savedArtifacts?.report) return [savedArtifacts.report];
    return [];
  }, [savedArtifacts]);

  const latestReport = executionReports[0];
  const projectStatus = workflowResult?.status || testProject?.status || workspace?.status || 'not_started';
  const historyItems = useMemo(() => (
    ((state.audit_log || state.execution_history) as Array<Record<string, unknown>> | undefined) ?? []
  ), [state]);
  const validations = [workflowResult?.scenario_validation, workflowResult?.testcase_validation].filter(Boolean);

  const handleCopyCode = (code: string, index: number) => {
    navigator.clipboard.writeText(code);
    setCopiedScriptIndex(index);
    setTimeout(() => setCopiedScriptIndex(null), 2000);
  };

  const tabsConfig: { id: ArtifactTab; label: string; icon: React.ElementType; count: number }[] = [
    { id: 'documents', label: 'Uploaded Specs', icon: FileText, count: documents.length },
    { id: 'scenarios', label: 'Test Scenarios', icon: ShieldCheck, count: testScenarios.length },
    { id: 'testcases', label: 'Test Cases', icon: FileCheck2, count: testCases.length },
    { id: 'scripts', label: 'Playwright Scripts', icon: Code2, count: playwrightScripts.length },
    { id: 'execution', label: 'Execution Reports', icon: PlayCircle, count: executionReports.length },
    { id: 'traceability', label: 'Traceability Matrix', icon: GitBranch, count: testCases.length },
    { id: 'history', label: 'Version History', icon: Clock3, count: historyItems.length },
    { id: 'validation', label: 'Validation Results', icon: Sparkles, count: validations.length },
  ];

  return (
    <div className="space-y-6 pb-12">
      {/* WORKSPACE NAVIGATION BREADCRUMB & TOP ACTIONS */}
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <Link
          href="/dashboard"
          className="inline-flex items-center gap-2 text-xs font-bold text-muted-foreground hover:text-primary transition"
        >
          <ArrowLeft className="h-4 w-4" /> Back to Dashboard
        </Link>

        <div className="flex items-center gap-2">
          <Link
            href="/test-case-generation"
            className="inline-flex items-center gap-1.5 rounded-xl border border-border bg-card px-3.5 py-2 text-xs font-bold hover:bg-muted transition"
          >
            <Plus className="h-4 w-4" /> Add Document Intake
          </Link>
          <Link
            href="/test-case-generation/automation"
            className="inline-flex items-center gap-1.5 rounded-xl bg-gradient-to-r from-orange-500 to-purple-600 px-4 py-2 text-xs font-bold text-white shadow-md shadow-orange-500/20 hover:opacity-95 transition"
          >
            <Zap className="h-4 w-4" /> Run Playwright Tests
          </Link>
        </div>
      </div>

      {/* PROJECT TITLE CARD HEADER */}
      <div className="relative overflow-hidden rounded-3xl border border-border/80 bg-card p-6 shadow-sm md:p-8">
        <div className="absolute -right-20 -top-24 h-64 w-64 rounded-full bg-purple-500/15 blur-3xl pointer-events-none" />
        <div className="relative flex flex-col gap-5 md:flex-row md:items-end md:justify-between">
          <div>
            <div className="mb-3 flex flex-wrap items-center gap-2">
              <span className="inline-flex items-center gap-1.5 rounded-full bg-emerald-500/10 px-3 py-1 text-[11px] font-bold uppercase tracking-wider text-emerald-600 dark:text-emerald-400">
                <span className="h-1.5 w-1.5 rounded-full bg-emerald-500 animate-pulse" />
                {projectStatus.replaceAll('_', ' ')}
              </span>
              <span className="rounded-full bg-purple-500/10 px-2.5 py-0.5 text-[11px] font-mono text-purple-400">
                ID: {projectId}
              </span>
            </div>
            <h1 className="text-2xl font-extrabold tracking-tight text-foreground md:text-4xl">
              {workspace?.name || testProject?.name || projectId.replace(/-/g, ' ')}
            </h1>
            <p className="mt-2 max-w-2xl text-xs text-muted-foreground leading-relaxed md:text-sm">
              {workspace?.description || 'No project description provided.'}
            </p>
          </div>

          <div className="flex items-center gap-4 border-t border-border/60 pt-4 md:border-0 md:pt-0">
            <div className="text-right">
              <span className="block text-2xl font-extrabold text-foreground">{playwrightScripts.length}</span>
              <span className="text-[10px] font-bold uppercase tracking-wider text-muted-foreground">Playwright Scripts</span>
            </div>
            <div className="h-8 w-px bg-border/60" />
            <div className="text-right">
              <span className="block text-lg font-extrabold capitalize text-primary">{executionStatus.replaceAll('_', ' ')}</span>
              <span className="text-[10px] font-bold uppercase tracking-wider text-muted-foreground">Execution Status</span>
            </div>
          </div>
        </div>
      </div>

      <section className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4 xl:grid-cols-7">
        <WorkspaceMetric label="Test Scenarios" value={testScenarios.length} />
        <WorkspaceMetric label="Test Cases" value={testCases.length} />
        <WorkspaceMetric label="Generated Scripts" value={playwrightScripts.length} />
        <WorkspaceMetric label="Total Executed" value={latestReport?.total_scripts ?? 0} />
        <WorkspaceMetric label="Passed" value={latestReport?.passed_scripts ?? 0} tone="green" />
        <WorkspaceMetric label="Failed" value={latestReport?.failed_scripts ?? 0} tone="red" />
        <WorkspaceMetric label="Skipped" value={latestReport?.skipped_scripts ?? 0} tone="amber" />
      </section>

      {/* INTERACTIVE WORKFLOW PROGRESS PIPELINE VISUALIZATION (STEPPER) */}
      <section className="rounded-2xl border border-border/80 bg-card/60 p-4 shadow-sm backdrop-blur-sm">
        <p className="text-[10px] font-bold uppercase tracking-widest text-primary mb-3">Interactive Workflow Pipeline</p>
        <div className="grid grid-cols-2 gap-2 sm:grid-cols-3 md:grid-cols-6">
          {[
            { step: 1, label: 'Doc Intake', tab: 'documents' },
            { step: 2, label: 'Test Scenarios', tab: 'scenarios' },
            { step: 3, label: 'Test Cases', tab: 'testcases' },
            { step: 4, label: 'Playwright Scripts', tab: 'scripts' },
            { step: 5, label: 'Execution Reports', tab: 'execution' },
            { step: 6, label: 'Traceability Matrix', tab: 'traceability' },
          ].map((st) => {
            const isActive = activeTab === st.tab;
            return (
              <button
                key={st.step}
                onClick={() => setActiveTab(st.tab as ArtifactTab)}
                className={`flex items-center gap-2.5 rounded-xl p-2.5 text-left transition-all ${
                  isActive
                    ? 'bg-gradient-to-r from-orange-500/20 to-purple-600/20 border border-purple-500/40 text-foreground shadow-sm'
                    : 'bg-background/40 hover:bg-background border border-border/50 text-muted-foreground'
                }`}
              >
                <div className={`flex h-6 w-6 shrink-0 items-center justify-center rounded-lg text-xs font-bold ${
                  isActive ? 'bg-gradient-to-r from-orange-500 to-purple-600 text-white' : 'bg-muted text-muted-foreground'
                }`}>
                  {st.step}
                </div>
                <span className="truncate text-xs font-semibold">{st.label}</span>
              </button>
            );
          })}
        </div>
      </section>

      {/* ARTIFACT NAVIGATION TABS (ALL 12 ARTIFACTS) */}
      <div className="flex items-center gap-1.5 overflow-x-auto border-b border-border/60 pb-2 scrollbar-none">
        {tabsConfig.map((tab) => {
          const Icon = tab.icon;
          const isActive = activeTab === tab.id;
          return (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              className={`flex items-center gap-2 rounded-xl px-3.5 py-2 text-xs font-bold whitespace-nowrap transition-all ${
                isActive
                  ? 'bg-gradient-to-r from-orange-500 to-purple-600 text-white shadow-md shadow-orange-500/15'
                  : 'bg-card/70 text-muted-foreground hover:bg-card hover:text-foreground border border-border/50'
              }`}
            >
              <Icon className="h-3.5 w-3.5" />
              <span>{tab.label}</span>
              <span className={`rounded-full px-1.5 py-0.2 text-[10px] ${
                isActive ? 'bg-white/20 text-white' : 'bg-muted text-muted-foreground'
              }`}>
                {tab.count}
              </span>
            </button>
          );
        })}
      </div>

      {/* ARTIFACT VIEW CONTENT AREA */}
      <AnimatePresence mode="wait">
        <motion.div
          key={activeTab}
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          exit={{ opacity: 0, y: -10 }}
          transition={{ duration: 0.2 }}
          className="rounded-3xl border border-border/80 bg-card p-6 shadow-sm"
        >
          {/* TAB 1: UPLOADED DOCUMENTS */}
          {activeTab === 'documents' && (
            <div className="space-y-4">
              <div className="flex justify-between items-center pb-3 border-b border-border/60">
                <div>
                  <h3 className="text-base font-bold">Uploaded SRS & PRD Documents</h3>
                  <p className="text-xs text-muted-foreground">Source requirement files used for AI feature extraction</p>
                </div>
                <button className="inline-flex items-center gap-1.5 rounded-xl bg-primary px-3.5 py-2 text-xs font-bold text-primary-foreground shadow-sm">
                  <Plus className="h-3.5 w-3.5" /> Upload File
                </button>
              </div>

              <div className="grid gap-4 sm:grid-cols-2">
                {documents.map((doc, idx) => (
                  <div key={idx} className="flex items-start justify-between rounded-2xl border border-border/70 bg-background/60 p-4 shadow-sm hover:border-primary/40 transition">
                    <div className="flex items-start gap-3">
                      <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-sky-500/10 text-sky-500 font-bold text-xs">
                        {String(doc.type || '—')}
                      </div>
                      <div>
                        <h4 className="text-sm font-bold text-foreground">{String(doc.name)}</h4>
                        <p className="text-xs text-muted-foreground mt-0.5">{String(doc.size || 'Size unavailable')} · {String(doc.uploadedAt || doc.created_at || 'Upload time unavailable')}</p>
                        <span className="mt-2 inline-flex items-center gap-1 rounded-full bg-emerald-500/10 px-2 py-0.5 text-[10px] font-bold text-emerald-600">
                          <CheckCircle2 className="h-3 w-3" /> {String(doc.status || 'Status unavailable')}
                        </span>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}



          {/* TAB 6: TEST SCENARIOS */}
          {activeTab === 'scenarios' && (
            <div className="space-y-4">
              <div className="pb-3 border-b border-border/60">
                <h3 className="text-base font-bold">Functional Test Scenarios</h3>
                <p className="text-xs text-muted-foreground">Extracted test conditions including edge cases</p>
              </div>
              <div className="grid gap-3 sm:grid-cols-2">
                {testScenarios.map((sc, idx) => (
                  <div key={idx} className="rounded-2xl border border-border/70 bg-background/60 p-4 space-y-2">
                    <span className="font-mono text-xs font-bold text-purple-400">{String(sc.scenario_id || sc.id || '')}</span>
                    <h4 className="text-xs font-bold text-foreground">{String(sc.title || sc.name || '')}</h4>
                    <span className="inline-block rounded-full bg-muted px-2 py-0.5 text-[10px] font-semibold text-muted-foreground">{String(sc.scenario_type || sc.type || '')}</span>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* TAB 7: TEST CASES */}
          {activeTab === 'testcases' && (
            <div className="space-y-4">
              <div className="pb-3 border-b border-border/60">
                <h3 className="text-base font-bold">Step-by-Step Test Cases</h3>
                <p className="text-xs text-muted-foreground">Actionable test steps ready for execution</p>
              </div>
              <div className="space-y-4">
                {testCases.map((tc, idx) => (
                  <div key={idx} className="rounded-2xl border border-border/70 bg-background/60 p-5 space-y-3">
                    <div className="flex justify-between items-center">
                      <span className="font-mono text-xs font-bold text-orange-500">{String(tc.test_case_id || tc.id || '')}</span>
                      <span className="rounded-full bg-emerald-500/10 px-2.5 py-0.5 text-[10px] font-bold text-emerald-500">{String(tc.validation_status || 'Generated')}</span>
                    </div>
                    <h4 className="text-sm font-bold">{String(tc.title)}</h4>
                    <div className="space-y-1 text-xs text-muted-foreground">
                      <p className="font-semibold text-foreground">Execution Steps:</p>
                      <ol className="list-decimal list-inside space-y-1 pl-1">
                        {Array.isArray(tc.steps) && tc.steps.map((st: unknown, sIdx: number) => (
                          <li key={sIdx}>{typeof st === 'string' ? st : String((st as Record<string, unknown>).action || '')}{typeof st === 'object' && st && (st as Record<string, unknown>).expected_result ? ` — Expected: ${String((st as Record<string, unknown>).expected_result)}` : ''}</li>
                        ))}
                      </ol>
                    </div>
                    <p className="text-xs font-medium text-emerald-600 dark:text-emerald-400 pt-2 border-t border-border/40">
                      <strong>Description:</strong> {String(tc.description || '')}
                    </p>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* TAB 8: PLAYWRIGHT TEST SCRIPTS */}
          {activeTab === 'scripts' && (
            <div className="space-y-6">
              <div className="flex justify-between items-center pb-3 border-b border-border/60">
                <div>
                  <h3 className="text-base font-bold">Generated Playwright Automation Scripts</h3>
                  <p className="text-xs text-muted-foreground">Executable TypeScript Playwright test code</p>
                </div>
                <button className="inline-flex items-center gap-1.5 rounded-xl bg-gradient-to-r from-orange-500 to-purple-600 px-4 py-2 text-xs font-bold text-white shadow-sm">
                  <Download className="h-3.5 w-3.5" /> Download Script Suite (.zip)
                </button>
              </div>

              {playwrightScripts.map((scr, idx) => (
                <div key={idx} className="rounded-2xl border border-border/80 bg-slate-950 text-slate-100 overflow-hidden shadow-lg">
                  <div className="flex items-center justify-between px-4 py-3 bg-slate-900 border-b border-slate-800">
                    <div className="flex items-center gap-2">
                      <Code2 className="h-4 w-4 text-purple-400" />
                      <span className="font-mono text-xs font-bold text-purple-300">{String(scr.name || scr.script_id || '')}</span>
                    </div>
                    <button
                      onClick={() => handleCopyCode(String(scr.source || ''), idx)}
                      className="inline-flex items-center gap-1.5 rounded-lg bg-slate-800 px-3 py-1.5 text-[11px] font-bold text-slate-300 hover:text-white hover:bg-slate-700 transition"
                    >
                      <Copy className="h-3.5 w-3.5" /> {copiedScriptIndex === idx ? 'Copied!' : 'Copy Code'}
                    </button>
                  </div>
                  <pre className="p-4 text-xs font-mono overflow-x-auto leading-relaxed text-slate-300">
                    {String(scr.source || '')}
                  </pre>
                </div>
              ))}
            </div>
          )}

          {/* TAB 9: EXECUTION REPORTS */}
          {activeTab === 'execution' && (
            <div className="space-y-4">
              <div className="pb-3 border-b border-border/60">
                <h3 className="text-base font-bold">Execution Reports & Evidence</h3>
                <p className="text-xs text-muted-foreground">Pass/fail statistics and duration logs</p>
              </div>
              <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-5">
                <div className="rounded-2xl border border-border bg-muted/20 p-4 text-center">
                  <span className="block text-3xl font-extrabold">{latestReport?.total_scripts ?? 0}</span>
                  <span className="text-xs font-bold uppercase tracking-wider text-muted-foreground">Total Scripts</span>
                </div>
                <div className="rounded-2xl border border-emerald-500/20 bg-emerald-500/5 p-4 text-center">
                  <span className="block text-3xl font-extrabold text-emerald-500">{latestReport?.passed_scripts ?? 0}</span>
                  <span className="text-xs font-bold uppercase tracking-wider text-muted-foreground">Passed Scripts</span>
                </div>
                <div className="rounded-2xl border border-rose-500/20 bg-rose-500/5 p-4 text-center">
                  <span className="block text-3xl font-extrabold text-rose-500">{latestReport?.failed_scripts ?? 0}</span>
                  <span className="text-xs font-bold uppercase tracking-wider text-muted-foreground">Failed Scripts</span>
                </div>
                <div className="rounded-2xl border border-amber-500/20 bg-amber-500/5 p-4 text-center">
                  <span className="block text-3xl font-extrabold text-amber-500">{latestReport?.skipped_scripts ?? 0}</span>
                  <span className="text-xs font-bold uppercase tracking-wider text-muted-foreground">Skipped Scripts</span>
                </div>
                <div className="rounded-2xl border border-purple-500/20 bg-purple-500/5 p-4 text-center">
                  <span className="block text-3xl font-extrabold text-purple-500">{latestReport ? `${latestReport.success_percentage}%` : '—'}</span>
                  <span className="text-xs font-bold uppercase tracking-wider text-muted-foreground">Success Rate</span>
                </div>
              </div>
            </div>
          )}

          {/* TAB 10: TRACEABILITY MATRIX */}
          {activeTab === 'traceability' && (
            <div className="space-y-4">
              <div className="pb-3 border-b border-border/60">
                <h3 className="text-base font-bold">End-to-End Traceability Matrix</h3>
                <p className="text-xs text-muted-foreground">Requirement ID ➔ User Story ➔ Test Case ➔ Automation Script</p>
              </div>
              <div className="overflow-x-auto">
                <table className="w-full text-left text-xs">
                  <thead>
                    <tr className="border-b border-border/60 text-[11px] font-bold uppercase tracking-wider text-muted-foreground">
                      <th className="py-2.5 px-3">Req ID</th>
                      <th className="py-2.5 px-3">User Story</th>
                      <th className="py-2.5 px-3">Test Case</th>
                      <th className="py-2.5 px-3">Automation Script</th>
                      <th className="py-2.5 px-3 text-right">Coverage</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-border/40 font-mono">
                    {testCases.map((testCase, idx) => {
                      const testCaseId = String(testCase.test_case_id || testCase.id || '');
                      const script = playwrightScripts.find((item) => String(item.test_case_id || '') === testCaseId);
                      return <tr key={`${testCaseId}-${idx}`} className="hover:bg-muted/30">
                        <td className="py-3 px-3 text-primary font-bold">{Array.isArray(testCase.requirement_ids) ? testCase.requirement_ids.join(', ') : '—'}</td>
                        <td className="py-3 px-3 font-sans font-medium">{Array.isArray(testCase.user_story_ids) ? testCase.user_story_ids.join(', ') : '—'}</td>
                        <td className="py-3 px-3 text-purple-400">{testCaseId}</td>
                        <td className="py-3 px-3 text-emerald-400">{String(script?.name || script?.script_id || 'Not generated')}</td>
                        <td className="py-3 px-3 text-right font-bold text-emerald-500">{script ? 'Covered' : 'Not covered'}</td>
                      </tr>
                    })}
                  </tbody>
                </table>
              </div>
            </div>
          )}

          {/* TAB 11: VERSION HISTORY */}
          {activeTab === 'history' && (
            <div className="space-y-4">
              <div className="pb-3 border-b border-border/60">
                <h3 className="text-base font-bold">Version History & Audit Log</h3>
                <p className="text-xs text-muted-foreground">Snapshot revisions of generated test suites</p>
              </div>
              <div className="space-y-3 text-xs">
                {historyItems.map((event, idx) => (
                  <div key={idx} className="flex justify-between items-center rounded-2xl border border-border/60 p-4">
                    <div>
                      <span className="rounded-md bg-primary/10 px-2 py-0.5 text-xs font-mono font-bold text-primary">{String(event.id || event.node_name || idx + 1)}</span>
                      <h4 className="text-xs font-bold text-foreground mt-1">{String(event.message || event.summary || event.status || '')}</h4>
                      <p className="text-[11px] text-muted-foreground mt-0.5">{String(event.actor || event.node_name || 'System')}</p>
                    </div>
                    <span className="text-[11px] text-muted-foreground font-mono">{String(event.timestamp || event.completed_at || event.started_at || '')}</span>
                  </div>
                ))}
                {!historyItems.length && <p className="rounded-xl border border-dashed border-border p-4 text-muted-foreground">No project history is available.</p>}
              </div>
            </div>
          )}

          {/* TAB 12: VALIDATION RESULTS */}
          {activeTab === 'validation' && (
            <div className="space-y-4">
              <div className="pb-3 border-b border-border/60">
                <h3 className="text-base font-bold">AI Validation & INVEST Quality Score</h3>
                <p className="text-xs text-muted-foreground">Automated quality check report for user stories and scenarios</p>
              </div>
              <div className="grid gap-4 sm:grid-cols-2">
                {validations.map((validation, index) => <div key={index} className="rounded-2xl border border-border bg-muted/20 p-4">
                  <p className="text-xs font-bold uppercase tracking-wider text-muted-foreground">{index === 0 ? 'Scenario validation' : 'Test-case validation'}</p>
                  <p className="mt-2 text-3xl font-extrabold text-primary">{Math.round((validation?.confidence_score ?? 0) * 100)}%</p>
                  <p className="mt-1 text-sm capitalize">Status: {validation?.status || 'Not available'}</p>
                  <p className="mt-1 text-xs text-muted-foreground">Issues: {validation?.issues?.length ?? 0}</p>
                </div>)}
                {!validations.length && <p className="rounded-xl border border-dashed border-border p-4 text-sm text-muted-foreground">No validation results are available.</p>}
              </div>
            </div>
          )}
        </motion.div>
      </AnimatePresence>
    </div>
  );
}

function WorkspaceMetric({ label, value, tone = 'default' }: { label: string; value: number | string; tone?: 'default' | 'green' | 'red' | 'amber' }) {
  const color = tone === 'green' ? 'text-emerald-500' : tone === 'red' ? 'text-rose-500' : tone === 'amber' ? 'text-amber-500' : 'text-foreground';
  return <div className="rounded-2xl border border-border/80 bg-card p-4 shadow-sm"><p className={`text-2xl font-extrabold ${color}`}>{value}</p><p className="mt-1 text-[10px] font-bold uppercase tracking-wider text-muted-foreground">{label}</p></div>;
}
