'use client';

import React, { useState } from 'react';
import { useRouter } from 'next/navigation';
import { motion, AnimatePresence } from 'framer-motion';
import { X, Sparkles, FolderPlus, UploadCloud, Globe, FileText, ArrowRight } from 'lucide-react';
import { useWorkspaceStore } from '@/store/workspaceStore';
import { useTestCaseWorkflowStore } from '@/testCase Frontend/store/workflowStore';

interface NewProjectModalProps {
  isOpen: boolean;
  onClose: () => void;
}

export const NewProjectModal: React.FC<NewProjectModalProps> = ({ isOpen, onClose }) => {
  const router = useRouter();
  const { createWorkspace } = useWorkspaceStore();
  const { setWorkflow } = useTestCaseWorkflowStore();
  const [name, setName] = useState('');
  const [description, setDescription] = useState('');
  const [clientDomain, setClientDomain] = useState('');
  const [targetUrl, setTargetUrl] = useState('');
  const [selectedFile, setSelectedFile] = useState<File | null>(null);

  if (!isOpen) return null;

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!name.trim()) return;

    const projectName = name.trim();
    const projectId = createWorkspace(projectName, description.trim() || `${clientDomain ? `${clientDomain} - ` : ''}Requirements & Test Script Suite`);
    
    // Generate workflow ID
    const workflowId = `wf_${Date.now().toString(36)}_${Math.random().toString(36).substring(2, 6)}`;

    // Keep the user-entered name attached to the active project throughout the
    // generator flow. The generator reads this persisted record after redirect.
    setWorkflow(workflowId, projectId, projectName);
    
    onClose();
    // Redirect to test case generation wizard or dedicated workspace
    router.push('/test-case-generation');
  };

  return (
    <AnimatePresence>
      <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm">
        <motion.div
          initial={{ opacity: 0, scale: 0.95, y: 10 }}
          animate={{ opacity: 1, scale: 1, y: 0 }}
          exit={{ opacity: 0, scale: 0.95, y: 10 }}
          className="relative w-full max-w-xl rounded-3xl border border-border/80 bg-card p-7 shadow-2xl overflow-hidden"
        >
          {/* Ambient Glow Header */}
          <div className="absolute -top-24 -right-24 w-60 h-60 bg-primary/20 rounded-full blur-3xl pointer-events-none" />
          <div className="absolute -bottom-24 -left-24 w-60 h-60 bg-purple-500/15 rounded-full blur-3xl pointer-events-none" />

          {/* Close button */}
          <button
            onClick={onClose}
            className="absolute top-5 right-5 p-2 rounded-xl text-muted-foreground hover:text-foreground hover:bg-muted/80 transition-colors"
            aria-label="Close modal"
          >
            <X className="w-5 h-5" />
          </button>

          <div className="flex items-center gap-3 mb-6">
            <div className="flex h-12 w-12 items-center justify-center rounded-2xl bg-gradient-to-br from-primary to-purple-600 text-primary-foreground shadow-lg shadow-primary/25">
              <FolderPlus className="w-6 h-6" />
            </div>
            <div>
              <span className="text-xs font-bold uppercase tracking-widest text-primary">AI Workspace</span>
              <h2 className="text-2xl font-bold text-foreground">Create New Project</h2>
            </div>
          </div>

          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label className="block text-xs font-semibold text-foreground mb-1.5 uppercase tracking-wider">
                Project Name <span className="text-rose-500">*</span>
              </label>
              <input
                type="text"
                required
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder="e.g. Aegis Enterprise Portal"
                className="w-full h-11 px-4 rounded-xl border border-border/80 bg-background text-sm text-foreground focus:outline-none focus:border-primary focus:ring-2 focus:ring-primary/20 transition"
              />
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div>
                <label className="block text-xs font-semibold text-foreground mb-1.5 uppercase tracking-wider flex items-center gap-1.5">
                  <FileText className="w-3.5 h-3.5 text-primary" /> Client / Domain
                </label>
                <input
                  type="text"
                  value={clientDomain}
                  onChange={(e) => setClientDomain(e.target.value)}
                  placeholder="e.g. Aegis Corp / FinTech"
                  className="w-full h-11 px-4 rounded-xl border border-border/80 bg-background text-sm text-foreground focus:outline-none focus:border-primary focus:ring-2 focus:ring-primary/20 transition"
                />
              </div>

              <div>
                <label className="block text-xs font-semibold text-foreground mb-1.5 uppercase tracking-wider flex items-center gap-1.5">
                  <Globe className="w-3.5 h-3.5 text-primary" /> Target App URL (Optional)
                </label>
                <input
                  type="url"
                  value={targetUrl}
                  onChange={(e) => setTargetUrl(e.target.value)}
                  placeholder="https://app.aegisportal.com"
                  className="w-full h-11 px-4 rounded-xl border border-border/80 bg-background text-sm text-foreground focus:outline-none focus:border-primary focus:ring-2 focus:ring-primary/20 transition"
                />
              </div>
            </div>

            <div>
              <label className="block text-xs font-semibold text-foreground mb-1.5 uppercase tracking-wider">
                Project Description & Scope
              </label>
              <textarea
                rows={2}
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                placeholder="Briefly describe the target application features and test automation scope..."
                className="w-full p-3.5 rounded-xl border border-border/80 bg-background text-sm text-foreground focus:outline-none focus:border-primary focus:ring-2 focus:ring-primary/20 transition resize-none"
              />
            </div>

            {/* Document Dropzone Preview */}
            <div className="border-2 border-dashed border-border/80 rounded-2xl p-4 bg-muted/20 text-center hover:bg-muted/40 transition cursor-pointer relative">
              <input
                type="file"
                onChange={(e) => setSelectedFile(e.target.files?.[0] || null)}
                className="absolute inset-0 w-full h-full opacity-0 cursor-pointer"
                accept=".pdf,.docx,.txt,.md"
              />
              <UploadCloud className="w-7 h-7 mx-auto text-primary mb-1.5" />
              <p className="text-xs font-medium text-foreground">
                {selectedFile ? selectedFile.name : 'Upload SRS / PRD Document (PDF, DOCX, TXT)'}
              </p>
              <p className="text-[11px] text-muted-foreground mt-0.5">
                {selectedFile ? `${(selectedFile.size / 1024).toFixed(1)} KB uploaded` : 'Optional - AI will automatically extract requirements & user stories'}
              </p>
            </div>

            <div className="flex items-center justify-end gap-3 pt-4 border-t border-border/60">
              <button
                type="button"
                onClick={onClose}
                className="px-5 py-2.5 rounded-xl border border-border/80 text-sm font-semibold text-foreground hover:bg-muted transition"
              >
                Cancel
              </button>
              <button
                type="submit"
                className="inline-flex items-center gap-2 px-6 py-2.5 rounded-xl bg-gradient-to-r from-orange-500 via-purple-600 to-indigo-600 text-white font-semibold text-sm shadow-lg shadow-purple-500/25 hover:opacity-95 hover:scale-[1.02] active:scale-[0.98] transition-all"
              >
                <Sparkles className="w-4 h-4" /> Start AI Generation <ArrowRight className="w-4 h-4" />
              </button>
            </div>
          </form>
        </motion.div>
      </div>
    </AnimatePresence>
  );
};
