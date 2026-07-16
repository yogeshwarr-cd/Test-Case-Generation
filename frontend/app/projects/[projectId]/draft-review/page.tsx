'use client';

import React, { useEffect, useState } from 'react';
import { useRouter, useParams } from 'next/navigation';
import { ShieldAlert, Check } from 'lucide-react';
import { api } from '@/services/api';
import { Story } from '@/services/mockData';
import { Button } from '@/components/common/Button';

export default function DraftReviewPage() {
  const router = useRouter();
  const params = useParams();
  const projectId = params?.projectId as string;

  const [stories, setStories] = useState<Story[]>([]);
  const [loading, setLoading] = useState(true);
  const [approvedIds, setApprovedIds] = useState<Set<string>>(new Set());

  useEffect(() => {
    api.getStories(projectId).then(data => {
      setStories(data);
      setLoading(false);
    });
  }, [projectId]);

  const toggleApprove = (id: string) => {
    setApprovedIds(prev => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  if (loading) {
    return <div className="p-8">Loading drafts...</div>;
  }

  return (
    <div className="flex-1 flex flex-col p-8 bg-background text-foreground h-full relative">
      <div className="mb-6">
        <h1 className="text-3xl font-bold tracking-tight">Draft Review (Pre-Validation)</h1>
        
        {/* Banner */}
        <div className="mt-4 bg-amber-500/10 border border-amber-500/20 text-amber-600 dark:text-amber-500 rounded-lg p-4 flex items-center gap-3">
          <ShieldAlert className="w-5 h-5" />
          <span className="text-sm font-medium">These stories haven't been automatically validated yet. Approving them runs the validation pipeline.</span>
        </div>
      </div>

      <div className="flex-1 overflow-y-auto pb-24 space-y-4">
        {stories.map(story => {
          const isApproved = approvedIds.has(story.id);
          return (
            <div key={story.id} className={`p-5 rounded-xl border transition-all ${isApproved ? 'border-primary bg-primary/5' : 'border-border bg-card'}`}>
              <div className="flex items-start justify-between">
                <div>
                  <div className="text-xs text-muted-foreground font-bold mb-1">{story.usId} • {story.epicName}</div>
                  <h3 className="text-sm font-semibold text-foreground mb-2">{story.summary}</h3>
                  <p className="text-xs text-muted-foreground line-clamp-2">{story.description}</p>
                </div>
                <Button 
                  variant={isApproved ? 'primary' : 'secondary'} 
                  size="sm" 
                  onClick={() => toggleApprove(story.id)}
                  className={isApproved ? 'bg-primary text-primary-foreground' : ''}
                >
                  {isApproved ? <><Check className="w-4 h-4 mr-1" /> Approved</> : 'Approve'}
                </Button>
              </div>
            </div>
          );
        })}
      </div>

      <div className="absolute bottom-0 left-0 right-0 p-6 bg-card/80 backdrop-blur-md border-t border-border flex items-center justify-end z-10">
        <Button onClick={() => router.push(`/projects/${projectId}/stories`)} size="lg" className="bg-primary hover:bg-primary/90 text-primary-foreground">
          Approve All, Run Validation
        </Button>
      </div>
    </div>
  );
}
