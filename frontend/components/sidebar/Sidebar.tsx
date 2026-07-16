'use client';

import React, { useState } from 'react';
import Link from 'next/link';
import { usePathname, useRouter, useParams } from 'next/navigation';
import { 
  LogOut, 
  Upload, 
  FileText, 
  Database, 
  Tag, 
  Bot, 
  CheckCircle, 
  Layers, 
  ShieldCheck, 
  Home,
  ChevronRight
} from 'lucide-react';
import { useWorkspaceStore } from '@/store/workspaceStore';

export const Sidebar: React.FC = () => {
  const pathname = usePathname();
  const router = useRouter();
  const params = useParams();
  const projectId = params?.projectId as string;
  const { workspaces } = useWorkspaceStore();
  const [isExpanded, setIsExpanded] = useState(true);

  const handleLogout = () => {
    localStorage.removeItem('auth_token');
    router.push('/');
  };

  const currentWorkspace = workspaces.find(w => w.id === projectId);

  // User-facing stages for BA Accelerator
  const steps = [
    { id: 0, label: 'AI Pipeline', icon: Bot, path: 'processing' },
    { id: 1, label: 'Req Analysis', icon: CheckCircle, path: 'requirements' },
    { id: 2, label: 'Outline Review', icon: Layers, path: 'epics' },
    { id: 3, label: 'Story Board', icon: FileText, path: 'stories' },
    { id: 4, label: 'Validation Gate', icon: ShieldCheck, path: 'validation' },
    { id: 5, label: 'Project History', icon: Bot, path: 'history' },
    { id: 6, label: 'Version Control', icon: Database, path: 'versioning' },
    { id: 7, label: 'Final Export', icon: CheckCircle, path: 'export' }
  ];

  // Calculate arc offset for the wheel effect
  const getOffset = (index: number, total: number) => {
    const normalized = index / (total - 1);
    const curve = Math.sin(normalized * Math.PI);
    return curve * 30; // 30px maximum bulge
  };

  return (
    <div className="flex h-screen select-none shrink-0 z-30 bg-background border-r border-border transition-all duration-500 relative" style={{ width: isExpanded ? '280px' : '80px' }}>
      
      {/* Toggle Button */}
      <button 
        onClick={() => setIsExpanded(!isExpanded)}
        className="absolute -right-3 top-6 w-6 h-6 bg-primary text-primary-foreground rounded-full flex items-center justify-center shadow-md z-40 hover:scale-110 transition-transform"
      >
        <ChevronRight className={`w-4 h-4 transition-transform duration-500 ${!isExpanded ? 'rotate-180' : ''}`} />
      </button>

      <div className="flex flex-col h-full w-full py-4 overflow-hidden relative">
        
        {/* Header */}
        <div className="px-5 flex items-center gap-2 mb-4 shrink-0">
          <div className="w-7 h-7 flex items-center justify-center shrink-0">
            <img src="/images_and_videos/logo-think.png" alt="BA Accelerator" className="w-full h-full object-contain" />
          </div>
          {isExpanded && (
            <div className="flex flex-col whitespace-nowrap overflow-hidden transition-opacity duration-300">
              <span className="text-[10px] text-muted-foreground uppercase tracking-widest">{currentWorkspace?.name || 'Workspace'}</span>
            </div>
          )}
        </div>

        {/* Home & Global actions */}
        <div className="px-3 mb-4 shrink-0 flex flex-col gap-1">
          <Link href="/dashboard" className="flex items-center gap-2 px-2 py-1.5 rounded-lg text-muted-foreground hover:text-primary hover:bg-primary/5 transition-colors group">
            <Home className="w-4 h-4 shrink-0 group-hover:scale-110 transition-transform" />
            {isExpanded && <span className="text-[13px] font-medium whitespace-nowrap">Dashboard</span>}
          </Link>
        </div>

        {/* Speedometer/Wheel Workflow Steps */}
        {projectId && (
          <div className="flex-1 overflow-y-auto overflow-x-hidden px-1 py-2 relative hide-scrollbar">
            {isExpanded && (
              <div className="px-4 mb-3">
                <span className="text-[10px] font-bold tracking-widest text-primary uppercase">Workflow Stages</span>
              </div>
            )}
            
            <div className="flex flex-col gap-1 relative w-full">
              {/* Vertical Arc Background Line */}
              {isExpanded && (
                <div className="absolute left-[38px] top-4 bottom-4 w-px bg-gradient-to-b from-transparent via-border to-transparent -z-10" />
              )}
              
              {steps.map((step, idx) => {
                const Icon = step.icon;
                const isActive = pathname.includes(step.path);
                const offset = isExpanded ? getOffset(idx, steps.length) : 0;
                
                return (
                  <Link
                    key={step.id}
                    href={`/projects/${projectId}/${step.path}`}
                    title={step.label}
                    className="flex items-center group relative h-9 my-0.5"
                    style={{ transform: `translateX(${offset}px)`, transition: 'all 0.3s ease' }}
                  >
                    <div className={`
                      flex items-center justify-center w-7 h-7 rounded-full shrink-0 mx-2 transition-all duration-300 shadow-sm
                      ${isActive ? 'bg-primary text-primary-foreground scale-110 shadow-primary/30' : 'bg-background text-muted-foreground border border-border group-hover:border-primary/50 group-hover:text-primary group-hover:bg-primary/5'}
                    `}>
                      <Icon className="w-3.5 h-3.5" />
                    </div>
                    
                    {isExpanded && (
                      <div className="flex flex-col whitespace-nowrap transition-opacity duration-300 overflow-hidden pr-4">
                        <span className={`text-[13px] font-medium ${isActive ? 'text-foreground' : 'text-muted-foreground group-hover:text-foreground'}`}>
                          {step.label}
                        </span>
                      </div>
                    )}
                  </Link>
                );
              })}
            </div>
          </div>
        )}

        {/* Bottom Actions */}
        <div className="px-3 mt-auto pt-3 border-t border-border/50 shrink-0 flex flex-col gap-1">
          <button
            onClick={handleLogout}
            className="flex items-center gap-2 px-2 py-1.5 rounded-lg text-muted-foreground hover:text-red-500 hover:bg-red-500/10 transition-colors group w-full text-left"
            title="Logout"
          >
            <LogOut className="w-4 h-4 shrink-0 group-hover:scale-110 transition-transform" />
            {isExpanded && <span className="text-[13px] font-medium whitespace-nowrap">Logout</span>}
          </button>
        </div>
      </div>

      <style dangerouslySetInnerHTML={{__html: `
        .hide-scrollbar::-webkit-scrollbar {
          display: none;
        }
        .hide-scrollbar {
          -ms-overflow-style: none;
          scrollbar-width: none;
        }
      `}} />
    </div>
  );
};
