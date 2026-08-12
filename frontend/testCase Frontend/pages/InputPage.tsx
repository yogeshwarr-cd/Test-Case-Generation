'use client';

import { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import Image from 'next/image';
import { ArrowRight, FileText, FolderKanban, ImagePlus, LoaderCircle, Plus, Sparkles, Trash2, UploadCloud, X } from 'lucide-react';
import { DynamicListField } from '../components/DynamicListField';
import { ConfidenceRing } from '../components/TraceabilityUI';
import { EMPTY_PAYLOAD, FIELD_LABELS } from '../constants';
import { testCaseApi } from '../services/testCaseApi';
import { loadActiveProjectName, useTestCaseWorkflowStore } from '../store/workflowStore';
import type { DocumentSession, ManualInputPayload, ParsedDocumentStory } from '../types';
import { cleanPayload, friendlyError } from '../utils';

const VISIBLE_INPUT_FIELDS = ['user_stories', 'acceptance_criteria'] as const;
const IMAGE_MAX_SIZE_MB = Number(process.env.NEXT_PUBLIC_IMAGE_MAX_SIZE_MB ?? 10);
const DOCUMENT_MAX_SIZE_MB = Number(process.env.NEXT_PUBLIC_DOCUMENT_MAX_SIZE_MB ?? 10);

export function InputPage() {
  const router = useRouter();
  const { hydrate, setWorkflow } = useTestCaseWorkflowStore();
  const [projectName, setProjectName] = useState(loadActiveProjectName);
  const [payload, setPayload] = useState<ManualInputPayload>(() => structuredClone(EMPTY_PAYLOAD));
  const [submitting, setSubmitting] = useState(false);
  const [mockMode, setMockMode] = useState(false);
  const [confidenceThreshold, setConfidenceThreshold] = useState(95);
  const [error, setError] = useState('');
  const [userStoryError, setUserStoryError] = useState('');
  const [imageError, setImageError] = useState('');
  const [referenceImage, setReferenceImage] = useState<File | null>(null);
  const [imagePreview, setImagePreview] = useState('');
  const [imageDescription, setImageDescription] = useState('');
  const [analysisStatus, setAnalysisStatus] = useState('');
  const [documentSession, setDocumentSession] = useState<DocumentSession | null>(null);
  const [documentStories, setDocumentStories] = useState<ParsedDocumentStory[]>([]);
  const [documentLoading, setDocumentLoading] = useState(false);
  const [documentError, setDocumentError] = useState('');

  useEffect(() => hydrate(), [hydrate]);

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

  const uploadDocument = async (file?: File) => {
    if (!file) return;
    const extension = file.name.split('.').pop()?.toLowerCase();
    if (!extension || !['pdf', 'docx', 'txt'].includes(extension)) {
      setDocumentError('Unsupported file. Select a PDF, DOCX, or TXT document.');
      return;
    }
    if (file.size > DOCUMENT_MAX_SIZE_MB * 1024 * 1024) {
      setDocumentError(`The document must be ${DOCUMENT_MAX_SIZE_MB} MB or smaller.`);
      return;
    }
    setDocumentLoading(true);
    setDocumentError('');
    try {
      const session = await testCaseApi.uploadDocument(file);
      setDocumentSession(session);
      setDocumentStories(session.stories);
      setPayload((current) => ({
        ...current,
        user_stories: session.stories.map((story) => story.text),
        acceptance_criteria: session.stories.flatMap((story) => story.acceptance_criteria),
      }));
      setUserStoryError('');
    } catch (requestError) {
      setDocumentSession(null);
      setDocumentStories([]);
      setDocumentError(friendlyError(requestError));
    } finally {
      setDocumentLoading(false);
    }
  };

  const removeDocument = () => {
    setDocumentSession(null);
    setDocumentStories([]);
    setDocumentError('');
  };

  const submit = async (event: React.FormEvent) => {
    event.preventDefault();
    if (submitting) return;
    const cleaned = cleanPayload(payload);
    if (documentSession && !documentStories.length) {
      setUserStoryError('The document must contain at least one user story.');
      return;
    }
    if (documentSession && documentStories.some((story) => !story.text.trim())) {
      setUserStoryError('Each extracted user story must contain text.');
      return;
    }
    if (documentSession && documentStories.some((story) => !story.acceptance_criteria.length || story.acceptance_criteria.some((criterion) => !criterion.trim()))) {
      setUserStoryError('Each extracted user story must have at least one acceptance criterion.');
      return;
    }
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
        const analysis = await testCaseApi.uploadImage(referenceImage, imageDescription, confidenceThreshold / 100);
        cleaned.image_ids = [analysis.image_id];
        setAnalysisStatus(`Image analyzed: ${analysis.screen_type} (${Math.round(analysis.analysis_confidence * 100)}% confidence · ${analysis.threshold_met ? 'threshold met' : 'below threshold'})`);
      }
      if (documentSession) {
        await testCaseApi.updateDocumentSession(documentSession.session_id, documentStories);
      }
      const response = await testCaseApi.startWorkflow(documentSession
        ? { source_type: 'manual', document_session_id: documentSession.session_id, mock_mode: mockMode, confidence_threshold: confidenceThreshold / 100 }
        : { source_type: 'manual', input_payload: cleaned, mock_mode: mockMode, confidence_threshold: confidenceThreshold / 100 });
      setWorkflow(response.workflow_id, response.project_id, projectName.trim() || undefined);
      router.push('/test-case-generation/progress');
    } catch (requestError) {
      setError(friendlyError(requestError));
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="space-y-6">
      <div className="relative flex min-h-[56vh] overflow-hidden rounded-[2rem] border border-primary/20 bg-gradient-to-br from-primary/15 via-card/90 to-card p-6 shadow-2xl shadow-primary/10 sm:p-10 lg:p-14">
        <div className="absolute -right-24 -top-24 h-80 w-80 rounded-full border border-primary/20 bg-primary/5 shadow-[0_0_100px_rgba(14,165,233,.16)]" aria-hidden="true" />
        <div className="absolute bottom-10 right-10 hidden grid-cols-3 gap-3 lg:grid" aria-hidden="true">{Array.from({ length: 9 }).map((_, index) => <span key={index} className="h-2 w-2 rounded-full bg-primary/30" />)}</div>
        <div className="relative z-10 flex max-w-5xl items-start gap-4 self-center">
          <div className="rounded-xl bg-primary p-3 text-primary-foreground shadow-xl shadow-primary/30"><Sparkles className="h-6 w-6" /></div>
          <div className="min-w-0">
            <p className="text-xs font-bold uppercase tracking-[0.2em] text-primary">AI workflow</p>
            <h1 className="mt-4 font-bold">Turn product intent into executable confidence.</h1>
            <p className="mt-6 max-w-2xl text-base leading-7 text-muted-foreground sm:text-lg">Provide user stories and acceptance criteria to generate test scenarios, traceable test cases, and production-ready automation evidence.</p>
            <div className="mt-8 flex flex-wrap gap-3 text-xs font-bold uppercase tracking-wider text-muted-foreground"><span>01 · Define</span><span className="text-primary">→</span><span>02 · Generate</span><span className="text-primary">→</span><span>03 · Validate</span><span className="text-primary">→</span><span>04 · Automate</span></div>
          </div>
        </div>
      </div>

      <form onSubmit={submit} className="space-y-6">
        {error && <div role="alert" className="rounded-xl border border-red-500/30 bg-red-500/10 p-4 text-sm text-red-600 dark:text-red-300">{error}</div>}
        
        {/* Project Name Input Card */}
        <section className="rounded-2xl border border-primary/20 bg-card p-5 shadow-sm sm:p-6">
          <div className="flex items-center gap-3 mb-3">
            <FolderKanban className="h-5 w-5 text-primary" />
            <div>
              <h2 className="font-semibold text-foreground">Project Name</h2>
              <p className="mt-0.5 text-xs text-muted-foreground">Give your test generation scope a descriptive title to organize your dashboard.</p>
            </div>
          </div>
          <input
            type="text"
            value={projectName}
            onChange={(e) => setProjectName(e.target.value)}
            placeholder="e.g., E-Commerce Checkout & Payment Gateway Test Suite"
            className="w-full rounded-xl border border-input bg-background p-3.5 text-sm font-semibold outline-none focus:border-primary focus:ring-2 focus:ring-primary/10 transition placeholder:text-muted-foreground/60"
          />
        </section>
        <section className="rounded-2xl border border-primary/20 bg-card p-5 shadow-sm sm:p-6" aria-labelledby="confidence-threshold-title">
          <div className="flex flex-col justify-between gap-5 sm:flex-row sm:items-center">
            <div className="max-w-2xl"><p className="text-xs font-bold uppercase tracking-[0.2em] text-primary">Global quality gate</p><h2 id="confidence-threshold-title" className="mt-2 text-xl font-bold">Confidence threshold</h2><p className="mt-1 text-sm leading-6 text-muted-foreground">This threshold controls scenario validation, test-case validation, regeneration decisions, manual-review gates, and automation evidence analysis for the entire workflow.</p></div>
            <output htmlFor="confidence-threshold" className="shrink-0"><ConfidenceRing value={confidenceThreshold} threshold={confidenceThreshold} label="Required threshold" size="lg" /></output>
          </div>
          <input id="confidence-threshold" type="range" min="1" max="100" step="1" value={confidenceThreshold} onChange={(event) => setConfidenceThreshold(Number(event.target.value))} className="mt-6 h-2 w-full cursor-pointer accent-primary" aria-valuetext={`${confidenceThreshold}% confidence`} />
          <div className="mt-2 flex justify-between text-xs font-medium text-muted-foreground"><span>Flexible · 1%</span><span>Balanced · 80%</span><span>Strict · 100%</span></div>
        </section>
        <div className="flex items-center justify-between rounded-2xl border border-border bg-card p-4 shadow-sm">
          <div><p className="font-semibold">Generation mode</p><p className="text-xs text-muted-foreground">Mock uses local sample output. When off, the configured live LLM is used.</p></div>
          <button type="button" role="switch" aria-checked={mockMode} onClick={() => setMockMode((current) => !current)} className={`rounded-xl border px-5 py-2 text-sm font-bold transition ${mockMode ? 'border-primary bg-primary text-primary-foreground' : 'border-input bg-background text-foreground hover:border-primary'}`}>Mock {mockMode ? 'ON' : 'OFF'}</button>
        </div>
        <section className="rounded-2xl border border-border bg-card p-5 shadow-sm sm:p-6">
          <div className="flex items-start gap-3">
            <FileText className="mt-0.5 h-5 w-5 text-primary" />
            <div>
              <h2 className="font-semibold">Upload user stories document</h2>
              <p className="mt-1 text-xs text-muted-foreground">PDF, DOCX, or TXT up to {DOCUMENT_MAX_SIZE_MB} MB. Extracted stories remain editable before generation.</p>
            </div>
          </div>
          {!documentSession ? (
            <label className={`mt-4 flex cursor-pointer flex-col items-center justify-center rounded-xl border border-dashed border-input bg-background px-6 py-8 text-center hover:border-primary hover:bg-primary/5 ${documentLoading ? 'pointer-events-none opacity-60' : ''}`}>
              {documentLoading ? <LoaderCircle className="h-8 w-8 animate-spin text-primary" /> : <UploadCloud className="h-8 w-8 text-muted-foreground" />}
              <span className="mt-3 text-sm font-semibold">{documentLoading ? 'Uploading and extracting stories…' : 'Choose a requirements document'}</span>
              <input type="file" accept=".pdf,.docx,.txt,application/pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document,text/plain" className="sr-only" disabled={documentLoading} onChange={(event) => { void uploadDocument(event.target.files?.[0]); event.currentTarget.value = ''; }} />
            </label>
          ) : (
            <div className="mt-4 space-y-4">
              <div className="flex items-center justify-between rounded-xl border border-primary/20 bg-primary/5 p-3">
                <div><p className="text-sm font-semibold">{documentSession.filename}</p><p className="text-xs text-muted-foreground">{documentStories.length} user {documentStories.length === 1 ? 'story' : 'stories'} extracted · temporary session expires in 1 hour</p></div>
                <button type="button" onClick={removeDocument} className="rounded-lg p-2 text-red-500 hover:bg-red-500/10" aria-label="Remove uploaded document"><X className="h-4 w-4" /></button>
              </div>
              <div className="space-y-4">
                {documentStories.map((story, storyIndex) => (
                  <div key={storyIndex} className="rounded-xl border border-border bg-background p-4">
                    <div className="flex gap-2">
                      <textarea value={story.text} onChange={(event) => setDocumentStories((items) => items.map((item, index) => index === storyIndex ? { ...item, text: event.target.value } : item))} aria-label={`Extracted user story ${storyIndex + 1}`} className="min-h-20 flex-1 rounded-lg border border-input bg-card p-3 text-sm outline-none focus:border-primary" />
                      <button type="button" onClick={() => setDocumentStories((items) => items.filter((_, index) => index !== storyIndex))} className="self-start rounded-lg p-2 text-red-500 hover:bg-red-500/10" aria-label={`Remove extracted story ${storyIndex + 1}`}><Trash2 className="h-4 w-4" /></button>
                    </div>
                    <p className="mb-2 mt-3 text-xs font-bold uppercase tracking-wide text-muted-foreground">Acceptance criteria</p>
                    {story.acceptance_criteria.map((criterion, criterionIndex) => (
                      <div key={criterionIndex} className="mb-2 flex gap-2">
                        <textarea value={criterion} onChange={(event) => setDocumentStories((items) => items.map((item, index) => index === storyIndex ? { ...item, acceptance_criteria: item.acceptance_criteria.map((value, acIndex) => acIndex === criterionIndex ? event.target.value : value) } : item))} aria-label={`Story ${storyIndex + 1} acceptance criterion ${criterionIndex + 1}`} className="min-h-16 flex-1 rounded-lg border border-input bg-card p-3 text-sm outline-none focus:border-primary" />
                        <button type="button" onClick={() => setDocumentStories((items) => items.map((item, index) => index === storyIndex ? { ...item, acceptance_criteria: item.acceptance_criteria.filter((_, acIndex) => acIndex !== criterionIndex) } : item))} className="self-start rounded-lg p-2 text-red-500 hover:bg-red-500/10" aria-label={`Remove acceptance criterion ${criterionIndex + 1}`}><Trash2 className="h-4 w-4" /></button>
                      </div>
                    ))}
                    <button type="button" onClick={() => setDocumentStories((items) => items.map((item, index) => index === storyIndex ? { ...item, acceptance_criteria: [...item.acceptance_criteria, ''] } : item))} className="inline-flex items-center gap-1 text-xs font-semibold text-primary hover:underline"><Plus className="h-3.5 w-3.5" /> Add criterion</button>
                  </div>
                ))}
                <button type="button" onClick={() => setDocumentStories((items) => [...items, { text: '', acceptance_criteria: [''] }])} className="inline-flex items-center gap-2 text-sm font-semibold text-primary hover:underline"><Plus className="h-4 w-4" /> Add user story</button>
              </div>
            </div>
          )}
          {documentError && <p role="alert" className="mt-3 text-sm text-red-500">{documentError}</p>}
          <p className="mt-3 text-xs text-muted-foreground">Prefer typing? Manual entry below remains available. Remove the document to generate from manual fields.</p>
        </section>
        {!documentSession && (
          <section className="grid gap-6 rounded-2xl border border-border bg-card p-5 shadow-sm sm:p-6 lg:grid-cols-2">
            {VISIBLE_INPUT_FIELDS.map((key) => (
              <DynamicListField
                key={key}
                label={FIELD_LABELS[key]}
                values={payload[key]}
                required={key === 'user_stories'}
                recommended={key === 'acceptance_criteria'}
                error={key === 'user_stories' ? userStoryError : undefined}
                onChange={(values) => updateList(key, values)}
              />
            ))}
          </section>
        )}

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
