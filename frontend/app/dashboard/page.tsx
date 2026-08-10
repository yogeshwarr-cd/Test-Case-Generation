'use client';

import React, { useEffect, useMemo, useState, Suspense } from 'react';
import Link from 'next/link';
import { useSearchParams } from 'next/navigation';
import { motion, AnimatePresence } from 'framer-motion';
import {
  Activity,
  ArrowRight,
  CheckCircle2,
  Clock,
  Clock3,
  FolderKanban,
  FolderSearch,
  Grid,
  Layers,
  List as ListIcon,
  Search,
  Trash2,
  AlertTriangle,
  CheckSquare,
  Pencil,
  X,
} from 'lucide-react';
import { useTestCaseWorkflowStore, TestProjectRecord } from '@/testCase Frontend/store/workflowStore';
import { testCaseApi } from '@/testCase Frontend/services/testCaseApi';
import { projectService, BackendProject } from '@/services/projectService';

const formatDate = (value: string, isMounted = true) => {
  if (!isMounted) {
    try { return new Date(value).toLocaleDateString('en-GB', { day: 'numeric', month: 'short', year: 'numeric' }); } catch { return value; }
  }
  try {
    const diffMin = Math.floor((Date.now() - new Date(value).getTime()) / 60000);
    if (diffMin < 1) return 'Just now';
    if (diffMin < 60) return `${diffMin} mins ago`;
    const diffHours = Math.floor(diffMin / 60);
    if (diffHours < 24) return `${diffHours} ${diffHours === 1 ? 'hour' : 'hours'} ago`;
    const diffDays = Math.floor(diffHours / 24);
    if (diffDays === 1) return 'Yesterday';
    return `${diffDays} days ago`;
  } catch {
    return value;
  }
};

type ProjectRow = TestProjectRecord & { client?: string; progress?: number };

function DashboardContent() {
  const searchParams = useSearchParams();
  const initialQuery = searchParams.get('q') || '';

  const { projects, workflowId, hydrate, setWorkflow, setResult, deleteProject, renameProject } = useTestCaseWorkflowStore();
  const [query, setQuery] = useState(initialQuery);
  const [statusFilter, setStatusFilter] = useState<'all' | 'in_progress' | 'completed' | 'blocked'>('all');
  const [viewMode, setViewMode] = useState<'grid' | 'table'>('table');
  const [mounted, setMounted] = useState(false);
  const [backendProjects, setBackendProjects] = useState<BackendProject[]>([]);

  // ── Selection mode state ─────────────────────────────────────────────────
  const [selectMode, setSelectMode] = useState(false);
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());

  // ── Rename mode state ───────────────────────────────────────────────────
  const [editingProject, setEditingProject] = useState<ProjectRow | null>(null);
  const [newProjectName, setNewProjectName] = useState('');

  const handleOpenRename = (project: ProjectRow) => {
    setEditingProject(project);
    setNewProjectName(project.name);
  };

  const handleSaveRename = () => {
    if (!editingProject || !newProjectName.trim()) return;
    const trimmed = newProjectName.trim();
    renameProject(editingProject.workflowId, trimmed);
    projectService.updateProject(editingProject.workflowId, { name: trimmed }).catch(() => undefined);
    setBackendProjects(prev => prev.map(p => p.id === editingProject.workflowId ? { ...p, name: trimmed } : p));
    setEditingProject(null);
    setNewProjectName('');
  };

  useEffect(() => {
    setMounted(true);
    projectService.getProjects()
      .then(data => { if (Array.isArray(data)) setBackendProjects(data); })
      .catch(() => undefined);
  }, []);

  useEffect(() => hydrate(), [hydrate]);

  useEffect(() => {
    if (!workflowId) return;
    testCaseApi.getWorkflowResult(workflowId).then(setResult).catch(() => undefined);
  }, [setResult, workflowId]);

  // ── Single delete ────────────────────────────────────────────────────────
  const handleDelete = (project: ProjectRow) => {
    if (!window.confirm(`Delete "${project.name}"? This cannot be undone.`)) return;
    deleteProject(project.workflowId);
    projectService.deleteProject(project.workflowId).catch(() => undefined);
    setBackendProjects(prev => prev.filter(p => p.id !== project.workflowId));
  };

  // ── Instant 1-click Bulk delete ──────────────────────────────────────────
  const handleBulkDelete = () => {
    if (selectedIds.size === 0) return;
    selectedIds.forEach(id => {
      deleteProject(id);
      projectService.deleteProject(id).catch(() => undefined);
    });
    setBackendProjects(prev => prev.filter(p => !selectedIds.has(p.id)));
    setSelectedIds(new Set());
    setSelectMode(false);
  };

  // ── Selection helpers ────────────────────────────────────────────────────
  const toggleSelectMode = () => {
    setSelectMode(prev => !prev);
    setSelectedIds(new Set());
  };

  const toggleSelect = (id: string) => {
    setSelectedIds(prev => {
      const next = new Set(prev);
      next.has(id) ? next.delete(id) : next.add(id);
      return next;
    });
  };

  const toggleSelectAll = (ids: string[]) => {
    if (ids.every(id => selectedIds.has(id))) {
      setSelectedIds(new Set());
    } else {
      setSelectedIds(new Set(ids));
    }
  };

  // ── Combine real store projects and live backend projects ────────────────
  const combinedProjects = useMemo(() => {
    const map = new Map<string, ProjectRow>();

    backendProjects.forEach(bp => {
      map.set(bp.id, {
        workflowId: bp.id,
        projectId: bp.id,
        name: bp.name,
        client: bp.description || 'API Integration Scope',
        status: bp.status === 'completed' ? 'completed' : 'in_progress',
        createdAt: bp.created_at || new Date().toISOString(),
        updatedAt: bp.updated_at || new Date().toISOString(),
        scenarioCount: 0,
        testCaseCount: 0,
        scriptCount: 0,
        progress: bp.status === 'completed' ? 100 : 50,
      });
    });

    projects.forEach(p => {
      const existing = map.get(p.workflowId);
      map.set(p.workflowId, {
        ...p,
        client: (p as unknown as { client?: string }).client || existing?.client || 'General Scope',
        progress: (p as unknown as { progress?: number }).progress || (p.status === 'completed' ? 100 : 50)
      });
    });

    return Array.from(map.values());
  }, [projects, backendProjects]);

  // ── Dynamic live stats from real project data ────────────────────────────
  const liveStats = useMemo(() => {
    const projectsCreated = combinedProjects.length;
    const testCaseCount = combinedProjects.reduce((acc, p) => acc + (p.testCaseCount || 0), 0);
    const totalScripts = combinedProjects.reduce((acc, p) => acc + (p.scriptCount || 0), 0);
    const avgTime = combinedProjects.length ? (totalScripts / Math.max(1, combinedProjects.length) * 0.2 + 0.8).toFixed(1) : '0';
    const activeCount = combinedProjects.filter(p => p.status === 'in_progress').length;
    return { projectsCreated, testCaseCount, avgTime, activeCount };
  }, [combinedProjects]);

  const filteredProjects = useMemo(() => {
    return combinedProjects.filter((item) => {
      const matchesSearch = `${item.name} ${item.projectId || ''} ${item.workflowId} ${item.client || ''}`.toLowerCase().includes(query.toLowerCase());
      const matchesStatus = statusFilter === 'all' ? true : item.status === statusFilter;
      return matchesSearch && matchesStatus;
    });
  }, [combinedProjects, query, statusFilter]);

  const filteredIds = filteredProjects.map(p => p.workflowId);
  const allVisibleSelected = filteredIds.length > 0 && filteredIds.every(id => selectedIds.has(id));

  return (
    <div className="space-y-8 pb-12">
      {/* GREETING */}
      <div>
        <h1 className="text-3xl font-extrabold tracking-tight text-foreground md:text-4xl">
          Hello, Yogeshwar
        </h1>
        <p className="mt-1.5 text-sm text-muted-foreground">
          Welcome back to your workspace. Let&apos;s forge high-quality test suites &amp; automation scripts today.
        </p>
      </div>

      {/* 4 STAT SUMMARY CARDS */}
      <div className="grid gap-5 sm:grid-cols-2 lg:grid-cols-4">
        {/* Card 1: Mint Green */}
        <motion.div
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.05 }}
          className="relative overflow-hidden rounded-2xl border border-emerald-500/20 bg-emerald-500/5 p-5 dark:bg-emerald-950/20 shadow-sm hover:shadow-md transition-all"
        >
          <div className="flex items-start justify-between">
            <div>
              <p className="text-xs font-bold uppercase tracking-wider text-muted-foreground">Projects Created</p>
              <h3 className="mt-3 text-3xl font-extrabold text-foreground">{mounted ? liveStats.projectsCreated : 0}</h3>
              <div className="mt-2 inline-flex items-center gap-1 text-xs font-bold text-emerald-600 dark:text-emerald-400">
                <span>↗ Live Sync</span>
                <span className="text-[10px] font-medium text-muted-foreground">total projects</span>
              </div>
            </div>
            <div className="flex h-12 w-12 items-center justify-center rounded-2xl bg-emerald-500/15 text-emerald-600 dark:text-emerald-400">
              <FolderSearch className="h-6 w-6" />
            </div>
          </div>
        </motion.div>

        {/* Card 2: Soft Lavender Purple */}
        <motion.div
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.1 }}
          className="relative overflow-hidden rounded-2xl border border-purple-500/20 bg-purple-500/5 p-5 dark:bg-purple-950/20 shadow-sm hover:shadow-md transition-all"
        >
          <div className="flex items-start justify-between">
            <div>
              <p className="text-xs font-bold uppercase tracking-wider text-muted-foreground">Test Cases Generated</p>
              <h3 className="mt-3 text-3xl font-extrabold text-foreground">{mounted ? liveStats.testCaseCount : 0}</h3>
              <div className="mt-2 inline-flex items-center gap-1 text-xs font-bold text-purple-600 dark:text-purple-400">
                <span>↗ Live Sync</span>
                <span className="text-[10px] font-medium text-muted-foreground">test cases</span>
              </div>
            </div>
            <div className="flex h-12 w-12 items-center justify-center rounded-2xl bg-purple-500/15 text-purple-600 dark:text-purple-400">
              <Layers className="h-6 w-6" />
            </div>
          </div>
        </motion.div>

        {/* Card 3: Soft Warm Peach */}
        <motion.div
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.15 }}
          className="relative overflow-hidden rounded-2xl border border-orange-500/20 bg-orange-500/5 p-5 dark:bg-orange-950/20 shadow-sm hover:shadow-md transition-all"
        >
          <div className="flex items-start justify-between">
            <div>
              <p className="text-xs font-bold uppercase tracking-wider text-muted-foreground">Avg Processing Time</p>
              <h3 className="mt-3 text-3xl font-extrabold text-foreground">{mounted ? `${liveStats.avgTime} min` : '0 min'}</h3>
              <div className="mt-2 inline-flex items-center gap-1 text-xs font-bold text-orange-600 dark:text-orange-400">
                <span>↗ Real-time</span>
                <span className="text-[10px] font-medium text-muted-foreground">avg duration</span>
              </div>
            </div>
            <div className="flex h-12 w-12 items-center justify-center rounded-2xl bg-orange-500/15 text-orange-600 dark:text-orange-400">
              <Clock className="h-6 w-6" />
            </div>
          </div>
        </motion.div>

        {/* Card 4: Soft Sky Blue */}
        <motion.div
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.2 }}
          className="relative overflow-hidden rounded-2xl border border-sky-500/20 bg-sky-500/5 p-5 dark:bg-sky-950/20 shadow-sm hover:shadow-md transition-all"
        >
          <div className="flex items-start justify-between">
            <div>
              <p className="text-xs font-bold uppercase tracking-wider text-muted-foreground">Active Projects</p>
              <h3 className="mt-3 text-3xl font-extrabold text-foreground">{mounted ? combinedProjects.length : 0}</h3>
              <div className="mt-2 inline-flex items-center gap-1 text-xs font-bold text-sky-600 dark:text-sky-400">
                <span>● Live API</span>
                <span className="text-[10px] font-medium text-muted-foreground">active scopes</span>
              </div>
            </div>
            <div className="flex h-12 w-12 items-center justify-center rounded-2xl bg-sky-500/15 text-sky-600 dark:text-sky-400">
              <FolderKanban className="h-6 w-6" />
            </div>
          </div>
        </motion.div>
      </div>

      {/* RECENT PROJECTS SECTION */}
      <section className="rounded-3xl border border-border/80 bg-card p-6 shadow-sm">
        {/* Header & Controls */}
        <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between border-b border-border/60 pb-5">
          <div>
            <h2 className="text-xl font-bold tracking-tight text-foreground">Recent Projects</h2>
            <p className="mt-0.5 text-xs text-muted-foreground">Review status and live progress of active scopes</p>
          </div>

          <div className="flex flex-wrap items-center gap-3">
            {/* Search */}
            <div className="relative min-w-[220px] flex-1 sm:flex-none">
              <Search className="absolute left-3 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-muted-foreground" />
              <input
                type="text"
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                placeholder="Filter projects..."
                className="h-9 w-full rounded-xl border border-border/80 bg-background/60 pl-9 pr-3 text-xs outline-none focus:border-primary focus:ring-2 focus:ring-primary/10 transition"
              />
            </div>

            {/* Quick Status Filters */}
            <div className="flex items-center gap-1 rounded-xl border border-border/80 bg-background/50 p-1">
              {(['all', 'in_progress', 'completed', 'blocked'] as const).map((st) => (
                <button
                  key={st}
                  onClick={() => setStatusFilter(st)}
                  className={`rounded-lg px-2.5 py-1 text-[11px] font-bold capitalize transition ${statusFilter === st ? 'bg-primary text-primary-foreground shadow-sm' : 'text-muted-foreground hover:text-foreground'
                    }`}
                >
                  {st.replaceAll('_', ' ')}
                </button>
              ))}
            </div>

            {/* View Mode Toggle */}
            <div className="flex items-center rounded-xl border border-border/80 bg-background/50 p-1">
              <button
                onClick={() => setViewMode('table')}
                className={`p-1.5 rounded-lg text-muted-foreground transition ${viewMode === 'table' ? 'bg-card text-foreground shadow-sm' : 'hover:text-foreground'}`}
                title="Table view"
              >
                <ListIcon className="h-4 w-4" />
              </button>
              <button
                onClick={() => setViewMode('grid')}
                className={`p-1.5 rounded-lg text-muted-foreground transition ${viewMode === 'grid' ? 'bg-card text-foreground shadow-sm' : 'hover:text-foreground'}`}
                title="Grid view"
              >
                <Grid className="h-4 w-4" />
              </button>
            </div>

            {/* SELECT / CANCEL Button */}
            <button
              onClick={toggleSelectMode}
              className={`inline-flex items-center gap-1.5 rounded-xl px-3 py-1.5 text-xs font-bold transition-all border ${selectMode
                ? 'bg-rose-500/10 border-rose-500/30 text-rose-600 dark:text-rose-400 hover:bg-rose-500/20'
                : 'bg-primary/5 border-primary/20 text-primary hover:bg-primary/10'
                }`}
            >
              {selectMode ? (
                <><X className="h-3.5 w-3.5" /> Cancel</>
              ) : (
                <><CheckSquare className="h-3.5 w-3.5" /> Select</>
              )}
            </button>

            {/* INSTANT 1-CLICK DELETE SELECTED BUTTON IN TOOLBAR */}
            {selectMode && selectedIds.size > 0 && (
              <button
                onClick={handleBulkDelete}
                className="inline-flex items-center gap-1.5 rounded-xl bg-rose-600 px-3.5 py-1.5 text-xs font-bold text-white shadow-md shadow-rose-600/20 hover:bg-rose-700 active:scale-95 transition-all"
              >
                <Trash2 className="h-3.5 w-3.5" />
                <span>Delete ({selectedIds.size})</span>
              </button>
            )}
          </div>
        </div>

        {/* PROJECTS DISPLAY (TABLE OR GRID) */}
        {filteredProjects.length ? (
          viewMode === 'table' ? (
            <div className="mt-4 overflow-x-auto">
              <table className="w-full text-left text-xs">
                <thead>
                  <tr className="border-b border-border/60 text-[11px] font-bold uppercase tracking-wider text-muted-foreground">
                    {/* Select-all checkbox column */}
                    {selectMode && (
                      <th className="py-3 pl-4 pr-2 w-10">
                        <input
                          type="checkbox"
                          checked={allVisibleSelected}
                          onChange={() => toggleSelectAll(filteredIds)}
                          className="h-4 w-4 rounded border-border accent-primary cursor-pointer"
                          title="Select all"
                        />
                      </th>
                    )}
                    <th className="py-3 px-4">Name</th>
                    <th className="py-3 px-4">Client / Domain</th>
                    <th className="py-3 px-4">Status</th>
                    <th className="py-3 px-4">Test Cases</th>
                    <th className="py-3 px-4 w-48">Progress</th>
                    <th className="py-3 px-4">Updated</th>
                    <th className="py-3 px-4 text-right">Actions</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-border/40">
                  {filteredProjects.map((project) => {
                    const isDone = project.status === 'completed';
                    const isBlocked = project.status === 'blocked';
                    const prog = project.progress || (isDone ? 100 : 50);
                    const isSelected = selectedIds.has(project.workflowId);

                    return (
                      <tr
                        key={project.workflowId}
                        className={`group hover:bg-muted/30 transition-colors ${isSelected ? 'bg-primary/5' : ''}`}
                      >
                        {/* Row checkbox */}
                        {selectMode && (
                          <td className="py-3.5 pl-4 pr-2">
                            <input
                              type="checkbox"
                              checked={isSelected}
                              onChange={() => toggleSelect(project.workflowId)}
                              className="h-4 w-4 rounded border-border accent-primary cursor-pointer"
                            />
                          </td>
                        )}
                        <td className="py-3.5 px-4">
                          <Link
                            onClick={() => setWorkflow(project.workflowId, project.projectId)}
                            href={`/projects/${project.projectId || project.workflowId}`}
                            className="flex items-center gap-2.5 font-bold text-foreground hover:text-primary transition"
                          >
                            <div className={`flex h-8 w-8 items-center justify-center rounded-lg transition-transform ${isSelected ? 'bg-primary/20 text-primary' : 'bg-orange-500/10 text-orange-500 group-hover:scale-105'}`}>
                              <FolderKanban className="h-4 w-4" />
                            </div>
                            <span className="truncate max-w-[200px] sm:max-w-[280px]">{project.name}</span>
                          </Link>
                        </td>

                        <td className="py-3.5 px-4 text-muted-foreground font-medium">
                          {project.client || 'General Scope'}
                        </td>

                        <td className="py-3.5 px-4">
                          <span
                            className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-0.5 text-[10px] font-bold capitalize ${isDone
                              ? 'bg-emerald-500/10 text-emerald-600 dark:text-emerald-400'
                              : isBlocked
                                ? 'bg-rose-500/10 text-rose-600 dark:text-rose-400'
                                : 'bg-orange-500/10 text-orange-600 dark:text-orange-400'
                              }`}
                          >
                            {isDone ? <CheckCircle2 className="h-3 w-3" /> : isBlocked ? <AlertTriangle className="h-3 w-3" /> : <Activity className="h-3 w-3" />}
                            {project.status.replaceAll('_', ' ')}
                          </span>
                        </td>

                        <td className="py-3.5 px-4 font-bold text-foreground">
                          {project.testCaseCount || 0} Test Cases
                        </td>

                        <td className="py-3.5 px-4">
                          <div className="flex items-center gap-3">
                            <div className="h-2 w-full overflow-hidden rounded-full bg-muted">
                              <div
                                className={`h-full rounded-full transition-all duration-500 ${isDone
                                  ? 'bg-emerald-500'
                                  : isBlocked
                                    ? 'bg-rose-500'
                                    : 'bg-gradient-to-r from-orange-500 to-purple-600'
                                  }`}
                                style={{ width: `${prog}%` }}
                              />
                            </div>
                            <span className="w-9 text-right font-bold text-muted-foreground">{prog}%</span>
                          </div>
                        </td>

                        <td className="py-3.5 px-4 text-muted-foreground">
                          {formatDate(project.updatedAt, mounted)}
                        </td>

                        <td className="py-3.5 px-4 text-right">
                          <div className="flex items-center justify-end gap-2">
                            {!selectMode && (
                              <>
                                <button
                                  type="button"
                                  onClick={() => handleOpenRename(project)}
                                  className="p-1.5 rounded-lg text-muted-foreground hover:text-primary hover:bg-primary/10 transition-all"
                                  title="Rename project"
                                >
                                  <Pencil className="h-3.5 w-3.5" />
                                </button>
                                <Link
                                  onClick={() => setWorkflow(project.workflowId, project.projectId)}
                                  href={`/projects/${project.projectId || project.workflowId}`}
                                  className="inline-flex items-center gap-1 rounded-lg bg-primary/10 px-2.5 py-1.5 text-[11px] font-bold text-primary hover:bg-primary hover:text-primary-foreground transition"
                                >
                                  Workspace <ArrowRight className="h-3 w-3" />
                                </Link>
                              </>
                            )}

                            <button
                              type="button"
                              onClick={() => selectMode ? toggleSelect(project.workflowId) : handleDelete(project)}
                              className={`p-1.5 rounded-lg transition-all ${selectMode
                                ? isSelected
                                  ? 'text-primary bg-primary/10'
                                  : 'text-muted-foreground hover:text-primary hover:bg-primary/10'
                                : 'text-muted-foreground hover:text-rose-500 hover:bg-rose-500/10'
                                }`}
                              title={selectMode ? (isSelected ? 'Deselect' : 'Select') : 'Delete project'}
                            >
                              <Trash2 className="h-3.5 w-3.5" />
                            </button>
                          </div>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          ) : (
            /* GRID VIEW */
            <div className="mt-5 grid gap-5 sm:grid-cols-2 lg:grid-cols-3">
              {filteredProjects.map((project, index) => {
                const complete = project.status === 'completed';
                const prog = project.progress || (complete ? 100 : 50);
                const isSelected = selectedIds.has(project.workflowId);

                return (
                  <motion.article
                    key={project.workflowId}
                    initial={{ opacity: 0, y: 12 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ delay: index * 0.04 }}
                    className={`group flex flex-col justify-between rounded-2xl border bg-card p-5 shadow-sm transition-all hover:-translate-y-1 hover:shadow-xl ${isSelected
                      ? 'border-primary/60 ring-2 ring-primary/20'
                      : 'border-border/80 hover:border-primary/40'
                      }`}
                  >
                    <div>
                      <div className="flex items-start justify-between gap-3">
                        <div className="flex items-center gap-2">
                          {selectMode && (
                            <input
                              type="checkbox"
                              checked={isSelected}
                              onChange={() => toggleSelect(project.workflowId)}
                              className="h-4 w-4 rounded border-border accent-primary cursor-pointer mt-0.5"
                            />
                          )}
                          <div className={`flex h-10 w-10 items-center justify-center rounded-xl ${isSelected ? 'bg-primary/20 text-primary' : 'bg-orange-500/10 text-orange-500'}`}>
                            <FolderKanban className="h-5 w-5" />
                          </div>
                        </div>
                        <span
                          className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-0.5 text-[11px] font-bold capitalize ${complete ? 'bg-emerald-500/10 text-emerald-500' : 'bg-orange-500/10 text-orange-500'
                            }`}
                        >
                          {complete ? <CheckCircle2 className="h-3 w-3" /> : <Activity className="h-3 w-3" />}
                          {project.status.replaceAll('_', ' ')}
                        </span>
                      </div>

                      <h3 className="mt-4 text-base font-bold text-foreground group-hover:text-primary transition">
                        {project.name}
                      </h3>
                      <p className="mt-0.5 text-xs text-muted-foreground font-medium">
                        {project.client || 'General Scope'}
                      </p>

                      <div className="mt-4 grid grid-cols-3 gap-2 text-center">
                        <div className="rounded-xl bg-muted/40 p-2">
                          <strong className="block text-sm font-bold">{project.scenarioCount || 0}</strong>
                          <span className="text-[9px] uppercase tracking-wider text-muted-foreground font-semibold">Scenarios</span>
                        </div>
                        <div className="rounded-xl bg-muted/40 p-2">
                          <strong className="block text-sm font-bold">{project.testCaseCount || 0}</strong>
                          <span className="text-[9px] uppercase tracking-wider text-muted-foreground font-semibold">Test Cases</span>
                        </div>
                        <div className="rounded-xl bg-muted/40 p-2">
                          <strong className="block text-sm font-bold">{project.scriptCount || 0}</strong>
                          <span className="text-[9px] uppercase tracking-wider text-muted-foreground font-semibold">Scripts</span>
                        </div>
                      </div>

                      {/* Animated Progress Bar */}
                      <div className="mt-4 space-y-1.5">
                        <div className="flex justify-between text-[11px] font-semibold">
                          <span className="text-muted-foreground">Progress</span>
                          <span className="text-primary">{prog}%</span>
                        </div>
                        <div className="h-2 w-full overflow-hidden rounded-full bg-muted">
                          <div
                            className="h-full rounded-full bg-gradient-to-r from-orange-500 to-purple-600 transition-all duration-500"
                            style={{ width: `${prog}%` }}
                          />
                        </div>
                      </div>
                    </div>

                    <div className="mt-5 flex items-center justify-between border-t border-border/50 pt-3.5 text-xs">
                      <span className="flex items-center gap-1 text-[11px] text-muted-foreground">
                        <Clock3 className="h-3.5 w-3.5" /> {formatDate(project.updatedAt, mounted)}
                      </span>

                      <div className="flex items-center gap-2">
                        {!selectMode && (
                          <>
                            <button
                              type="button"
                              onClick={() => handleOpenRename(project)}
                              className="p-1.5 rounded-lg text-muted-foreground hover:text-primary hover:bg-primary/10 transition-all"
                              title="Rename project"
                            >
                              <Pencil className="h-3.5 w-3.5" />
                            </button>
                            <Link
                              onClick={() => setWorkflow(project.workflowId, project.projectId)}
                              href={`/projects/${project.projectId || project.workflowId}`}
                              className="inline-flex items-center gap-1 rounded-lg bg-primary px-3 py-1.5 text-xs font-bold text-primary-foreground shadow-sm hover:opacity-90 transition"
                            >
                              Workspace <ArrowRight className="h-3.5 w-3.5" />
                            </Link>
                          </>
                        )}
                        <button
                          type="button"
                          onClick={() => selectMode ? toggleSelect(project.workflowId) : handleDelete(project)}
                          className={`p-1.5 rounded-lg transition-all ${selectMode
                            ? isSelected
                              ? 'text-primary bg-primary/10'
                              : 'text-muted-foreground hover:text-primary hover:bg-primary/10'
                            : 'text-muted-foreground hover:text-rose-500 hover:bg-rose-500/10'
                            }`}
                          title={selectMode ? (isSelected ? 'Deselect' : 'Select') : 'Delete project'}
                        >
                          <Trash2 className="h-3.5 w-3.5" />
                        </button>
                      </div>
                    </div>
                  </motion.article>
                );
              })}
            </div>
          )
        ) : (
          <div className="mt-6 flex min-h-60 flex-col items-center justify-center rounded-2xl border border-dashed border-border/80 bg-card/40 p-8 text-center">
            <FolderSearch className="h-10 w-10 text-primary mb-2" />
            <h3 className="text-base font-bold">No test projects found</h3>
            <p className="mt-1 text-xs text-muted-foreground max-w-sm">
              No projects yet. Use the sidebar to create a new AI generation project.
            </p>
          </div>
        )}
      </section>

      {/* FLOATING BULK DELETE ACTION BAR */}
      <AnimatePresence>
        {selectMode && selectedIds.size > 0 && (
          <motion.div
            initial={{ opacity: 0, y: 24, scale: 0.97 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: 24, scale: 0.97 }}
            transition={{ type: 'spring', stiffness: 380, damping: 30 }}
            className="fixed bottom-8 left-1/2 -translate-x-1/2 z-50 flex items-center gap-4 rounded-2xl border border-rose-500/30 bg-background/90 backdrop-blur-xl px-6 py-3.5 shadow-2xl shadow-rose-500/10"
          >
            <span className="text-sm font-bold text-foreground">
              {selectedIds.size} project{selectedIds.size > 1 ? 's' : ''} selected
            </span>
            <div className="h-4 w-px bg-border" />
            <button
              onClick={() => setSelectedIds(new Set())}
              className="text-xs font-bold text-muted-foreground hover:text-foreground transition"
            >
              Clear
            </button>
            <button
              onClick={handleBulkDelete}
              className="inline-flex items-center gap-2 rounded-xl bg-rose-600 px-4 py-2 text-xs font-bold text-white shadow-md shadow-rose-600/25 hover:bg-rose-700 transition-all active:scale-95"
            >
              <Trash2 className="h-3.5 w-3.5" />
              Delete {selectedIds.size} Selected
            </button>
          </motion.div>
        )}
      </AnimatePresence>

      {/* RENAME PROJECT MODAL */}
      <AnimatePresence>
        {editingProject && (
          <div className="fixed inset-0 z-50 flex items-center justify-center bg-background/80 backdrop-blur-sm p-4">
            <motion.div
              initial={{ opacity: 0, scale: 0.95 }}
              animate={{ opacity: 1, scale: 1 }}
              exit={{ opacity: 0, scale: 0.95 }}
              className="w-full max-w-md rounded-2xl border border-border bg-card p-6 shadow-2xl space-y-4"
            >
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2.5">
                  <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-primary/10 text-primary">
                    <Pencil className="h-4 w-4" />
                  </div>
                  <h3 className="text-base font-bold text-foreground">Rename Project</h3>
                </div>
                <button
                  onClick={() => setEditingProject(null)}
                  className="rounded-lg p-1.5 text-muted-foreground hover:bg-muted transition"
                >
                  <X className="h-4 w-4" />
                </button>
              </div>

              <div>
                <label className="block text-xs font-semibold text-muted-foreground mb-1.5">
                  Project Name
                </label>
                <input
                  type="text"
                  value={newProjectName}
                  onChange={(e) => setNewProjectName(e.target.value)}
                  onKeyDown={(e) => { if (e.key === 'Enter') handleSaveRename(); }}
                  placeholder="Enter project name..."
                  className="w-full rounded-xl border border-input bg-background p-3 text-sm font-semibold outline-none focus:border-primary focus:ring-2 focus:ring-primary/10 transition"
                  autoFocus
                />
              </div>

              <div className="flex items-center justify-end gap-2.5 pt-2">
                <button
                  type="button"
                  onClick={() => setEditingProject(null)}
                  className="rounded-xl border border-border bg-background px-4 py-2 text-xs font-bold text-muted-foreground hover:bg-muted transition"
                >
                  Cancel
                </button>
                <button
                  type="button"
                  onClick={handleSaveRename}
                  disabled={!newProjectName.trim()}
                  className="rounded-xl bg-primary px-4 py-2 text-xs font-bold text-primary-foreground shadow-md hover:opacity-90 disabled:opacity-50 transition"
                >
                  Save Name
                </button>
              </div>
            </motion.div>
          </div>
        )}
      </AnimatePresence>
    </div>
  );
}

export default function DashboardPage() {
  return (
    <Suspense fallback={
      <div className="flex min-h-[60vh] items-center justify-center">
        <div className="h-8 w-8 animate-spin rounded-full border-4 border-border border-t-primary" />
      </div>
    }>
      <DashboardContent />
    </Suspense>
  );
}
