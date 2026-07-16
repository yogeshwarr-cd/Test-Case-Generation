'use client';

import React, { useRef, useState, useEffect } from 'react';
import { useRouter, useParams } from 'next/navigation';
import { 
  Upload, FileText, ChevronDown, ChevronUp, Sparkles, Database, 
  Cloud, AlertCircle, CheckCircle2, Trash2, Eye, RefreshCw, 
  Globe, Server, ArrowLeft, ArrowRight, EyeOff, Check, X,
  FileSpreadsheet, FileArchive, Loader2, ArrowRightCircle
} from 'lucide-react';
import { Button } from '@/components/common/Button';
import { Badge } from '@/components/common/Badge';

interface ImportedDoc {
  id: string;
  source: 'Local' | 'Google Drive' | 'SharePoint' | 'Jira' | 'Confluence';
  name: string;
  size: string;
  time: string;
  status: 'Imported' | 'Validated' | 'Ready';
}

interface TimelineStep {
  id: string;
  label: string;
  status: 'Completed' | 'Running' | 'Waiting' | 'Failed';
  time?: string;
}

const initialTimelineSteps: Omit<TimelineStep, 'status'>[] = [
  { id: '1', label: 'Document Uploaded Successfully' },
  { id: '2', label: 'File Validation Completed' },
  { id: '3', label: 'Reading Document' },
  { id: '4', label: 'Extracting Text' },
  { id: '5', label: 'Identifying Requirement Sections' },
  { id: '6', label: 'Functional Requirements Extracted' },
  { id: '7', label: 'Business Rules Extracted' },
  { id: '8', label: 'Non-functional Requirements Extracted' },
  { id: '9', label: 'Removing Duplicate Content' },
  { id: '10', label: 'Structuring Requirements' },
  { id: '11', label: 'Content Validation Completed' },
  { id: '12', label: 'Requirements Ready for AI Processing' },
];

export default function IntakePage() {
  const router = useRouter();
  const params = useParams();
  const projectId = params?.projectId as string;
  
  const fileInputRef = useRef<HTMLInputElement>(null);
  const timelineEndRef = useRef<HTMLDivElement>(null);
  
  const [dragActive, setDragActive] = useState(false);
  const [selectedSource, setSelectedSource] = useState<'Local' | 'Google Drive' | 'SharePoint' | 'Jira' | 'Confluence' | null>(null);
  const [carouselStopped, setCarouselStopped] = useState(false);

  // Loaded animation
  const [isLoaded, setIsLoaded] = useState(false);
  useEffect(() => {
    setIsLoaded(true);
  }, []);

  // Imported Documents List
  const [documents, setDocuments] = useState<ImportedDoc[]>([]);

  // Timeline States
  const [timelineSteps, setTimelineSteps] = useState<TimelineStep[]>(
    initialTimelineSteps.map(s => ({ ...s, status: 'Waiting' }))
  );
  const [isProcessing, setIsProcessing] = useState(false);
  const [overallProgress, setOverallProgress] = useState(0);

  // Dynamic Panel inputs state
  const [gdriveLink, setGdriveLink] = useState('');
  const [gdriveState, setGdriveState] = useState<'idle' | 'loading' | 'success'>('idle');
  const [sharepointLink, setSharepointLink] = useState('');
  const [sharepointState, setSharepointState] = useState<'idle' | 'loading' | 'success'>('idle');
  
  const [jiraUrl, setJiraUrl] = useState('');
  const [jiraEmail, setJiraEmail] = useState('');
  const [jiraToken, setJiraToken] = useState('');
  const [showJiraToken, setShowJiraToken] = useState(false);
  const [jiraProject, setJiraProject] = useState('');
  const [jiraState, setJiraState] = useState<'idle' | 'connecting' | 'success'>('idle');
  const [selectedJiraProject, setSelectedJiraProject] = useState('');
  const [selectedJiraIssue, setSelectedJiraIssue] = useState('');

  const [confluenceUrl, setConfluenceUrl] = useState('');
  const [confluenceEmail, setConfluenceEmail] = useState('');
  const [confluenceToken, setConfluenceToken] = useState('');
  const [showConfluenceToken, setShowConfluenceToken] = useState(false);
  const [confluenceSpace, setConfluenceSpace] = useState('');
  const [confluenceState, setConfluenceState] = useState<'idle' | 'connecting' | 'success'>('idle');

  // Preview modals
  const [activePreviewDoc, setActivePreviewDoc] = useState<ImportedDoc | null>(null);
  const [toast, setToast] = useState<{ message: string; type: 'success' | 'error' } | null>(null);

  const [showValidationDialog, setShowValidationDialog] = useState(false);
  const [pendingDocName, setPendingDocName] = useState('');
  const [validationMode, setValidationMode] = useState<'step-by-step' | 'final-review' | null>(null);

  const promptValidationMode = (name: string) => {
    setPendingDocName(name);
    setShowValidationDialog(true);
  };

  const showToast = (message: string, type: 'success' | 'error' = 'success') => {
    setToast({ message, type });
    setTimeout(() => setToast(null), 3000);
  };

  // Scroll timeline container to bottom when steps activate
  useEffect(() => {
    if (isProcessing) {
      timelineEndRef.current?.scrollIntoView({ behavior: 'smooth' });
    }
  }, [timelineSteps, isProcessing]);

  // Trigger processing simulation
  const startProcessingPipeline = (docName: string) => {
    setIsProcessing(true);
    setOverallProgress(0);
    setTimelineSteps(initialTimelineSteps.map(s => ({ ...s, status: 'Waiting' })));

    let currentStepIdx = 0;
    const interval = setInterval(() => {
      setTimelineSteps(prev => {
        const nextSteps = prev.map(step => ({ ...step }));
        // Mark previous steps as completed safely
        for (let i = 0; i < Math.min(currentStepIdx, nextSteps.length); i++) {
          nextSteps[i].status = 'Completed';
          if (!nextSteps[i].time || nextSteps[i].time === 'Processing...') {
            nextSteps[i].time = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' });
          }
        }
        // Mark current as running
        if (currentStepIdx < nextSteps.length) {
          nextSteps[currentStepIdx].status = 'Running';
          nextSteps[currentStepIdx].time = 'Processing...';
        }
        return nextSteps;
      });

      const progressVal = Math.round(((currentStepIdx + 1) / initialTimelineSteps.length) * 100);
      setOverallProgress(Math.min(progressVal, 100));

      currentStepIdx++;
      if (currentStepIdx > initialTimelineSteps.length) {
        clearInterval(interval);
        setTimelineSteps(prev => prev.map(s => ({ ...s, status: 'Completed', time: s.time || new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) })));
        setOverallProgress(100);
        setIsProcessing(false);
        showToast(`AI Pipeline analysis finished for ${docName}`);
      }
    }, 1800);
  };

  const uploadLocalFile = (file: File) => {
    const name = file.name;
    const size = (file.size / (1024 * 1024)).toFixed(1) + ' MB';
    const newDoc: ImportedDoc = {
      id: `doc-${Date.now()}`,
      source: 'Local',
      name,
      size,
      time: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
      status: 'Ready'
    };
    setDocuments(prev => [newDoc, ...prev]);
    showToast(`Successfully uploaded ${name}`);
    promptValidationMode(name);
  };

  const handleDrag = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    if (e.type === "dragenter" || e.type === "dragover") {
      setDragActive(true);
    } else if (e.type === "dragleave") {
      setDragActive(false);
    }
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setDragActive(false);

    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      uploadLocalFile(e.dataTransfer.files[0]);
    }
  };

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      uploadLocalFile(e.target.files[0]);
    }
  };

  const selectSource = (source: 'Local' | 'Google Drive' | 'SharePoint' | 'Jira' | 'Confluence') => {
    setSelectedSource(source);
    setCarouselStopped(true);
    showToast(`Selected source: ${source}`);
  };

  // Google Drive Sim
  const handleGdriveImport = (e: React.FormEvent) => {
    e.preventDefault();
    if (!gdriveLink.trim()) return;
    setGdriveState('loading');
    setTimeout(() => {
      setGdriveState('success');
      const newDoc: ImportedDoc = {
        id: `gdrive-${Date.now()}`,
        source: 'Google Drive',
        name: 'Shared Drive Document.docx',
        size: '1.2 MB',
        time: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
        status: 'Validated'
      };
      setDocuments(prev => [newDoc, ...prev]);
      showToast("Imported from Google Drive successfully");
      promptValidationMode('Shared Drive Document.docx');
    }, 1500);
  };

  // SharePoint Sim
  const handleSharepointImport = (e: React.FormEvent) => {
    e.preventDefault();
    if (!sharepointLink.trim()) return;
    setSharepointState('loading');
    setTimeout(() => {
      setSharepointState('success');
      const newDoc: ImportedDoc = {
        id: `sp-${Date.now()}`,
        source: 'SharePoint',
        name: 'SharePoint Requirements Guide.pdf',
        size: '4.7 MB',
        time: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
        status: 'Validated'
      };
      setDocuments(prev => [newDoc, ...prev]);
      showToast("Imported from SharePoint successfully");
      promptValidationMode('SharePoint Requirements Guide.pdf');
    }, 1500);
  };

  // Jira Sim
  const handleJiraConnect = (e: React.FormEvent) => {
    e.preventDefault();
    setJiraState('connecting');
    setTimeout(() => {
      setJiraState('success');
      showToast("Successfully connected to Jira Cloud");
    }, 1500);
  };

  const handleJiraImport = () => {
    const newDoc: ImportedDoc = {
      id: `jira-${Date.now()}`,
      source: 'Jira',
      name: `${selectedJiraProject || 'JIRA'}: ${selectedJiraIssue || 'All Epics'}`,
      size: '28 Issues',
      time: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
      status: 'Ready'
    };
    setDocuments(prev => [newDoc, ...prev]);
    showToast("Imported issues from Jira");
    promptValidationMode(`${selectedJiraProject || 'JIRA'} Issue Queue`);
  };

  // Confluence Sim
  const handleConfluenceConnect = (e: React.FormEvent) => {
    e.preventDefault();
    setConfluenceState('connecting');
    setTimeout(() => {
      setConfluenceState('success');
      showToast("Successfully connected to Confluence Space");
    }, 1500);
  };

  const handleConfluenceImport = () => {
    const newDoc: ImportedDoc = {
      id: `conf-${Date.now()}`,
      source: 'Confluence',
      name: `Space: ${confluenceSpace || 'PRODUCT'} - Requirements Page`,
      size: '14 KB',
      time: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
      status: 'Ready'
    };
    setDocuments(prev => [newDoc, ...prev]);
    showToast("Imported page content from Confluence");
    promptValidationMode(`Confluence Space ${confluenceSpace || 'PRODUCT'}`);
  };

  const carouselItems: { id: 'Local' | 'Google Drive' | 'SharePoint' | 'Jira' | 'Confluence'; icon: string; title: string; desc: string; status: string }[] = [
    { id: 'Local', icon: '📄', title: 'Local Upload', desc: 'Upload PDF, DOC, DOCX, XLS and XLSX files directly.', status: 'Connected' },
    { id: 'Google Drive', icon: '☁', title: 'Google Drive', desc: 'Import documents using a Google Drive shared link.', status: 'Not Connected' },
    { id: 'SharePoint', icon: '🏢', title: 'Microsoft SharePoint', desc: 'Import documents using a SharePoint link.', status: 'Not Connected' },
    { id: 'Jira', icon: '🟦', title: 'Jira Cloud', desc: 'Import requirements directly from Jira issues.', status: 'Not Connected' },
    { id: 'Confluence', icon: '📘', title: 'Confluence', desc: 'Import Business Requirement Documents.', status: 'Not Connected' },
  ];

  // Duplicate items array to make seamless infinite loop slider
  const doubleCarouselItems = [...carouselItems, ...carouselItems];

  return (
    <div className="flex-1 flex flex-col min-h-screen bg-slate-50/50 pb-24 select-none relative font-sans">
      
      {/* Toast Notification */}
      {toast && (
        <div className="fixed bottom-28 right-8 z-50 bg-slate-900 text-white text-xs px-4 py-3 rounded-lg shadow-xl flex items-center gap-2 border border-slate-800 transition-all transform animate-bounce">
          <CheckCircle2 className="w-4 h-4 text-emerald-400" />
          <span>{toast.message}</span>
        </div>
      )}

      {/* Header Area */}
      <div 
        className={`px-8 pt-8 pb-6 border-b border-slate-200 bg-white transition-all duration-700 transform ${
          isLoaded ? 'translate-y-0 opacity-100' : '-translate-y-4 opacity-0'
        }`}
      >
        <div className="flex flex-col gap-2 max-w-7xl mx-auto">
          <h1 className="text-3xl font-extrabold tracking-tight text-slate-900">Requirements Intake</h1>
          <p className="text-sm text-slate-500 max-w-3xl leading-relaxed">
            Import business requirements from local files, cloud storage or enterprise tools before AI generation begins.
          </p>
        </div>
      </div>

      {/* Main Content Body */}
      <div className="flex-1 px-8 py-8 space-y-8 max-w-7xl mx-auto w-full">
        
        {/* Choose Source Section - Carousel Logo Slider */}
        <div className="space-y-4 overflow-hidden relative">
          <div className="flex items-center justify-between">
            <h2 className="text-xs font-bold uppercase tracking-wider text-slate-400">Choose Requirement Source</h2>
            {selectedSource && (
              <button 
                onClick={() => { setSelectedSource(null); setCarouselStopped(false); }}
                className="text-xs text-blue-600 hover:text-blue-800 font-semibold flex items-center gap-1.5"
              >
                <RefreshCw className="w-3 h-3" />
                Reset Carousel
              </button>
            )}
          </div>
          
          {/* Infinite Carousel Slider Wrapper */}
          <div className="relative w-full overflow-hidden py-4 px-1">
            {/* Soft left/right fade masks */}
            <div className="absolute left-0 top-0 bottom-0 w-24 bg-gradient-to-r from-slate-50/50 to-transparent pointer-events-none z-10" />
            <div className="absolute right-0 top-0 bottom-0 w-24 bg-gradient-to-l from-slate-50/50 to-transparent pointer-events-none z-10" />

            <div 
              className={`flex gap-6 w-max ${
                carouselStopped ? '' : 'animate-marquee'
              }`}
              style={{
                animationPlayState: carouselStopped ? 'paused' : undefined
              }}
            >
              {doubleCarouselItems.map((item, idx) => {
                const isSelected = selectedSource === item.id;
                return (
                  <div
                    key={`${item.id}-${idx}`}
                    onClick={() => selectSource(item.id)}
                    className={`group shrink-0 w-72 rounded-2xl p-5 border transition-all duration-300 transform select-none cursor-pointer flex flex-col justify-between h-44 ${
                      isSelected
                        ? 'bg-white border-blue-500 shadow-xl ring-2 ring-blue-500/30 scale-102'
                        : 'bg-white/80 backdrop-blur-md border-slate-200 hover:border-blue-400 hover:shadow-lg hover:scale-102'
                    }`}
                  >
                    <div>
                      <div className="flex items-center justify-between mb-3">
                        <span className="text-2xl">{item.icon}</span>
                        {isSelected ? (
                          <div className="w-5 h-5 rounded-full bg-blue-500 flex items-center justify-center text-white text-[10px] animate-scaleIn">
                            <Check className="w-3.5 h-3.5" />
                          </div>
                        ) : (
                          <span className={`text-[10px] px-2 py-0.5 rounded-full border ${
                            item.status === 'Connected' 
                              ? 'bg-emerald-50 text-emerald-700 border-emerald-200' 
                              : 'bg-slate-50 text-slate-400 border-slate-200'
                          }`}>
                            {item.status}
                          </span>
                        )}
                      </div>
                      
                      <h3 className="text-sm font-bold text-slate-900 group-hover:text-blue-600 transition-colors">{item.title}</h3>
                      <p className="text-[11px] text-slate-500 leading-relaxed mt-1 line-clamp-2">{item.desc}</p>
                    </div>

                    <div className="flex items-center justify-between pt-2">
                      <span className="text-[10px] font-bold text-blue-600 opacity-0 group-hover:opacity-100 transition-opacity">
                        Select Source
                      </span>
                      <ArrowRightCircle className="w-4 h-4 text-slate-400 group-hover:text-blue-500 transition-colors" />
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        </div>

        {/* Dynamic Import Panel */}
        {selectedSource && (
          <div className="bg-white rounded-2xl border border-slate-200 shadow-sm p-8 transition-all duration-500 animate-slideUp">
            
            {/* LOCAL UPLOAD */}
            {selectedSource === 'Local' && (
              <div className="space-y-6">
                <div 
                  onDragEnter={handleDrag}
                  onDragOver={handleDrag}
                  onDragLeave={handleDrag}
                  onDrop={handleDrop}
                  onClick={() => fileInputRef.current?.click()}
                  className={`flex flex-col items-center justify-center border-2 border-dashed rounded-xl p-12 text-center transition-all cursor-pointer min-h-[220px] ${
                    dragActive 
                      ? 'border-blue-500 bg-blue-50/20' 
                      : 'border-slate-200 hover:border-slate-400 bg-slate-50/50'
                  }`}
                >
                  <input 
                    ref={fileInputRef}
                    type="file"
                    onChange={handleFileChange}
                    accept=".pdf,.docx,.doc,.xls,.xlsx"
                    className="hidden"
                  />
                  <div className="w-12 h-12 rounded-full bg-white shadow-sm flex items-center justify-center mb-4 text-slate-400 border border-slate-100 animate-pulse">
                    <Upload className="w-6 h-6 text-slate-500" />
                  </div>
                  <h3 className="font-semibold text-sm text-slate-900 mb-1">Drag & Drop Requirement Documents</h3>
                  <p className="text-xs text-slate-400 max-w-xs leading-relaxed mb-4">
                    Supported formats: PDF, DOC, DOCX, XLS, XLSX
                  </p>
                  <Button variant="secondary" size="sm">
                    Browse Files
                  </Button>
                </div>
              </div>
            )}

            {/* GOOGLE DRIVE */}
            {selectedSource === 'Google Drive' && (
              <div className="max-w-xl mx-auto space-y-6 py-4">
                <div className="flex flex-col items-center text-center space-y-2 mb-4">
                  <div className="w-12 h-12 rounded-xl bg-amber-50 flex items-center justify-center text-amber-500 border border-amber-100">
                    <Cloud className="w-6 h-6 animate-bounce" />
                  </div>
                  <h3 className="font-semibold text-sm text-slate-900">Google Drive shared link import</h3>
                  <p className="text-xs text-slate-400 leading-relaxed">
                    Import files directly from shared Google Drive resources.
                  </p>
                </div>

                {gdriveState === 'idle' && (
                  <form onSubmit={handleGdriveImport} className="space-y-4">
                    <div className="space-y-1">
                      <label className="text-xs font-semibold text-slate-500">Google Drive Document Link</label>
                      <input 
                        type="url"
                        placeholder="https://docs.google.com/document/d/..."
                        value={gdriveLink}
                        onChange={(e) => setGdriveLink(e.target.value)}
                        className="w-full bg-slate-50 border border-slate-200 rounded-lg px-3 py-2 text-xs text-slate-900 focus:outline-none focus:ring-1 focus:ring-blue-500"
                        required
                      />
                    </div>
                    <Button type="submit" className="w-full bg-blue-600 hover:bg-blue-700 text-white font-medium text-xs">
                      Import from Drive
                    </Button>
                  </form>
                )}

                {gdriveState === 'loading' && (
                  <div className="flex flex-col items-center justify-center space-y-4 py-8">
                    <Loader2 className="w-8 h-8 text-blue-500 animate-spin" />
                    <p className="text-xs text-slate-500">Establishing cloud connection & pulling document streams...</p>
                  </div>
                )}

                {gdriveState === 'success' && (
                  <div className="bg-slate-50 rounded-xl p-6 border border-slate-200 flex flex-col items-center text-center space-y-3">
                    <div className="w-8 h-8 rounded-full bg-emerald-100 flex items-center justify-center text-emerald-600">
                      <Check className="w-4 h-4" />
                    </div>
                    <div>
                      <h4 className="text-xs font-bold text-slate-900">Connected Successfully</h4>
                      <p className="text-[11px] text-slate-500">Loaded Shared Drive Document.docx</p>
                    </div>
                    <Button variant="ghost" size="sm" onClick={() => { setGdriveState('idle'); setGdriveLink(''); }}>
                      Import Another
                    </Button>
                  </div>
                )}
              </div>
            )}

            {/* SHAREPOINT */}
            {selectedSource === 'SharePoint' && (
              <div className="max-w-xl mx-auto space-y-6 py-4">
                <div className="flex flex-col items-center text-center space-y-2 mb-4">
                  <div className="w-12 h-12 rounded-xl bg-blue-50 flex items-center justify-center text-blue-500 border border-blue-100">
                    <Server className="w-6 h-6 animate-pulse" />
                  </div>
                  <h3 className="font-semibold text-sm text-slate-900">SharePoint document link import</h3>
                  <p className="text-xs text-slate-400 leading-relaxed">
                    Import files from active SharePoint documents.
                  </p>
                </div>

                {sharepointState === 'idle' && (
                  <form onSubmit={handleSharepointImport} className="space-y-4">
                    <div className="space-y-1">
                      <label className="text-xs font-semibold text-slate-500">SharePoint Link</label>
                      <input 
                        type="url"
                        placeholder="https://company.sharepoint.com/:w:/r/..."
                        value={sharepointLink}
                        onChange={(e) => setSharepointLink(e.target.value)}
                        className="w-full bg-slate-50 border border-slate-200 rounded-lg px-3 py-2 text-xs text-slate-900 focus:outline-none focus:ring-1 focus:ring-blue-500"
                        required
                      />
                    </div>
                    <Button type="submit" className="w-full bg-blue-600 hover:bg-blue-700 text-white font-medium text-xs">
                      Import from SharePoint
                    </Button>
                  </form>
                )}

                {sharepointState === 'loading' && (
                  <div className="flex flex-col items-center justify-center space-y-4 py-8">
                    <Loader2 className="w-8 h-8 text-blue-500 animate-spin" />
                    <p className="text-xs text-slate-500">Connecting to enterprise nodes & downloading documents...</p>
                  </div>
                )}

                {sharepointState === 'success' && (
                  <div className="bg-slate-50 rounded-xl p-6 border border-slate-200 flex flex-col items-center text-center space-y-3">
                    <div className="w-8 h-8 rounded-full bg-emerald-100 flex items-center justify-center text-emerald-600">
                      <Check className="w-4 h-4" />
                    </div>
                    <div>
                      <h4 className="text-xs font-bold text-slate-900">Connected Successfully</h4>
                      <p className="text-[11px] text-slate-500">Loaded SharePoint Requirements Guide.pdf</p>
                    </div>
                    <Button variant="ghost" size="sm" onClick={() => { setSharepointState('idle'); setSharepointLink(''); }}>
                      Import Another
                    </Button>
                  </div>
                )}
              </div>
            )}

            {/* JIRA */}
            {selectedSource === 'Jira' && (
              <div className="max-w-xl mx-auto space-y-6 py-4">
                {jiraState === 'idle' && (
                  <form onSubmit={handleJiraConnect} className="space-y-4">
                    <div className="border-b border-slate-100 pb-3">
                      <h3 className="font-bold text-sm text-slate-950">Connect Jira Cloud</h3>
                      <p className="text-[10px] text-slate-400">Import issue lists and backlog epics into parsing steps.</p>
                    </div>

                    <div className="space-y-3">
                      <div className="space-y-1">
                        <label className="text-xs font-semibold text-slate-500">Jira URL</label>
                        <input 
                          type="url"
                          placeholder="https://company.atlassian.net"
                          value={jiraUrl}
                          onChange={(e) => setJiraUrl(e.target.value)}
                          className="w-full bg-slate-50 border border-slate-200 rounded-lg px-3 py-2 text-xs text-slate-900 focus:outline-none focus:ring-1 focus:ring-blue-500"
                          required
                        />
                      </div>

                      <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                        <div className="space-y-1">
                          <label className="text-xs font-semibold text-slate-500">Email</label>
                          <input 
                            type="email"
                            placeholder="user@company.com"
                            value={jiraEmail}
                            onChange={(e) => setJiraEmail(e.target.value)}
                            className="w-full bg-slate-50 border border-slate-200 rounded-lg px-3 py-2 text-xs text-slate-900 focus:outline-none focus:ring-1 focus:ring-blue-500"
                            required
                          />
                        </div>
                        
                        <div className="space-y-1 relative">
                          <label className="text-xs font-semibold text-slate-500">API Token</label>
                          <input 
                            type={showJiraToken ? 'text' : 'password'}
                            placeholder="Jira API Token"
                            value={jiraToken}
                            onChange={(e) => setJiraToken(e.target.value)}
                            className="w-full bg-slate-50 border border-slate-200 rounded-lg px-3 py-2 pr-9 text-xs text-slate-900 focus:outline-none focus:ring-1 focus:ring-blue-500"
                            required
                          />
                          <button 
                            type="button"
                            onClick={() => setShowJiraToken(!showJiraToken)}
                            className="absolute right-2.5 bottom-2.5 text-slate-400 hover:text-slate-600"
                          >
                            {showJiraToken ? <EyeOff className="w-3.5 h-3.5" /> : <Eye className="w-3.5 h-3.5" />}
                          </button>
                        </div>
                      </div>

                      <div className="space-y-1">
                        <label className="text-xs font-semibold text-slate-500">Jira Project</label>
                        <input 
                          type="text"
                          placeholder="Project Key (e.g. SHOP)"
                          value={jiraProject}
                          onChange={(e) => setJiraProject(e.target.value)}
                          className="w-full bg-slate-50 border border-slate-200 rounded-lg px-3 py-2 text-xs text-slate-900 focus:outline-none focus:ring-1 focus:ring-blue-500"
                          required
                        />
                      </div>
                    </div>

                    <div className="flex justify-end gap-2 pt-2">
                      <Button type="button" variant="ghost" size="sm" onClick={() => setJiraState('idle')}>
                        Cancel
                      </Button>
                      <Button type="submit" size="sm" className="bg-blue-600 hover:bg-blue-700 text-white font-medium">
                        Connect
                      </Button>
                    </div>
                  </form>
                )}

                {jiraState === 'connecting' && (
                  <div className="flex flex-col items-center justify-center space-y-4 py-8">
                    <Loader2 className="w-8 h-8 text-blue-500 animate-spin" />
                    <p className="text-xs text-slate-500">Authenticating credentials & retrieving Jira projects catalog...</p>
                  </div>
                )}

                {jiraState === 'success' && (
                  <div className="space-y-4">
                    <div className="flex items-center gap-2 bg-emerald-50 text-emerald-800 text-xs p-3 rounded-lg border border-emerald-100 animate-fadeIn">
                      <CheckCircle2 className="w-4 h-4 text-emerald-600" />
                      <span>Connected Successfully to <strong>Jira Cloud</strong></span>
                    </div>

                    <div className="grid grid-cols-2 gap-4">
                      <div className="space-y-1">
                        <label className="text-xs font-semibold text-slate-500">Select Project</label>
                        <select 
                          value={selectedJiraProject} 
                          onChange={(e) => setSelectedJiraProject(e.target.value)}
                          className="w-full bg-slate-50 border border-slate-200 rounded-lg px-3 py-2 text-xs text-slate-900 focus:outline-none"
                        >
                          <option value="">Choose project...</option>
                          <option value="Checkout Flow Redesign (CFR)">Checkout Flow Redesign (CFR)</option>
                          <option value="Mobile Core API (MCA)">Mobile Core API (MCA)</option>
                        </select>
                      </div>

                      <div className="space-y-1">
                        <label className="text-xs font-semibold text-slate-500">Select Epic/Issue Filter</label>
                        <select 
                          value={selectedJiraIssue} 
                          onChange={(e) => setSelectedJiraIssue(e.target.value)}
                          className="w-full bg-slate-50 border border-slate-200 rounded-lg px-3 py-2 text-xs text-slate-900 focus:outline-none"
                        >
                          <option value="">Select epics filter...</option>
                          <option value="Epic: Checkout Optimization">Epic: Checkout Optimization</option>
                          <option value="All active backlog user stories">All active backlog user stories</option>
                        </select>
                      </div>
                    </div>

                    <div className="flex justify-between pt-2">
                      <Button variant="ghost" size="sm" onClick={() => setJiraState('idle')}>
                        Disconnect
                      </Button>
                      <Button size="sm" onClick={handleJiraImport} className="bg-blue-600 hover:bg-blue-700 text-white">
                        Import from Jira
                      </Button>
                    </div>
                  </div>
                )}
              </div>
            )}

            {/* CONFLUENCE */}
            {selectedSource === 'Confluence' && (
              <div className="max-w-xl mx-auto space-y-6 py-4">
                {confluenceState === 'idle' && (
                  <form onSubmit={handleConfluenceConnect} className="space-y-4">
                    <div className="border-b border-slate-100 pb-3">
                      <h3 className="font-bold text-sm text-slate-950">Connect Confluence Cloud</h3>
                      <p className="text-[10px] text-slate-400">Pull requirement documents and wiki templates directly.</p>
                    </div>

                    <div className="space-y-3">
                      <div className="space-y-1">
                        <label className="text-xs font-semibold text-slate-500">Confluence URL</label>
                        <input 
                          type="url"
                          placeholder="https://company.atlassian.net/wiki"
                          value={confluenceUrl}
                          onChange={(e) => setConfluenceUrl(e.target.value)}
                          className="w-full bg-slate-50 border border-slate-200 rounded-lg px-3 py-2 text-xs text-slate-900 focus:outline-none focus:ring-1 focus:ring-blue-500"
                          required
                        />
                      </div>

                      <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                        <div className="space-y-1">
                          <label className="text-xs font-semibold text-slate-500">Email</label>
                          <input 
                            type="email"
                            placeholder="user@company.com"
                            value={confluenceEmail}
                            onChange={(e) => setConfluenceEmail(e.target.value)}
                            className="w-full bg-slate-50 border border-slate-200 rounded-lg px-3 py-2 text-xs text-slate-900 focus:outline-none focus:ring-1 focus:ring-blue-500"
                            required
                          />
                        </div>
                        
                        <div className="space-y-1 relative">
                          <label className="text-xs font-semibold text-slate-500">API Token</label>
                          <input 
                            type={showConfluenceToken ? 'text' : 'password'}
                            placeholder="Confluence API Token"
                            value={confluenceToken}
                            onChange={(e) => setConfluenceToken(e.target.value)}
                            className="w-full bg-slate-50 border border-slate-200 rounded-lg px-3 py-2 pr-9 text-xs text-slate-900 focus:outline-none focus:ring-1 focus:ring-blue-500"
                            required
                          />
                          <button 
                            type="button"
                            onClick={() => setShowConfluenceToken(!showConfluenceToken)}
                            className="absolute right-2.5 bottom-2.5 text-slate-400 hover:text-slate-600"
                          >
                            {showConfluenceToken ? <EyeOff className="w-3.5 h-3.5" /> : <Eye className="w-3.5 h-3.5" />}
                          </button>
                        </div>
                      </div>

                      <div className="space-y-1">
                        <label className="text-xs font-semibold text-slate-500">Confluence Space</label>
                        <input 
                          type="text"
                          placeholder="Space Key (e.g. PROD)"
                          value={confluenceSpace}
                          onChange={(e) => setConfluenceSpace(e.target.value)}
                          className="w-full bg-slate-50 border border-slate-200 rounded-lg px-3 py-2 text-xs text-slate-900 focus:outline-none focus:ring-1 focus:ring-blue-500"
                          required
                        />
                      </div>
                    </div>

                    <div className="flex justify-end gap-2 pt-2">
                      <Button type="button" variant="ghost" size="sm" onClick={() => setConfluenceState('idle')}>
                        Cancel
                      </Button>
                      <Button type="submit" size="sm" className="bg-blue-600 hover:bg-blue-700 text-white font-medium">
                        Connect
                      </Button>
                    </div>
                  </form>
                )}

                {confluenceState === 'connecting' && (
                  <div className="flex flex-col items-center justify-center space-y-4 py-8">
                    <Loader2 className="w-8 h-8 text-blue-500 animate-spin" />
                    <p className="text-xs text-slate-500">Connecting wiki services & pulling Confluence page hierarchy...</p>
                  </div>
                )}

                {confluenceState === 'success' && (
                  <div className="space-y-4">
                    <div className="flex items-center gap-2 bg-emerald-50 text-emerald-800 text-xs p-3 rounded-lg border border-emerald-100 animate-fadeIn">
                      <CheckCircle2 className="w-4 h-4 text-emerald-600" />
                      <span>Connected Successfully to <strong>Confluence</strong></span>
                    </div>

                    <div className="bg-slate-50 rounded-lg border border-slate-200 p-4 space-y-2">
                      <h4 className="text-xs font-bold text-slate-900">Browse Space Pages</h4>
                      <p className="text-[11px] text-slate-500">Loaded 3 main requirement pages inside the space.</p>
                    </div>

                    <div className="flex justify-between pt-2">
                      <Button variant="ghost" size="sm" onClick={() => setConfluenceState('idle')}>
                        Disconnect
                      </Button>
                      <Button size="sm" onClick={handleConfluenceImport} className="bg-blue-600 hover:bg-blue-700 text-white">
                        Import Selected Pages
                      </Button>
                    </div>
                  </div>
                )}
              </div>
            )}

          </div>
        )}

        {/* AI Processing Timeline & Process Indicator (Rendered below selected source connection) */}
        {isProcessing && (
          <div className="bg-white rounded-2xl border border-slate-200 shadow-sm p-8 space-y-6 animate-slideUp">
            <div className="border-b border-slate-100 pb-4">
              <h3 className="text-sm font-bold text-slate-900">Processing Status</h3>
              <p className="text-[11px] text-slate-400 mt-0.5">Live status of the requirement import and extraction pipeline.</p>
            </div>

            {/* Overall Progress indicator */}
            <div className="space-y-2">
              <div className="flex items-center justify-between text-xs font-semibold text-slate-700">
                <span>Overall Progress</span>
                <span className="text-blue-600">{overallProgress}%</span>
              </div>
              <div className="w-full bg-slate-100 h-2.5 rounded-full overflow-hidden">
                <div 
                  className="bg-blue-500 h-full transition-all duration-300"
                  style={{ width: `${overallProgress}%` }}
                />
              </div>
            </div>

            {/* Vertical timeline steps */}
            <div className="space-y-4 max-h-[350px] overflow-y-auto pr-2 relative mt-4">
              {timelineSteps.map((step, idx) => {
                const isCompleted = step.status === 'Completed';
                const isRunning = step.status === 'Running';
                const isWaiting = step.status === 'Waiting';

                return (
                  <div key={step.id} className="flex gap-4 items-start relative select-none">
                    {/* Progress connector line */}
                    {idx < timelineSteps.length - 1 && (
                      <div 
                        className={`absolute left-3.5 top-7 bottom-0 w-0.5 -translate-x-1/2 ${
                          isCompleted ? 'bg-emerald-500' : isRunning ? 'bg-blue-300' : 'bg-slate-100'
                        }`} 
                        style={{ height: 'calc(100% - 14px)' }}
                      />
                    )}

                    {/* Step Icon */}
                    <div className="relative shrink-0 z-10">
                      {isCompleted && (
                        <div className="w-7 h-7 rounded-full bg-emerald-50 border border-emerald-200 text-emerald-600 flex items-center justify-center animate-scaleIn">
                          <Check className="w-4 h-4" />
                        </div>
                      )}
                      {isRunning && (
                        <div className="w-7 h-7 rounded-full bg-blue-50 border border-blue-200 text-blue-600 flex items-center justify-center animate-pulse">
                          <Loader2 className="w-4 h-4 animate-spin" />
                        </div>
                      )}
                      {isWaiting && (
                        <div className="w-7 h-7 rounded-full bg-slate-100 border border-slate-200 text-slate-400 flex items-center justify-center">
                          <span className="w-1.5 h-1.5 rounded-full bg-slate-300" />
                        </div>
                      )}
                    </div>

                    {/* Content */}
                    <div className="flex-1 min-w-0 pt-0.5">
                      <div className="flex items-center justify-between gap-4">
                        <p className={`text-xs font-semibold leading-relaxed truncate ${
                          isCompleted ? 'text-slate-900' : isRunning ? 'text-blue-600' : 'text-slate-400'
                        }`}>
                          {step.label}
                        </p>
                        <div className="flex items-center gap-2 shrink-0">
                          {step.time && (
                            <span className="text-[10px] text-slate-400 font-mono">{step.time}</span>
                          )}
                          <Badge variant={step.status === 'Completed' ? 'active' : step.status === 'Running' ? 'processing' : 'pending'}>
                            {step.status}
                          </Badge>
                        </div>
                      </div>
                    </div>
                  </div>
                );
              })}
              <div ref={timelineEndRef} />
            </div>
          </div>
        )}

        {/* Imported Documents Table */}
        {documents.length > 0 && (
          <div className="bg-white rounded-2xl border border-slate-200 shadow-sm p-6 space-y-4 animate-fadeIn">
            <div className="flex items-center justify-between">
              <h3 className="text-sm font-bold text-slate-900">Imported Documents</h3>
              <span className="text-[11px] text-slate-500">{documents.length} item(s) total</span>
            </div>

            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs border-collapse">
                <thead>
                  <tr className="border-b border-slate-100 text-slate-400 font-bold">
                    <th className="py-3 px-4">Source</th>
                    <th className="py-3 px-4">Document Name</th>
                    <th className="py-3 px-4">Imported Time</th>
                    <th className="py-3 px-4">Status</th>
                    <th className="py-3 px-4 text-right">Actions</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {documents.map((doc) => (
                    <tr key={doc.id} className="hover:bg-slate-50/50 transition-colors">
                      <td className="py-3 px-4 font-medium text-slate-600">
                        {doc.source === 'Local' && '📄 Local'}
                        {doc.source === 'Google Drive' && '☁ Drive'}
                        {doc.source === 'SharePoint' && '🏢 SharePoint'}
                        {doc.source === 'Jira' && '🟦 Jira'}
                        {doc.source === 'Confluence' && '📘 Confluence'}
                      </td>
                      <td className="py-3 px-4 font-semibold text-slate-900">{doc.name}</td>
                      <td className="py-3 px-4 text-slate-400">{doc.time}</td>
                      <td className="py-3 px-4">
                        <Badge variant={doc.status === 'Ready' ? 'active' : doc.status === 'Validated' ? 'processing' : 'pending'}>
                          {doc.status}
                        </Badge>
                      </td>
                      <td className="py-3 px-4 text-right space-x-1">
                        <button 
                          onClick={() => setActivePreviewDoc(doc)}
                          className="p-1 hover:bg-slate-100 rounded text-slate-500 hover:text-slate-800 transition-colors"
                          title="Preview"
                        >
                          <Eye className="w-3.5 h-3.5" />
                        </button>
                        <button 
                          onClick={() => {
                            setDocuments(prev => prev.filter(d => d.id !== doc.id));
                            showToast("Document deleted");
                          }}
                          className="p-1 hover:bg-red-50 rounded text-slate-400 hover:text-red-500 transition-colors"
                          title="Delete"
                        >
                          <Trash2 className="w-3.5 h-3.5" />
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}

      </div>

      {/* Document Preview Modal */}
      {activePreviewDoc && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
          <div className="absolute inset-0 bg-black/60 backdrop-blur-xs" onClick={() => setActivePreviewDoc(null)} />
          <div className="relative w-full max-w-2xl bg-white border border-slate-200 p-6 rounded-xl shadow-2xl flex flex-col max-h-[80vh] animate-scaleIn">
            <div className="flex items-center justify-between border-b border-slate-100 pb-4 mb-4">
              <div>
                <span className="text-[10px] uppercase font-bold text-slate-400 block">{activePreviewDoc.source} Document</span>
                <h3 className="text-sm font-bold text-slate-900">{activePreviewDoc.name}</h3>
              </div>
              <button onClick={() => setActivePreviewDoc(null)} className="text-slate-400 hover:text-slate-600 text-xl font-medium">&times;</button>
            </div>
            
            <div className="flex-1 overflow-y-auto space-y-4 text-xs leading-relaxed text-slate-600 p-4 bg-slate-50 rounded-lg">
              <p className="font-semibold text-slate-900">Document Stream Content Preview:</p>
              <p>
                1. System Overview: The checkout redesign focuses on simplifying user inputs down to a 3-step timeline (Info, Shipping, Payment).
              </p>
              <p>
                2. Auth Rules: Support guest checkout, OAuth 2.0 social login, and 1-click profiles.
              </p>
              <p>
                3. Business Rules: Free standard shipping is automatically applied if cart subtotal is above $100.
              </p>
            </div>

            <div className="flex justify-end pt-4 border-t border-slate-100 mt-4">
              <Button size="sm" onClick={() => setActivePreviewDoc(null)}>Close Preview</Button>
            </div>
          </div>
        </div>
      )}

      {/* Validation Mode Dialog */}
      {showValidationDialog && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm animate-fadeIn">
          <div className="bg-white rounded-2xl p-8 max-w-lg w-full mx-4 shadow-2xl animate-scaleIn border border-slate-200">
            <div className="flex items-start justify-between mb-6">
              <div>
                <h3 className="text-xl font-bold text-slate-900 mb-2">Select Validation Mode</h3>
                <p className="text-sm text-slate-500">Choose how you want to validate the generated requirements and user stories.</p>
              </div>
              <button 
                onClick={() => setShowValidationDialog(false)}
                className="text-slate-400 hover:text-slate-600 transition-colors"
              >
                <X className="w-5 h-5" />
              </button>
            </div>
            
            <div className="space-y-4">
              <button 
                onClick={() => setValidationMode('step-by-step')}
                className={`w-full flex items-start gap-4 p-4 rounded-xl border text-left transition-all ${
                  validationMode === 'step-by-step' 
                    ? 'border-blue-500 bg-blue-50/50 ring-1 ring-blue-500/30' 
                    : 'border-slate-200 hover:border-blue-300 hover:bg-slate-50'
                }`}
              >
                <div className={`mt-0.5 w-5 h-5 rounded-full border flex items-center justify-center shrink-0 ${
                  validationMode === 'step-by-step' ? 'border-blue-500 bg-blue-500 text-white' : 'border-slate-300'
                }`}>
                  {validationMode === 'step-by-step' && <Check className="w-3 h-3" />}
                </div>
                <div>
                  <h4 className="font-semibold text-slate-900 text-sm mb-1">Step-by-step validation mode</h4>
                  <p className="text-xs text-slate-500 leading-relaxed">Review and approve chunks, classifications, and epics at each stage before proceeding to the next.</p>
                </div>
              </button>
              
              <button 
                onClick={() => setValidationMode('final-review')}
                className={`w-full flex items-start gap-4 p-4 rounded-xl border text-left transition-all ${
                  validationMode === 'final-review' 
                    ? 'border-blue-500 bg-blue-50/50 ring-1 ring-blue-500/30' 
                    : 'border-slate-200 hover:border-blue-300 hover:bg-slate-50'
                }`}
              >
                <div className={`mt-0.5 w-5 h-5 rounded-full border flex items-center justify-center shrink-0 ${
                  validationMode === 'final-review' ? 'border-blue-500 bg-blue-500 text-white' : 'border-slate-300'
                }`}>
                  {validationMode === 'final-review' && <Check className="w-3 h-3" />}
                </div>
                <div>
                  <h4 className="font-semibold text-slate-900 text-sm mb-1">Human review at the last validation</h4>
                  <p className="text-xs text-slate-500 leading-relaxed">Let the AI process everything autonomously and only require human review at the final User Story validation stage.</p>
                </div>
              </button>
            </div>
            
            <div className="flex justify-end gap-3 mt-8">
              <Button variant="ghost" onClick={() => setShowValidationDialog(false)}>
                Cancel
              </Button>
              <Button 
                disabled={!validationMode}
                className="bg-blue-600 hover:bg-blue-700 text-white disabled:opacity-50"
                onClick={() => {
                  setShowValidationDialog(false);
                  startProcessingPipeline(pendingDocName);
                }}
              >
                Start Processing
              </Button>
            </div>
          </div>
        </div>
      )}

      {/* Sticky Bottom Action Bar */}
      <div className="fixed bottom-0 left-0 right-0 z-40 bg-white border-t border-slate-200 py-4 px-8 flex items-center justify-between shadow-2xl">
        <div className="flex items-center gap-3">
          <Button variant="ghost" size="sm" onClick={() => router.push('/dashboard')} className="flex items-center gap-2">
            <ArrowLeft className="w-3.5 h-3.5" />
            Back
          </Button>
          <Button variant="ghost" size="sm" onClick={() => { setDocuments([]); showToast("Cleared all documents"); }} className="text-slate-500 hover:text-red-500">
            Clear All
          </Button>
        </div>

        <Button 
          onClick={() => router.push(`/projects/${projectId}/chunks`)}
          disabled={documents.length === 0}
          className="flex items-center gap-2 bg-slate-950 hover:bg-slate-800 text-white border-none shadow-sm disabled:opacity-40 disabled:cursor-not-allowed"
        >
          Continue to Module Outline
          <ArrowRight className="w-3.5 h-3.5" />
        </Button>
      </div>
    </div>
  );
}
