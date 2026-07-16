'use client';

import React from 'react';

export const Table = ({ headers, children }: { headers: string[]; children: React.ReactNode }) => {
  return (
    <div className="w-full overflow-x-auto">
      <table className="w-full border-collapse text-left text-xs text-slate-500">
        <thead>
          <tr className="border-b border-slate-200 bg-slate-50">
            {headers.map((h, i) => (
              <th key={i} className="p-3 font-semibold text-slate-900">{h}</th>
            ))}
          </tr>
        </thead>
        <tbody className="divide-y divide-slate-100 bg-white">
          {children}
        </tbody>
      </table>
    </div>
  );
};
