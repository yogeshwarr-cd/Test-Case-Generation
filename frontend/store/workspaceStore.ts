import { create } from 'zustand';
import { persist } from 'zustand/middleware';
import { Workspace } from '@/lib/types/project';

interface WorkspaceState {
  workspaces: Workspace[];
  activeWorkspaceId: string | null;
  setActiveWorkspaceId: (id: string | null) => void;
  createWorkspace: (name: string, description: string) => void;
  removeWorkspace: (id: string) => void;
}

export const useWorkspaceStore = create<WorkspaceState>()(
  persist(
    (set) => ({
      workspaces: [],
      activeWorkspaceId: null,
      setActiveWorkspaceId: (id) => set({ activeWorkspaceId: id }),
      createWorkspace: (name, description) =>
        set((state) => {
          const baseId = name.toLowerCase().replace(/\s+/g, '-').replace(/[^a-z0-9-]/g, '');
          // Ensure uniqueness by appending a short timestamp suffix when the id already exists
          const existingIds = new Set(state.workspaces.map((w) => w.id));
          const id = existingIds.has(baseId) ? `${baseId}-${Date.now().toString(36)}` : baseId;
          const newWorkspace: Workspace = {
            id,
            name,
            description,
            status: 'active',
            doc_count: 0,
            story_count: 0,
            updated_at: 'Just now',
          };
          return { workspaces: [newWorkspace, ...state.workspaces] };
        }),
      removeWorkspace: (id) =>
        set((state) => ({ workspaces: state.workspaces.filter((w) => w.id !== id) })),
    }),
    { name: 'ba-workspaces' }
  )
);
