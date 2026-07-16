'use client';

import React from 'react';

export default function AuditLogsPage() {
  return (
    <div className="flex-1 flex flex-col p-8 space-y-6 select-none bg-background transition-colors min-h-screen">
      <div className="border-b border-slate-200 pb-4">
        <h1 className="text-2xl font-bold text-slate-900">Audit Logs</h1>
        <p className="text-xs text-slate-500">Audit logs and AI generation console inputs</p>
      </div>
      <div className="bg-white p-6 rounded-xl border border-slate-200 shadow-sm text-center py-12">
        <p className="text-sm text-slate-500">This view will be enabled during Phase 2.</p>
      </div>
    </div>
  );
}
