'use client';

import React from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Loader2, CheckCircle2, XCircle, Bot } from 'lucide-react';
import { ProcessLog } from '@/services/mockData';
import { cn } from '@/lib/utils';

interface LiveActivityFeedProps {
  logs: ProcessLog[];
  isFullWidth?: boolean;
}

export function LiveActivityFeed({ logs, isFullWidth = false }: LiveActivityFeedProps) {
  return (
    <div className={cn("flex flex-col bg-card border border-border overflow-hidden", isFullWidth ? "w-full rounded-xl" : "w-80 h-full shadow-lg")}>
      <div className="p-4 border-b border-border bg-muted/30 flex items-center justify-between">
        <h3 className="font-semibold text-sm flex items-center gap-2 text-foreground">
          <Bot className="w-4 h-4 text-primary" />
          Live Activity Feed
        </h3>
        <span className="text-xs text-muted-foreground">{logs.length} updates</span>
      </div>
      
      <div className="flex-1 overflow-y-auto p-4 space-y-3">
        <AnimatePresence initial={false}>
          {logs.map((log) => (
            <motion.div
              key={log.id}
              initial={{ opacity: 0, x: -10, height: 0 }}
              animate={{ opacity: 1, x: 0, height: 'auto' }}
              className="flex gap-3 text-sm"
            >
              <div className="shrink-0 mt-0.5">
                {log.status === 'in-progress' && <Loader2 className="w-4 h-4 text-amber-500 animate-spin" />}
                {log.status === 'success' && <CheckCircle2 className="w-4 h-4 text-green-500" />}
                {log.status === 'failed' && <XCircle className="w-4 h-4 text-red-500" />}
              </div>
              
              <div className="flex flex-col gap-0.5">
                <span className="text-foreground leading-snug">{log.message}</span>
                <span className="text-[10px] text-muted-foreground opacity-70 flex gap-2">
                  <span>{log.timestamp}</span>
                </span>
              </div>
            </motion.div>
          ))}
        </AnimatePresence>
        
        {logs.length === 0 && (
          <div className="h-full flex flex-col items-center justify-center text-muted-foreground text-sm opacity-60">
            <Bot className="w-8 h-8 mb-2 opacity-50" />
            <p>Waiting for activity...</p>
          </div>
        )}
      </div>
    </div>
  );
}
