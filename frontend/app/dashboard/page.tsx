'use client';

import Link from 'next/link';
import { motion } from 'framer-motion';
import { Activity, ArrowRight, CheckCircle2, Clock3, Code2, FileCheck2, FlaskConical, FolderSearch, PlayCircle, Plus, Search, Sparkles, XCircle } from 'lucide-react';
import { useEffect, useMemo, useState } from 'react';
import { useTestCaseWorkflowStore } from '@/testCase Frontend/store/workflowStore';
import { testCaseApi } from '@/testCase Frontend/services/testCaseApi';

const formatDate = (value: string) => new Intl.DateTimeFormat('en', { month: 'short', day: 'numeric', year: 'numeric', hour: '2-digit', minute: '2-digit' }).format(new Date(value));

export default function TestProjectsPage() {
  const { projects, workflowId, hydrate, setWorkflow, setResult } = useTestCaseWorkflowStore();
  const [query, setQuery] = useState('');
  useEffect(() => hydrate(), [hydrate]);
  useEffect(() => {
    if (!workflowId) return;
    testCaseApi.getWorkflowResult(workflowId).then(setResult).catch(() => undefined);
  }, [setResult, workflowId]);
  const filtered = useMemo(() => projects.filter((item) => `${item.name} ${item.projectId} ${item.workflowId}`.toLowerCase().includes(query.toLowerCase())), [projects, query]);

  return (
    <div className="space-y-8">
      <section className="relative overflow-hidden rounded-[1.75rem] border border-border bg-card p-6 shadow-sm md:p-9">
        <div className="absolute -right-20 -top-24 h-64 w-64 rounded-full bg-primary/15 blur-3xl" />
        <div className="relative flex flex-col gap-7 md:flex-row md:items-end md:justify-between">
          <div className="max-w-3xl"><div className="inline-flex items-center gap-2 rounded-full bg-primary/10 px-3 py-1.5 text-xs font-bold uppercase tracking-[.16em] text-primary"><FlaskConical className="h-3.5 w-3.5" /> Test Intelligence</div><h1 className="mt-5 text-3xl font-bold tracking-tight md:text-5xl">Test script projects</h1><p className="mt-4 max-w-2xl text-sm leading-6 text-muted-foreground md:text-base">Resume generated scenarios and test cases, inspect Playwright scripts, and review execution evidence and reports.</p></div>
          <Link href="/test-case-generation" className="inline-flex h-12 items-center justify-center gap-2 rounded-xl bg-primary px-5 text-sm font-bold text-primary-foreground shadow-lg shadow-primary/20 transition hover:-translate-y-0.5"><Plus className="h-5 w-5" /> New Test Project</Link>
        </div>
      </section>

      <section>
        <div className="flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between"><div><p className="text-xs font-bold uppercase tracking-[.18em] text-primary">Generation history</p><h2 className="mt-1 text-2xl font-bold">Your projects</h2><p className="mt-1 text-sm text-muted-foreground">{projects.length} test {projects.length === 1 ? 'project' : 'projects'}</p></div><label className="relative block w-full sm:w-80"><Search className="absolute left-3.5 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" /><input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Search test projects..." className="h-11 w-full rounded-xl border border-border bg-card pl-10 pr-4 text-sm outline-none transition focus:border-primary focus:ring-4 focus:ring-primary/10" /></label></div>

        {filtered.length ? <div className="mt-5 grid gap-5 lg:grid-cols-2">{filtered.map((project, index) => {
          const complete = project.status === 'completed';
          return <motion.article key={project.workflowId} initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: index * .05 }} className="group rounded-2xl border border-border bg-card p-5 shadow-sm transition-all hover:-translate-y-1 hover:border-primary/40 hover:shadow-xl">
            <div className="flex items-start justify-between gap-4"><div className="flex h-11 w-11 items-center justify-center rounded-xl bg-primary/10 text-primary"><Code2 className="h-5 w-5" /></div><span className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-[11px] font-bold capitalize ${complete ? 'bg-emerald-500/10 text-emerald-500' : 'bg-amber-500/10 text-amber-500'}`}>{complete ? <CheckCircle2 className="h-3 w-3" /> : <Activity className="h-3 w-3" />}{project.status.replaceAll('_', ' ')}</span></div>
            <h3 className="mt-4 text-lg font-bold">{project.name}</h3><p className="mt-1 truncate font-mono text-[11px] text-muted-foreground">Workflow {project.workflowId}</p>
            <div className="mt-5 grid grid-cols-3 gap-2"><Metric icon={Sparkles} label="Scenarios" value={project.scenarioCount} /><Metric icon={FileCheck2} label="Test cases" value={project.testCaseCount} /><Metric icon={Code2} label="Scripts" value={project.scriptCount} /></div>
            {project.execution && <div className="mt-4 rounded-xl border border-border bg-muted/30 p-3"><div className="flex items-center justify-between"><span className="flex items-center gap-2 text-xs font-bold"><PlayCircle className="h-4 w-4 text-primary" /> Latest execution</span><strong className="text-sm text-primary">{project.execution.successPercentage}%</strong></div><div className="mt-2 flex gap-4 text-xs text-muted-foreground"><span className="flex items-center gap-1"><CheckCircle2 className="h-3.5 w-3.5 text-emerald-500" /> {project.execution.passed} passed</span><span className="flex items-center gap-1"><XCircle className="h-3.5 w-3.5 text-red-500" /> {project.execution.failed} failed</span></div></div>}
            <div className="mt-5 flex flex-wrap items-center gap-2 border-t border-border pt-4"><Link onClick={() => setWorkflow(project.workflowId, project.projectId)} href="/test-case-generation/results" className="inline-flex items-center gap-2 rounded-lg bg-primary px-3.5 py-2 text-xs font-bold text-primary-foreground">View generated tests <ArrowRight className="h-3.5 w-3.5" /></Link><Link onClick={() => setWorkflow(project.workflowId, project.projectId)} href="/test-case-generation/automation?view=history" className="inline-flex items-center gap-2 rounded-lg border border-border px-3.5 py-2 text-xs font-bold hover:bg-muted"><Code2 className="h-3.5 w-3.5" /> Scripts & execution</Link><span className="ml-auto flex items-center gap-1 text-[11px] text-muted-foreground"><Clock3 className="h-3.5 w-3.5" /> {formatDate(project.updatedAt)}</span></div>
          </motion.article>;
        })}</div> : <div className="mt-5 flex min-h-72 flex-col items-center justify-center rounded-2xl border border-dashed border-border bg-card/60 p-8 text-center"><FolderSearch className="h-10 w-10 text-primary" /><h2 className="mt-4 text-xl font-bold">{query ? 'No matching test projects' : 'No test projects yet'}</h2><p className="mt-2 max-w-md text-sm text-muted-foreground">Complete a test-case generation workflow and it will appear here with its scripts and execution results.</p>{!query && <Link href="/test-case-generation" className="mt-5 inline-flex items-center gap-2 rounded-xl bg-primary px-4 py-2.5 text-sm font-bold text-primary-foreground"><Plus className="h-4 w-4" /> Start generating</Link>}</div>}
      </section>
    </div>
  );
}

function Metric({ icon: Icon, label, value }: { icon: typeof Sparkles; label: string; value: number }) {
  return <div className="rounded-xl bg-muted/45 p-3"><Icon className="h-4 w-4 text-primary" /><strong className="mt-2 block text-xl">{value}</strong><span className="text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">{label}</span></div>;
}
