'use client';

import Link from 'next/link';
import { useParams } from 'next/navigation';
import { motion } from 'framer-motion';
import { Activity, ArrowLeft, ArrowRight, BookOpenCheck, Boxes, CheckSquare2, Clock3, Code2, FileCheck2, FileText, GitBranch, Layers3, Loader2, PlayCircle, ScrollText, ShieldCheck, Sparkles } from 'lucide-react';
import { useEffect, useMemo, useState } from 'react';
import { api } from '@/services/api';
import { useWorkspaceStore } from '@/store/workspaceStore';

const asArray = (value: unknown) => Array.isArray(value) ? value : [];

export default function ProjectOverviewPage() {
  const { projectId } = useParams<{ projectId: string }>();
  const workspace = useWorkspaceStore((store) => store.workspaces.find((item) => item.id === projectId));
  const [state, setState] = useState<Record<string, unknown>>({});
  const [loading, setLoading] = useState(true);
  const [offline, setOffline] = useState(false);

  useEffect(() => {
    api.getWorkflowState(projectId).then((response) => setState(response.state || {})).catch(() => setOffline(true)).finally(() => setLoading(false));
  }, [projectId]);

  const artifacts = useMemo(() => [
    { label: 'Uploaded documents', icon: FileText, count: asArray(state.documents || state.uploaded_documents || state.source_documents).length || (state.file_path ? 1 : workspace?.doc_count || 0), path: 'requirements', tone: 'sky' },
    { label: 'Epics', icon: Layers3, count: asArray(state.epics).length, path: 'epics', tone: 'violet' },
    { label: 'Features', icon: Boxes, count: asArray(state.features).length, path: 'epics', tone: 'indigo' },
    { label: 'User stories', icon: BookOpenCheck, count: asArray(state.user_stories || state.stories).length || workspace?.story_count || 0, path: 'stories', tone: 'cyan' },
    { label: 'Acceptance criteria', icon: CheckSquare2, count: asArray(state.user_stories || state.stories).reduce((total: number, story: unknown) => total + asArray((story as Record<string, unknown>)?.acceptance_criteria).length, 0), path: 'stories', tone: 'emerald' },
    { label: 'Test scenarios', icon: ShieldCheck, count: asArray(state.test_scenarios || state.scenarios).length, path: 'validation', tone: 'amber' },
    { label: 'Test cases', icon: FileCheck2, count: asArray(state.test_cases).length, path: 'validation', tone: 'rose' },
    { label: 'Playwright scripts', icon: Code2, count: asArray(state.playwright_scripts || state.generated_scripts || state.test_scripts).length, path: 'export', tone: 'blue' },
    { label: 'Execution results', icon: PlayCircle, count: asArray(state.execution_results || state.test_results).length, path: 'history', tone: 'lime' },
    { label: 'Reports', icon: ScrollText, count: asArray(state.reports).length, path: 'export', tone: 'orange' },
    { label: 'Traceability', icon: GitBranch, count: asArray(state.traceability_matrix || state.traceability).length, path: 'stories', tone: 'fuchsia' },
    { label: 'Version history', icon: Clock3, count: asArray(state.versions || state.version_history || state.execution_history).length, path: 'versioning', tone: 'slate' },
  ], [state, workspace]);

  const total = artifacts.reduce((sum, item) => sum + Number(item.count || 0), 0);
  const status = state.workflow_status || workspace?.status || 'active';

  return (
    <div className="min-h-full overflow-y-auto bg-[radial-gradient(circle_at_top_right,rgba(14,165,233,.1),transparent_30%)] p-5 md:p-8 lg:p-10">
      <div className="mx-auto max-w-7xl">
        <Link href="/dashboard" className="inline-flex items-center gap-2 text-sm font-semibold text-muted-foreground transition hover:text-primary"><ArrowLeft className="h-4 w-4" /> All projects</Link>
        <div className="mt-6 flex flex-col gap-5 border-b border-border pb-7 md:flex-row md:items-end md:justify-between">
          <div><div className="mb-3 flex items-center gap-2"><span className="inline-flex items-center gap-1.5 rounded-full bg-emerald-500/10 px-2.5 py-1 text-[11px] font-bold uppercase tracking-wider text-emerald-600"><span className="h-1.5 w-1.5 rounded-full bg-emerald-500" />{String(status).replaceAll('_', ' ')}</span>{offline && <span className="text-xs text-amber-600">Saved workspace · backend unavailable</span>}</div><h1 className="text-3xl font-bold tracking-tight md:text-4xl">{workspace?.name || projectId}</h1><p className="mt-2 max-w-2xl text-sm leading-6 text-muted-foreground">{workspace?.description || 'All generated project outputs are collected here so you can resume without regenerating completed work.'}</p></div>
          <Link href={`/projects/${projectId}/processing`} className="inline-flex h-11 items-center justify-center gap-2 rounded-xl bg-primary px-5 text-sm font-bold text-primary-foreground shadow-lg shadow-primary/20 transition hover:-translate-y-0.5"><Activity className="h-4 w-4" /> Continue workflow <ArrowRight className="h-4 w-4" /></Link>
        </div>

        {loading ? <div className="flex min-h-64 items-center justify-center gap-3 text-sm text-muted-foreground"><Loader2 className="h-5 w-5 animate-spin text-primary" /> Loading saved artifacts…</div> : <>
          <div className="mt-7 grid gap-4 sm:grid-cols-3"><div className="rounded-2xl border border-border bg-card p-5"><Sparkles className="h-5 w-5 text-sky-500" /><p className="mt-4 text-3xl font-bold">{total}</p><p className="mt-1 text-xs font-semibold uppercase tracking-wider text-muted-foreground">Saved artifacts</p></div><div className="rounded-2xl border border-border bg-card p-5"><Layers3 className="h-5 w-5 text-violet-500" /><p className="mt-4 text-3xl font-bold">{artifacts.filter((item) => item.count > 0).length}</p><p className="mt-1 text-xs font-semibold uppercase tracking-wider text-muted-foreground">Artifact types</p></div><div className="rounded-2xl border border-border bg-card p-5"><GitBranch className="h-5 w-5 text-emerald-500" /><p className="mt-4 text-3xl font-bold capitalize">{String(status).replaceAll('_', ' ')}</p><p className="mt-1 text-xs font-semibold uppercase tracking-wider text-muted-foreground">Workflow status</p></div></div>
          <div className="mt-8"><h2 className="text-xl font-bold">Project artifacts</h2><p className="mt-1 text-sm text-muted-foreground">Open any collection to review or continue working with its saved data.</p></div>
          <div className="mt-4 grid gap-4 sm:grid-cols-2 xl:grid-cols-3">{artifacts.map((item, index) => <motion.div key={item.label} initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: index * .035 }}><Link href={`/projects/${projectId}/${item.path}`} className="group flex items-center gap-4 rounded-2xl border border-border bg-card p-4 shadow-sm transition-all hover:-translate-y-0.5 hover:border-primary/40 hover:shadow-lg"><div className="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl bg-muted text-primary transition group-hover:bg-primary group-hover:text-primary-foreground"><item.icon className="h-5 w-5" /></div><div className="min-w-0 flex-1"><h3 className="truncate text-sm font-bold">{item.label}</h3><p className="mt-1 text-xs text-muted-foreground">{item.count ? `${item.count} saved item${item.count === 1 ? '' : 's'}` : 'Ready when generated'}</p></div><ArrowRight className="h-4 w-4 text-muted-foreground transition-transform group-hover:translate-x-1 group-hover:text-primary" /></Link></motion.div>)}</div>
        </>}
      </div>
    </div>
  );
}
