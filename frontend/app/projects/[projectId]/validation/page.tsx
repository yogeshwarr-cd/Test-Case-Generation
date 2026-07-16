'use client';

import React, { useEffect, useState } from 'react';
import { useParams, useRouter } from 'next/navigation';
import {
  CheckCircle2, XCircle, AlertTriangle, Info, ShieldCheck,
  RefreshCw, Gauge, Loader2,
} from 'lucide-react';
import { api } from '@/services/api';
import { Button } from '@/components/common/Button';
import { cn } from '@/lib/utils';

interface ValidationIssue {
  issue_id: string;
  severity: 'INFO' | 'WARNING' | 'ERROR' | 'CRITICAL';
  category: string;
  story_id: string | null;
  field: string;
  message: string;
  source_reference: string | null;
  suggested_action: string | null;
}

interface ConfidenceCriterionScore {
  category: string;
  score: number;
  max_score: number;
  passed: boolean;
  issue_count: number;
  details: string[];
}

interface ValidationData {
  passed: boolean;
  confidence_score: number;
  threshold: number;
  issues: ValidationIssue[];
  criteria_scores: ConfidenceCriterionScore[];
  recommendations: string[];
}

export default function FinalValidationPage() {
  const params = useParams();
  const router = useRouter();
  const projectId = params?.projectId as string;

  const [loading, setLoading] = useState(true);
  const [data, setData] = useState<ValidationData | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<'critical' | 'warning' | 'info'>('critical');

  useEffect(() => {
    api
      .getWorkflowState(projectId)
      .then((res) => {
        const valResult = res.state?.validation_result || null;
        if (!valResult) {
          setError('Validation has not been run yet. Complete the workflow pipeline first.');
          setLoading(false);
          return;
        }
        setData({
          passed: valResult.passed ?? false,
          confidence_score: valResult.confidence_score ?? 0.0,
          threshold: valResult.threshold ?? 0.8,
          issues: valResult.issues || [],
          criteria_scores: valResult.criteria_scores || [],
          recommendations: valResult.recommendations || [],
        });
        setLoading(false);
      })
      .catch((err) => {
        setError(err?.message || 'Failed to load validation results.');
        setLoading(false);
      });
  }, [projectId]);

  if (loading) {
    return (
      <div className="flex-1 flex items-center justify-center p-8 bg-background">
        <div className="flex flex-col items-center gap-3 text-muted-foreground">
          <Loader2 className="w-7 h-7 animate-spin text-primary" />
          <p className="text-sm">Loading validation records...</p>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex-1 flex items-center justify-center p-8 bg-background">
        <div className="flex flex-col items-center gap-4 text-amber-500 max-w-md text-center">
          <AlertTriangle className="w-7 h-7" />
          <p className="text-sm font-medium">{error}</p>
          <Button variant="secondary" onClick={() => router.push(`/projects/${projectId}/processing`)}>
            Back to Processing
          </Button>
        </div>
      </div>
    );
  }

  if (!data) return null;

  const criticalIssues = data.issues.filter((i) => i.severity === 'CRITICAL' || i.severity === 'ERROR');
  const warningIssues = data.issues.filter((i) => i.severity === 'WARNING');
  const infoIssues = data.issues.filter((i) => i.severity === 'INFO');
  const activeIssues =
    activeTab === 'critical' ? criticalIssues :
    activeTab === 'warning' ? warningIssues : infoIssues;

  const scorePercent = Math.round(data.confidence_score * 100);
  const thresholdPercent = Math.round(data.threshold * 100);

  return (
    <div className="flex-1 flex flex-col p-8 space-y-8 bg-background text-foreground overflow-y-auto">
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <div className="text-[11px] text-muted-foreground flex gap-2 items-center mb-1 uppercase tracking-wider font-bold">
            <span>Project Workspace</span> <span>/</span> <span className="text-foreground">Validation Gate</span>
          </div>
          <h1 className="text-2xl font-bold tracking-tight">Validation Gate</h1>
          <p className="text-[13px] text-muted-foreground mt-1">
            AI quality analysis of generated user stories.
          </p>
        </div>
        <div
          className={cn(
            'flex items-center gap-3 px-5 py-3 rounded-xl border font-semibold text-sm',
            data.passed
              ? 'bg-green-500/10 border-green-500/30 text-green-600'
              : 'bg-red-500/10 border-red-500/30 text-red-600'
          )}
        >
          {data.passed ? (
            <CheckCircle2 className="w-5 h-5" />
          ) : (
            <XCircle className="w-5 h-5" />
          )}
          {data.passed ? 'Validation Passed' : 'Validation Failed'}
        </div>
      </div>

      {/* Score overview */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <div className="bg-card border border-border rounded-xl p-5 shadow-sm">
          <div className="flex items-center gap-2 text-muted-foreground text-xs font-bold uppercase tracking-wider mb-3">
            <Gauge className="w-4 h-4" /> Confidence Score
          </div>
          <div className="text-4xl font-black text-foreground">{scorePercent}%</div>
          <div className="text-xs text-muted-foreground mt-1">
            Threshold: {thresholdPercent}%
          </div>
          <div className="mt-3 h-2 bg-muted rounded-full overflow-hidden">
            <div
              className={cn('h-full rounded-full', data.passed ? 'bg-green-500' : 'bg-red-500')}
              style={{ width: `${Math.min(scorePercent, 100)}%` }}
            />
          </div>
        </div>

        <div className="bg-card border border-border rounded-xl p-5 shadow-sm">
          <div className="flex items-center gap-2 text-muted-foreground text-xs font-bold uppercase tracking-wider mb-3">
            <AlertTriangle className="w-4 h-4" /> Total Issues
          </div>
          <div className="text-4xl font-black text-foreground">{data.issues.length}</div>
          <div className="flex gap-2 mt-3 flex-wrap">
            <span className="text-[11px] font-bold bg-red-500/10 text-red-500 px-2 py-0.5 rounded">
              {criticalIssues.length} Critical
            </span>
            <span className="text-[11px] font-bold bg-amber-500/10 text-amber-500 px-2 py-0.5 rounded">
              {warningIssues.length} Warning
            </span>
            <span className="text-[11px] font-bold bg-blue-500/10 text-blue-500 px-2 py-0.5 rounded">
              {infoIssues.length} Info
            </span>
          </div>
        </div>

        <div className="bg-card border border-border rounded-xl p-5 shadow-sm">
          <div className="flex items-center gap-2 text-muted-foreground text-xs font-bold uppercase tracking-wider mb-3">
            <ShieldCheck className="w-4 h-4" /> Criteria Passed
          </div>
          <div className="text-4xl font-black text-foreground">
            {data.criteria_scores.filter((c) => c.passed).length}
            <span className="text-xl text-muted-foreground font-medium">
              /{data.criteria_scores.length}
            </span>
          </div>
          <div className="text-xs text-muted-foreground mt-1">quality criteria</div>
        </div>
      </div>

      {/* Criteria scores */}
      {data.criteria_scores.length > 0 && (
        <div className="bg-card border border-border rounded-xl p-6 shadow-sm">
          <h2 className="text-sm font-bold mb-4 flex items-center gap-2">
            <ShieldCheck className="w-4 h-4 text-primary" /> Quality Criteria Breakdown
          </h2>
          <div className="space-y-3">
            {data.criteria_scores.map((criterion, idx) => (
              <div key={idx} className="space-y-1">
                <div className="flex items-center justify-between text-sm">
                  <span className="font-medium text-foreground">{criterion.category}</span>
                  <div className="flex items-center gap-2">
                    <span className="text-muted-foreground text-xs">
                      {criterion.score}/{criterion.max_score}
                    </span>
                    {criterion.passed ? (
                      <CheckCircle2 className="w-4 h-4 text-green-500" />
                    ) : (
                      <XCircle className="w-4 h-4 text-red-500" />
                    )}
                  </div>
                </div>
                <div className="h-1.5 bg-muted rounded-full overflow-hidden">
                  <div
                    className={cn(
                      'h-full rounded-full',
                      criterion.passed ? 'bg-green-500' : 'bg-red-400'
                    )}
                    style={{ width: `${(criterion.score / criterion.max_score) * 100}%` }}
                  />
                </div>
                {criterion.details.length > 0 && (
                  <ul className="pl-4 text-[12px] text-muted-foreground space-y-0.5">
                    {criterion.details.map((d, i) => (
                      <li key={i} className="list-disc">{d}</li>
                    ))}
                  </ul>
                )}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Issues */}
      {data.issues.length > 0 && (
        <div className="bg-card border border-border rounded-xl p-6 shadow-sm">
          <h2 className="text-sm font-bold mb-4">Validation Issues</h2>
          <div className="flex gap-1 mb-4 border-b border-border">
            {(['critical', 'warning', 'info'] as const).map((tab) => {
              const count = tab === 'critical' ? criticalIssues.length : tab === 'warning' ? warningIssues.length : infoIssues.length;
              return (
                <button
                  key={tab}
                  onClick={() => setActiveTab(tab)}
                  className={cn(
                    'px-4 py-2 text-[13px] font-semibold border-b-2 -mb-px transition-colors capitalize',
                    activeTab === tab
                      ? 'border-primary text-primary'
                      : 'border-transparent text-muted-foreground hover:text-foreground'
                  )}
                >
                  {tab} ({count})
                </button>
              );
            })}
          </div>

          <div className="space-y-3">
            {activeIssues.length === 0 ? (
              <p className="text-sm text-muted-foreground py-4 text-center">No {activeTab} issues.</p>
            ) : (
              activeIssues.map((issue) => (
                <div
                  key={issue.issue_id}
                  className={cn(
                    'p-4 rounded-xl border text-sm',
                    issue.severity === 'CRITICAL' || issue.severity === 'ERROR'
                      ? 'bg-red-500/5 border-red-500/20'
                      : issue.severity === 'WARNING'
                      ? 'bg-amber-500/5 border-amber-500/20'
                      : 'bg-blue-500/5 border-blue-500/20'
                  )}
                >
                  <div className="flex items-start gap-3">
                    {issue.severity === 'CRITICAL' || issue.severity === 'ERROR' ? (
                      <XCircle className="w-4 h-4 text-red-500 shrink-0 mt-0.5" />
                    ) : issue.severity === 'WARNING' ? (
                      <AlertTriangle className="w-4 h-4 text-amber-500 shrink-0 mt-0.5" />
                    ) : (
                      <Info className="w-4 h-4 text-blue-500 shrink-0 mt-0.5" />
                    )}
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2 flex-wrap mb-1">
                        <span className="font-semibold text-foreground">{issue.category}</span>
                        {issue.story_id && (
                          <span className="text-[10px] bg-muted text-muted-foreground px-1.5 py-0.5 rounded font-mono">
                            {issue.story_id}
                          </span>
                        )}
                        <span className="text-[10px] text-muted-foreground font-mono">{issue.field}</span>
                      </div>
                      <p className="text-muted-foreground leading-relaxed">{issue.message}</p>
                      {issue.suggested_action && (
                        <p className="mt-2 text-xs font-medium text-foreground/70">
                          → {issue.suggested_action}
                        </p>
                      )}
                    </div>
                  </div>
                </div>
              ))
            )}
          </div>
        </div>
      )}

      {/* Recommendations */}
      {data.recommendations.length > 0 && (
        <div className="bg-card border border-border rounded-xl p-6 shadow-sm">
          <h2 className="text-sm font-bold mb-3 flex items-center gap-2">
            <RefreshCw className="w-4 h-4 text-primary" /> Recommendations
          </h2>
          <ul className="space-y-2">
            {data.recommendations.map((rec, idx) => (
              <li key={idx} className="flex items-start gap-2 text-sm text-muted-foreground">
                <span className="text-primary font-bold shrink-0">{idx + 1}.</span>
                <span>{rec}</span>
              </li>
            ))}
          </ul>
        </div>
      )}

      {/* Actions */}
      <div className="flex gap-3 pb-8">
        <Button
          onClick={() => router.push(`/projects/${projectId}/stories`)}
          variant="secondary"
        >
          Back to Stories
        </Button>
        <Button
          onClick={() => router.push(`/projects/${projectId}/export`)}
          className="bg-primary hover:bg-primary/90 text-primary-foreground"
        >
          Continue to Export
        </Button>
      </div>
    </div>
  );
}
