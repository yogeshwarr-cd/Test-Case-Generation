'use client';

import React, { useEffect, useState } from 'react';
import { useRouter, useParams } from 'next/navigation';
import {
  Search, LayoutGrid, List, AlertTriangle, Check, CheckCircle2,
  ChevronDown, ChevronUp, Edit2, RotateCw, X, Loader2, ArrowRight,
} from 'lucide-react';
import { api } from '@/services/api';
import { Story, EntityStatus } from '@/services/mockData';
import { ConfidenceBadge } from '@/components/common/ConfidenceBadge';
import { Button } from '@/components/common/Button';
import { cn } from '@/lib/utils';
import { motion, AnimatePresence } from 'framer-motion';

export default function StoryBoardPage() {
  const router = useRouter();
  const params = useParams();
  const projectId = params?.projectId as string;

  const [stories, setStories] = useState<Story[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [viewMode, setViewMode] = useState<'grid' | 'list'>('list');
  const [searchQuery, setSearchQuery] = useState('');
  const [statusFilter, setStatusFilter] = useState<'all' | EntityStatus>('all');

  useEffect(() => {
    api
      .getStories(projectId)
      .then((data) => {
        setStories(data);
        setLoading(false);
      })
      .catch((err) => {
        setError(err?.message || 'Failed to load stories.');
        setLoading(false);
      });
  }, [projectId]);

  const handleStatusChange = async (storyId: string, newStatus: EntityStatus, bumpVersion?: boolean) => {
    try {
      const updated = await api.updateStory(projectId, storyId, { status: newStatus });
      setStories((prev) =>
        prev.map((s) =>
          s.id === storyId
            ? { ...updated, version: bumpVersion ? (s.version || 1) + 1 : s.version }
            : s
        )
      );
    } catch (err) {
      console.error(err);
    }
  };

  const handleUpdateStory = (updatedStory: Story) => {
    setStories((prev) => prev.map((s) => (s.id === updatedStory.id ? updatedStory : s)));
  };

  const filteredStories = stories.filter((story) => {
    const matchesSearch =
      story.summary.toLowerCase().includes(searchQuery.toLowerCase()) ||
      story.usId.toLowerCase().includes(searchQuery.toLowerCase()) ||
      story.epicName.toLowerCase().includes(searchQuery.toLowerCase());
    const matchesStatus = statusFilter === 'all' || story.status === statusFilter;
    return matchesSearch && matchesStatus;
  });

  if (loading) {
    return (
      <div className="flex-1 flex items-center justify-center p-8 bg-background">
        <div className="flex flex-col items-center gap-3 text-muted-foreground">
          <Loader2 className="w-7 h-7 animate-spin text-primary" />
          <p className="text-sm">Loading story board...</p>
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

  if (stories.length === 0) {
    return (
      <div className="flex-1 flex items-center justify-center p-8 bg-background">
        <div className="flex flex-col items-center gap-3 text-muted-foreground max-w-md text-center">
          <p className="text-sm">
            No user stories generated yet. The pipeline may still be running.
          </p>
          <Button variant="secondary" onClick={() => router.push(`/projects/${projectId}/processing`)}>
            Back to Processing
          </Button>
        </div>
      </div>
    );
  }

  return (
    <div className="flex-1 overflow-y-auto bg-muted/10 text-foreground relative h-full">
      {/* Header */}
      <div className="p-6 pb-4 border-b border-border bg-background">
        <div className="text-[11px] text-muted-foreground flex gap-2 items-center mb-1 uppercase tracking-wider font-bold">
          <span>Project Workspace</span> <span>/</span> <span className="text-foreground">Story Board</span>
        </div>
        <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-4">
          <div>
            <h1 className="text-2xl font-bold tracking-tight">Story Board</h1>
            <p className="text-[13px] text-muted-foreground mt-1">
              {stories.length} user stories generated from your document.
            </p>
          </div>

          <div className="flex flex-wrap items-center gap-3">
            <Button
              size="sm"
              onClick={() =>
                setStories((prev) => prev.map((s) => ({ ...s, status: 'approved' as EntityStatus })))
              }
              className="bg-green-500 hover:bg-green-600 text-white font-semibold h-[32px]"
            >
              <CheckCircle2 className="w-4 h-4 mr-2" /> Approve All
            </Button>

            <div className="relative w-[240px]">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-muted-foreground" />
              <input
                type="text"
                placeholder="Search stories..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="w-full pl-9 pr-4 h-[32px] bg-background border border-input rounded-lg text-[13px] focus:outline-none focus:ring-1 focus:ring-primary"
              />
            </div>

            <select
              value={statusFilter}
              onChange={(e) => setStatusFilter(e.target.value as any)}
              className="bg-background border border-input text-[13px] rounded-lg px-3 h-[32px] focus:outline-none focus:ring-1 focus:ring-primary"
            >
              <option value="all">All Statuses</option>
              <option value="ready_for_review">Ready for Review</option>
              <option value="needs_ba_review">Needs BA Review</option>
              <option value="approved">Approved</option>
              <option value="rejected">Rejected</option>
            </select>

            <div className="flex bg-muted/50 rounded-lg p-1 border border-border">
              <button
                onClick={() => setViewMode('grid')}
                className={cn('p-1.5 rounded transition-colors', viewMode === 'grid' ? 'bg-background shadow-sm text-foreground' : 'text-muted-foreground')}
              >
                <LayoutGrid className="w-4 h-4" />
              </button>
              <button
                onClick={() => setViewMode('list')}
                className={cn('p-1.5 rounded transition-colors', viewMode === 'list' ? 'bg-background shadow-sm text-foreground' : 'text-muted-foreground')}
              >
                <List className="w-4 h-4" />
              </button>
            </div>
          </div>
        </div>
      </div>

      {/* Story grid / list */}
      <div className="p-6 pb-24">
        <div className={cn(
          viewMode === 'grid'
            ? 'grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4'
            : 'flex flex-col gap-4 max-w-5xl mx-auto'
        )}>
          {filteredStories.map((story) => (
            <StoryCard
              key={story.id}
              story={story}
              projectId={projectId}
              viewMode={viewMode}
              onStatusChange={(status, bumpVersion) => handleStatusChange(story.id, status, bumpVersion)}
              onUpdate={handleUpdateStory}
            />
          ))}
          {filteredStories.length === 0 && (
            <div className="col-span-full py-12 text-center text-muted-foreground">
              No stories match your filters.
            </div>
          )}
        </div>
      </div>

      {/* Sticky bottom bar */}
      <div className="sticky bottom-0 left-0 right-0 p-6 bg-card/80 backdrop-blur-md border-t border-border flex items-center justify-between z-10">
        <div className="flex items-center gap-3">
          {stories.some(s => s.status === 'needs_ba_review' || s.status === 'ready_for_review') ? (
            <div className="flex items-center gap-2 text-amber-500 text-sm font-medium">
              <AlertTriangle className="w-5 h-5" />
              <span>Review all {stories.length} stories before proceeding.</span>
            </div>
          ) : !stories.some(s => s.status === 'approved') ? (
            <div className="flex items-center gap-2 text-amber-500 text-sm font-medium">
              <AlertTriangle className="w-5 h-5" />
              <span>Approve at least one story to continue.</span>
            </div>
          ) : (
            <div className="flex items-center gap-2 text-green-500 text-sm font-medium">
              <CheckCircle2 className="w-5 h-5" />
              <span>Stories reviewed! Ready for validation.</span>
            </div>
          )}
        </div>
        <Button
          disabled={stories.some(s => s.status === 'needs_ba_review' || s.status === 'ready_for_review') || !stories.some(s => s.status === 'approved')}
          onClick={() => router.push(`/projects/${projectId}/validation`)}
          size="lg"
          className="bg-primary hover:bg-primary/90 text-primary-foreground text-base shadow-md disabled:opacity-50"
        >
          Proceed to Validation <ArrowRight className="w-4 h-4 ml-2" />
        </Button>
      </div>
    </div>
  );
}

function StoryCard({
  story,
  projectId,
  viewMode,
  onStatusChange,
  onUpdate,
}: {
  story: Story;
  projectId: string;
  viewMode: 'grid' | 'list';
  onStatusChange: (status: EntityStatus, bumpVersion?: boolean) => void;
  onUpdate: (updated: Story) => void;
}) {
  const [expandedACs, setExpandedACs] = useState(false);
  const [isFeedbackOpen, setIsFeedbackOpen] = useState(false);
  const [feedbackText, setFeedbackText] = useState('');
  const [isRegenerating, setIsRegenerating] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  const [isEditing, setIsEditing] = useState(false);
  const [editTitle, setEditTitle] = useState(story.summary);
  const [editDesc, setEditDesc] = useState(story.description);

  const handleSaveEdit = async () => {
    if (!editTitle.trim()) return;
    setIsSaving(true);
    try {
      const updated = await api.updateStory(projectId, story.id, {
        summary: editTitle,
        description: editDesc,
      });
      onUpdate(updated);
      setIsEditing(false);
    } catch (err) {
      console.error('Failed to save story edit:', err);
    } finally {
      setIsSaving(false);
    }
  };

  const handleRegenerate = async () => {
    if (!feedbackText.trim()) return;
    setIsFeedbackOpen(false);
    setIsRegenerating(true);
    try {
      // Build a minimal retry request using current story data
      const resolvedWorkflowId = (typeof window !== 'undefined' && localStorage.getItem(`wf_id_${projectId}`)) || projectId;
      const retryRequest = {
        workflow_id: resolvedWorkflowId,
        previous_stories: [
          {
            id: story.id,
            feature_id: story.feature,
            epic_id: story.epicId || null,
            title: story.summary,
            user_story: story.summary,
            description: story.description,
            acceptance_criteria: story.acceptanceCriteria.map((ac, i) => ({
              id: `AC-${i + 1}`,
              description: ac,
              source_refs: [],
            })),
            business_rules: story.businessRules,
            dependencies: story.dependencies.map((d, i) => ({
              id: `DEP-${i + 1}`,
              description: d,
              depends_on: [],
              source_refs: [],
            })),
            priority: story.priority || 'MEDIUM',
            story_points: story.storyPoints || 3,
            confidence_score: story.confidenceScore,
            traceability: { workflow_id: projectId },
          },
        ],
        validation_issues: [
          {
            issue_id: 'UI-FEEDBACK',
            severity: 'WARNING',
            category: 'BA Feedback',
            story_id: story.id,
            field: 'general',
            message: feedbackText,
          },
        ],
        retry_attempt: 1,
      };
      const newStory = await api.retryStoryGeneration(
        retryRequest,
        story.sNo - 1,
        { [story.epicId || '']: story.epicName }
      );
      onUpdate(newStory);
      onStatusChange('ready_for_review', true);
    } catch (err) {
      console.error('Regeneration failed:', err);
      // Still bump the version visually so the BA knows a retry was attempted
      onStatusChange('ready_for_review', true);
    } finally {
      setFeedbackText('');
      setIsRegenerating(false);
    }
  };

  return (
    <div
      className={cn(
        'bg-card border rounded-xl overflow-visible shadow-sm flex flex-col relative group transition-all',
        story.status === 'approved'
          ? 'border-l-4 border-l-green-500'
          : story.status === 'rejected'
          ? 'border-l-4 border-l-red-500'
          : story.status === 'needs_ba_review'
          ? 'border-l-4 border-l-amber-500 shadow-amber-500/10'
          : 'border-l-4 border-l-primary'
      )}
    >
      {isRegenerating ? (
        <div className="p-4 flex flex-col items-center justify-center space-y-3 text-muted-foreground animate-pulse h-[180px]">
          <RotateCw className="w-5 h-5 animate-spin text-primary" />
          <p className="text-[13px]">Regenerating story based on feedback...</p>
        </div>
      ) : (
        <>
          <div className="p-4 flex-1 flex flex-col relative">
            {/* Top row */}
            <div className="flex justify-between items-start mb-4 gap-4">
              <div className="flex gap-2 items-center flex-wrap">
                <span className="text-xs font-bold text-muted-foreground bg-muted px-2 py-0.5 rounded">
                  #{story.sNo}
                </span>
                <span className="text-sm font-bold text-primary flex items-center gap-2">
                  {story.usId}
                  {story.version && story.version > 1 && (
                    <span className="text-[10px] bg-primary/10 text-primary px-1.5 py-0.5 rounded font-bold">
                      v{story.version}
                    </span>
                  )}
                </span>
                <span className="text-xs font-medium text-muted-foreground bg-accent px-2 py-0.5 rounded line-clamp-1">
                  {story.epicName}
                </span>
                {story.priority && (
                  <span
                    className={cn(
                      'text-[10px] font-bold px-2 py-0.5 rounded uppercase tracking-wide',
                      story.priority === 'HIGH'
                        ? 'bg-red-500/10 text-red-500 border border-red-500/20'
                        : story.priority === 'MEDIUM'
                        ? 'bg-blue-500/10 text-blue-500 border border-blue-500/20'
                        : 'bg-slate-500/10 text-slate-500 border border-slate-500/20'
                    )}
                  >
                    {story.priority}
                  </span>
                )}
                {story.storyPoints !== undefined && (
                  <span className="text-[10px] font-bold text-purple-600 bg-purple-500/10 px-2 py-0.5 rounded border border-purple-500/20">
                    {story.storyPoints} SP
                  </span>
                )}
              </div>
              <div className="flex items-center gap-2">
                {story.status === 'needs_ba_review' && (
                  <div className="group/warning relative">
                    <AlertTriangle className="w-4 h-4 text-amber-500 cursor-help" />
                    <div className="absolute top-full right-0 mt-2 hidden group-hover/warning:block z-50 w-64 p-2 bg-popover text-popover-foreground text-xs rounded border border-border shadow-lg">
                      {story.validationFinding || 'Needs BA Review'}
                    </div>
                  </div>
                )}
                <ConfidenceBadge score={story.confidenceScore} />
              </div>
            </div>

            {/* Content */}
            {isEditing ? (
              <div className="space-y-3 mb-4">
                <textarea
                  value={editTitle}
                  onChange={(e) => setEditTitle(e.target.value)}
                  className="w-full bg-background border border-input rounded-lg px-3 py-2 text-[15px] font-semibold text-foreground focus:outline-none focus:ring-1 focus:ring-primary resize-none"
                  rows={2}
                />
                <textarea
                  value={editDesc}
                  onChange={(e) => setEditDesc(e.target.value)}
                  className="w-full bg-background border border-input rounded-lg px-3 py-2 text-[13px] text-foreground focus:outline-none focus:ring-1 focus:ring-primary resize-none"
                  rows={3}
                />
                <div className="flex gap-2">
                  <Button
                    size="sm"
                    onClick={handleSaveEdit}
                    disabled={isSaving}
                    className="bg-primary text-primary-foreground h-7 text-[11px]"
                  >
                    {isSaving ? <Loader2 className="w-3 h-3 animate-spin" /> : 'Save'}
                  </Button>
                  <Button size="sm" variant="ghost" onClick={() => setIsEditing(false)} className="h-7 text-[11px]">
                    Cancel
                  </Button>
                </div>
              </div>
            ) : (
              <div className="mb-4">
                <h3 className="font-semibold text-foreground text-[15px] mb-1 leading-snug">{story.summary}</h3>
                <p className="text-[13px] text-muted-foreground leading-relaxed line-clamp-2">{story.description}</p>
              </div>
            )}

            {/* Expandable ACs */}
            <div className="mt-auto border-t border-border pt-4">
              <button
                onClick={() => setExpandedACs(!expandedACs)}
                className="flex items-center justify-between w-full text-[13px] font-semibold text-foreground hover:text-primary transition-colors"
              >
                <span>
                  Acceptance Criteria{' '}
                  <span className="bg-muted text-muted-foreground text-[11px] px-1.5 py-0.5 rounded ml-2">
                    {story.acceptanceCriteria.length}
                  </span>
                </span>
                {expandedACs ? <ChevronUp className="w-3.5 h-3.5" /> : <ChevronDown className="w-3.5 h-3.5" />}
              </button>

              <AnimatePresence>
                {expandedACs && (
                  <motion.div
                    initial={{ height: 0, opacity: 0 }}
                    animate={{ height: 'auto', opacity: 1 }}
                    exit={{ height: 0, opacity: 0 }}
                    className="overflow-hidden"
                  >
                    <div className="mt-4 space-y-3 pl-3 border-l-2 border-primary/30">
                      {story.acceptanceCriteria.map((ac, i) => (
                        <div
                          key={i}
                          className="text-[13px] text-foreground bg-muted/40 p-2.5 rounded-lg leading-relaxed border border-border/50"
                        >
                          {ac}
                        </div>
                      ))}
                      {story.businessRules.length > 0 && (
                        <div className="mt-3">
                          <div className="text-[11px] font-bold text-muted-foreground uppercase mb-1.5 tracking-wider">
                            Business Rules
                          </div>
                          <ul className="list-disc pl-4 text-[13px] text-muted-foreground space-y-1">
                            {story.businessRules.map((br, i) => (
                              <li key={i}>{br}</li>
                            ))}
                          </ul>
                        </div>
                      )}
                    </div>
                  </motion.div>
                )}
              </AnimatePresence>
            </div>
          </div>

          {/* Feedback drawer */}
          <AnimatePresence>
            {isFeedbackOpen && (
              <motion.div
                initial={{ height: 0, opacity: 0 }}
                animate={{ height: 'auto', opacity: 1 }}
                exit={{ height: 0, opacity: 0 }}
                className="border-t border-border bg-muted/30 px-5 py-4 overflow-hidden"
              >
                <label className="text-xs font-semibold text-foreground mb-2 block">
                  Regenerate instructions
                </label>
                <textarea
                  className="w-full bg-background border border-input rounded-lg px-3 py-2 text-sm text-foreground focus:outline-none focus:ring-1 focus:ring-primary resize-none mb-3"
                  rows={2}
                  placeholder="e.g., Rewrite ACs in BDD format."
                  value={feedbackText}
                  onChange={(e) => setFeedbackText(e.target.value)}
                />
                <div className="flex justify-end gap-2">
                  <Button size="sm" variant="ghost" onClick={() => setIsFeedbackOpen(false)}>
                    Cancel
                  </Button>
                  <Button
                    size="sm"
                    className="bg-primary text-primary-foreground"
                    disabled={!feedbackText.trim()}
                    onClick={handleRegenerate}
                  >
                    Regenerate Story
                  </Button>
                </div>
              </motion.div>
            )}
          </AnimatePresence>

          {/* Actions footer */}
          {!isEditing && (
            <div className="bg-muted/20 border-t border-border p-2.5 flex flex-wrap gap-2 items-center justify-end">
              <Button
                size="sm"
                variant="secondary"
                className="h-7 px-2.5 text-[11px] font-semibold bg-background"
                onClick={() => {
                  setIsEditing(true);
                  setIsFeedbackOpen(false);
                  setEditTitle(story.summary);
                  setEditDesc(story.description);
                }}
              >
                <Edit2 className="w-3 h-3 mr-1.5" /> Edit
              </Button>
              <Button
                size="sm"
                variant="secondary"
                className={cn('h-7 px-2.5 text-[11px] font-semibold bg-background', isFeedbackOpen && 'bg-accent')}
                onClick={() => {
                  setIsFeedbackOpen(!isFeedbackOpen);
                  setIsEditing(false);
                }}
              >
                <RotateCw className="w-3 h-3 mr-1.5" /> Regenerate
              </Button>
              <Button
                size="sm"
                variant="secondary"
                className={cn(
                  'h-7 px-2.5 text-[11px] font-semibold bg-background hover:bg-red-50 hover:text-red-600 hover:border-red-200 dark:hover:bg-red-900/20 dark:hover:text-red-400',
                  story.status === 'rejected' &&
                    'bg-red-50 border-red-200 text-red-600 dark:bg-red-900/20 dark:text-red-400'
                )}
                onClick={() => onStatusChange('rejected')}
              >
                <X className="w-3 h-3 mr-1.5" /> Reject
              </Button>
              <Button
                size="sm"
                variant="secondary"
                className={cn(
                  'h-7 px-2.5 text-[11px] font-semibold bg-background hover:bg-green-50 hover:text-green-600 hover:border-green-200 dark:hover:bg-green-900/20 dark:hover:text-green-400',
                  story.status === 'approved' &&
                    'bg-green-50 border-green-200 text-green-600 dark:bg-green-900/20 dark:text-green-400'
                )}
                onClick={() => onStatusChange('approved')}
              >
                <Check className="w-3 h-3 mr-1.5" /> Approve
              </Button>
            </div>
          )}
        </>
      )}
    </div>
  );
}
