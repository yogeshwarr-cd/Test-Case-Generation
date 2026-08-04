'use client';

import React from 'react';

export const Table = ({ headers, children }: { headers: string[]; children: React.ReactNode }) => {
  return (
    <div className="w-full overflow-x-auto rounded-xl border border-border" tabIndex={0} role="region" aria-label="Scrollable data table">
      <table className="w-full min-w-max border-collapse text-left text-sm text-muted-foreground">
        <thead>
          <tr className="border-b border-border bg-muted/60">
            {headers.map((h, i) => (
              <th key={`${h}-${i}`} scope="col" className="whitespace-nowrap p-3 font-semibold text-foreground sm:p-4">{h}</th>
            ))}
          </tr>
        </thead>
        <tbody className="divide-y divide-border bg-card">
          {children}
        </tbody>
      </table>
    </div>
  );
};
