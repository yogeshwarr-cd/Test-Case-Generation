'use client';

import React, { useEffect, useState } from 'react';
import { useRouter, useParams } from 'next/navigation';
import { ChevronRight, Loader2, AlertTriangle } from 'lucide-react';
import { Button } from '@/components/common/Button';
import { api } from '@/services/api';
import { SegmentationChunk } from '@/services/mockData';

const LABELS = [
  'Functional Requirement',
  'Non-Functional Requirement',
  'Business Rule',
  'Persona',
  'Business Goal',
  'Constraint',
  'Edge Case',
  'Dependency',
  'Out of Scope',
  'Uncategorized',
];

export default function SegmentationPage() {
  const router = useRouter();
  const params = useParams();
  const projectId = params?.projectId as string;

  const [chunks, setChunks] = useState<SegmentationChunk[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api
      .getSegmentationChunks(projectId)
      .then((data) => {
        setChunks(data);
        setLoading(false);
      })
      .catch((err) => {
        setError(err?.message || 'Failed to load chunks.');
        setLoading(false);
      });
  }, [projectId]);

  const updateLabel = (id: string, newLabel: string) => {
    setChunks((prev) => prev.map((c) => (c.id === id ? { ...c, label: newLabel } : c)));
  };

  if (loading) {
    return (
      <div className="flex-1 flex items-center justify-center p-8 bg-background">
        <div className="flex flex-col items-center gap-3 text-muted-foreground">
          <Loader2 className="w-7 h-7 animate-spin text-primary" />
          <p className="text-sm">Loading segmentation data...</p>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex-1 flex items-center justify-center p-8 bg-background">
        <div className="flex flex-col items-center gap-3 text-red-500 max-w-md text-center">
          <AlertTriangle className="w-7 h-7" />
          <p className="text-sm font-medium">{error}</p>
          <Button variant="secondary" onClick={() => router.back()}>Go Back</Button>
        </div>
      </div>
    );
  }

  if (chunks.length === 0) {
    return (
      <div className="flex-1 flex items-center justify-center p-8 bg-background">
        <div className="flex flex-col items-center gap-3 text-muted-foreground max-w-md text-center">
          <p className="text-sm">No segmentation chunks found for this workflow yet. Run the pipeline first.</p>
          <Button variant="secondary" onClick={() => router.back()}>Go Back</Button>
        </div>
      </div>
    );
  }

  return (
    <div className="flex-1 flex flex-col p-8 bg-background text-foreground h-full">
      <div className="mb-6">
        <div className="text-xs text-muted-foreground flex gap-2 items-center mb-1 uppercase tracking-wider font-bold">
          <span>Project Workspace</span> <span>/</span> <span className="text-foreground">Segmentation Review</span>
        </div>
        <h1 className="text-3xl font-bold tracking-tight">Segmentation Review</h1>
        <p className="text-sm text-muted-foreground mt-1">
          Review the {chunks.length} extracted chunks and their AI-assigned context labels.
        </p>
      </div>

      <div className="flex-1 overflow-y-auto bg-card border border-border rounded-xl shadow-sm mb-6">
        <table className="w-full text-sm text-left text-muted-foreground">
          <thead className="text-xs text-foreground uppercase bg-muted/50 border-b border-border sticky top-0">
            <tr>
              <th className="px-4 py-3 w-28">Chunk ID</th>
              <th className="px-4 py-3">Content</th>
              {chunks.some((c) => c.sectionTitle) && (
                <th className="px-4 py-3 w-40">Section</th>
              )}
              <th className="px-4 py-3 w-56">Context Label</th>
            </tr>
          </thead>
          <tbody>
            {chunks.map((chunk) => (
              <tr key={chunk.id} className="border-b border-border hover:bg-muted/20 align-top">
                <td className="px-4 py-3 font-mono text-xs text-muted-foreground whitespace-nowrap">
                  {chunk.id.length > 12 ? `${chunk.id.slice(0, 12)}…` : chunk.id}
                </td>
                <td className="px-4 py-3 text-foreground leading-relaxed text-sm">
                  {chunk.text}
                  {chunk.tokenCount !== undefined && (
                    <span className="ml-2 text-[10px] text-muted-foreground bg-muted px-1.5 py-0.5 rounded">
                      {chunk.tokenCount} tok
                    </span>
                  )}
                </td>
                {chunks.some((c) => c.sectionTitle) && (
                  <td className="px-4 py-3 text-xs text-muted-foreground">{chunk.sectionTitle || '—'}</td>
                )}
                <td className="px-4 py-3">
                  <select
                    value={chunk.label}
                    onChange={(e) => updateLabel(chunk.id, e.target.value)}
                    className="bg-background border border-input text-foreground text-xs rounded-lg focus:ring-primary focus:border-primary block w-full p-2"
                  >
                    {LABELS.map((l) => (
                      <option key={l} value={l}>{l}</option>
                    ))}
                  </select>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div className="flex justify-end pt-4 border-t border-border">
        <Button
          onClick={() => router.push(`/projects/${projectId}/requirements`)}
          size="lg"
          className="bg-primary hover:bg-primary/90 text-primary-foreground"
        >
          Continue to Requirements <ChevronRight className="w-4 h-4 ml-2" />
        </Button>
      </div>
    </div>
  );
}
