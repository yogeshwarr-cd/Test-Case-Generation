'use client';

import React from 'react';
import { CheckCircle2, Loader2, AlertCircle } from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';

export type AutosaveState = 'saved' | 'saving' | 'failed';

interface AutosaveIndicatorProps {
  state: AutosaveState;
  onRetry?: () => void;
}

export function AutosaveIndicator({ state, onRetry }: AutosaveIndicatorProps) {
  return (
    <div className="flex items-center gap-1.5 text-xs font-medium h-5">
      <AnimatePresence mode="wait">
        {state === 'saved' && (
          <motion.div
            key="saved"
            initial={{ opacity: 0, y: 5 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -5 }}
            className="flex items-center gap-1.5 text-muted-foreground"
          >
            <CheckCircle2 className="w-3.5 h-3.5" />
            <span>Saved</span>
          </motion.div>
        )}
        
        {state === 'saving' && (
          <motion.div
            key="saving"
            initial={{ opacity: 0, y: 5 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -5 }}
            className="flex items-center gap-1.5 text-muted-foreground"
          >
            <Loader2 className="w-3.5 h-3.5 animate-spin" />
            <span>Saving...</span>
          </motion.div>
        )}

        {state === 'failed' && (
          <motion.div
            key="failed"
            initial={{ opacity: 0, y: 5 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -5 }}
            className="flex items-center gap-1.5 text-red-500 cursor-pointer hover:text-red-600 transition-colors"
            onClick={onRetry}
          >
            <AlertCircle className="w-3.5 h-3.5" />
            <span>Save failed — retry</span>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
