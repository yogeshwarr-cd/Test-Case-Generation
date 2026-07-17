'use client';

import { useEffect, useMemo, useState } from 'react';
import { useRouter } from 'next/navigation';
import { Check, LoaderCircle, RotateCcw } from 'lucide-react';
import { StatePanel } from '../components/StatePanel';
import { testCaseApi } from '../services/testCaseApi';
import { useTestCaseWorkflowStore } from '../store/workflowStore';
import type { WorkflowResult } from '../types';
import { confidencePercent, friendlyError } from '../utils';

export function ReviewPage() {
  const router = useRouter();
  const { workflowId, snapshot, result, hydrate, setResult, setSnapshot } = useTestCaseWorkflowStore();
  const [data, setData] = useState<WorkflowResult | null>(result);
  const [feedback, setFeedback] = useState('');
  const [correctedData, setCorrectedData] = useState('{}');
  const [loading, setLoading] = useState(!result);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => hydrate(), [hydrate]);
  useEffect(() => {
    if (!workflowId || data) return;
    testCaseApi.getWorkflowResult(workflowId).then((response) => {
      setData(response);
      setResult(response);
    }).catch((requestError) => setError(friendlyError(requestError))).finally(() => setLoading(false));
  }, [data, setResult, workflowId]);

  const stage = snapshot?.status === 'testcase_manual_review' || data?.current_stage === 'testcase_manual_review' ? 'testcase_manual_review' : 'scenario_manual_review';
  const validation = stage === 'scenario_manual_review' ? data?.scenario_validation : data?.testcase_validation;
  const generated = stage === 'scenario_manual_review' ? data?.scenarios : data?.test_cases;
  const reviewLabel = stage === 'scenario_manual_review' ? 'Scenario review' : 'Test-case review';
  const attempts = stage === 'scenario_manual_review' ? snapshot?.scenario_attempt_count : snapshot?.testcase_attempt_count;
  const preview = useMemo(() => {
    try { return JSON.stringify(JSON.parse(correctedData), null, 2); } catch { return 'Corrected data must be valid JSON.'; }
  }, [correctedData]);

  const resume = async () => {
    if (!workflowId || submitting) return;
    if (!feedback.trim()) {
      setError('Feedback is required before the workflow can resume.');
      return;
    }
    let corrected: Record<string, unknown>;
    try {
      corrected = JSON.parse(correctedData) as Record<string, unknown>;
    } catch {
      setError('Corrected data must be a valid JSON object.');
      return;
    }
    setSubmitting(true);
    setError('');
    try {
      const response = await testCaseApi.resumeWorkflow(workflowId, { stage, feedback: feedback.trim(), corrected_data: corrected });
      setSnapshot(response);
      router.push('/test-case-generation/progress');
    } catch (requestError) {
      setError(friendlyError(requestError));
    } finally {
      setSubmitting(false);
    }
  };
  const approve = async () => {
    if (!workflowId || submitting) return;
    setSubmitting(true);setError('');
    try {
      const response = await testCaseApi.approveManualReview(workflowId, stage);
      setSnapshot(response);
      if (response.status === 'completed') {
        const completed = await testCaseApi.getWorkflowResult(workflowId);setResult(completed);router.push('/test-case-generation/results');
      } else router.push('/test-case-generation/progress');
    } catch (requestError) { setError(friendlyError(requestError)); }
    finally { setSubmitting(false); }
  };

  if (!workflowId) return <StatePanel type="error" title="No active workflow" message="The manual-review page needs an active workflow ID." />;
  if (loading) return <StatePanel type="loading" title="Loading review data" message="Fetching generated data and validation findings." />;

  return (
    <div className="space-y-6">
      <div>
        <p className="text-xs font-bold uppercase tracking-[0.2em] text-amber-500">Manual intervention required</p>
        <h1 className="mt-2 text-2xl font-bold">{reviewLabel}</h1>
        <p className="mt-1 text-sm text-muted-foreground">Workflow {workflowId} paused after {attempts ?? 3} generation attempts.</p>
      </div>
      {error && <div role="alert" className="rounded-xl border border-red-500/30 bg-red-500/10 p-4 text-sm text-red-600 dark:text-red-300">{error}</div>}
      <div className="grid gap-6 lg:grid-cols-[1.1fr_.9fr]">
        <section className="space-y-5 rounded-2xl border border-border bg-card p-5 sm:p-6">
          <div className="grid gap-3 sm:grid-cols-3">
            <Metric label="Confidence" value={`${confidencePercent(validation?.confidence_score)}%`} />
            <Metric label="Validation" value={validation?.status ?? 'Manual review'} />
            <Metric label="Generated items" value={String(generated?.length ?? 0)} />
          </div>
          <div>
            <h2 className="font-semibold">Validation issues</h2>
            <div className="mt-3 space-y-2">
              {validation?.issues?.length ? validation.issues.map((issue, index) => (
                <div key={`${issue.issue_code}-${index}`} className="rounded-lg border border-amber-500/20 bg-amber-500/5 p-3">
                  <p className="text-sm font-semibold">{issue.description}</p>
                  {issue.recommendation && <p className="mt-1 text-xs text-muted-foreground">{issue.recommendation}</p>}
                </div>
              )) : <p className="text-sm text-muted-foreground">No detailed issues were returned by the backend.</p>}
            </div>
          </div>
          <details className="rounded-xl border border-border">
            <summary className="cursor-pointer p-4 text-sm font-semibold">Original generated data</summary>
            <pre className="max-h-[520px] overflow-auto border-t border-border p-4 text-xs">{JSON.stringify(generated ?? [], null, 2)}</pre>
          </details>
          <div>
            <h2 className="font-semibold">Generated {stage === 'scenario_manual_review' ? 'scenarios' : 'test cases'}</h2>
            <p className="mt-1 text-sm text-muted-foreground">All generated outputs remain visible for review, including items with low confidence.</p>
            <div className="mt-3 space-y-3">
              {generated?.map((item) => {
                const isTestCase = 'test_case_id' in item;
                const id = isTestCase ? item.test_case_id : item.scenario_id;
                const score = confidencePercent(validation?.entity_scores?.[id] ?? validation?.confidence_score);
                return <article key={id} className="rounded-xl border border-border bg-background p-4"><div className="flex flex-wrap items-start justify-between gap-3"><div><p className="text-xs font-semibold text-primary">{id}</p><h3 className="mt-1 font-semibold">{item.title}</h3></div><span className="rounded-full bg-primary/10 px-2.5 py-1 text-xs font-semibold text-primary">Confidence {score}%</span></div><p className="mt-2 text-sm text-muted-foreground">{item.description}</p>{isTestCase && item.steps?.length ? <ol className="mt-3 space-y-2">{item.steps.map((step) => <li key={step.step_number} className="rounded-lg bg-muted p-3 text-sm"><span className="font-semibold">{step.step_number}. {step.action}</span><p className="mt-1 text-muted-foreground">Expected: {step.expected_result}</p></li>)}</ol> : null}</article>;
              })}
            </div>
          </div>
        </section>
        <section className="space-y-5 rounded-2xl border border-border bg-card p-5 sm:p-6">
          <label className="block space-y-2">
            <span className="text-sm font-semibold">Review feedback <span className="text-red-500">*</span></span>
            <textarea value={feedback} onChange={(event) => setFeedback(event.target.value)} className="min-h-32 w-full rounded-lg border border-input bg-background p-3 text-sm outline-none focus:border-primary focus:ring-2 focus:ring-primary/20" placeholder="Explain the corrections and what the next generation attempt must address." />
          </label>
          <label className="block space-y-2">
            <span className="text-sm font-semibold">Corrected data (JSON)</span>
            <textarea value={correctedData} onChange={(event) => setCorrectedData(event.target.value)} className="min-h-48 w-full rounded-lg border border-input bg-background p-3 font-mono text-xs outline-none focus:border-primary focus:ring-2 focus:ring-primary/20" />
          </label>
          <div>
            <p className="text-sm font-semibold">Corrected data preview</p>
            <pre className="mt-2 max-h-40 overflow-auto rounded-lg bg-muted p-3 text-xs">{preview}</pre>
          </div>
          <div className="flex flex-wrap gap-3">
            <button onClick={approve} disabled={submitting || !generated?.length} className="inline-flex items-center gap-2 rounded-lg bg-green-600 px-4 py-2 text-sm font-semibold text-white hover:bg-green-700 disabled:opacity-60">
              {submitting ? <LoaderCircle className="h-4 w-4 animate-spin" /> : <Check className="h-4 w-4" />} Approve generated {stage === 'scenario_manual_review' ? 'scenarios' : 'test cases'}
            </button>
            <button onClick={resume} disabled={submitting} className="inline-flex items-center gap-2 rounded-lg bg-primary px-4 py-2 text-sm font-semibold text-primary-foreground disabled:opacity-60">
              {submitting ? <LoaderCircle className="h-4 w-4 animate-spin" /> : <RotateCcw className="h-4 w-4" />} Resume workflow
            </button>
            <button onClick={() => router.push('/test-case-generation/progress')} className="rounded-lg border border-border px-4 py-2 text-sm font-semibold hover:bg-muted">Return to progress</button>
          </div>
        </section>
      </div>
    </div>
  );
}

function Metric({ label, value }: { label: string; value: string }) {
  return <div className="rounded-lg bg-muted p-3"><p className="text-xs text-muted-foreground">{label}</p><p className="mt-1 font-semibold capitalize">{value}</p></div>;
}
