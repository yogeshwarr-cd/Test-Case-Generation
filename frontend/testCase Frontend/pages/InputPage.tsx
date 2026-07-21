'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import Image from 'next/image';
import { ArrowRight, ImagePlus, LoaderCircle, Sparkles, X } from 'lucide-react';
import { DynamicListField } from '../components/DynamicListField';
import { EMPTY_PAYLOAD, FIELD_LABELS } from '../constants';
import { testCaseApi } from '../services/testCaseApi';
import { useTestCaseWorkflowStore } from '../store/workflowStore';
import type { ManualInputPayload } from '../types';
import { cleanPayload, friendlyError } from '../utils';

const VISIBLE_INPUT_FIELDS = ['user_stories', 'epics', 'features'] as const;
const IMAGE_MAX_SIZE_MB = Number(process.env.NEXT_PUBLIC_IMAGE_MAX_SIZE_MB ?? 10);

export function InputPage() {
  const router = useRouter();
  const setWorkflow = useTestCaseWorkflowStore((state) => state.setWorkflow);
  const [payload, setPayload] = useState<ManualInputPayload>(() => structuredClone(EMPTY_PAYLOAD));
  const [submitting, setSubmitting] = useState(false);
  const [mockMode, setMockMode] = useState(false);
  const [error, setError] = useState('');
  const [userStoryError, setUserStoryError] = useState('');
  const [imageError, setImageError] = useState('');
  const [referenceImage, setReferenceImage] = useState<File | null>(null);
  const [imagePreview, setImagePreview] = useState('');
  const [imageDescription, setImageDescription] = useState('');
  const [analysisStatus, setAnalysisStatus] = useState('');

  const updateList = (key: Exclude<keyof ManualInputPayload, 'tech_stack'>, values: string[]) =>
    setPayload((current) => ({ ...current, [key]: values }));

  const uploadReferenceImage = (file?: File) => {
    if (!file) return;
    if (!['image/png', 'image/jpeg', 'image/webp'].includes(file.type)) { setImageError('Select a PNG, JPEG, or WebP image.'); return; }
    if (file.size > IMAGE_MAX_SIZE_MB * 1024 * 1024) { setImageError(`The image must be ${IMAGE_MAX_SIZE_MB} MB or smaller.`); return; }
    const reader = new FileReader();
    reader.onload = () => {
      setReferenceImage(file);setImagePreview(String(reader.result));
      setImageError('');
    };
    reader.onerror = () => setImageError('The image could not be read.');
    reader.readAsDataURL(file);
  };

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
      if (referenceImage) {
        setAnalysisStatus('Analyzing image locally…');
        const analysis = await testCaseApi.uploadImage(referenceImage, imageDescription);
        cleaned.image_ids = [analysis.image_id];
        setAnalysisStatus(`Image analyzed: ${analysis.screen_type} (${Math.round(analysis.analysis_confidence * 100)}% confidence)`);
      }
      const response = await testCaseApi.startWorkflow({ source_type: 'manual', input_payload: cleaned, mock_mode: mockMode });
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
            <p className="mt-2 max-w-3xl text-sm text-muted-foreground">Provide user stories, epics, and features to generate test coverage and traceability.</p>
          </div>
        </div>
      </div>

      <form onSubmit={submit} className="space-y-6">
        {error && <div role="alert" className="rounded-xl border border-red-500/30 bg-red-500/10 p-4 text-sm text-red-600 dark:text-red-300">{error}</div>}
        <div className="flex items-center justify-between rounded-2xl border border-border bg-card p-4 shadow-sm">
          <div><p className="font-semibold">Generation mode</p><p className="text-xs text-muted-foreground">Mock uses local sample output. When off, the configured live LLM is used.</p></div>
          <button type="button" role="switch" aria-checked={mockMode} onClick={() => setMockMode((current) => !current)} className={`rounded-xl border px-5 py-2 text-sm font-bold transition ${mockMode ? 'border-primary bg-primary text-primary-foreground' : 'border-input bg-background text-foreground hover:border-primary'}`}>Mock {mockMode ? 'ON' : 'OFF'}</button>
        </div>
        <section className="grid gap-6 rounded-2xl border border-border bg-card p-5 shadow-sm sm:p-6 lg:grid-cols-2">
          {VISIBLE_INPUT_FIELDS.map((key) => (
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
          <div className="flex items-center gap-3"><ImagePlus className="h-5 w-5 text-primary" /><div><h2 className="font-semibold">Wireframe or application screenshot</h2><p className="mt-1 text-xs text-muted-foreground">Upload a PNG, JPEG, or WebP image up to {IMAGE_MAX_SIZE_MB} MB.</p></div></div>
          {!imagePreview ? (
            <label className="mt-4 flex cursor-pointer flex-col items-center justify-center rounded-xl border border-dashed border-input bg-background px-6 py-10 text-center hover:border-primary hover:bg-primary/5">
              <ImagePlus className="h-8 w-8 text-muted-foreground" /><span className="mt-3 text-sm font-semibold">Choose a wireframe or screenshot</span><span className="mt-1 text-xs text-muted-foreground">Click to browse your device</span>
              <input type="file" accept="image/png,image/jpeg,image/webp,.png,.jpg,.jpeg,.webp" className="sr-only" onChange={(event) => uploadReferenceImage(event.target.files?.[0])} />
            </label>
          ) : (
            <div className="relative mt-4 overflow-hidden rounded-xl border border-border bg-background p-3">
              <Image src={imagePreview} alt="Uploaded wireframe or application screenshot preview" width={1200} height={700} unoptimized className="max-h-80 w-full rounded-lg object-contain" />
              <button type="button" onClick={() => { setReferenceImage(null);setImagePreview('');setAnalysisStatus(''); }} className="absolute right-5 top-5 rounded-full bg-background/90 p-2 text-red-500 shadow hover:bg-red-500 hover:text-white" aria-label="Remove uploaded image"><X className="h-4 w-4" /></button>
            </div>
          )}
          <label className="mt-4 block space-y-2"><span className="text-sm font-semibold">Image description <span className="font-normal text-muted-foreground">(optional)</span></span><textarea value={imageDescription} onChange={(event) => setImageDescription(event.target.value)} rows={3} placeholder="Example: Login-page wireframe for the customer portal" className="w-full rounded-lg border border-input bg-background p-3 text-sm outline-none focus:border-primary" /></label>
          {analysisStatus && <p role="status" className="mt-3 text-sm font-medium text-primary">{analysisStatus}</p>}
          {imageError && <p role="alert" className="mt-2 text-sm text-red-500">{imageError}</p>}
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
