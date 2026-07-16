'use client';

import { useWorkspaceStore } from '@/store/workspaceStore';

export const useProject = (projectId: string) => {
  const { workspaces } = useWorkspaceStore();
  return workspaces.find(w => w.id === projectId);
};
