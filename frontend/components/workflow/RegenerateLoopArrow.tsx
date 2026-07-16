'use client';

import React from 'react';
import { RotateCw } from 'lucide-react';

export const RegenerateLoopArrow = ({ isLooping }: { isLooping: boolean }) => {
  return (
    <RotateCw className={`w-4 h-4 text-slate-500 ${isLooping ? 'animate-spin' : ''}`} />
  );
};
