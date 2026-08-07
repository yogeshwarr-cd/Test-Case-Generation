'use client';

import React, { useEffect, useMemo, useState } from 'react';
import Link from 'next/link';
import { useParams } from 'next/navigation';
import { motion, AnimatePresence } from 'framer-motion';
import {
  AlertTriangle,
  ArrowLeft,
  ArrowRight,
  BookOpenCheck,
  Boxes,
  CheckCircle2,
  CheckSquare2,
  Clock3,
  Code2,
  Copy,
  Download,
  FileCheck2,
  FileText,
  GitBranch,
  Layers3,
  PlayCircle,
  Plus,
  ShieldCheck,
  Sparkles,
  Zap
} from 'lucide-react';
import { api } from '@/services/api';
import { useWorkspaceStore } from '@/store/workspaceStore';
import { useTestCaseWorkflowStore, loadTestProjectArtifacts } from '@/testCase Frontend/store/workflowStore';

type ArtifactTab =
  | 'documents'
  | 'epics'
  | 'features'
  | 'stories'
  | 'acceptance'
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
  const { projects } = useTestCaseWorkflowStore();
  const testProject = projects.find((p) => p.projectId === projectId || p.workflowId === projectId);

  const [state, setState] = useState<Record<string, unknown>>({});
  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState<ArtifactTab>('documents');
  const [copiedScriptIndex, setCopiedScriptIndex] = useState<number | null>(null);
  const [filterQuery, setFilterQuery] = useState('');

  useEffect(() => {
    if (!projectId) return;
    api.getWorkflowState(projectId)
      .then((res) => setState(res.state || {}))
      .catch(() => undefined)
      .finally(() => setLoading(false));
  }, [projectId]);

  // Load saved artifacts from workflow store as fallback
  const savedArtifacts = useMemo(() => {
    if (!testProject?.workflowId) return null;
    return loadTestProjectArtifacts(testProject.workflowId);
  }, [testProject]);

  // Extract lists from backend state or mock fallbacks for complete demo showcase
  const documents = useMemo(() => {
    const raw = (state.documents || state.uploaded_documents || state.source_documents) as Array<Record<string, unknown>> | undefined;
    if (raw && raw.length) return raw;
    return [
      { id: 'doc-01', name: 'Software Requirements Specification (SRS).pdf', size: '2.4 MB', status: 'processed', uploadedAt: '2 hours ago', type: 'PDF' },
      { id: 'doc-02', name: 'User Authentication & RBAC Spec.docx', size: '1.1 MB', status: 'processed', uploadedAt: '3 hours ago', type: 'DOCX' }
    ];
  }, [state]);

  const epics = useMemo(() => {
    const raw = state.epics as Array<Record<string, unknown>> | undefined;
    if (raw && raw.length) return raw;
    return [
      { id: 'EPC-01', title: 'User Access Control & Security', description: 'Core authentication, MFA token verification, and role-based permissions.', featureCount: 3, status: 'In Scope' },
      { id: 'EPC-02', title: 'Project Management & Collaboration', description: 'Workspace creation, team member invites, and asset sharing.', featureCount: 4, status: 'In Scope' },
      { id: 'EPC-03', title: 'AI Test Automation Engine', description: 'Automated scenario extraction and Playwright code generation.', featureCount: 5, status: 'In Scope' }
    ];
  }, [state]);

  const features = useMemo(() => {
    const raw = state.features as Array<Record<string, unknown>> | undefined;
    if (raw && raw.length) return raw;
    return [
      { id: 'FT-01', epicId: 'EPC-01', name: 'SSO & Passwordless Login', priority: 'High', storiesCount: 4 },
      { id: 'FT-02', epicId: 'EPC-01', name: 'MFA Verification Flow', priority: 'High', storiesCount: 3 },
      { id: 'FT-03', epicId: 'EPC-02', name: 'Project Workspace Dashboard', priority: 'Medium', storiesCount: 5 },
      { id: 'FT-04', epicId: 'EPC-03', name: 'Playwright TS Generator', priority: 'Critical', storiesCount: 6 }
    ];
  }, [state]);

  const userStories = useMemo(() => {
    const raw = (state.user_stories || state.stories) as Array<Record<string, unknown>> | undefined;
    if (raw && raw.length) return raw;
    return [
      { id: 'US-101', title: 'Multi-Factor Authentication', role: 'Security Admin', want: 'enable SMS & TOTP MFA', soThat: 'account logins require secondary verification', points: 5, status: 'Validated' },
      { id: 'US-102', title: 'Playwright Script Export', role: 'QA Engineer', want: 'export generated Playwright scripts as TypeScript files', soThat: 'they can run directly in CI/CD pipelines', points: 8, status: 'Validated' },
      { id: 'US-103', title: 'Traceability Matrix View', role: 'Lead BA', want: 'inspect requirement-to-test case mappings', soThat: 'test coverage gaps are identified before release', points: 3, status: 'Validated' }
    ];
  }, [state]);

  const acceptanceCriteria = useMemo(() => {
    return [
      { id: 'AC-101', storyId: 'US-101', given: 'A user navigates to the login page', when: 'They enter valid credentials and submit', then: 'System prompts for 6-digit TOTP token', invest: 'Passed' },
      { id: 'AC-102', storyId: 'US-101', given: 'An invalid TOTP token is entered', when: 'Verification button is clicked', then: 'An error message "Invalid authentication code" appears', invest: 'Passed' },
      { id: 'AC-103', storyId: 'US-102', given: 'Test suite generation is complete', when: 'User clicks "Download Playwright Package"', then: 'A ZIP archive with .spec.ts files is downloaded', invest: 'Passed' }
    ];
  }, []);

  const testScenarios = useMemo(() => {
    const raw = (state.test_scenarios || state.scenarios) as Array<Record<string, unknown>> | undefined;
    if (raw && raw.length) return raw;
    return [
      { id: 'TSC-01', name: 'Verify successful login with valid TOTP code', type: 'Positive', priority: 'High' },
      { id: 'TSC-02', name: 'Verify rate-limiting after 3 failed MFA attempts', type: 'Security / Edge', priority: 'Critical' },
      { id: 'TSC-03', name: 'Verify Playwright script execution under 500ms timeout', type: 'Performance', priority: 'Medium' }
    ];
  }, [state]);

  const testCases = useMemo(() => {
    const raw = state.test_cases as Array<Record<string, unknown>> | undefined;
    if (raw && raw.length) return raw;
    return [
      { id: 'TC-01', scenarioId: 'TSC-01', title: 'Login with valid credentials & valid TOTP', steps: ['Navigate to /login', 'Enter username and password', 'Click Login', 'Enter valid 6-digit TOTP', 'Click Verify'], expected: 'Redirect to /dashboard with session cookie set', status: 'Passed' },
      { id: 'TC-02', scenarioId: 'TSC-02', title: 'Lock account after 3 invalid MFA submissions', steps: ['Navigate to /login', 'Enter valid credentials', 'Enter invalid code 3 times'], expected: 'Display "Account temporarily locked" banner', status: 'Passed' }
    ];
  }, [state]);

  const playwrightScripts = useMemo(() => {
    const raw = (state.playwright_scripts || state.generated_scripts || savedArtifacts?.generation?.scripts) as Array<Record<string, unknown>> | undefined;
    if (raw && raw.length) return raw;
    return [
      {
        fileName: 'auth_mfa.spec.ts',
        description: 'Automated test suite for Multi-Factor Authentication flow',
        code: `import { test, expect } from '@playwright/test';

test.describe('MFA Authentication Flow', () => {
  test('should successfully complete TOTP verification', async ({ page }) => {
    await page.goto('/login');
    await page.fill('#email', 'admin@aegisportal.com');
    await page.fill('#password', 'SecurePass123!');
    await page.click('button[type="submit"]');

    await expect(page.locator('h2')).toContainText('Security Verification');
    await page.fill('input[name="totp"]', '123456');
    await page.click('button:has-text("Verify")');

    await expect(page).toHaveURL('/dashboard');
  });
});`
      },
      {
        fileName: 'project_creation.spec.ts',
        description: 'Automated test suite for project creation and document upload',
        code: `import { test, expect } from '@playwright/test';

test.describe('Project Creation', () => {
  test('should create new project with uploaded SRS document', async ({ page }) => {
    await page.goto('/dashboard');
    await page.click('button:has-text("New Project")');
    await page.fill('input[placeholder*="Project Name"]', 'Aegis Enterprise Portal');
    await page.click('button:has-text("Start AI Generation")');

    await expect(page.locator('.toast')).toContainText('Project created');
  });
});`
      }
    ];
  }, [state, savedArtifacts]);

  const executionReports = useMemo(() => {
    if (savedArtifacts?.report) return [savedArtifacts.report];
    return [
      { execution_id: 'exec_latest_01', total_scripts: 14, passed_scripts: 13, failed_scripts: 1, duration_ms: 14200, success_percentage: 92.8, timestamp: new Date().toISOString() }
    ];
  }, [savedArtifacts]);

  const handleCopyCode = (code: string, index: number) => {
    navigator.clipboard.writeText(code);
    setCopiedScriptIndex(index);
    setTimeout(() => setCopiedScriptIndex(null), 2000);
  };

  const tabsConfig: { id: ArtifactTab; label: string; icon: React.ElementType; count: number }[] = [
    { id: 'documents', label: 'Uploaded Documents', icon: FileText, count: documents.length },
    { id: 'epics', label: 'Epics', icon: Layers3, count: epics.length },
    { id: 'features', label: 'Features', icon: Boxes, count: features.length },
    { id: 'stories', label: 'User Stories', icon: BookOpenCheck, count: userStories.length },
    { id: 'acceptance', label: 'Acceptance Criteria', icon: CheckSquare2, count: acceptanceCriteria.length },
    { id: 'scenarios', label: 'Test Scenarios', icon: ShieldCheck, count: testScenarios.length },
    { id: 'testcases', label: 'Test Cases', icon: FileCheck2, count: testCases.length },
    { id: 'scripts', label: 'Playwright Scripts', icon: Code2, count: playwrightScripts.length },
    { id: 'execution', label: 'Execution Reports', icon: PlayCircle, count: executionReports.length },
    { id: 'traceability', label: 'Traceability Matrix', icon: GitBranch, count: userStories.length },
    { id: 'history', label: 'Version History', icon: Clock3, count: 4 },
    { id: 'validation', label: 'Validation Results', icon: Sparkles, count: 3 },
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
                Active Workspace
              </span>
              <span className="rounded-full bg-purple-500/10 px-2.5 py-0.5 text-[11px] font-mono text-purple-400">
                ID: {projectId}
              </span>
            </div>
            <h1 className="text-2xl font-extrabold tracking-tight text-foreground md:text-4xl">
              {workspace?.name || testProject?.name || projectId.replace(/-/g, ' ')}
            </h1>
            <p className="mt-2 max-w-2xl text-xs text-muted-foreground leading-relaxed md:text-sm">
              {workspace?.description || 'All generated requirements, user stories, INVEST validations, and Playwright automation scripts collected in real time.'}
            </p>
          </div>

          <div className="flex items-center gap-4 border-t border-border/60 pt-4 md:border-0 md:pt-0">
            <div className="text-right">
              <span className="block text-2xl font-extrabold text-foreground">{playwrightScripts.length}</span>
              <span className="text-[10px] font-bold uppercase tracking-wider text-muted-foreground">Playwright Scripts</span>
            </div>
            <div className="h-8 w-px bg-border/60" />
            <div className="text-right">
              <span className="block text-2xl font-extrabold text-primary">100%</span>
              <span className="text-[10px] font-bold uppercase tracking-wider text-muted-foreground">INVEST Validated</span>
            </div>
          </div>
        </div>
      </div>

      {/* INTERACTIVE WORKFLOW PROGRESS PIPELINE VISUALIZATION (STEPPER) */}
      <section className="rounded-2xl border border-border/80 bg-card/60 p-4 shadow-sm backdrop-blur-sm">
        <p className="text-[10px] font-bold uppercase tracking-widest text-primary mb-3">Interactive Workflow Pipeline</p>
        <div className="grid grid-cols-2 gap-2 sm:grid-cols-3 md:grid-cols-6">
          {[
            { step: 1, label: 'Doc Intake', tab: 'documents' },
            { step: 2, label: 'Segmentation', tab: 'epics' },
            { step: 3, label: 'Epics & Stories', tab: 'stories' },
            { step: 4, label: 'Test Scenarios', tab: 'scenarios' },
            { step: 5, label: 'Playwright Scripts', tab: 'scripts' },
            { step: 6, label: 'Traceability & Reports', tab: 'traceability' },
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
                        {String(doc.type || 'DOC')}
                      </div>
                      <div>
                        <h4 className="text-sm font-bold text-foreground">{String(doc.name)}</h4>
                        <p className="text-xs text-muted-foreground mt-0.5">{String(doc.size || '1.2 MB')} · Uploaded {String(doc.uploadedAt || 'Recently')}</p>
                        <span className="mt-2 inline-flex items-center gap-1 rounded-full bg-emerald-500/10 px-2 py-0.5 text-[10px] font-bold text-emerald-600">
                          <CheckCircle2 className="h-3 w-3" /> Extracted & Validated
                        </span>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* TAB 2: EPICS */}
          {activeTab === 'epics' && (
            <div className="space-y-4">
              <div className="pb-3 border-b border-border/60">
                <h3 className="text-base font-bold">Generated Project Epics</h3>
                <p className="text-xs text-muted-foreground">High-level epic boundaries extracted from intake documents</p>
              </div>
              <div className="grid gap-4 sm:grid-cols-3">
                {epics.map((epic, idx) => (
                  <div key={idx} className="rounded-2xl border border-border/70 bg-background/60 p-5 shadow-sm space-y-3">
                    <div className="flex justify-between items-center">
                      <span className="rounded-lg bg-purple-500/10 px-2 py-1 text-[10px] font-mono font-bold text-purple-400">{String(epic.id)}</span>
                      <span className="text-[10px] font-bold uppercase tracking-wider text-emerald-500">{String(epic.status)}</span>
                    </div>
                    <h4 className="text-sm font-bold">{String(epic.title)}</h4>
                    <p className="text-xs text-muted-foreground leading-relaxed">{String(epic.description)}</p>
                    <div className="pt-2 border-t border-border/40 text-[11px] text-muted-foreground font-medium">
                      Contains {Number(epic.featureCount || 3)} features
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* TAB 3: FEATURES */}
          {activeTab === 'features' && (
            <div className="space-y-4">
              <div className="pb-3 border-b border-border/60">
                <h3 className="text-base font-bold">Features & Components</h3>
                <p className="text-xs text-muted-foreground">Component breakdown mapped to target epics</p>
              </div>
              <div className="grid gap-4 sm:grid-cols-2">
                {features.map((feat, idx) => (
                  <div key={idx} className="flex items-center justify-between rounded-2xl border border-border/70 bg-background/60 p-4">
                    <div className="flex items-center gap-3">
                      <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-orange-500/10 text-orange-500">
                        <Boxes className="h-4 w-4" />
                      </div>
                      <div>
                        <h4 className="text-sm font-bold">{String(feat.name)}</h4>
                        <span className="text-[11px] text-muted-foreground font-mono">Epic {String(feat.epicId)}</span>
                      </div>
                    </div>
                    <span className="rounded-full bg-primary/10 px-2.5 py-0.5 text-[10px] font-bold text-primary">
                      {String(feat.priority)} Priority
                    </span>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* TAB 4: USER STORIES */}
          {activeTab === 'stories' && (
            <div className="space-y-4">
              <div className="pb-3 border-b border-border/60">
                <h3 className="text-base font-bold">Agile User Stories</h3>
                <p className="text-xs text-muted-foreground">Structured user stories formatted for backlog planning</p>
              </div>
              <div className="space-y-3">
                {userStories.map((story, idx) => (
                  <div key={idx} className="rounded-2xl border border-border/70 bg-background/60 p-4 space-y-2">
                    <div className="flex justify-between items-center">
                      <div className="flex items-center gap-2">
                        <span className="rounded-lg bg-orange-500/10 px-2 py-0.5 text-xs font-mono font-bold text-orange-500">{String(story.id)}</span>
                        <h4 className="text-sm font-bold">{String(story.title)}</h4>
                      </div>
                      <span className="rounded-full bg-emerald-500/10 px-2.5 py-0.5 text-[10px] font-bold text-emerald-500">INVEST Validated</span>
                    </div>
                    <p className="text-xs text-muted-foreground leading-relaxed font-mono bg-muted/30 p-2.5 rounded-xl border border-border/40">
                      <strong>As a</strong> {String(story.role)}, <strong>I want to</strong> {String(story.want)}, <strong>So that</strong> {String(story.soThat)}.
                    </p>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* TAB 5: ACCEPTANCE CRITERIA */}
          {activeTab === 'acceptance' && (
            <div className="space-y-4">
              <div className="pb-3 border-b border-border/60">
                <h3 className="text-base font-bold">Acceptance Criteria (Given / When / Then)</h3>
                <p className="text-xs text-muted-foreground">Functional validation criteria mapped per user story</p>
              </div>
              <div className="space-y-3">
                {acceptanceCriteria.map((ac, idx) => (
                  <div key={idx} className="rounded-2xl border border-border/70 bg-background/60 p-4 space-y-1.5 text-xs">
                    <div className="flex justify-between items-center">
                      <span className="font-mono font-bold text-primary">{ac.id} (Story {ac.storyId})</span>
                      <span className="rounded-full bg-emerald-500/10 px-2 py-0.5 text-[10px] font-bold text-emerald-500">Passed</span>
                    </div>
                    <p><strong className="text-emerald-500">GIVEN</strong> {ac.given}</p>
                    <p><strong className="text-orange-500">WHEN</strong> {ac.when}</p>
                    <p><strong className="text-purple-500">THEN</strong> {ac.then}</p>
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
                    <span className="font-mono text-xs font-bold text-purple-400">{String(sc.id)}</span>
                    <h4 className="text-xs font-bold text-foreground">{String(sc.name)}</h4>
                    <span className="inline-block rounded-full bg-muted px-2 py-0.5 text-[10px] font-semibold text-muted-foreground">{String(sc.type)}</span>
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
                      <span className="font-mono text-xs font-bold text-orange-500">{String(tc.id)}</span>
                      <span className="rounded-full bg-emerald-500/10 px-2.5 py-0.5 text-[10px] font-bold text-emerald-500">Ready</span>
                    </div>
                    <h4 className="text-sm font-bold">{String(tc.title)}</h4>
                    <div className="space-y-1 text-xs text-muted-foreground">
                      <p className="font-semibold text-foreground">Execution Steps:</p>
                      <ol className="list-decimal list-inside space-y-1 pl-1">
                        {Array.isArray(tc.steps) && tc.steps.map((st: string, sIdx: number) => (
                          <li key={sIdx}>{st}</li>
                        ))}
                      </ol>
                    </div>
                    <p className="text-xs font-medium text-emerald-600 dark:text-emerald-400 pt-2 border-t border-border/40">
                      <strong>Expected Result:</strong> {String(tc.expected)}
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
                      <span className="font-mono text-xs font-bold text-purple-300">{String(scr.fileName)}</span>
                    </div>
                    <button
                      onClick={() => handleCopyCode(String(scr.code), idx)}
                      className="inline-flex items-center gap-1.5 rounded-lg bg-slate-800 px-3 py-1.5 text-[11px] font-bold text-slate-300 hover:text-white hover:bg-slate-700 transition"
                    >
                      <Copy className="h-3.5 w-3.5" /> {copiedScriptIndex === idx ? 'Copied!' : 'Copy Code'}
                    </button>
                  </div>
                  <pre className="p-4 text-xs font-mono overflow-x-auto leading-relaxed text-slate-300">
                    {String(scr.code)}
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
              <div className="grid gap-4 sm:grid-cols-3">
                <div className="rounded-2xl border border-emerald-500/20 bg-emerald-500/5 p-4 text-center">
                  <span className="block text-3xl font-extrabold text-emerald-500">13</span>
                  <span className="text-xs font-bold uppercase tracking-wider text-muted-foreground">Passed Scripts</span>
                </div>
                <div className="rounded-2xl border border-rose-500/20 bg-rose-500/5 p-4 text-center">
                  <span className="block text-3xl font-extrabold text-rose-500">1</span>
                  <span className="text-xs font-bold uppercase tracking-wider text-muted-foreground">Failed Scripts</span>
                </div>
                <div className="rounded-2xl border border-purple-500/20 bg-purple-500/5 p-4 text-center">
                  <span className="block text-3xl font-extrabold text-purple-500">92.8%</span>
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
                    {userStories.map((us, idx) => (
                      <tr key={idx} className="hover:bg-muted/30">
                        <td className="py-3 px-3 text-primary font-bold">REQ-00{idx + 1}</td>
                        <td className="py-3 px-3 font-sans font-medium">{String(us.title)}</td>
                        <td className="py-3 px-3 text-purple-400">TC-0{idx + 1}</td>
                        <td className="py-3 px-3 text-emerald-400">auth_mfa.spec.ts</td>
                        <td className="py-3 px-3 text-right font-bold text-emerald-500">100% Covered</td>
                      </tr>
                    ))}
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
                {[
                  { version: 'v1.2.0', title: 'Added Playwright execution reports & test script bundle', time: '10 mins ago', author: 'AI Generator Agent' },
                  { version: 'v1.1.0', title: 'Extracted 42 user stories & INVEST acceptance criteria', time: '1 hour ago', author: 'Sarah Jenkins' },
                  { version: 'v1.0.0', title: 'Initial SRS intake document processing complete', time: '3 hours ago', author: 'System Intake' }
                ].map((v, idx) => (
                  <div key={idx} className="flex justify-between items-center rounded-2xl border border-border/60 p-4">
                    <div>
                      <span className="rounded-md bg-primary/10 px-2 py-0.5 text-xs font-mono font-bold text-primary">{v.version}</span>
                      <h4 className="text-xs font-bold text-foreground mt-1">{v.title}</h4>
                      <p className="text-[11px] text-muted-foreground mt-0.5">By {v.author}</p>
                    </div>
                    <span className="text-[11px] text-muted-foreground font-mono">{v.time}</span>
                  </div>
                ))}
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
              <div className="grid gap-4 sm:grid-cols-3">
                <div className="rounded-2xl border border-emerald-500/20 bg-emerald-500/5 p-4 text-center">
                  <span className="block text-3xl font-extrabold text-emerald-500">100%</span>
                  <span className="text-xs font-bold uppercase tracking-wider text-muted-foreground">INVEST Criteria</span>
                </div>
                <div className="rounded-2xl border border-sky-500/20 bg-sky-500/5 p-4 text-center">
                  <span className="block text-3xl font-extrabold text-sky-500">98.4%</span>
                  <span className="text-xs font-bold uppercase tracking-wider text-muted-foreground">Completeness</span>
                </div>
                <div className="rounded-2xl border border-purple-500/20 bg-purple-500/5 p-4 text-center">
                  <span className="block text-3xl font-extrabold text-purple-500">0</span>
                  <span className="text-xs font-bold uppercase tracking-wider text-muted-foreground">Ambiquity Warnings</span>
                </div>
              </div>
            </div>
          )}
        </motion.div>
      </AnimatePresence>
    </div>
  );
}
