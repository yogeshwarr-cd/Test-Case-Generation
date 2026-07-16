'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import { ArrowRight, LoaderCircle, Sparkles } from 'lucide-react';
import { DynamicListField } from '../components/DynamicListField';
import { EMPTY_PAYLOAD, FIELD_LABELS } from '../constants';
import { testCaseApi } from '../services/testCaseApi';
import { useTestCaseWorkflowStore } from '../store/workflowStore';
import type { ManualInputPayload } from '../types';
import { cleanPayload, friendlyError } from '../utils';

export function InputPage() {
  const router = useRouter();
  const setWorkflow = useTestCaseWorkflowStore((state) => state.setWorkflow);
  const [payload, setPayload] = useState<ManualInputPayload>(() => structuredClone(EMPTY_PAYLOAD));
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState('');
  const [userStoryError, setUserStoryError] = useState('');

  const updateList = (key: Exclude<keyof ManualInputPayload, 'tech_stack'>, values: string[]) =>
    setPayload((current) => ({ ...current, [key]: values }));

  const submit = async (event: React.FormEvent) => {
    event.preventDefault();
    if (submitting) return;
    const cleaned = cleanPayload(payload);
    if (!cleaned.user_stories.length) {
      setUserStoryError('Enter at least one user story to start generation.');
      return;
    }
    setUserStoryError('');
    setError('');
    setSubmitting(true);
    try {
      const response = await testCaseApi.startWorkflow({ source_type: 'manual', input_payload: cleaned });
      setWorkflow(response.workflow_id, response.project_id);
      router.push('/test-case-generation/progress');
    } catch (requestError) {
      setError(friendlyError(requestError));
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="space-y-6">
      <div className="rounded-2xl border border-primary/20 bg-gradient-to-br from-primary/10 via-card to-card p-6 sm:p-8">
        <div className="flex items-start gap-4">
          <div className="rounded-xl bg-primary p-3 text-primary-foreground"><Sparkles className="h-6 w-6" /></div>
          <div>
            <p className="text-xs font-bold uppercase tracking-[0.2em] text-primary">AI workflow</p>
            <h1 className="mt-2 text-2xl font-bold sm:text-3xl">Generate test scenarios and test cases</h1>
            <p className="mt-2 max-w-3xl text-sm text-muted-foreground">Provide approved requirement details. Only user stories are required; the additional context improves coverage, validation, and traceability.</p>
          </div>
        </div>
      </div>

      <form onSubmit={submit} className="space-y-6">
        {error && <div role="alert" className="rounded-xl border border-red-500/30 bg-red-500/10 p-4 text-sm text-red-600 dark:text-red-300">{error}</div>}
        <section className="grid gap-6 rounded-2xl border border-border bg-card p-5 shadow-sm sm:p-6 lg:grid-cols-2">
          {(Object.keys(FIELD_LABELS) as Array<Exclude<keyof ManualInputPayload, 'tech_stack'>>).map((key) => (
            <DynamicListField
              key={key}
              label={FIELD_LABELS[key]}
              values={payload[key]}
              required={key === 'user_stories'}
              error={key === 'user_stories' ? userStoryError : undefined}
              onChange={(values) => updateList(key, values)}
            />
          ))}
        </section>

        <section className="rounded-2xl border border-border bg-card p-5 shadow-sm sm:p-6">
          <h2 className="text-lg font-semibold">Technology stack</h2>
          <p className="mt-1 text-sm text-muted-foreground">Optional implementation context for more relevant test coverage.</p>
          <div className="mt-5 grid gap-4 sm:grid-cols-2 lg:grid-cols-5">
            {(Object.keys(payload.tech_stack) as Array<keyof ManualInputPayload['tech_stack']>).map((key) => (
              <label key={key} className="space-y-2">
                <span className="text-sm font-medium capitalize">{key}</span>
                <input
                  value={payload.tech_stack[key]}
                  onChange={(event) => setPayload((current) => ({ ...current, tech_stack: { ...current.tech_stack, [key]: event.target.value } }))}
                  className="h-10 w-full rounded-lg border border-input bg-background px-3 text-sm outline-none focus:border-primary focus:ring-2 focus:ring-primary/20"
                  placeholder={key === 'other' ? 'Other tools' : `${key} technology`}
                />
              </label>
            ))}
          </div>
        </section>

        <div className="flex justify-end">
          <button
            type="submit"
            disabled={submitting}
            className="inline-flex min-w-52 items-center justify-center gap-2 rounded-xl bg-primary px-6 py-3 text-sm font-bold text-primary-foreground shadow-lg shadow-primary/20 transition hover:bg-primary/90 disabled:cursor-not-allowed disabled:opacity-60"
          >
            {submitting ? <><LoaderCircle className="h-4 w-4 animate-spin" /> Starting workflow…</> : <>Generate test cases <ArrowRight className="h-4 w-4" /></>}
          </button>
        </div>
      </form>
    </div>
  );
}
