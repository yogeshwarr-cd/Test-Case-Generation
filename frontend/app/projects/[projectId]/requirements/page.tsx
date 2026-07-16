'use client';

import React, { useEffect, useState } from 'react';
import { useRouter, useParams } from 'next/navigation';
import { Button } from '@/components/common/Button';
import { GripVertical, ChevronDown, ArrowRight, Loader2, AlertTriangle } from 'lucide-react';
import { cn } from '@/lib/utils';
import { motion, AnimatePresence } from 'framer-motion';
import { api } from '@/services/api';
import { ExtractedRequirementCategory } from '@/services/mockData';

export default function RequirementsPage() {
  const router = useRouter();
  const params = useParams();
  const projectId = params?.projectId as string;

  const [requirements, setRequirements] = useState<ExtractedRequirementCategory[]>([]);
  const [expandedIds, setExpandedIds] = useState<Set<string>>(new Set());
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api
      .getRequirements(projectId)
      .then((data) => {
        setRequirements(data);
        if (data.length > 0) {
          setExpandedIds(new Set([data[0].id]));
        }
        setLoading(false);
      })
      .catch((err) => {
        setError(err?.message || 'Failed to load requirements.');
        setLoading(false);
      });
  }, [projectId]);

  const toggleAccordion = (id: string) => {
    setExpandedIds((prev) => {
      const next = new Set(prev);
      next.has(id) ? next.delete(id) : next.add(id);
      return next;
    });
  };

  if (loading) {
    return (
      <div className="flex-1 flex items-center justify-center p-8 bg-background">
        <div className="flex flex-col items-center gap-3 text-muted-foreground">
          <Loader2 className="w-7 h-7 animate-spin text-primary" />
          <p className="text-sm">Loading extracted requirements...</p>
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

  if (requirements.length === 0) {
    return (
      <div className="flex-1 flex items-center justify-center p-8 bg-background">
        <div className="flex flex-col items-center gap-3 text-muted-foreground max-w-md text-center">
          <p className="text-sm">
            No requirements have been extracted yet. Make sure the workflow pipeline has completed successfully.
          </p>
          <Button variant="secondary" onClick={() => router.push(`/projects/${projectId}/processing`)}>
            Back to Processing
          </Button>
        </div>
      </div>
    );
  }

  return (
    <div className="flex-1 flex flex-col h-full bg-background text-foreground relative">
      {/* Header */}
      <div className="p-6 pb-4 shrink-0 border-b border-border bg-background flex items-center justify-between">
        <div className="flex items-center gap-3">
          <h1 className="text-2xl font-bold tracking-tight">Extracted Requirements</h1>
          <div className="flex items-center gap-1 text-[11px] text-muted-foreground mt-1 cursor-default font-medium">
            <GripVertical className="w-3.5 h-3.5 opacity-50" />
            drag to reorder
          </div>
        </div>
        <Button
          onClick={() => router.push(`/projects/${projectId}/epics`)}
          className="bg-primary hover:bg-primary/90 text-primary-foreground shadow-md flex items-center gap-2 h-9 px-4 rounded-lg font-semibold"
        >
          Continue <ArrowRight className="w-4 h-4" />
        </Button>
      </div>

      {/* Accordion list */}
      <div className="flex-1 overflow-y-auto p-6 pb-24 bg-muted/10">
        <div className="max-w-4xl mx-auto space-y-3">
          {requirements.map((category) => {
            const isExpanded = expandedIds.has(category.id);
            return (
              <div
                key={category.id}
                className="bg-card border border-border rounded-xl overflow-hidden shadow-sm"
              >
                <button
                  onClick={() => toggleAccordion(category.id)}
                  className="w-full flex items-center justify-between p-4 bg-card hover:bg-accent/30 transition-colors focus:outline-none"
                >
                  <div className="flex items-center gap-3">
                    <GripVertical className="w-4 h-4 text-muted-foreground/50" />
                    <h3 className="font-bold text-foreground text-[15px]">{category.title}</h3>
                    <span className="bg-muted text-muted-foreground text-[11px] font-bold px-2.5 py-0.5 rounded-full">
                      {category.items.length}
                    </span>
                  </div>
                  <ChevronDown
                    className={cn(
                      'w-5 h-5 text-muted-foreground transition-transform duration-200',
                      isExpanded && 'rotate-180'
                    )}
                  />
                </button>

                <AnimatePresence initial={false}>
                  {isExpanded && (
                    <motion.div
                      initial={{ height: 0, opacity: 0 }}
                      animate={{ height: 'auto', opacity: 1 }}
                      exit={{ height: 0, opacity: 0 }}
                      transition={{ duration: 0.2, ease: 'easeInOut' }}
                    >
                      <div className="border-t border-border bg-background p-5 pt-4">
                        <ol className="list-decimal list-outside ml-5 space-y-3">
                          {category.items.map((item, idx) => (
                            <li
                              key={idx}
                              className="text-[14px] text-foreground pl-2 leading-relaxed marker:text-muted-foreground/80 marker:font-medium"
                            >
                              {item}
                            </li>
                          ))}
                        </ol>
                      </div>
                    </motion.div>
                  )}
                </AnimatePresence>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}
