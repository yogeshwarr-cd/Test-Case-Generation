'use client';

import React, { useEffect, useState } from 'react';
import { useRouter, useParams } from 'next/navigation';
import {
  Check, X, Edit2, RotateCw, CheckCircle2, AlertTriangle,
  ArrowRight, ChevronUp, ChevronDown, ShieldCheck, Loader2,
} from 'lucide-react';
import { api } from '@/services/api';
import { Epic, EntityStatus } from '@/services/mockData';
import { Button } from '@/components/common/Button';
import { cn } from '@/lib/utils';
import { motion, AnimatePresence } from 'framer-motion';

type OutlineFeature = {
  id: string;
  epicId: string;
  title: string;
  summary: string;
};

const storyText = (story: any) =>
  story?.summary || story?.one_line_story || story?.one_line_text || story?.title || '';

export default function EpicReviewPage() {
  const router = useRouter();
  const params = useParams();
  const projectId = params?.projectId as string;

  const [epics, setEpics] = useState<Epic[]>([]);
  const [features, setFeatures] = useState<OutlineFeature[]>([]);
  const [oneLineStories, setOneLineStories] = useState<any[]>([]);
  const [expandedOneLineStories, setExpandedOneLineStories] = useState<Set<string>>(new Set());
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [regeneratingIds, setRegeneratingIds] = useState<Set<string>>(new Set());
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editTitle, setEditTitle] = useState('');
  const [editSummary, setEditSummary] = useState('');
  const [activeFeedbackId, setActiveFeedbackId] = useState<string | null>(null);
  const [feedbackText, setFeedbackText] = useState('');
  const [isTraceabilityOpen, setIsTraceabilityOpen] = useState(false);
  const [workflowStatus, setWorkflowStatus] = useState<string>('UNKNOWN');

  useEffect(() => {
    // Fetch epics and one-line stories in one state call
    api
      .getWorkflowState(projectId)
      .then((res: any) => {
        const state = res.state || {};
        setWorkflowStatus(state.workflow_status || 'UNKNOWN');
        const rawEpics: any[] = state.epics || [];
        setEpics(
          rawEpics.map((e: any, idx: number) => ({
            id: e.id,
            sNo: idx + 1,
            title: e.name || e.title || e.id,
            summary: e.description || '',
            status: (e.metadata?.status as EntityStatus) || 'needs_review',
            confidenceScore: e.metadata?.confidence_score ?? 0,
          }))
        );
        const rawFeatures: any[] = state.features || [];
        setFeatures(
          rawFeatures.map((feature: any) => ({
            id: feature.id,
            epicId: feature.metadata?.epic_id || feature.epic_id || feature.epic || '',
            title: feature.name || feature.title || feature.id,
            summary: feature.description || '',
          }))
        );
        const ols: any[] = state.one_line_stories || [];
        setOneLineStories(ols);
        setLoading(false);
      })
      .catch((err) => {
        setError(err?.message || 'Failed to load epics.');
        setLoading(false);
      });
  }, [projectId]);

  const toggleOneLineStories = (epicId: string) => {
    setExpandedOneLineStories((prev) => {
      const next = new Set(prev);
      next.has(epicId) ? next.delete(epicId) : next.add(epicId);
      return next;
    });
  };

  const handleStatusChange = async (epicId: string, newStatus: EntityStatus) => {
    try {
      const updated = await api.updateEpic(projectId, epicId, { status: newStatus });
      setEpics((prev) => prev.map((e) => (e.id === epicId ? updated : e)));
    } catch (err) {
      console.error(err);
    }
  };

  const handleSaveEdit = async (epicId: string) => {
    if (!editTitle.trim() || !editSummary.trim()) return;
    try {
      const updated = await api.updateEpic(projectId, epicId, {
        title: editTitle,
        summary: editSummary,
      });
      setEpics((prev) => prev.map((e) => (e.id === epicId ? updated : e)));
      setEditingId(null);
    } catch (err) {
      console.error(err);
    }
  };

  const handleRegenerate = async (epicId: string) => {
    if (!feedbackText.trim()) return;
    setRegeneratingIds((prev) => new Set(prev).add(epicId));
    setActiveFeedbackId(null);
    try {
      const updatedEpic = await api.regenerateEpic(projectId, epicId, feedbackText);
      setEpics((prev) =>
        prev.map((e) =>
          e.id === epicId ? { ...updatedEpic, status: 'ready' as EntityStatus, version: (e.version || 1) + 1 } : e
        )
      );
    } catch (err) {
      console.error(err);
    } finally {
      setRegeneratingIds((prev) => {
        const next = new Set(prev);
        next.delete(epicId);
        return next;
      });
      setFeedbackText('');
    }
  };

  const handleEditClick = (epic: Epic) => {
    setEditingId(epic.id);
    setEditTitle(epic.title);
    setEditSummary(epic.summary);
    setActiveFeedbackId(null);
  };

  const allApproved = epics.length > 0 && epics.every((e) => e.status === 'approved');
  const allReviewed = epics.length > 0 && epics.every((e) => e.status === 'approved' || e.status === 'rejected');
  const hasApproved = epics.some((e) => e.status === 'approved');
  const canProceed = allReviewed && hasApproved;

  useEffect(() => {
    // Only auto-redirect if all reviewed AND we are already past the outline generation stage
    if (canProceed && workflowStatus !== 'OUTLINE_REVIEW_REQUIRED') {
      const timer = setTimeout(() => {
        router.push(`/projects/${projectId}/stories`);
      }, 1500);
      return () => clearTimeout(timer);
    }
  }, [canProceed, projectId, router, workflowStatus]);

  const handleApproveOutline = async () => {
    try {
      await api.approveOutline(projectId);
      router.push(`/projects/${projectId}/processing`);
    } catch (err) {
      console.error('Failed to approve outline:', err);
    }
  };

  if (loading) {
    return (
      <div className="flex-1 flex items-center justify-center p-8 bg-background">
        <div className="flex flex-col items-center gap-3 text-muted-foreground">
          <Loader2 className="w-7 h-7 animate-spin text-primary" />
          <p className="text-sm">Loading epics...</p>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex-1 flex items-center justify-center p-8 bg-background">
        <div className="flex flex-col items-center gap-4 text-red-500 max-w-md text-center">
          <AlertTriangle className="w-7 h-7" />
          <p className="text-sm font-medium">{error}</p>
          <Button variant="secondary" onClick={() => router.push(`/projects/${projectId}/processing`)}>
            Back to Processing
          </Button>
        </div>
      </div>
    );
  }

  if (epics.length === 0) {
    return (
      <div className="flex-1 flex items-center justify-center p-8 bg-background">
        <div className="flex flex-col items-center gap-3 text-muted-foreground max-w-md text-center">
          <p className="text-sm">
            No epics generated yet. The pipeline may still be running or may have encountered an error.
          </p>
          <Button variant="secondary" onClick={() => router.push(`/projects/${projectId}/processing`)}>
            Back to Processing
          </Button>
        </div>
      </div>
    );
  }

  return (
    <div className="flex-1 flex flex-col h-full bg-background text-foreground relative">
      <div className="flex-1 overflow-y-auto p-6 pb-24">
        <div className="mb-4 flex flex-col md:flex-row md:items-center justify-between gap-4">
          <div>
            <div className="text-[11px] text-muted-foreground flex gap-2 items-center mb-1 uppercase tracking-wider font-bold">
              <span>Project Workspace</span> <span>/</span>
              <span className="text-foreground">Outline Review</span>
            </div>
            <h1 className="text-2xl font-bold tracking-tight">Epic Outline Review</h1>
            <p className="text-[13px] text-muted-foreground mt-1">
              Review the AI-generated epics. Approve, reject, edit, or regenerate based on your needs.
            </p>
          </div>

          <div className="flex gap-2 items-center shrink-0">
            <Button
              onClick={() => setIsTraceabilityOpen(!isTraceabilityOpen)}
              className={cn(
                'bg-secondary text-secondary-foreground font-semibold h-9 border border-border flex items-center gap-1.5',
                isTraceabilityOpen && 'bg-accent border-accent text-accent-foreground shadow-inner'
              )}
            >
              <ShieldCheck className="w-4 h-4" /> Traceability Matrix
            </Button>
            {!allApproved && (
              <Button
                onClick={() => setEpics((prev) => prev.map((e) => ({ ...e, status: 'approved' as EntityStatus })))}
                className="bg-green-500 hover:bg-green-600 text-white font-semibold h-9 shadow-sm"
              >
                <CheckCircle2 className="w-4 h-4" /> Approve All
              </Button>
            )}
          </div>
        </div>

        {/* Traceability Matrix */}
        {isTraceabilityOpen && (
          <div className="bg-card border border-border rounded-xl p-6 mb-6 shadow-sm max-w-5xl">
            <h3 className="text-sm font-bold text-foreground mb-3 flex items-center gap-2">
              <ShieldCheck className="w-4 h-4 text-primary" /> Epic & One-Line Story Traceability
            </h3>
            <div className="overflow-x-auto rounded-lg border border-border">
              <table className="w-full text-xs text-left border-collapse">
                <thead>
                  <tr className="border-b border-border bg-muted/40">
                    <th className="p-3 font-bold text-muted-foreground w-1/3">Epic</th>
                    <th className="p-3 font-bold text-muted-foreground">Mapped Stories</th>
                  </tr>
                </thead>
                <tbody>
                  {epics.map((epic) => {
                    const mapped = oneLineStories.filter(
                      (s: any) => s.epic_id === epic.id || s.epic === epic.id
                    );
                    const epicStory = mapped[0];
                    return (
                      <tr key={epic.id} className="border-b border-border hover:bg-muted/10 font-medium">
                        <td className="p-3 text-foreground font-semibold">{epic.title}</td>
                        <td className="p-3">
                          {!epicStory ? (
                            <span className="text-muted-foreground">—</span>
                          ) : (
                            <span className="bg-primary/10 text-primary border border-primary/20 px-2 py-0.5 rounded font-medium">
                              {epicStory.id}
                            </span>
                          )}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </div>
        )}

        {/* Epic cards */}
        <div className="max-w-5xl space-y-3">
          {epics.map((epic) => {
            const isRegenerating = regeneratingIds.has(epic.id);
            const isEditing = editingId === epic.id;
            const isFeedbackOpen = activeFeedbackId === epic.id;
            const epicStories = oneLineStories.filter(
              (s: any) => s.epic_id === epic.id || s.epic === epic.id
            );
            const epicFeatures = features.filter((feature) => feature.epicId === epic.id);
            const epicStory = epicStories[0];

            return (
              <div
                key={epic.id}
                className={cn(
                  'bg-card border rounded-xl overflow-visible transition-all shadow-sm',
                  epic.status === 'approved'
                    ? 'border-l-4 border-l-green-500'
                    : epic.status === 'rejected'
                    ? 'border-l-4 border-l-red-500'
                    : 'border-l-4 border-l-primary'
                )}
              >
                {isRegenerating ? (
                  <div className="p-4 flex flex-col items-center justify-center space-y-3 text-muted-foreground animate-pulse h-[80px]">
                    <RotateCw className="w-5 h-5 animate-spin text-primary" />
                    <p className="text-[13px]">Regenerating epic...</p>
                  </div>
                ) : (
                  <div>
                    <div className="p-4 flex flex-col md:flex-row items-start md:items-center justify-between gap-4">
                      <div className="flex-1 min-w-0">
                        {isEditing ? (
                          <div className="space-y-3">
                            <input
                              type="text"
                              value={editTitle}
                              onChange={(e) => setEditTitle(e.target.value)}
                              className="w-full bg-background border border-input rounded-lg px-3 py-2 text-base font-bold text-foreground focus:outline-none focus:ring-1 focus:ring-primary"
                            />
                            <input
                              type="text"
                              value={editSummary}
                              onChange={(e) => setEditSummary(e.target.value)}
                              className="w-full bg-background border border-input rounded-lg px-3 py-2 text-sm text-foreground focus:outline-none focus:ring-1 focus:ring-primary"
                            />
                            <div className="flex gap-2 pt-2">
                              <Button
                                size="sm"
                                onClick={() => handleSaveEdit(epic.id)}
                                className="bg-primary hover:bg-primary/90 text-primary-foreground"
                              >
                                Save
                              </Button>
                              <Button size="sm" variant="ghost" onClick={() => setEditingId(null)}>
                                Cancel
                              </Button>
                            </div>
                          </div>
                        ) : (
                          <div className="flex gap-3 items-start">
                            <div className="shrink-0 mt-0.5">
                              <span className="text-[11px] font-bold px-2 py-0.5 bg-muted text-muted-foreground rounded tracking-wider">
                                EP-{String(epic.sNo).padStart(3, '0')}
                              </span>
                            </div>
                            <div>
                              <h3 className="text-[15px] font-semibold text-foreground flex items-center gap-2 leading-snug">
                                {epic.title}
                                {epic.version && epic.version > 1 && (
                                  <span className="text-[10px] bg-primary/10 text-primary px-1.5 py-0.5 rounded font-bold">
                                    v{epic.version}
                                  </span>
                                )}
                                {epic.status === 'approved' && <CheckCircle2 className="w-4 h-4 text-green-500" />}
                                {epic.status === 'rejected' && <X className="w-4 h-4 text-red-500" />}
                              </h3>
                              <p className="text-[13px] text-muted-foreground mt-0.5 line-clamp-2 leading-relaxed">
                                {epic.summary}
                              </p>
                            </div>
                          </div>
                        )}
                      </div>

                      {!isEditing && (
                        <div className="flex items-center gap-2 shrink-0">
                          <Button
                            size="sm"
                            variant="secondary"
                            className="h-7 px-2.5 text-[11px] font-semibold"
                            onClick={() => handleEditClick(epic)}
                          >
                            <Edit2 className="w-3 h-3 mr-1.5" /> Edit
                          </Button>
                          <Button
                            size="sm"
                            variant="secondary"
                            className={cn('h-7 px-2.5 text-[11px] font-semibold', isFeedbackOpen && 'bg-accent')}
                            onClick={() => {
                              setActiveFeedbackId(isFeedbackOpen ? null : epic.id);
                              setEditingId(null);
                            }}
                          >
                            <RotateCw className="w-3 h-3 mr-1.5" /> Regenerate
                          </Button>
                          <Button
                            size="sm"
                            variant="secondary"
                            className={cn(
                              'h-7 px-2.5 text-[11px] font-semibold hover:bg-red-50 hover:text-red-600 hover:border-red-200 dark:hover:bg-red-900/20 dark:hover:text-red-400',
                              epic.status === 'rejected' &&
                                'bg-red-50 border-red-200 text-red-600 dark:bg-red-900/20 dark:text-red-400'
                            )}
                            onClick={() => handleStatusChange(epic.id, 'rejected')}
                          >
                            <X className="w-3 h-3 mr-1.5" /> Reject
                          </Button>
                          <Button
                            size="sm"
                            variant="secondary"
                            className={cn(
                              'h-7 px-2.5 text-[11px] font-semibold hover:bg-green-50 hover:text-green-600 hover:border-green-200 dark:hover:bg-green-900/20 dark:hover:text-green-400',
                              epic.status === 'approved' &&
                                'bg-green-50 border-green-200 text-green-600 dark:bg-green-900/20 dark:text-green-400'
                            )}
                            onClick={() => handleStatusChange(epic.id, 'approved')}
                          >
                            <Check className="w-3 h-3 mr-1.5" /> Approve
                          </Button>
                        </div>
                      )}
                    </div>

                    {/* Regenerate feedback drawer */}
                    <AnimatePresence>
                      {isFeedbackOpen && (
                        <motion.div
                          initial={{ height: 0, opacity: 0 }}
                          animate={{ height: 'auto', opacity: 1 }}
                          exit={{ height: 0, opacity: 0 }}
                          className="border-t border-border bg-muted/30 px-5 py-4 overflow-hidden"
                        >
                          <label className="text-xs font-semibold text-foreground mb-2 block">
                            What should we change about this Epic?
                          </label>
                          <textarea
                            className="w-full bg-background border border-input rounded-lg px-3 py-2 text-sm text-foreground focus:outline-none focus:ring-1 focus:ring-primary resize-none mb-3"
                            rows={2}
                            placeholder="e.g., Make sure it includes guest checkout options."
                            value={feedbackText}
                            onChange={(e) => setFeedbackText(e.target.value)}
                          />
                          <div className="flex justify-end gap-2">
                            <Button size="sm" variant="ghost" onClick={() => setActiveFeedbackId(null)}>
                              Cancel
                            </Button>
                            <Button
                              size="sm"
                              className="bg-primary hover:bg-primary/90 text-primary-foreground"
                              disabled={!feedbackText.trim()}
                              onClick={() => handleRegenerate(epic.id)}
                            >
                              Submit & Regenerate
                            </Button>
                          </div>
                        </motion.div>
                      )}
                    </AnimatePresence>

                    {/* Epic hierarchy: all features followed by one consolidated story. */}
                    {(epicFeatures.length > 0 || epicStory) && (
                      <div className="border-t border-border px-5 py-3 bg-muted/5">
                        <button
                          onClick={() => toggleOneLineStories(epic.id)}
                          className="flex items-center gap-2 text-xs font-semibold text-muted-foreground hover:text-primary transition-colors focus:outline-none"
                        >
                          {expandedOneLineStories.has(epic.id) ? (
                            <ChevronUp className="w-3.5 h-3.5" />
                          ) : (
                            <ChevronDown className="w-3.5 h-3.5" />
                          )}
                          <span>
                            View Epic Details ({epicFeatures.length} {epicFeatures.length === 1 ? 'Feature' : 'Features'}, {epicStory ? 1 : 0} One-Line Story)
                          </span>
                        </button>

                        <AnimatePresence>
                          {expandedOneLineStories.has(epic.id) && (
                            <motion.div
                              initial={{ height: 0, opacity: 0 }}
                              animate={{ height: 'auto', opacity: 1 }}
                              exit={{ height: 0, opacity: 0 }}
                              className="mt-3 overflow-hidden"
                            >
                              <div className="space-y-4 border-l border-border pl-4 ml-1.5 py-1">
                                <div>
                                  <p className="mb-2 text-[11px] font-bold uppercase tracking-wider text-muted-foreground">
                                    Features
                                  </p>
                                  {epicFeatures.length > 0 ? (
                                    <ul className="space-y-2">
                                      {epicFeatures.map((feature) => (
                                        <li key={feature.id} className="text-xs text-foreground flex items-start gap-2 leading-relaxed">
                                          <span className="font-bold text-primary shrink-0">{feature.id}:</span>
                                          <span>{feature.title}</span>
                                        </li>
                                      ))}
                                    </ul>
                                  ) : (
                                    <p className="text-xs text-muted-foreground">No mapped features.</p>
                                  )}
                                </div>

                                {epicStory && (
                                  <div className="rounded-lg border border-primary/20 bg-primary/5 p-3">
                                    <p className="mb-1.5 text-[11px] font-bold uppercase tracking-wider text-primary">
                                      Epic One-Line Story
                                    </p>
                                    <p className="text-xs text-foreground leading-relaxed">
                                      <span className="font-bold text-primary">{epicStory.id}: </span>
                                      {storyText(epicStory)}
                                    </p>
                                  </div>
                                )}
                              </div>
                            </motion.div>
                          )}
                        </AnimatePresence>
                      </div>
                    )}
                  </div>
                )}
              </div>
            );
          })}
        </div>
      </div>

      {/* Sticky bottom bar */}
      <div className="sticky bottom-0 left-0 right-0 p-6 bg-card/80 backdrop-blur-md border-t border-border flex items-center justify-between z-10">
        <div className="flex items-center gap-3">
          {!allReviewed ? (
            <div className="flex items-center gap-2 text-amber-500 text-sm font-medium">
              <AlertTriangle className="w-5 h-5" />
              <span>Review all {epics.length} epics before proceeding.</span>
            </div>
          ) : !hasApproved ? (
            <div className="flex items-center gap-2 text-amber-500 text-sm font-medium">
              <AlertTriangle className="w-5 h-5" />
              <span>Approve at least one epic to continue.</span>
            </div>
          ) : (
            <div className="flex items-center gap-2 text-green-500 text-sm font-medium">
              <CheckCircle2 className="w-5 h-5" />
              <span>Epics reviewed! Navigating to story generation...</span>
            </div>
          )}
        </div>
        <Button
          disabled={!canProceed}
          onClick={workflowStatus === 'OUTLINE_REVIEW_REQUIRED' ? handleApproveOutline : () => router.push(`/projects/${projectId}/stories`)}
          size="lg"
          className="bg-primary hover:bg-primary/90 text-primary-foreground text-base shadow-md disabled:opacity-50"
        >
          {workflowStatus === 'OUTLINE_REVIEW_REQUIRED' ? 'Approve & Continue Pipeline' : 'Proceed to Story Generation'} <ArrowRight className="w-4 h-4 ml-2" />
        </Button>
      </div>
    </div>
  );
}
