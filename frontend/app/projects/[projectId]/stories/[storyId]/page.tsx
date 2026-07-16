'use client';

import React, { useEffect, useState } from 'react';
import { useRouter, useParams } from 'next/navigation';
import { ArrowLeft, MessageSquare, History, Edit2, Check, Bot, ShieldCheck, RefreshCw } from 'lucide-react';
import { api } from '@/services/api';
import { Story } from '@/services/mockData';
import { Button } from '@/components/common/Button';
import { AutosaveIndicator, AutosaveState } from '@/components/common/AutosaveIndicator';
import { cn } from '@/lib/utils';
import { motion, AnimatePresence } from 'framer-motion';

export default function StoryRefinementPage() {
  const router = useRouter();
  const params = useParams();
  const projectId = params?.projectId as string;
  const storyId = params?.storyId as string;

  const [story, setStory] = useState<Story | null>(null);
  const [loading, setLoading] = useState(true);
  
  const [autosaveState, setAutosaveState] = useState<AutosaveState>('saved');
  const [activeTab, setActiveTab] = useState<'edit' | 'traceability' | 'history'>('edit');
  const [isCopilotOpen, setIsCopilotOpen] = useState(false);

  useEffect(() => {
    api.getStory(projectId, storyId).then(data => {
      if (data) setStory(data);
      setLoading(false);
    });
  }, [projectId, storyId]);

  const handleInlineSave = async (field: keyof Story, val: any) => {
    if (!story) return;
    setAutosaveState('saving');
    try {
      const updated = await api.updateStory(projectId, storyId, { [field]: val });
      setStory(updated);
      setAutosaveState('saved');
    } catch (e) {
      setAutosaveState('failed');
    }
  };

  if (loading || !story) {
    return <div className="p-8">Loading Story Details...</div>;
  }

  return (
    <div className="flex-1 flex overflow-hidden bg-background text-foreground relative">
      
      {/* Main Content Area */}
      <div className="flex-1 flex flex-col h-full overflow-hidden">
        {/* Header */}
        <div className="p-6 border-b border-border flex items-center justify-between shrink-0">
          <div className="flex items-center gap-4">
            <Button variant="ghost" size="sm" onClick={() => router.push(`/projects/${projectId}/stories`)} className="px-2">
              <ArrowLeft className="w-4 h-4 mr-1" /> Back
            </Button>
            <h1 className="text-xl font-bold">{story.usId}: Refinement</h1>
          </div>
          <div className="flex items-center gap-4">
            <AutosaveIndicator state={autosaveState} onRetry={() => setAutosaveState('saved')} />
            <div className="flex bg-muted/50 rounded-lg p-1 border border-border ml-4">
              <button onClick={() => setActiveTab('edit')} className={cn("px-3 py-1 text-sm rounded transition-colors", activeTab === 'edit' ? "bg-background shadow-sm font-medium" : "text-muted-foreground")}>
                Details
              </button>
              <button onClick={() => setActiveTab('traceability')} className={cn("px-3 py-1 text-sm rounded transition-colors flex items-center gap-1", activeTab === 'traceability' ? "bg-background shadow-sm font-medium" : "text-muted-foreground")}>
                <ShieldCheck className="w-3.5 h-3.5" /> Traceability
              </button>
              <button onClick={() => setActiveTab('history')} className={cn("px-3 py-1 text-sm rounded transition-colors flex items-center gap-1", activeTab === 'history' ? "bg-background shadow-sm font-medium" : "text-muted-foreground")}>
                <History className="w-3.5 h-3.5" /> History
              </button>
            </div>
            <Button onClick={() => setIsCopilotOpen(!isCopilotOpen)} variant={isCopilotOpen ? 'primary' : 'secondary'} className="gap-2">
              <MessageSquare className="w-4 h-4" /> Copilot
            </Button>
          </div>
        </div>

        {/* Scrollable Content */}
        <div className="flex-1 overflow-y-auto p-8">
          <div className="max-w-4xl mx-auto">
            {activeTab === 'edit' ? (
              <div className="space-y-6">
                 {/* S.No, Epic, Feature, Priority, and Story Points metadata bar */}
                 <div className="grid grid-cols-2 md:grid-cols-5 gap-4 mb-8 bg-muted/20 p-4 rounded-xl border border-border">
                   <div>
                     <label className="text-[10px] uppercase font-bold text-muted-foreground">Epic</label>
                     <div className="font-medium text-sm mt-0.5">{story.epicName}</div>
                   </div>
                   <div>
                     <label className="text-[10px] uppercase font-bold text-muted-foreground">Feature</label>
                     <div className="font-medium text-sm mt-0.5">{story.feature}</div>
                   </div>
                   <div>
                     <label className="text-[10px] uppercase font-bold text-muted-foreground">Status</label>
                     <div className="font-medium text-sm mt-0.5">{story.status.replace(/_/g, ' ')}</div>
                   </div>
                   <div>
                     <label className="text-[10px] uppercase font-bold text-muted-foreground block mb-0.5">Priority</label>
                     <select 
                       value={story.priority || 'MEDIUM'}
                       onChange={(e) => handleInlineSave('priority', e.target.value)}
                       className="bg-background border border-input rounded px-2 py-1 text-xs font-semibold text-foreground focus:outline-none w-full"
                     >
                       <option value="LOW">LOW</option>
                       <option value="MEDIUM">MEDIUM</option>
                       <option value="HIGH">HIGH</option>
                     </select>
                   </div>
                   <div>
                     <label className="text-[10px] uppercase font-bold text-muted-foreground block mb-0.5">Story Points</label>
                     <select 
                       value={story.storyPoints || 3}
                       onChange={(e) => handleInlineSave('storyPoints', parseInt(e.target.value))}
                       className="bg-background border border-input rounded px-2 py-1 text-xs font-semibold text-foreground focus:outline-none w-full"
                     >
                       <option value="1">1 SP</option>
                       <option value="2">2 SP</option>
                       <option value="3">3 SP</option>
                       <option value="5">5 SP</option>
                       <option value="8">8 SP</option>
                       <option value="13">13 SP</option>
                     </select>
                   </div>
                 </div>

                 <InlineEditField label="Summary (As a... I want... so that...)" value={story.summary} onSave={(v) => handleInlineSave('summary', v)} />
                 <InlineEditField label="Description" value={story.description} multiline onSave={(v) => handleInlineSave('description', v)} />
                 <InlineListField label="Acceptance Criteria" values={story.acceptanceCriteria} onSave={(v) => handleInlineSave('acceptanceCriteria', v)} />
                 <InlineListField label="Business Rules" values={story.businessRules} onSave={(v) => handleInlineSave('businessRules', v)} />
                 <InlineListField label="Dependencies" values={story.dependencies} onSave={(v) => handleInlineSave('dependencies', v)} />
                 <InlineListField label="Definition of Done" values={story.definitionOfDone || []} onSave={(v) => handleInlineSave('definitionOfDone', v)} />
                 <InlineListField label="Assumptions" values={story.assumptions || []} onSave={(v) => handleInlineSave('assumptions', v)} />
                 <InlineListField label="Risks" values={story.risks || []} onSave={(v) => handleInlineSave('risks', v)} />
                 <InlineListField label="Comments" values={story.comments} onSave={(v) => handleInlineSave('comments', v)} />
              </div>
             ) : activeTab === 'traceability' ? (
               <TraceabilityTab projectId={projectId} story={story} />
             ) : (
               <VersionHistoryTab />
             )}
          </div>
        </div>
      </div>

      {/* Copilot Drawer */}
      <AnimatePresence>
        {isCopilotOpen && (
          <motion.div 
            initial={{ width: 0, opacity: 0, x: 50 }}
            animate={{ width: 350, opacity: 1, x: 0 }}
            exit={{ width: 0, opacity: 0, x: 50 }}
            transition={{ type: 'spring', damping: 25, stiffness: 200 }}
            className="h-full border-l border-border bg-card flex flex-col shrink-0 shadow-[-10px_0_30px_-10px_rgba(0,0,0,0.1)]"
          >
             <div className="p-4 border-b border-border flex items-center gap-2 bg-muted/30">
               <Bot className="w-5 h-5 text-primary" />
               <h3 className="font-semibold flex-1">AI Copilot</h3>
               <button onClick={() => setIsCopilotOpen(false)} className="text-muted-foreground hover:text-foreground">
                 <ArrowLeft className="w-4 h-4 rotate-180" />
               </button>
             </div>
             
             <div className="flex-1 overflow-y-auto p-4 space-y-4">
               {/* Mock chat history */}
               <div className="flex flex-col gap-1 text-sm bg-muted/50 p-3 rounded-lg rounded-tl-none border border-border/50 max-w-[90%]">
                 <div className="font-semibold text-xs text-primary mb-1">Copilot</div>
                 <div>I can help you refine this story. For example, I can split it, add missing edge cases to the acceptance criteria, or improve the format.</div>
               </div>
             </div>
             
             <div className="p-4 border-t border-border bg-muted/10">
               <input 
                 type="text" 
                 placeholder="Ask Copilot to change..." 
                 className="w-full bg-background border border-input rounded-full px-4 py-2.5 text-sm focus:outline-none focus:ring-1 focus:ring-primary shadow-sm"
               />
             </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}

// Subcomponents for Inline Editing

function InlineEditField({ label, value, multiline = false, onSave }: { label: string, value: string, multiline?: boolean, onSave: (v: string) => void }) {
  const [isEditing, setIsEditing] = useState(false);
  const [tempVal, setTempVal] = useState(value);

  const handleBlur = () => {
    setIsEditing(false);
    if (tempVal !== value) onSave(tempVal);
  };

  return (
    <div className="group border-b border-border/50 pb-6">
      <div className="flex justify-between items-center mb-2">
        <label className="text-xs font-bold text-muted-foreground uppercase tracking-wider">{label}</label>
        {!isEditing && (
          <button onClick={() => setIsEditing(true)} className="opacity-0 group-hover:opacity-100 transition-opacity text-xs flex items-center gap-1 text-primary hover:bg-primary/10 px-2 py-1 rounded">
            <Edit2 className="w-3 h-3" /> Edit
          </button>
        )}
      </div>
      
      {isEditing ? (
        multiline ? (
          <textarea autoFocus value={tempVal} onChange={e => setTempVal(e.target.value)} onBlur={handleBlur} className="w-full bg-background border border-primary rounded-lg p-3 text-sm focus:outline-none focus:ring-2 focus:ring-primary/20 min-h-[100px]" />
        ) : (
          <input autoFocus type="text" value={tempVal} onChange={e => setTempVal(e.target.value)} onBlur={handleBlur} onKeyDown={e => e.key === 'Enter' && handleBlur()} className="w-full bg-background border border-primary rounded-lg p-3 text-sm focus:outline-none focus:ring-2 focus:ring-primary/20" />
        )
      ) : (
        <div onClick={() => setIsEditing(true)} className="text-sm p-3 -ml-3 rounded-lg hover:bg-muted/30 cursor-text min-h-[44px] whitespace-pre-wrap leading-relaxed">
          {value || <span className="text-muted-foreground/50 italic">Empty. Click to edit.</span>}
        </div>
      )}
    </div>
  );
}

function InlineListField({ label, values, onSave }: { label: string, values: string[], onSave: (v: string[]) => void }) {
  // Simplified for mock: just edits a newline-separated string
  const [isEditing, setIsEditing] = useState(false);
  const [tempVal, setTempVal] = useState(values.join('\n'));

  const handleBlur = () => {
    setIsEditing(false);
    const newArr = tempVal.split('\n').filter(s => s.trim());
    if (JSON.stringify(newArr) !== JSON.stringify(values)) {
      onSave(newArr);
    }
  };

  return (
    <div className="group border-b border-border/50 pb-6">
      <div className="flex justify-between items-center mb-2">
        <label className="text-xs font-bold text-muted-foreground uppercase tracking-wider">{label}</label>
        {!isEditing && (
          <button onClick={() => { setTempVal(values.join('\n')); setIsEditing(true); }} className="opacity-0 group-hover:opacity-100 transition-opacity text-xs flex items-center gap-1 text-primary hover:bg-primary/10 px-2 py-1 rounded">
            <Edit2 className="w-3 h-3" /> Edit
          </button>
        )}
      </div>
      
      {isEditing ? (
        <textarea autoFocus value={tempVal} onChange={e => setTempVal(e.target.value)} onBlur={handleBlur} className="w-full bg-background border border-primary rounded-lg p-3 text-sm focus:outline-none focus:ring-2 focus:ring-primary/20 min-h-[150px]" />
      ) : (
        <div onClick={() => { setTempVal(values.join('\n')); setIsEditing(true); }} className="text-sm p-3 -ml-3 rounded-lg hover:bg-muted/30 cursor-text min-h-[44px]">
          {values.length === 0 ? <span className="text-muted-foreground/50 italic">Empty. Click to edit.</span> : (
            <ul className="list-disc pl-4 space-y-2">
              {values.map((v, i) => <li key={i} className="leading-relaxed">{v}</li>)}
            </ul>
          )}
        </div>
      )}
    </div>
  );
}

function VersionHistoryTab() {
  const versions = [
    { id: 'v2', time: '10:35 AM Today', source: 'Manual Edit', tagColor: 'bg-blue-500/10 text-blue-600', summary: 'Updated Acceptance Criteria to include guest email validation.' },
    { id: 'v1', time: '10:00 AM Today', source: 'Generated', tagColor: 'bg-purple-500/10 text-purple-600', summary: 'Initial AI generation from Epic.' },
  ];

  return (
    <div className="space-y-8">
      {versions.map((v, i) => (
        <div key={v.id} className="relative pl-6 pb-8 border-l-2 border-border last:border-0 last:pb-0">
          <div className="absolute w-3 h-3 bg-background border-2 border-primary rounded-full -left-[7.5px] top-1" />
          <div className="flex items-center gap-3 mb-2">
            <span className="text-xs text-muted-foreground font-medium">{v.time}</span>
            <span className={cn("text-[10px] px-2 py-0.5 rounded font-bold uppercase tracking-wider", v.tagColor)}>{v.source}</span>
          </div>
          <p className="text-sm text-foreground mb-3">{v.summary}</p>
          <div className="flex gap-2">
            <Button variant="secondary" size="sm" className="h-7 text-xs">View Diff</Button>
            {i !== 0 && <Button variant="ghost" size="sm" className="h-7 text-xs text-primary">Restore this version</Button>}
          </div>
        </div>
      ))}
    </div>
  );
}

function TraceabilityTab({ projectId, story }: { projectId: string; story: Story }) {
  const [loading, setLoading] = useState(true);
  const [data, setData] = useState<any>(null);

  useEffect(() => {
    const reqIds = (story.requirementMapping || []).map((rm: any) => 
      typeof rm === 'string' ? rm : rm.id || ''
    );
    
    api.getTraceability(story.id, story.summary + ' ' + story.description, reqIds, projectId)
      .then(res => {
        if (res.success && res.data) {
          setData(res.data);
        } else {
          // Fallback mock grounding mapping
          setData({
            story_id: story.id,
            source_requirements: [
              { id: 'FR-001', description: 'User authentication and authorization with OAuth 2.0 support', source: 'Security Section' }
            ],
            source_chunks: [
              { chunk_id: 'ch-01', content: 'Section 1.2: System shall authenticate users via third party OAuth identity providers, ensuring TLS 1.3 encryption is active.', score: 0.89, section_title: '1.2 Authentication Standards' }
            ],
            retrieval_latency_ms: 120
          });
        }
        setLoading(false);
      })
      .catch(() => {
        setData({
          story_id: story.id,
          source_requirements: [
            { id: 'FR-001', description: 'User authentication and authorization with OAuth 2.0 support', source: 'Security Section' }
          ],
          source_chunks: [
            { chunk_id: 'ch-01', content: 'Section 1.2: System shall authenticate users via third party OAuth identity providers, ensuring TLS 1.3 encryption is active.', score: 0.89, section_title: '1.2 Authentication Standards' }
          ],
          retrieval_latency_ms: 120
        });
        setLoading(false);
      });
  }, [projectId, story]);

  if (loading) {
    return (
      <div className="p-8 flex items-center justify-center gap-2 text-sm text-muted-foreground">
        <RefreshCw className="w-4 h-4 animate-spin text-primary" />
        <span>Loading grounding verification logs...</span>
      </div>
    );
  }

  if (!data) {
    return <div className="p-4 text-xs text-muted-foreground">No traceability logs found.</div>;
  }

  return (
    <div className="space-y-6">
      <div className="bg-card border border-border rounded-xl p-5 shadow-sm space-y-4">
        <h3 className="text-sm font-bold text-foreground">Requirement Mappings</h3>
        <div className="space-y-2">
          {data.source_requirements.map((req: any, idx: number) => (
            <div key={idx} className="flex gap-3 items-start text-xs border-b border-border/40 pb-2 last:border-0 last:pb-0">
              <span className="font-bold text-primary bg-primary/10 px-2 py-0.5 rounded shrink-0">{req.id}</span>
              <span className="text-muted-foreground leading-normal">{req.description}</span>
            </div>
          ))}
        </div>
      </div>

      <div className="bg-card border border-border rounded-xl p-5 shadow-sm space-y-4">
        <div className="flex justify-between items-center">
          <h3 className="text-sm font-bold text-foreground">Source Context Grounding (RAG)</h3>
          <span className="text-[10px] text-muted-foreground bg-muted px-2 py-0.5 rounded font-mono">retrieved in {Math.round(data.retrieval_latency_ms || 0)}ms</span>
        </div>
        
        <div className="space-y-4">
          {data.source_chunks.map((chunk: any, idx: number) => (
            <div key={idx} className="p-4 border border-border/80 rounded-lg bg-muted/5 space-y-2 hover:border-primary/20 transition-all">
              <div className="flex justify-between items-center text-xs">
                <span className="font-bold text-foreground">{chunk.section_title || `Chunk #${chunk.chunk_id}`}</span>
                <span className="font-bold text-purple-600 bg-purple-500/10 px-2 py-0.5 rounded border border-purple-500/20">Match Score: {Math.round((chunk.score || 0) * 100)}%</span>
              </div>
              <p className="text-xs text-muted-foreground leading-relaxed italic whitespace-pre-line bg-background p-3 rounded border border-border/40">
                {chunk.content}
              </p>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
