'use client';

import React, { useEffect, useState, useRef } from 'react';
import { useRouter, useParams } from 'next/navigation';
import { motion, AnimatePresence } from 'framer-motion';
import { LiveActivityFeed } from '@/components/common/LiveActivityFeed';
import { ProcessLog } from '@/services/mockData';
import { Button } from '@/components/common/Button';
import { api } from '@/services/api';
import {
  CheckCircle2, AlertTriangle, RotateCw, ArrowRight,
  Loader2, FileSearch, Cpu, GitBranch, BookOpen, ShieldCheck, Sparkles
} from 'lucide-react';

// ─── localStorage key helpers ──────────────────────────────────────────────────
function filePathKey(projectId: string) { return `wf_file_path_${projectId}`; }
function workflowIdKey(projectId: string) { return `wf_id_${projectId}`; }

// ─── Pipeline stages definition ────────────────────────────────────────────────
const PIPELINE_STAGES = [
  { key: 'Preprocessing',         label: 'Document Ingestion',       icon: FileSearch,  desc: 'Parsing and chunking document' },
  { key: 'RequirementAnalysis',   label: 'Requirement Analysis',     icon: BookOpen,    desc: 'Extracting functional requirements' },
  { key: 'EpicGeneration',        label: 'Epic Generation',          icon: GitBranch,   desc: 'Structuring high-level epics' },
  { key: 'FeatureGeneration',     label: 'Feature Mapping',          icon: Cpu,         desc: 'Mapping features to epics' },
  { key: 'UserStoryGeneration',   label: 'User Story Generation',    icon: Sparkles,    desc: 'Generating detailed user stories' },
  { key: 'ValidationGate',        label: 'Quality Validation',       icon: ShieldCheck, desc: 'INVEST compliance & confidence scoring' },
];

const NODE_TO_STAGE: Record<string, string> = {
  // Initial states
  'START': 'Preprocessing',
  'PENDING': 'Preprocessing',
  'RUNNING': 'Preprocessing',
  // LangGraph snake_case internal names (from _core_node_names)
  'preprocessing': 'Preprocessing',
  'requirement_analysis': 'RequirementAnalysis',
  'epic_generation': 'EpicGeneration',
  'feature_generation': 'FeatureGeneration',
  'one_line_story_generation': 'FeatureGeneration',
  'nlp_rag_hook': 'UserStoryGeneration',
  'user_story_generation': 'UserStoryGeneration',
  'validation': 'ValidationGate',
  'human_review_hook': 'ValidationGate',
  // PascalCase display names (may come from some places)
  'Preprocessing': 'Preprocessing',
  'RequirementAnalysis': 'RequirementAnalysis',
  'Requirements Analysis': 'RequirementAnalysis',
  'EpicGeneration': 'EpicGeneration',
  'Epic Generation': 'EpicGeneration',
  'FeatureGeneration': 'FeatureGeneration',
  'Feature Generation': 'FeatureGeneration',
  'OneLineStoryMapping': 'FeatureGeneration',
  'RAGContextRetrieval': 'UserStoryGeneration',
  'UserStoryGeneration': 'UserStoryGeneration',
  'User Story Generation': 'UserStoryGeneration',
  'ValidationGate': 'ValidationGate',
  'Validation Gate': 'ValidationGate',
  // Terminal states
  'COMPLETED': 'COMPLETED',
  'END': 'COMPLETED',
};

export default function ProcessingPage() {
  const router = useRouter();
  const params = useParams();
  const projectId = params?.projectId as string;

  const [currentNode, setCurrentNode]   = useState<string>('PENDING');
  const [logs, setLogs]                 = useState<ProcessLog[]>([]);
  const [isComplete, setIsComplete]     = useState(false);
  const [errorDetails, setErrorDetails] = useState<string | null>(null);
  const [startError, setStartError]     = useState<string | null>(null);
  const [pollCount, setPollCount]       = useState(0);

  const startedRef = useRef(false);
  const completedRef = useRef(false);

  // Derive which stage index is active
  const activeStageKey = NODE_TO_STAGE[currentNode] || '';
  const activeStageIdx = PIPELINE_STAGES.findIndex(s => s.key === activeStageKey);

  useEffect(() => {
    if (startedRef.current) return;
    startedRef.current = true;

    let pollTimer: ReturnType<typeof setTimeout>;

    const startAndPoll = async () => {
      // ── 1. Resolve or start workflow ──────────────────────────────────────
      let workflowId = localStorage.getItem(workflowIdKey(projectId));

      if (workflowId) {
        try {
          await api.getWorkflowState(workflowId);
        } catch (err: any) {
          const msg: string = err?.message || '';
          if (msg.toLowerCase().includes('not found') || msg.toLowerCase().includes('was not found')) {
            localStorage.removeItem(workflowIdKey(projectId));
            workflowId = null as unknown as string | null;
          }
        }
      }

      if (!workflowId) {
        const filePath = localStorage.getItem(filePathKey(projectId));
        if (!filePath) {
          setStartError('No document found. Please go back to the Intake page and upload a document first.');
          return;
        }
        try {
          const res = await api.startWorkflow(filePath, 0.8, 3, projectId);
          workflowId = res.workflow_id as string;
          if (!workflowId) throw new Error('Backend did not return a workflow_id.');
          localStorage.setItem(workflowIdKey(projectId), workflowId);
        } catch (err: any) {
          const msg: string = err?.message || 'Unknown error';
          if (msg.toLowerCase().includes('failed to fetch') || msg.toLowerCase().includes('networkerror')) {
            setStartError('Cannot reach the backend. Make sure the FastAPI server is running on port 8000.');
          } else {
            setStartError(msg);
          }
          return;
        }
      }

      // ── 2. Poll every 2 seconds ───────────────────────────────────────────
      const pollStatus = async () => {
        if (completedRef.current) return;

        try {
          const res = await api.getWorkflowState(workflowId!);
          const state = res.state || {};
          const wfStatus: string = res.workflow_status || state.workflow_status || 'RUNNING';
          const node: string = state.current_node || currentNode;

          setCurrentNode(node);
          setPollCount(p => p + 1);

          // Map execution_history to log entries
          if (Array.isArray(state.execution_history) && state.execution_history.length > 0) {
            const mappedLogs: ProcessLog[] = state.execution_history.map((event: any, idx: number) => {
              let message = `Completed ${event.node_name} in ${Math.round(event.duration_ms || 0)}ms.`;
              if (event.status === 'failed') {
                const rawErr: string = event.error?.message || event.error?.detail || '';
                message = `${event.node_name} failed: ${rawErr || 'unexpected pipeline error'}`;
              }
              return {
                id: `log-${idx}`,
                message,
                agent: event.node_name || 'System Agent',
                status: event.status === 'failed' ? 'failed' : 'success',
                timestamp: new Date(event.completed_at || event.started_at).toLocaleTimeString(),
              };
            });
            setLogs(mappedLogs);
          }

          if (wfStatus === 'COMPLETED' || wfStatus === 'REVIEW_REQUIRED' || wfStatus === 'OUTLINE_REVIEW_REQUIRED') {
            completedRef.current = true;
            setIsComplete(true);
            setCurrentNode(wfStatus);
            return;
          }

          if (wfStatus === 'FAILED') {
            completedRef.current = true;
            const rawErr: string = state.last_error?.message || state.last_error?.detail
              || res.last_error?.message || res.last_error?.detail
              || 'Pipeline encountered an unexpected error.';
            setErrorDetails(rawErr);
            return;
          }
        } catch (err) {
          console.warn('Status polling error:', err);
        }

        if (!completedRef.current) {
          pollTimer = setTimeout(pollStatus, 2000);
        }
      };

      pollStatus();
    };

    startAndPoll();

    return () => {
      if (pollTimer) clearTimeout(pollTimer);
    };
  }, [projectId]);

  const handleRetry = () => {
    localStorage.removeItem(filePathKey(projectId));
    localStorage.removeItem(workflowIdKey(projectId));
    completedRef.current = false;
    router.push(`/projects/${projectId}/intake`);
  };

  const handleContinue = () => {
    if (currentNode === 'OUTLINE_REVIEW_REQUIRED') {
      router.push(`/projects/${projectId}/epics`);
    } else {
      router.push(`/projects/${projectId}/requirements`);
    }
  };

  return (
    <div className="flex-1 flex flex-col min-h-0 bg-background text-foreground overflow-auto">
      {/* ── Header ────────────────────────────────────────────────────────── */}
      <div className="border-b border-border px-8 py-5">
        <div className="flex items-center justify-between max-w-5xl mx-auto">
          <div>
            <h1 className="text-xl font-bold text-foreground">AI Pipeline</h1>
            <p className="text-sm text-muted-foreground mt-0.5">
              {isComplete
                ? (currentNode === 'OUTLINE_REVIEW_REQUIRED' ? 'Initial outline generated. Awaiting your review.' : 'All agents completed successfully')
                : startError
                  ? 'Could not start the pipeline'
                  : errorDetails
                    ? 'Pipeline encountered an error'
                    : 'Processing your document through the multi-agent pipeline…'}
            </p>
          </div>
          <div className="flex items-center gap-2">
            {isComplete && (
              <motion.div initial={{ opacity: 0, scale: 0.9 }} animate={{ opacity: 1, scale: 1 }}>
                <Button onClick={handleContinue} className="flex items-center gap-2 bg-primary text-primary-foreground hover:bg-primary/90 shadow-md">
                  {currentNode === 'OUTLINE_REVIEW_REQUIRED' ? 'Review Epics & Features' : 'Review Requirements'} <ArrowRight className="w-4 h-4" />
                </Button>
              </motion.div>
            )}
            {(startError || errorDetails) && (
              <Button onClick={handleRetry} variant="secondary" className="flex items-center gap-2">
                <RotateCw className="w-4 h-4" /> Go Back & Retry
              </Button>
            )}
          </div>
        </div>
      </div>

      {/* ── Content ───────────────────────────────────────────────────────── */}
      <div className="flex-1 px-8 py-6 max-w-5xl mx-auto w-full space-y-6">

        {/* Start error banner */}
        {startError && (
          <motion.div initial={{ opacity: 0, y: -8 }} animate={{ opacity: 1, y: 0 }}
            className="bg-red-500/10 text-red-500 border border-red-500/20 rounded-xl p-4 flex items-start gap-3">
            <AlertTriangle className="w-5 h-5 shrink-0 mt-0.5" />
            <div>
              <h4 className="font-bold text-sm mb-1">Could Not Start Workflow</h4>
              <p className="text-xs leading-normal">{startError}</p>
            </div>
          </motion.div>
        )}

        {/* Runtime error banner */}
        {errorDetails && (
          <motion.div initial={{ opacity: 0, y: -8 }} animate={{ opacity: 1, y: 0 }}
            className="bg-red-500/10 text-red-500 border border-red-500/20 rounded-xl p-4 flex items-start gap-3">
            <AlertTriangle className="w-5 h-5 shrink-0 mt-0.5" />
            <div>
              <h4 className="font-bold text-sm mb-1">Processing Encountered an Error</h4>
              <p className="text-xs leading-normal whitespace-pre-wrap">{errorDetails}</p>
            </div>
          </motion.div>
        )}

        {/* Completion success banner */}
        {isComplete && (
          <motion.div initial={{ opacity: 0, y: -8 }} animate={{ opacity: 1, y: 0 }}
            className="bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 border border-emerald-500/20 rounded-xl p-4 flex items-center gap-3">
            <CheckCircle2 className="w-5 h-5 shrink-0" />
            <div>
              <h4 className="font-bold text-sm">Pipeline Complete!</h4>
              <p className="text-xs mt-0.5 opacity-80">All agents ran successfully. Click "Review Requirements" to inspect the output.</p>
            </div>
          </motion.div>
        )}

        {/* ── Pipeline stage timeline ─────────────────────────────────────── */}
        {!startError && (
          <div className="bg-card border border-border rounded-2xl overflow-hidden">
            <div className="px-6 py-4 border-b border-border">
              <h2 className="text-sm font-semibold text-foreground">Agent Pipeline</h2>
              <p className="text-xs text-muted-foreground mt-0.5">Multi-agent workflow — 6 stages</p>
            </div>
            <div className="divide-y divide-border">
              {PIPELINE_STAGES.map((stage, idx) => {
                const Icon = stage.icon;
                const isDone    = isComplete || (activeStageIdx > idx && activeStageIdx !== -1);
                const isActive  = !isComplete && activeStageKey === stage.key;
                const isPending = !isDone && !isActive;

                return (
                  <motion.div
                    key={stage.key}
                    className={`flex items-center gap-4 px-6 py-4 transition-colors ${isActive ? 'bg-primary/5' : ''}`}
                    initial={{ opacity: 0, x: -12 }}
                    animate={{ opacity: 1, x: 0 }}
                    transition={{ delay: idx * 0.06 }}
                  >
                    {/* Status indicator */}
                    <div className={`shrink-0 w-8 h-8 rounded-full flex items-center justify-center transition-all
                      ${isDone    ? 'bg-emerald-500/15 text-emerald-500'   : ''}
                      ${isActive  ? 'bg-primary/15 text-primary ring-2 ring-primary/30' : ''}
                      ${isPending ? 'bg-muted/40 text-muted-foreground' : ''}
                    `}>
                      {isDone   ? <CheckCircle2 className="w-4 h-4" />                          : null}
                      {isActive ? <Loader2 className="w-4 h-4 animate-spin" />                  : null}
                      {isPending ? <Icon className="w-4 h-4 opacity-50" />                       : null}
                    </div>

                    {/* Label + desc */}
                    <div className="flex-1 min-w-0">
                      <p className={`text-sm font-medium leading-tight ${isPending ? 'text-muted-foreground' : 'text-foreground'}`}>
                        {stage.label}
                      </p>
                      <p className="text-xs text-muted-foreground mt-0.5">{stage.desc}</p>
                    </div>

                    {/* State badge */}
                    <span className={`shrink-0 text-[11px] font-semibold px-2 py-0.5 rounded-full
                      ${isDone    ? 'bg-emerald-500/15 text-emerald-600 dark:text-emerald-400' : ''}
                      ${isActive  ? 'bg-primary/15 text-primary'       : ''}
                      ${isPending ? 'bg-muted/50 text-muted-foreground' : ''}
                    `}>
                      {isDone ? 'Done' : isActive ? 'Running' : 'Pending'}
                    </span>
                  </motion.div>
                );
              })}
            </div>

            {/* Progress bar */}
            <div className="px-6 pb-4 pt-2 border-t border-border">
              <div className="flex items-center justify-between mb-1.5">
                <span className="text-xs text-muted-foreground">Overall progress</span>
                <span className="text-xs font-medium text-foreground">
                  {isComplete ? '100%' : activeStageIdx === -1 ? '0%' : `${Math.round(((activeStageIdx + 0.5) / PIPELINE_STAGES.length) * 100)}%`}
                </span>
              </div>
              <div className="h-1.5 bg-muted rounded-full overflow-hidden">
                <motion.div
                  className="h-full bg-gradient-to-r from-primary to-primary/70 rounded-full"
                  initial={{ width: '0%' }}
                  animate={{
                    width: isComplete
                      ? '100%'
                      : activeStageIdx === -1
                        ? '2%'
                        : `${Math.round(((activeStageIdx + 0.5) / PIPELINE_STAGES.length) * 100)}%`
                  }}
                  transition={{ duration: 0.6, ease: 'easeOut' }}
                />
              </div>
            </div>
          </div>
        )}

        {/* ── Live activity feed ───────────────────────────────────────────── */}
        {!startError && (
          <div className="bg-card border border-border rounded-2xl overflow-hidden">
            <div className="px-6 py-4 border-b border-border flex items-center justify-between">
              <div>
                <h2 className="text-sm font-semibold text-foreground">Live Agent Log</h2>
                <p className="text-xs text-muted-foreground mt-0.5">Real-time pipeline events</p>
              </div>
              {!isComplete && !errorDetails && !startError && (
                <div className="flex items-center gap-1.5">
                  <span className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse" />
                  <span className="text-xs text-muted-foreground">Live</span>
                </div>
              )}
            </div>
            <div className="h-56">
              <LiveActivityFeed logs={logs} isFullWidth />
            </div>
          </div>
        )}

        {/* ── Bottom CTA strip ─────────────────────────────────────────────── */}
        {isComplete && (
          <motion.div
            initial={{ opacity: 0, y: 16 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.2 }}
            className="flex flex-col items-center gap-3 py-4"
          >
            <p className="text-sm text-muted-foreground">
              Your AI-generated backlog is ready for review
            </p>
            <Button onClick={handleContinue} size="lg"
              className="bg-primary hover:bg-primary/90 text-primary-foreground shadow-lg flex items-center gap-2 px-8">
              Review Requirements <ArrowRight className="w-4 h-4" />
            </Button>
          </motion.div>
        )}
      </div>
    </div>
  );
}
