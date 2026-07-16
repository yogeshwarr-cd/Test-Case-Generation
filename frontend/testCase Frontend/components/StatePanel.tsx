import { AlertCircle, Inbox, LoaderCircle } from 'lucide-react';

export function StatePanel({ type, title, message }: { type: 'loading' | 'error' | 'empty'; title: string; message: string }) {
  const Icon = type === 'loading' ? LoaderCircle : type === 'error' ? AlertCircle : Inbox;
  return (
    <div className="flex min-h-64 flex-col items-center justify-center rounded-2xl border border-border bg-card p-8 text-center">
      <Icon className={`mb-4 h-10 w-10 ${type === 'loading' ? 'animate-spin text-primary' : type === 'error' ? 'text-red-500' : 'text-muted-foreground'}`} />
      <h2 className="text-lg font-semibold">{title}</h2>
      <p className="mt-2 max-w-lg text-sm text-muted-foreground">{message}</p>
    </div>
  );
}
