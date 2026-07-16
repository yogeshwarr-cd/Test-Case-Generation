'use client';

import { Plus, Trash2 } from 'lucide-react';

interface DynamicListFieldProps {
  label: string;
  values: string[];
  required?: boolean;
  error?: string;
  onChange: (values: string[]) => void;
}

export function DynamicListField({ label, values, required, error, onChange }: DynamicListFieldProps) {
  return (
    <fieldset className="space-y-3">
      <div>
        <legend className="text-sm font-semibold">{label}{required && <span className="ml-1 text-red-500">*</span>}</legend>
        <p className="mt-1 text-xs text-muted-foreground">Add each item separately for cleaner traceability.</p>
      </div>
      {values.map((value, index) => (
        <div key={index} className="flex items-start gap-2">
          <textarea
            value={value}
            onChange={(event) => onChange(values.map((item, itemIndex) => itemIndex === index ? event.target.value : item))}
            aria-label={`${label} ${index + 1}`}
            className="min-h-20 flex-1 resize-y rounded-lg border border-input bg-background px-3 py-2 text-sm outline-none focus:border-primary focus:ring-2 focus:ring-primary/20"
            placeholder={`Enter ${label.toLowerCase().replace(/s$/, '')}`}
          />
          <button
            type="button"
            onClick={() => onChange(values.length === 1 ? [''] : values.filter((_, itemIndex) => itemIndex !== index))}
            className="mt-1 rounded-lg p-2 text-muted-foreground hover:bg-red-500/10 hover:text-red-500"
            aria-label={`Remove ${label} item ${index + 1}`}
          >
            <Trash2 className="h-4 w-4" />
          </button>
        </div>
      ))}
      <button type="button" onClick={() => onChange([...values, ''])} className="inline-flex items-center gap-2 text-sm font-semibold text-primary hover:underline">
        <Plus className="h-4 w-4" /> Add another
      </button>
      {error && <p className="text-sm text-red-500" role="alert">{error}</p>}
    </fieldset>
  );
}
