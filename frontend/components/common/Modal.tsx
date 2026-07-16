'use client';

import React from 'react';
import { cn } from '@/lib/utils';

interface ModalProps {
  isOpen: boolean;
  onClose: () => void;
  title: string;
  children: React.ReactNode;
  fullScreen?: boolean;
}

export const Modal: React.FC<ModalProps> = ({ isOpen, onClose, title, children, fullScreen }) => {
  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 sm:p-6">
      {/* Overlay */}
      <div 
        className="absolute inset-0 bg-black/60 backdrop-blur-sm transition-opacity" 
        onClick={onClose} 
      />
      
      {/* Content Container */}
      <div className={cn(
        "relative transform overflow-hidden rounded-xl bg-background border border-border p-6 shadow-2xl transition-all flex flex-col",
        fullScreen ? "w-full max-w-5xl h-[90vh]" : "w-full max-w-md"
      )}>
        <div className="flex items-center justify-between border-b border-border pb-4 mb-4 shrink-0">
          <h3 className="text-xl font-bold text-foreground">{title}</h3>
          <button 
            onClick={onClose} 
            className="text-muted-foreground hover:text-foreground transition-colors text-2xl leading-none font-medium"
          >
            &times;
          </button>
        </div>
        <div className="flex-1 overflow-y-auto">
          {children}
        </div>
      </div>
    </div>
  );
};
