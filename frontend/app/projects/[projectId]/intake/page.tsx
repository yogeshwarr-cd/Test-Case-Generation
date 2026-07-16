'use client';

import React, { useState, useRef } from 'react';
import { useRouter, useParams } from 'next/navigation';
import { Upload, FileText, CheckCircle2, AlertTriangle, Loader2 } from 'lucide-react';
import { Button } from '@/components/common/Button';
import { api } from '@/services/api';

export default function IntakePage() {
  const router = useRouter();
  const params = useParams();
  const projectId = params?.projectId as string;

  const [hasFile, setHasFile] = useState(false);
  const [file, setFile] = useState<File | null>(null);
  const [filePath, setFilePath] = useState<string>('');
  const [uploading, setUploading] = useState(false);
  const [starting, setStarting] = useState(false);
  const [toastMessage, setToastMessage] = useState('');
  const [errorMessage, setErrorMessage] = useState('');
  const fileInputRef = useRef<HTMLInputElement>(null);

  const showToast = (msg: string) => {
    setToastMessage(msg);
    setTimeout(() => setToastMessage(''), 3000);
  };

  const handleFileSelect = async (selectedFile: File) => {
    if (!selectedFile) return;

    setUploading(true);
    setErrorMessage('');

    try {
      const result = await api.importDocument(selectedFile);
      setFile(selectedFile);
      setFilePath(result.file_path);
      setHasFile(true);
      showToast('Document parsed successfully.');
    } catch (err: any) {
      setErrorMessage(err?.message || 'Failed to upload document. Make sure the backend is running.');
    } finally {
      setUploading(false);
    }
  };

  const handleDropZoneClick = () => {
    if (!uploading) fileInputRef.current?.click();
  };

  const handleFileInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const selected = e.target.files?.[0];
    if (selected) handleFileSelect(selected);
  };

  const handleDrop = (e: React.DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    const dropped = e.dataTransfer.files?.[0];
    if (dropped) handleFileSelect(dropped);
  };

  const handleDragOver = (e: React.DragEvent<HTMLDivElement>) => {
    e.preventDefault();
  };

  const handleGenerateOutline = async () => {
    if (!filePath) return;

    setStarting(true);
    setErrorMessage('');

    try {
      // Store file path under the key the processing page expects
      localStorage.setItem(`wf_file_path_${projectId}`, filePath);
      // Clear any stale workflow_id from a previous run
      localStorage.removeItem(`wf_id_${projectId}`);
      router.push(`/projects/${projectId}/processing`);
    } catch (err: any) {
      setErrorMessage(err?.message || 'Failed to navigate to processing.');
      setStarting(false);
    }
  };

  return (
    <div className="flex-1 flex flex-col p-8 bg-background text-foreground overflow-y-auto">
      {/* Breadcrumb & Header */}
      <div className="mb-8">
        <div className="text-xs text-muted-foreground flex gap-2 items-center mb-2">
          <span>Home</span> <span>/</span> <span className="font-semibold text-foreground">Project Workspace</span>
        </div>
        <h1 className="text-3xl font-bold tracking-tight">Project Intake</h1>
        <p className="text-sm text-muted-foreground mt-1">Upload your Product Requirement Document (PRD) to begin.</p>
      </div>

      <div className="flex-1 max-w-4xl w-full">
        {!hasFile ? (
          <>
            <div
              onClick={handleDropZoneClick}
              onDrop={handleDrop}
              onDragOver={handleDragOver}
              className="border-2 border-dashed border-border rounded-xl p-16 flex flex-col items-center justify-center bg-card hover:bg-muted/30 hover:border-primary/50 transition-all cursor-pointer text-center group"
            >
              {uploading ? (
                <>
                  <Loader2 className="w-10 h-10 text-primary animate-spin mb-4" />
                  <p className="text-muted-foreground font-medium">Uploading and parsing document...</p>
                </>
              ) : (
                <>
                  <div className="w-16 h-16 rounded-full bg-primary/10 text-primary flex items-center justify-center mb-6 group-hover:scale-110 transition-transform">
                    <Upload className="w-8 h-8" />
                  </div>
                  <h3 className="text-xl font-bold mb-2 text-foreground">Upload PRD Document</h3>
                  <p className="text-muted-foreground mb-6 max-w-md">
                    Drag and drop your PDF, DOCX, or TXT file here, or click to browse files from your computer.
                  </p>
                  <Button className="bg-primary hover:bg-primary/90 text-primary-foreground">
                    Select File
                  </Button>
                </>
              )}
            </div>
            <input
              ref={fileInputRef}
              type="file"
              accept=".pdf,.docx,.txt,.doc"
              className="hidden"
              onChange={handleFileInputChange}
            />
            {errorMessage && (
              <div className="mt-4 flex items-start gap-3 bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 text-red-700 dark:text-red-400 rounded-xl p-4 text-sm">
                <AlertTriangle className="w-5 h-5 shrink-0 mt-0.5" />
                <span>{errorMessage}</span>
              </div>
            )}
          </>
        ) : (
          <div className="space-y-6">
            <div className="bg-card border border-border rounded-xl p-6 flex items-start gap-4">
              <div className="w-12 h-12 rounded-lg bg-blue-100 text-blue-600 flex items-center justify-center dark:bg-blue-900/30 dark:text-blue-400 shrink-0">
                <FileText className="w-6 h-6" />
              </div>
              <div className="flex-1">
                <h3 className="font-bold text-foreground text-lg">{file?.name || 'Document'}</h3>
                <p className="text-sm text-muted-foreground mb-4">
                  {file ? `${(file.size / 1024).toFixed(0)} KB • Uploaded just now` : 'Uploaded'}
                </p>
                <div className="flex items-center gap-2 text-sm text-green-600 dark:text-green-500 font-medium">
                  <CheckCircle2 className="w-4 h-4" />
                  Ready for processing
                </div>
              </div>
            </div>

            {errorMessage && (
              <div className="flex items-start gap-3 bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 text-red-700 dark:text-red-400 rounded-xl p-4 text-sm">
                <AlertTriangle className="w-5 h-5 shrink-0 mt-0.5" />
                <span>{errorMessage}</span>
              </div>
            )}

            <div className="flex justify-end">
              <Button
                onClick={handleGenerateOutline}
                disabled={starting}
                size="lg"
                className="bg-primary hover:bg-primary/90 text-primary-foreground text-base px-8 py-6 h-auto shadow-md shadow-primary/20 hover:shadow-lg hover:shadow-primary/30 transition-all disabled:opacity-60"
              >
                {starting ? (
                  <>
                    <Loader2 className="w-5 h-5 mr-2 animate-spin" />
                    Starting...
                  </>
                ) : (
                  'Generate Outline'
                )}
              </Button>
            </div>
          </div>
        )}
      </div>

      {/* Toast Notification */}
      {toastMessage && (
        <div className="fixed bottom-6 right-6 bg-popover text-popover-foreground border border-border shadow-lg rounded-lg px-4 py-3 flex items-center gap-3 animate-in slide-in-from-bottom-5">
          <CheckCircle2 className="w-5 h-5 text-green-500" />
          <span className="font-medium text-sm">{toastMessage}</span>
        </div>
      )}
    </div>
  );
}
