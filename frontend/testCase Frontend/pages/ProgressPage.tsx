'use client';

import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { useRouter } from 'next/navigation';
import { Check, Circle, LoaderCircle, RefreshCw, Wifi, WifiOff } from 'lucide-react';
import { WORKFLOW_STAGES } from '../constants';
import { testCaseApi } from '../services/testCaseApi';
import { useTestCaseWorkflowStore } from '../store/workflowStore';
import type { WorkflowEvent } from '../types';
import { confidencePercent, friendlyError } from '../utils';
import { StatePanel } from '../components/StatePanel';

export function ProgressPage() {
  const router = useRouter();
  const { workflowId, snapshot, hydrate, setSnapshot, setResult } = useTestCaseWorkflowStore();
  const [connection, setConnection] = useState<'connecting' | 'connected' | 'reconnecting' | 'closed'>('connecting');
  const [error, setError] = useState('');
  const [elapsed, setElapsed] = useState(0);
  const retryRef = useRef(0);
  const closeRef = useRef<(() => void) | null>(null);
  const connectRef = useRef<() => void>(() => undefined);
  const reconnectTimerRef = useRef<number | null>(null);

  useEffect(() => hydrate(), [hydrate]);
  useEffect(() => {
    const timer = window.setInterval(() => setElapsed((value) => value + 1), 1000);
    return () => window.clearInterval(timer);
  }, []);

  const routeForEvent = useCallback(async (event: WorkflowEvent) => {
    if (!workflowId) return;
    if (event.status === 'completed') {
      closeRef.current?.();
      setConnection('closed');
      try {
        const result = await testCaseApi.getWorkflowResult(workflowId);
        setResult(result);
        router.replace('/test-case-generation/results');
      } catch (requestError) {
        setError(friendlyError(requestError));
      }
    } else if (event.status === 'scenario_manual_review' || event.status === 'testcase_manual_review') {
      closeRef.current?.();
      setConnection('closed');
      router.replace('/test-case-generation/review');
    } else if (event.status === 'failed' || event.status === 'cancelled') {
      closeRef.current?.();
      setConnection('closed');
    }
  }, [router, setResult, workflowId]);

  const connect = useCallback(() => {
    if (!workflowId || closeRef.current) return;
    setConnection(retryRef.current ? 'reconnecting' : 'connecting');
    closeRef.current = testCaseApi.connectToWorkflowEvents(workflowId, {
      onOpen: () => {
        retryRef.current = 0;
        setConnection('connected');
        setError('');
      },
      onEvent: (event) => {
        setSnapshot(event);
        void routeForEvent(event);
      },
      onError: () => {
        closeRef.current?.();
        closeRef.current = null;
        if (retryRef.current >= 3) {
          setConnection('closed');
          setError('Live progress could not reconnect. Your workflow was not restarted; use Retry connection to continue watching it.');
          return;
        }
        retryRef.current += 1;
        setConnection('reconnecting');
        reconnectTimerRef.current = window.setTimeout(() => connectRef.current(), retryRef.current * 1500);
      },
    });
  }, [routeForEvent, setSnapshot, workflowId]);
  useEffect(() => {
    connectRef.current = connect;
  }, [connect]);

  useEffect(() => {
    if (!workflowId) return;
    connect();
    return () => {
      closeRef.current?.();
      closeRef.current = null;
      if (reconnectTimerRef.current) window.clearTimeout(reconnectTimerRef.current);
    };
  }, [connect, workflowId]);

  const stageIndex = useMemo(() => {
    const stage = snapshot?.current_stage;
    if (!stage) return -1;
    if (stage === 'generating_scenarios' && (snapshot.scenario_attempt_count ?? 0) > 1) return 3;
    if (stage === 'generating_test_cases' && (snapshot.testcase_attempt_count ?? 0) > 1) return 6;
    return WORKFLOW_STAGES.findIndex((item) => item.key === stage);
  }, [snapshot]);

  if (!workflowId) {
    return <StatePanel type="error" title="No active workflow" message="Start a Test Case Generation workflow before opening progress." />;
  }

  const progress = snapshot?.progress_percentage ?? Math.max(5, Math.round(((stageIndex + 1) / WORKFLOW_STAGES.length) * 100));
  const failed = snapshot?.status === 'failed' || snapshot?.status === 'cancelled';

  return (
    <div className="mx-auto max-w-5xl space-y-6">
      <div className="flex flex-col justify-between gap-4 sm:flex-row sm:items-end">
        <div>
          <p className="text-xs font-bold uppercase tracking-[0.2em] text-primary">Workflow progress</p>
          <h1 className="mt-2 text-2xl font-bold">Generating your test assets</h1>
          <p className="mt-1 break-all text-sm text-muted-foreground">Workflow ID: {workflowId}</p>
        </div>
        <div className="flex items-center gap-2 rounded-full border border-border bg-card px-3 py-2 text-xs font-medium">
          {connection === 'connected' ? <Wifi className="h-4 w-4 text-green-500" /> : <WifiOff className="h-4 w-4 text-amber-500" />}
          {connection}
        </div>
      </div>

      <section className="rounded-2xl border border-border bg-card p-5 shadow-sm sm:p-7">
        <div className="flex items-center justify-between text-sm">
          <span className="font-semibold">{snapshot?.message ?? snapshot?.current_stage?.replaceAll('_', ' ') ?? 'Waiting for workflow updates'}</span>
          <span className="text-muted-foreground">{progress}%</span>
        </div>
        <div className="mt-3 h-2 overflow-hidden rounded-full bg-muted">
          <div className="h-full rounded-full bg-primary transition-all duration-500" style={{ width: `${Math.min(progress, 100)}%` }} />
        </div>
        <div className="mt-4 grid grid-cols-2 gap-3 text-sm sm:grid-cols-4">
          <Metric label="Elapsed" value={`${Math.floor(elapsed / 60)}m ${elapsed % 60}s`} />
          <Metric label="Status" value={snapshot?.status?.replaceAll('_', ' ') ?? 'pending'} />
          <Metric label="Scenario attempts" value={String(snapshot?.scenario_attempt_count ?? '—')} />
          <Metric label="Confidence" value={snapshot?.confidence_score === undefined ? '—' : `${confidencePercent(snapshot.confidence_score)}%`} />
        </div>
      </section>

      <section className="rounded-2xl border border-border bg-card p-5 shadow-sm sm:p-7">
        <ol className="space-y-1">
          {WORKFLOW_STAGES.map((stage, index) => {
            const completed = snapshot?.status === 'completed' || index < stageIndex;
            const active = index === stageIndex && !failed;
            return (
              <li key={stage.key} className={`flex items-center gap-4 rounded-xl px-3 py-3 ${active ? 'bg-primary/10' : ''}`}>
                <div className={`flex h-8 w-8 shrink-0 items-center justify-center rounded-full border ${completed ? 'border-green-500 bg-green-500 text-white' : active ? 'border-primary bg-primary text-primary-foreground' : 'border-border text-muted-foreground'}`}>
                  {completed ? <Check className="h-4 w-4" /> : active ? <LoaderCircle className="h-4 w-4 animate-spin" /> : <Circle className="h-3 w-3" />}
                </div>
                <div className="flex-1">
                  <p className={`text-sm font-semibold ${!completed && !active ? 'text-muted-foreground' : ''}`}>{stage.label}</p>
                  {stage.optional && <p className="text-xs text-muted-foreground">Runs only when validation requests regeneration.</p>}
                </div>
              </li>
            );
          })}
        </ol>
      </section>

      {(error || failed) && (
        <div className="rounded-xl border border-red-500/30 bg-red-500/10 p-5">
          <h2 className="font-semibold text-red-600 dark:text-red-300">{failed ? 'Workflow stopped' : 'Connection interrupted'}</h2>
          <p className="mt-1 text-sm text-muted-foreground">{error || snapshot?.errors?.join(' ') || 'The workflow could not complete.'}</p>
          <div className="mt-4 flex flex-wrap gap-3">
            {!failed && <button onClick={() => { retryRef.current = 0; setError(''); connect(); }} className="inline-flex items-center gap-2 rounded-lg bg-primary px-4 py-2 text-sm font-semibold text-primary-foreground"><RefreshCw className="h-4 w-4" /> Retry connection</button>}
            <button onClick={() => router.push('/test-case-generation')} className="rounded-lg border border-border px-4 py-2 text-sm font-semibold hover:bg-muted">Return to input</button>
          </div>
        </div>
      )}
    </div>
  );
}

function Metric({ label, value }: { label: string; value: string }) {
  return <div className="rounded-lg bg-muted/60 p-3"><p className="text-xs text-muted-foreground">{label}</p><p className="mt-1 truncate font-semibold capitalize">{value}</p></div>;
}
