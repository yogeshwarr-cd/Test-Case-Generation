'use client';

import React, { useEffect, useState } from 'react';
import { useParams } from 'next/navigation';
import { Clock, Filter, Bot, User, ChevronDown, ChevronUp } from 'lucide-react';
import { api } from '@/services/api';
import { ProjectHistoryEvent } from '@/services/mockData';

export default function ProjectHistoryPage() {
  const params = useParams();
  const projectId = params?.projectId as string;

  const [history, setHistory] = useState<ProjectHistoryEvent[]>([]);
  const [loading, setLoading] = useState(true);
  const [actorFilter, setActorFilter] = useState<'all' | 'system' | 'ba'>('all');

  useEffect(() => {
    api.getHistory(projectId).then(data => {
      setHistory(data);
      setLoading(false);
    });
  }, [projectId]);

  const filteredHistory = history.filter(event => 
    actorFilter === 'all' || event.actorType === actorFilter
  );

  if (loading) {
    return <div className="p-8">Loading Project History...</div>;
  }

  return (
    <div className="flex-1 flex flex-col p-6 pb-24 bg-background text-foreground overflow-y-auto">
      <div className="mb-4 flex items-end justify-between border-b border-border pb-4 shrink-0">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">Project History</h1>
          <p className="text-[13px] text-muted-foreground mt-1">A complete timeline of all automated and manual changes in this project.</p>
        </div>
        
        <div className="flex items-center gap-3">
          <Filter className="w-4 h-4 text-muted-foreground" />
          <div className="flex bg-muted/50 rounded-lg p-1 border border-border">
            <button 
              onClick={() => setActorFilter('all')}
              className={`px-3 py-1.5 text-xs rounded transition-colors ${actorFilter === 'all' ? 'bg-background shadow-sm font-semibold' : 'text-muted-foreground'}`}
            >
              All Events
            </button>
            <button 
              onClick={() => setActorFilter('system')}
              className={`px-3 py-1.5 text-xs rounded transition-colors flex items-center gap-1.5 ${actorFilter === 'system' ? 'bg-background shadow-sm font-semibold' : 'text-muted-foreground'}`}
            >
              <Bot className="w-3.5 h-3.5" /> System
            </button>
            <button 
              onClick={() => setActorFilter('ba')}
              className={`px-3 py-1.5 text-xs rounded transition-colors flex items-center gap-1.5 ${actorFilter === 'ba' ? 'bg-background shadow-sm font-semibold' : 'text-muted-foreground'}`}
            >
              <User className="w-3.5 h-3.5" /> BA / Manual
            </button>
          </div>
        </div>
      </div>

      <div className="max-w-5xl mx-auto w-full relative">
        {/* Timeline line */}
        <div className="absolute left-[88px] top-0 bottom-0 w-px bg-border z-0" />
        
        <div className="space-y-6 relative z-10">
          {filteredHistory.map((event) => (
            <HistoryEventCard key={event.id} event={event} />
          ))}
          
          {filteredHistory.length === 0 && (
            <div className="py-12 text-center text-muted-foreground">
              No events found for this filter.
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

function HistoryEventCard({ event }: { event: ProjectHistoryEvent }) {
  const [isExpanded, setIsExpanded] = useState(false);
  const timeStr = new Date(event.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
  const dateStr = new Date(event.timestamp).toLocaleDateString([], { month: 'short', day: 'numeric' });

  return (
    <div className="flex group">
      {/* Timestamp */}
      <div className="w-[80px] shrink-0 pt-3 pr-4 text-right">
        <div className="text-xs font-bold text-foreground">{timeStr}</div>
        <div className="text-[10px] text-muted-foreground">{dateStr}</div>
      </div>
      
      {/* Node */}
      <div className="w-[17px] flex justify-center shrink-0 pt-3.5">
        <div className={`w-3 h-3 rounded-full border-2 bg-background ${event.actorType === 'system' ? 'border-primary' : 'border-purple-500'}`} />
      </div>
      
      {/* Content Card */}
      <div className="flex-1 pl-4 pb-2">
        <div className="bg-card border border-border rounded-lg p-3 shadow-sm group-hover:border-primary/30 transition-colors">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between mb-1.5 gap-2">
            <div className="flex items-center gap-2">
              <span className={`text-[10px] px-2 py-0.5 rounded font-bold uppercase tracking-wider flex items-center gap-1 ${
                event.actorType === 'system' ? 'bg-primary/10 text-primary' : 'bg-purple-500/10 text-purple-600'
              }`}>
                {event.actorType === 'system' ? <Bot className="w-3 h-3" /> : <User className="w-3.5 h-3.5" />}
                {event.actor}
              </span>
              <span className="text-[11px] font-semibold text-foreground bg-muted px-2 py-0.5 rounded border border-border">
                {event.target}
              </span>
            </div>
          </div>
          <p className="text-[13px] text-muted-foreground leading-relaxed">
            {event.summary}
          </p>

          {/* Optional Telemetry */}
          {event.telemetry && Object.keys(event.telemetry).length > 0 && (
            <div className="mt-3 border-t border-border/50 pt-2">
              <button 
                onClick={() => setIsExpanded(!isExpanded)}
                className="flex items-center gap-1 text-[10px] font-bold text-muted-foreground hover:text-primary transition-colors focus:outline-none uppercase tracking-wider"
              >
                {isExpanded ? <ChevronUp className="w-3 h-3" /> : <ChevronDown className="w-3 h-3" />}
                <span>Advanced Details</span>
              </button>
              
              {isExpanded && (
                <div className="mt-2 bg-muted/30 border border-border rounded p-3 text-[11px] font-mono text-muted-foreground space-y-1 select-text">
                  {Object.entries(event.telemetry).map(([key, val]) => (
                    <div key={key} className="flex justify-between flex-wrap gap-2 border-b border-border/20 py-1 last:border-0">
                      <span className="font-semibold text-foreground">{key}:</span>
                      <span className="text-right max-w-xs truncate">{typeof val === 'object' ? JSON.stringify(val) : String(val)}</span>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
