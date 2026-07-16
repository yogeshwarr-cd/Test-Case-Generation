'use client';

import React, { useState } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { Plus, FolderPlus, Clock, CheckCircle2, ArrowRight, Trash2 } from 'lucide-react';
import { useWorkspaceStore } from '@/store/workspaceStore';
import { Badge } from '@/components/common/Badge';
import { Button } from '@/components/common/Button';
import { cn } from '@/lib/utils';

export default function DashboardPage() {
  const { workspaces } = useWorkspaceStore();



  return (
    <div className="flex-1 flex flex-col p-6 space-y-6 select-none bg-background text-foreground transition-colors overflow-y-auto">
      {/* Top Banner Header */}
      <div className="flex items-center justify-between border-b border-border pb-4 shrink-0">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-foreground">Projects</h1>
          <p className="text-[13px] text-muted-foreground mt-1">Manage your PRD-to-user-stories workspaces</p>
        </div>
        
        {workspaces.length > 0 && (
          <Link href="/projects/new">
            <Button size="sm" className="flex items-center gap-2 bg-primary hover:bg-primary/90 text-primary-foreground border-none shadow-md h-8">
              <Plus className="w-3.5 h-3.5" />
              New Project
            </Button>
          </Link>
        )}
      </div>

      {workspaces.length === 0 ? (
        <div className="flex-1 flex flex-col items-center justify-center max-w-md mx-auto text-center space-y-6">
          <div className="w-32 h-32 bg-primary/10 text-primary rounded-full flex items-center justify-center mb-4">
            <FolderPlus className="w-16 h-16 opacity-80" />
          </div>
          <div>
            <h2 className="text-2xl font-bold mb-2">No projects yet</h2>
            <p className="text-muted-foreground text-sm">Start your first project by uploading a PRD to automatically generate a structured backlog.</p>
          </div>
          <Link href="/projects/new">
            <Button size="lg" className="w-full sm:w-auto bg-primary hover:bg-primary/90 text-primary-foreground text-base">
              <Plus className="w-5 h-5 mr-2" />
              Create New Project
            </Button>
          </Link>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {workspaces.map((ws) => (
            <div 
              key={ws.id}
              className="bg-card rounded-xl p-5 border border-border flex flex-col justify-between space-y-4 shadow-sm hover:shadow-md transition-shadow group relative overflow-visible"
            >
              <div className="space-y-3">
                <div className="flex items-start justify-between gap-4">
                  <h3 className="font-semibold text-[15px] text-card-foreground tracking-tight group-hover:text-primary transition-colors">{ws.name}</h3>
                  <Badge variant={ws.status}>{ws.status}</Badge>
                </div>
                <div className="flex items-center gap-2 text-[11px] text-muted-foreground">
                  <Clock className="w-3.5 h-3.5" />
                  Created {ws.updated_at}
                </div>
              </div>

              <div className="flex items-center justify-between pt-3 border-t border-border/50">
                <Button 
                  onClick={() => {
                    if (window.confirm("Are you sure you want to delete this project?")) {
                      useWorkspaceStore.getState().removeWorkspace(ws.id);
                    }
                  }}
                  variant="ghost" 
                  size="sm" 
                  className="text-destructive hover:text-destructive hover:bg-destructive/10 text-xs px-2 h-8"
                  title="Delete Project"
                >
                  <Trash2 className="w-4 h-4" />
                </Button>
                <Link href={`/projects/${ws.id}/epics`}>
                  <Button size="sm" className="bg-primary hover:bg-primary/90 text-primary-foreground text-xs px-3 py-1.5 h-8 rounded-lg font-bold border-none transition-colors shadow-sm">
                    Open Project
                  </Button>
                </Link>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

