'use client';

import React from 'react';

export default function ProjectSettingsPage() {
  return (
    <div className="flex-1 flex flex-col p-8 space-y-6 max-w-2xl mx-auto select-none bg-background transition-colors min-h-screen">
      <div className="border-b border-slate-200 pb-4">
        <h1 className="text-2xl font-bold text-slate-900">Project Settings</h1>
        <p className="text-xs text-slate-500">Edit threshold and attempts configuration</p>
      </div>
      <div className="bg-white p-6 rounded-xl border border-slate-200 shadow-sm text-center py-12">
        <p className="text-sm text-slate-500">Project configuration details are currently set to default.</p>
      </div>
    </div>
  );
}
