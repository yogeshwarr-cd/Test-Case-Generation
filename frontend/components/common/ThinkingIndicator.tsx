'use client';

import React, { useEffect, useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';

export type PipelineStage = {
  stageKey: string;
  statusText: string;
  mockDurationMs: number;
};

export const MOCK_PIPELINE_STAGES = {
  intake: [
    { stageKey: 'upload', statusText: 'Reading your document...', mockDurationMs: 2800 },
    { stageKey: 'extract', statusText: 'Extracting requirements...', mockDurationMs: 3200 },
  ],
  epics: [
    { stageKey: 'identify', statusText: 'Identifying epics...', mockDurationMs: 2500 },
    { stageKey: 'draft', statusText: 'Drafting outline...', mockDurationMs: 3100 },
  ],
  segmentation: [
    { stageKey: 'classify', statusText: 'Classifying requirement chunks...', mockDurationMs: 3000 }
  ],
  stories: [
    { stageKey: 'draft_stories', statusText: 'Drafting user stories...', mockDurationMs: 3500 },
  ],
  validation: [
    { stageKey: 'check', statusText: 'Checking story quality...', mockDurationMs: 3000 },
  ],
  finalizing: [
    { stageKey: 'finalize', statusText: 'Finalizing your backlog...', mockDurationMs: 2500 },
  ]
};

export function ThinkingIndicator({ 
  stages, 
  onComplete,
  activeNode
}: { 
  stages?: PipelineStage[];
  onComplete?: () => void;
  activeNode?: string;
}) {
  const nodeTextMap: Record<string, string> = {
    'START': 'Preprocessing document',
    'Preprocessing': 'Preprocessing document',
    'RequirementAnalysis': 'Analyzing business rules and functional requirements',
    'Requirements Analysis': 'Analyzing business rules and functional requirements',
    'EpicGeneration': 'Drafting epic outline review',
    'Epic Generation': 'Drafting epic outline review',
    'FeatureGeneration': 'Defining user features',
    'Feature Generation': 'Defining user features',
    'OneLineStoryMapping': 'Mapping one-line stories to epics',
    'One-Line Story Mapping': 'Mapping one-line stories to epics',
    'RAGContextRetrieval': 'Retrieving grounding RAG context',
    'RAG Context Retrieval': 'Retrieving grounding RAG context',
    'UserStoryGeneration': 'Generating detailed user stories',
    'User Story Generation': 'Generating detailed user stories',
    'ValidationGate': 'Performing quality gates validation',
    'Validation Gate': 'Performing quality gates validation',
    'COMPLETED': 'Outline generated successfully',
    'END': 'Outline generated successfully'
  };

  const [currentIndex, setCurrentIndex] = useState(0);
  const hasCompleted = React.useRef(false);

  useEffect(() => {
    if (activeNode) return;

    if (!stages || stages.length === 0 || currentIndex >= stages.length) {
      if (stages && currentIndex >= stages.length && onComplete && !hasCompleted.current) {
        hasCompleted.current = true;
        onComplete();
      }
      return;
    }

    const currentStage = stages[currentIndex];
    const timer = setTimeout(() => {
      setCurrentIndex(prev => prev + 1);
    }, currentStage.mockDurationMs);

    return () => clearTimeout(timer);
  }, [currentIndex, stages, onComplete, activeNode]);

  const rawText = activeNode ? (nodeTextMap[activeNode] || `Running ${activeNode}`) : (stages && stages[currentIndex]?.statusText || 'Processing');
  const cleanText = rawText.replace(/\.+$/, '');

  if (!activeNode && stages && currentIndex >= stages.length) return null;

  return (
    <div className="flex items-center justify-start gap-3 h-[52px] mb-4 w-full">
      <motion.div
        animate={{ scale: [1, 1.06, 1], opacity: [0.85, 1, 0.85] }}
        transition={{ duration: 2, ease: 'easeInOut', repeat: Infinity }}
        className="shrink-0 w-12 h-12 flex items-center justify-center"
      >
        <motion.img 
          src="/images_and_videos/logo-think.png" 
          alt="Thinking" 
          className="w-full h-full object-contain" 
          animate={{ rotate: 360 }}
          transition={{ duration: 3, ease: 'linear', repeat: Infinity }}
        />
      </motion.div>
      <div className="relative flex-1 overflow-hidden h-[24px]">
        <AnimatePresence mode="wait">
          <motion.div
            key={cleanText}
            initial={{ opacity: 0, y: 5 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -5 }}
            transition={{ duration: 0.3 }}
            className="absolute inset-0 flex items-center"
          >
            <span className="text-[13px] md:text-[14px] text-muted-foreground font-medium">
              {cleanText}
              {activeNode !== 'COMPLETED' && activeNode !== 'END' && (
                <motion.span
                  animate={{ opacity: [0.3, 1, 0.3] }}
                  transition={{ duration: 1.5, repeat: Infinity, ease: 'easeInOut' }}
                  className="inline-block ml-[2px] tracking-widest"
                >
                  ...
                </motion.span>
              )}
            </span>
          </motion.div>
        </AnimatePresence>
      </div>
    </div>
  );
}
