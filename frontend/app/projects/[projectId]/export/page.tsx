'use client';

import React, { useEffect, useState } from 'react';
import { useParams } from 'next/navigation';
import { Download, FileText, FileSpreadsheet, File, Loader2, AlertTriangle } from 'lucide-react';
import { api } from '@/services/api';
import { Story, Epic } from '@/services/mockData';
import { Button } from '@/components/common/Button';
import { Modal } from '@/components/common/Modal';
import { cn } from '@/lib/utils';

type ExportFormat = 'json' | 'csv' | 'txt';
type ExportStatus = 'idle' | 'processing' | 'done' | 'error';

export default function ExportPage() {
  const params = useParams();
  const projectId = params?.projectId as string;

  const [epics, setEpics] = useState<Epic[]>([]);
  const [stories, setStories] = useState<Story[]>([]);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);

  const [isExportModalOpen, setIsExportModalOpen] = useState(false);
  const [selectedFormat, setSelectedFormat] = useState<ExportFormat>('json');
  const [exportStatus, setExportStatus] = useState<ExportStatus>('idle');
  const [exportError, setExportError] = useState<string | null>(null);

  useEffect(() => {
    Promise.all([api.getEpics(projectId), api.getStories(projectId)])
      .then(([eps, sts]) => {
        setEpics(eps);
        setStories(sts);
        setLoading(false);
      })
      .catch((err) => {
        setLoadError(err?.message || 'Failed to load workflow data.');
        setLoading(false);
      });
  }, [projectId]);

  const handleExport = async () => {
    setExportStatus('processing');
    setExportError(null);
    try {
      await api.exportWorkflow(projectId, selectedFormat);
      setExportStatus('done');
    } catch (err: any) {
      setExportError(err?.message || 'Export failed.');
      setExportStatus('error');
    }
  };

  if (loading) {
    return (
      <div className="flex-1 flex items-center justify-center bg-background">
        <div className="flex flex-col items-center gap-3 text-muted-foreground">
          <Loader2 className="w-8 h-8 animate-spin text-primary" />
          <p className="text-sm font-medium">Loading document preview...</p>
        </div>
      </div>
    );
  }

  if (loadError) {
    return (
      <div className="flex-1 flex items-center justify-center bg-background">
        <div className="flex flex-col items-center gap-3 text-red-500 max-w-md text-center">
          <AlertTriangle className="w-7 h-7" />
          <p className="text-sm font-medium">{loadError}</p>
        </div>
      </div>
    );
  }

  if (epics.length === 0 && stories.length === 0) {
    return (
      <div className="flex-1 flex items-center justify-center bg-background">
        <div className="flex flex-col items-center gap-3 text-muted-foreground max-w-md text-center">
          <p className="text-sm">No workflow data found. Run the pipeline first.</p>
        </div>
      </div>
    );
  }

  // Group stories by epic for the preview
  const groupedStories = epics.map((epic) => ({
    epic,
    stories: stories.filter((s) => s.epicId === epic.id),
  }));
  // Stories not belonging to any epic
  const orphanStories = stories.filter((s) => !epics.find((e) => e.id === s.epicId));

  return (
    <div className="flex-1 overflow-y-auto bg-background w-full h-full relative">
      {/* Page Header */}
      <div className="px-6 py-5 border-b border-border bg-background">
        <div className="text-[11px] text-muted-foreground flex gap-2 items-center mb-1 uppercase tracking-wider font-bold">
          <span>Project Workspace</span> <span>/</span>{' '}
          <span className="text-foreground">Final Preview</span>
        </div>
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
          <div>
            <h1 className="text-2xl font-bold tracking-tight">Product Requirements Document</h1>
            <p className="text-[13px] text-muted-foreground mt-1">
              {epics.length} epic{epics.length !== 1 ? 's' : ''} &middot; {stories.length} user stor{stories.length !== 1 ? 'ies' : 'y'} &middot; Generated {new Date().toLocaleDateString()}
            </p>
          </div>
          <Button
            onClick={() => { setIsExportModalOpen(true); setExportStatus('idle'); setExportError(null); }}
            className="bg-primary hover:bg-primary/90 text-primary-foreground font-semibold px-4 h-9 shadow-sm rounded-lg flex items-center gap-2"
          >
            <Download className="w-4 h-4" /> Export
          </Button>
        </div>
      </div>

      {/* Document preview */}
      <div className="p-6 md:p-10 bg-muted/10 min-h-screen">
        <div className="max-w-4xl mx-auto bg-card border border-border shadow-sm p-8 md:p-12 rounded-xl text-foreground font-sans">
          <div className="space-y-12">
            {groupedStories.map(({ epic, stories: epicStories }) => (
              <div key={epic.id} className="epic-section">
                <h2 className="text-[18px] md:text-[20px] font-bold mb-2 text-primary">
                  {epic.sNo}. Epic: {epic.title}
                </h2>
                <p className="text-[15px] mb-6 leading-relaxed text-foreground/90">{epic.summary}</p>

                {epicStories.length === 0 ? (
                  <p className="text-sm text-muted-foreground italic">No stories linked to this epic.</p>
                ) : (
                  <div className="space-y-8">
                    {epicStories.map((story, sIdx) => (
                      <StoryPreview key={story.id} story={story} index={sIdx} />
                    ))}
                  </div>
                )}
              </div>
            ))}

            {orphanStories.length > 0 && (
              <div className="epic-section">
                <h2 className="text-[18px] font-bold mb-4 text-muted-foreground">
                  Unlinked Stories
                </h2>
                <div className="space-y-8">
                  {orphanStories.map((story, idx) => (
                    <StoryPreview key={story.id} story={story} index={idx} />
                  ))}
                </div>
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Export modal */}
      <Modal isOpen={isExportModalOpen} onClose={() => setIsExportModalOpen(false)} title="Export Artifacts">
        <div className="space-y-4">
          <p className="text-[13px] text-muted-foreground">Select a format to download your data.</p>

          <div className="space-y-2">
            <ExportOption
              id="json"
              title="JSON"
              desc="Full structured data — epics, stories, all fields."
              icon={<File className="w-5 h-5 text-yellow-500" />}
              selected={selectedFormat === 'json'}
              onClick={() => { setSelectedFormat('json'); setExportStatus('idle'); }}
            />
            <ExportOption
              id="csv"
              title="CSV Spreadsheet"
              desc="User stories table — for Jira / Azure DevOps import."
              icon={<FileSpreadsheet className="w-5 h-5 text-green-500" />}
              selected={selectedFormat === 'csv'}
              onClick={() => { setSelectedFormat('csv'); setExportStatus('idle'); }}
            />
            <ExportOption
              id="txt"
              title="Plain Text PRD"
              desc="Formatted PRD document as plain text."
              icon={<FileText className="w-5 h-5 text-blue-500" />}
              selected={selectedFormat === 'txt'}
              onClick={() => { setSelectedFormat('txt'); setExportStatus('idle'); }}
            />
          </div>

          {exportError && (
            <div className="flex items-start gap-2 text-red-500 text-sm bg-red-500/10 border border-red-500/20 rounded-lg p-3">
              <AlertTriangle className="w-4 h-4 shrink-0 mt-0.5" />
              <span>{exportError}</span>
            </div>
          )}

          <div className="pt-2">
            {exportStatus === 'idle' || exportStatus === 'error' ? (
              <Button onClick={handleExport} className="w-full h-10 text-[13px] font-semibold bg-primary hover:bg-primary/90 text-primary-foreground rounded-lg">
                Generate &amp; Download
              </Button>
            ) : exportStatus === 'processing' ? (
              <div className="flex items-center justify-center gap-2 w-full h-10 text-[13px] font-medium text-primary bg-primary/5 rounded-lg border border-primary/10">
                <Loader2 className="w-4 h-4 animate-spin" /> Generating...
              </div>
            ) : (
              <div className="flex items-center justify-center gap-2 w-full h-10 text-[13px] font-semibold bg-green-500/10 text-green-600 rounded-lg border border-green-500/20">
                Download started ✓
              </div>
            )}
          </div>
        </div>
      </Modal>
    </div>
  );
}

function StoryPreview({ story, index }: { story: Story; index: number }) {
  return (
    <div className="story-section">
      <h3 className="text-[16px] font-bold mb-2 text-foreground">
        {story.usId}: {story.feature}
      </h3>
      <div className="text-[14px] leading-relaxed bg-muted/20 border border-border/50 p-4 rounded-lg text-foreground/90 mb-4">
        {story.summary}
      </div>
      {story.description && (
        <p className="mb-5 text-[14px] leading-relaxed text-muted-foreground">{story.description}</p>
      )}
      {story.acceptanceCriteria.length > 0 && (
        <>
          <h4 className="font-bold text-[12px] uppercase tracking-wider text-muted-foreground mb-2 mt-5">
            Acceptance Criteria
          </h4>
          <ul className="list-disc pl-5 space-y-1.5 mb-5 text-[14px] text-foreground/80">
            {story.acceptanceCriteria.map((ac, i) => (
              <li key={i}>{ac}</li>
            ))}
          </ul>
        </>
      )}
      {story.businessRules.length > 0 && (
        <>
          <h4 className="font-bold text-[12px] uppercase tracking-wider text-muted-foreground mb-2 mt-5">
            Business Rules
          </h4>
          <ul className="list-disc pl-5 space-y-1.5 mb-5 text-[14px] text-foreground/80">
            {story.businessRules.map((br, i) => (
              <li key={i}>{br}</li>
            ))}
          </ul>
        </>
      )}
      {story.dependencies.length > 0 && (
        <>
          <h4 className="font-bold text-[12px] uppercase tracking-wider text-muted-foreground mb-2 mt-5">
            Dependencies
          </h4>
          <ul className="list-disc pl-5 space-y-1.5 mb-5 text-[14px] text-foreground/80">
            {story.dependencies.map((dep, i) => (
              <li key={i}>{dep}</li>
            ))}
          </ul>
        </>
      )}
    </div>
  );
}

function ExportOption({
  id, title, desc, icon, selected, onClick,
}: {
  id: string; title: string; desc: string; icon: React.ReactNode; selected: boolean; onClick: () => void;
}) {
  return (
    <label
      className={cn(
        'flex items-center gap-3 p-3 rounded-xl border cursor-pointer transition-colors',
        selected ? 'border-primary bg-primary/5' : 'border-border/80 bg-card hover:border-primary/30'
      )}
    >
      <input
        type="radio"
        name="export_format"
        value={id}
        checked={selected}
        onChange={onClick}
        className="w-4 h-4 text-primary focus:ring-primary border-border ml-1"
      />
      <div className="w-9 h-9 rounded-lg bg-background border border-border/50 flex items-center justify-center shrink-0">
        {icon}
      </div>
      <div className="flex-1">
        <h3 className="font-semibold text-[14px] text-foreground leading-tight">{title}</h3>
        <p className="text-[12px] text-muted-foreground mt-0.5">{desc}</p>
      </div>
    </label>
  );
}
