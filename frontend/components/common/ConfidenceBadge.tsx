'use client';

import React from 'react';
import { cn } from '@/lib/utils';

interface ConfidenceBadgeProps {
  score: number;
  className?: string;
}

export function ConfidenceBadge({ score, className }: ConfidenceBadgeProps) {
  const isHigh = score >= 85;
  
  return (
    <div 
      className={cn(
        "group relative inline-flex items-center justify-center w-3 h-3 rounded-full cursor-help",
        isHigh ? "bg-green-500" : "bg-amber-500",
        className
      )}
    >
      {/* Tooltip */}
      <div className="absolute bottom-full mb-2 hidden group-hover:block z-50">
        <div className="bg-popover text-popover-foreground text-xs rounded shadow-lg px-2 py-1 whitespace-nowrap border border-border">
          Confidence: {score}%
        </div>
      </div>
    </div>
  );
}
