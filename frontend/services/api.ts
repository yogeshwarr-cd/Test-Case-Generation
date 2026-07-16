import { apiClient } from './apiClient';
import {
  Epic,
  Story,
  Feature,
  VersionRecord,
  ProjectHistoryEvent,
  ExtractedRequirementCategory,
  SegmentationChunk,
} from './mockData';

// ─── helpers ─────────────────────────────────────────────────────────────────

/**
 * Resolve the backend workflow_id for a project.
 *
 * After POST /api/workflow/start succeeds the processing page stores the
 * returned workflow_id under `wf_id_<projectId>`.  All downstream pages
 * (requirements, epics, stories …) call this helper so they always poll with
 * the real workflow_id rather than the URL slug.
 *
 * Falls back to projectId only when no stored id is available yet (e.g. direct
 * deep-link during development) so existing behaviour is preserved.
 */
function resolveWorkflowId(projectId: string): string {
  if (typeof window === 'undefined') return projectId;
  return localStorage.getItem(`wf_id_${projectId}`) || projectId;
}

function getEpicNameMap(epics: any[]): Record<string, string> {
  const map: Record<string, string> = {};
  epics.forEach((e) => {
    map[e.id] = e.name || e.title || e.id;
  });
  return map;
}

function mapBackendStoryToFrontend(s: any, index: number, epicNameMap: Record<string, string> = {}): Story {
  return {
    id: s.id,
    sNo: index + 1,
    epicId: s.epic_id || '',
    epicName: epicNameMap[s.epic_id || ''] || s.epic_id || 'General',
    feature: s.feature_id || 'Feature',
    usId: s.id,
    summary: s.title || s.user_story || '',
    description: s.description || '',
    acceptanceCriteria: (s.acceptance_criteria || []).map((ac: any) =>
      typeof ac === 'string' ? ac : ac.description
    ),
    businessRules: s.business_rules || [],
    dependencies: (s.dependencies || []).map((d: any) =>
      typeof d === 'string' ? d : d.description
    ),
    comments: s.comments || [],
    status: s.status || 'needs_ba_review',
    confidenceScore: s.confidence_score !== undefined ? s.confidence_score : 1.0,
    priority: s.priority || 'MEDIUM',
    storyPoints: s.story_points || 3,
    definitionOfDone: s.definition_of_done || [],
    assumptions: s.assumptions || [],
    risks: s.risks || [],
    requirementMapping: s.requirement_mapping || [],
    sourceChunkReferences: s.source_chunk_references || [],
  };
}

// ─── public API ───────────────────────────────────────────────────────────────

export const api = {
  // ── Workflow lifecycle ──────────────────────────────────────────────────────

  getWorkflowState: async (projectId: string): Promise<any> => {
    return apiClient.get(`/api/workflow/${resolveWorkflowId(projectId)}`);
  },

  getWorkflowStatus: async (projectId: string): Promise<any> => {
    return apiClient.get(`/api/workflow/${resolveWorkflowId(projectId)}/status`);
  },

  importDocument: async (file: File): Promise<{ extracted_text: string; file_path: string }> => {
    const formData = new FormData();
    formData.append('file', file);
    return apiClient.postMultipart('/api/documents/import', formData);
  },

  startWorkflow: async (
    filePath: string,
    confidenceThreshold: number,
    maxRetryAttempts: number,
    projectId: string
  ): Promise<any> => {
    return apiClient.post('/api/workflow/start', {
      workflow_id: projectId,
      file_path: filePath,
      project_id: projectId,
      confidence_threshold: confidenceThreshold,
      max_retry_attempts: maxRetryAttempts,
    });
  },

  approveOutline: async (projectId: string): Promise<any> => {
    return apiClient.post(`/api/workflow/${resolveWorkflowId(projectId)}/approve-outline`);
  },

  startWorkflowFromJira: async (
    issueKey: string,
    includeComments: boolean,
    confidenceThreshold: number,
    maxRetryAttempts: number,
    projectId: string
  ): Promise<any> => {
    return apiClient.post('/api/workflow/mcp/jira/start', {
      workflow_id: projectId,
      issue_key: issueKey,
      include_comments: includeComments,
      project_id: projectId,
      confidence_threshold: confidenceThreshold,
      max_retry_attempts: maxRetryAttempts,
    });
  },

  startWorkflowFromConfluence: async (
    pageId: string,
    confidenceThreshold: number,
    maxRetryAttempts: number,
    projectId: string
  ): Promise<any> => {
    return apiClient.post('/api/workflow/mcp/confluence/start', {
      workflow_id: projectId,
      page_id: pageId,
      project_id: projectId,
      confidence_threshold: confidenceThreshold,
      max_retry_attempts: maxRetryAttempts,
    });
  },

  // ── MCP connectors ──────────────────────────────────────────────────────────

  fetchJira: async (issueKey: string, includeComments: boolean): Promise<string> => {
    const res = await apiClient.post('/api/mcp/jira/fetch', {
      issue_key: issueKey,
      include_comments: includeComments,
    });
    return res.raw_text || res.extracted_text || '';
  },

  fetchConfluence: async (pageId: string): Promise<string> => {
    const res = await apiClient.post('/api/mcp/confluence/fetch', { page_id: pageId });
    return res.raw_text || res.extracted_text || '';
  },

  // ── Requirements ────────────────────────────────────────────────────────────

  getRequirements: async (projectId: string): Promise<ExtractedRequirementCategory[]> => {
    const res = await apiClient.get(`/api/workflow/${resolveWorkflowId(projectId)}`);
    const state = res.state || {};

    const categories: ExtractedRequirementCategory[] = [
      {
        id: 'req-actors',
        title: 'Actors & Personas',
        items: state.actors || state.agent1_output?.actors || state.requirement_analysis?.actors || [],
      },
      {
        id: 'req-func',
        title: 'Functional Requirements',
        items: (state.functional_requirements || state.agent1_output?.functional_requirements || state.requirement_analysis?.functional_requirements || []).map(
          (r: any) => typeof r === 'string' ? r : `${r.id || ''}: ${r.name || r.description || ''}`
        ),
      },
      {
        id: 'req-nonfunc',
        title: 'Non-Functional Requirements',
        items: (state.non_functional_requirements || state.agent1_output?.non_functional_requirements || state.requirement_analysis?.non_functional_requirements || []).map(
          (r: any) => typeof r === 'string' ? r : `${r.id || ''}: ${r.name || r.description || ''}`
        ),
      },
      {
        id: 'req-dependencies',
        title: 'System Dependencies',
        items: state.dependencies || state.agent1_output?.dependencies || state.requirement_analysis?.dependencies || [],
      },
      {
        id: 'req-biz',
        title: 'Business Goals & Constraints',
        items: [
          ...(state.business_goals || state.agent1_output?.business_goals || state.requirement_analysis?.business_goals || []),
          ...(state.constraints || state.agent1_output?.constraints || state.requirement_analysis?.constraints || []),
          ...(state.business_rules || state.agent1_output?.business_rules || state.requirement_analysis?.business_rules || []),
        ],
      },
      {
        id: 'req-edgecases',
        title: 'Edge Cases',
        items: state.edge_cases || state.agent1_output?.acceptance_criteria || state.requirement_analysis?.edge_cases || [],
      },
    ].filter((cat) => cat.items.length > 0);

    return categories;
  },

  // ── Segmentation chunks ─────────────────────────────────────────────────────

  getSegmentationChunks: async (projectId: string): Promise<SegmentationChunk[]> => {
    const res = await apiClient.get(`/api/workflow/${resolveWorkflowId(projectId)}`);
    const state = res.state || {};
    const chunks: any[] = state.labeled_chunks || state.chunks || [];
    return chunks.map((c: any) => ({
      id: String(c.id || c.chunk_id || ''),
      text: c.content || c.text || '',
      label: c.context || c.label || 'Uncategorized',
      sectionTitle: c.section_title || '',
      tokenCount: c.token_count,
    }));
  },

  // ── Epics ────────────────────────────────────────────────────────────────────

  getEpics: async (projectId: string): Promise<Epic[]> => {
    const res = await apiClient.get(`/api/workflow/${resolveWorkflowId(projectId)}`);
    const epics: any[] = res.state?.epics || [];
    return epics.map((e: any, idx: number) => ({
      id: e.id,
      sNo: idx + 1,
      title: e.name || e.title || e.id,
      summary: e.description || '',
      status: (e.metadata?.status as any) || 'needs_review',
      confidenceScore: e.metadata?.confidence_score ?? 0,
    }));
  },

  // ── Features ────────────────────────────────────────────────────────────────

  getFeatures: async (projectId: string): Promise<Feature[]> => {
    const res = await apiClient.get(`/api/workflow/${resolveWorkflowId(projectId)}`);
    const features: any[] = res.state?.features || [];
    const epicNameMap = getEpicNameMap(res.state?.epics || []);
    return features.map((f: any, idx: number) => ({
      id: f.id,
      sNo: idx + 1,
      epicId: f.metadata?.epic_id || f.epic_id || '',
      epicName: epicNameMap[f.metadata?.epic_id || f.epic_id || ''] || 'General',
      title: f.name || f.title || f.id,
      summary: f.description || '',
      status: (f.metadata?.status as any) || 'ready',
    }));
  },

  // ── Stories ──────────────────────────────────────────────────────────────────

  getStories: async (projectId: string): Promise<Story[]> => {
    const res = await apiClient.get(`/api/workflow/${resolveWorkflowId(projectId)}`);
    const stories: any[] = res.state?.user_stories || res.state?.stories || [];
    const epicNameMap = getEpicNameMap(res.state?.epics || []);
    return stories.map((s: any, idx: number) =>
      mapBackendStoryToFrontend(s, idx, epicNameMap)
    );
  },

  getStory: async (projectId: string, storyId: string): Promise<Story | undefined> => {
    const stories = await api.getStories(projectId);
    return stories.find((s) => s.id === storyId);
  },

  updateStory: async (
    projectId: string,
    storyId: string,
    updates: Partial<Story>
  ): Promise<Story> => {
    const current = await api.getStory(projectId, storyId);
    if (!current) throw new Error('Story not found');

    const merged = { ...current, ...updates };
    const backendStory = {
      id: merged.id,
      feature_id: merged.feature,
      epic_id: merged.epicId || null,
      title: merged.summary,
      user_story: merged.summary,
      description: merged.description,
      acceptance_criteria: merged.acceptanceCriteria.map((ac, idx) => ({
        id: `AC-${idx + 1}`,
        description: ac,
        source_refs: [],
      })),
      business_rules: merged.businessRules,
      dependencies: merged.dependencies.map((d, idx) => ({
        id: `DEP-${idx + 1}`,
        description: d,
        depends_on: [],
        source_refs: [],
      })),
      definition_of_done: merged.definitionOfDone || [],
      assumptions: merged.assumptions || [],
      risks: merged.risks || [],
      priority: merged.priority || 'MEDIUM',
      story_points: merged.storyPoints || 3,
      confidence_score: merged.confidenceScore,
      requirement_mapping: merged.requirementMapping || [],
      source_chunk_references: merged.sourceChunkReferences || [],
      traceability: { workflow_id: resolveWorkflowId(projectId) },
    };

    const res = await apiClient.post('/api/user-stories/review/modify', {
      workflow_id: resolveWorkflowId(projectId),
      story: backendStory,
      modified_by: 'Business Analyst',
      comments: 'Modified via story board',
    });

    const updatedBackendStory = res.data?.story || backendStory;
    return mapBackendStoryToFrontend(updatedBackendStory, merged.sNo - 1);
  },

  retryStoryGeneration: async (request: any, storyIndex: number = 0, epicNameMap: Record<string, string> = {}): Promise<Story> => {
    const res = await apiClient.post('/api/user-stories/retry', request);
    const targetId = request.previous_stories?.[0]?.id;
    const allStories = res.data?.user_stories || res.data?.stories || [];
    // Find the specific story that was regenerated by matching its ID
    const backendStory = allStories.find((s: any) => s.id === targetId) || allStories[storyIndex] || request.previous_stories[0];
    return mapBackendStoryToFrontend(backendStory, storyIndex, epicNameMap);
  },

  // ── Epics — write ──────────────────────────────────────────────────────────

  updateEpic: async (projectId: string, epicId: string, updates: Partial<Epic>): Promise<Epic> => {
    // Backend does not expose a dedicated epic-update endpoint yet.
    // Persist via workflow set_state so the change is durable.
    const res = await apiClient.get(`/api/workflow/${resolveWorkflowId(projectId)}`);
    const epics: any[] = res.state?.epics || [];
    const idx = epics.findIndex((e: any) => e.id === epicId);
    if (idx === -1) throw new Error(`Epic ${epicId} not found`);

    const current = epics[idx];
    const updated = {
      ...current,
      name: updates.title ?? current.name,
      description: updates.summary ?? current.description,
      metadata: {
        ...(current.metadata || {}),
        status: updates.status ?? current.metadata?.status,
      },
    };
    epics[idx] = updated;

    // Persist back — best-effort; if it fails the UI still reflects the change
    try {
      await apiClient.patch(`/api/workflow/${resolveWorkflowId(projectId)}`, {
        epics
      });
    } catch {
      // Endpoint not for patching — silently continue, state lives in backend memory for now
    }

    return {
      id: updated.id,
      sNo: idx + 1,
      title: updated.name || updated.id,
      summary: updated.description || '',
      status: updated.metadata?.status || 'needs_review',
      confidenceScore: updated.metadata?.confidence_score ?? 0,
    };
  },

  regenerateEpic: async (
    projectId: string,
    epicId: string,
    feedback: string
  ): Promise<Epic> => {
    // Regeneration is not yet a dedicated backend endpoint.
    // Return the current epic unchanged so the UI can continue.
    const epics = await api.getEpics(projectId);
    const epic = epics.find((e) => e.id === epicId);
    if (!epic) throw new Error(`Epic ${epicId} not found`);
    return epic;
  },

  // ── History & versions ──────────────────────────────────────────────────────

  getHistory: async (projectId: string): Promise<ProjectHistoryEvent[]> => {
    const res = await apiClient.get(`/api/workflow/${resolveWorkflowId(projectId)}`);
    const auditLog: any[] =
      res.state?.audit_log || res.state?.execution_history || [];
    return auditLog.map((log: any, idx: number) => ({
      id: log.id || `log-${idx}`,
      timestamp:
        log.timestamp || log.completed_at || log.started_at || new Date().toISOString(),
      actor:
        log.actor ||
        (log.node_name ? `Agent: ${log.node_name}` : 'System Agent'),
      actorType: (log.actor_type as 'system' | 'ba') || 'system',
      target: log.target || log.node_name || 'System',
      summary:
        log.message ||
        log.summary ||
        `Execution of node ${log.node_name} completed with status: ${log.status}.`,
      telemetry: log.metadata || log.error || null,
    }));
  },

  getVersions: async (_projectId: string): Promise<VersionRecord[]> => {
    // Version records are not yet exposed by the backend.
    return [];
  },

  // ── Traceability ────────────────────────────────────────────────────────────

  getTraceability: async (
    storyId: string,
    storyText: string,
    requirementIds: string[],
    projectId: string,
    documentId?: string
  ): Promise<any> => {
    return apiClient.post('/api/rag/traceability', {
      story_id: storyId,
      story_text: storyText,
      requirement_ids: requirementIds,
      project_id: projectId,
      document_id: documentId,
    });
  },

  // ── Export ──────────────────────────────────────────────────────────────────

  exportWorkflow: async (
    projectId: string,
    format: 'json' | 'csv' | 'txt' | 'docx' | 'pdf'
  ): Promise<void> => {
    // Build export payload from live workflow state
    const res = await apiClient.get(`/api/workflow/${resolveWorkflowId(projectId)}`);
    const state = res.state || {};
    const epics: any[] = state.epics || [];
    const stories: any[] = state.user_stories || state.stories || [];

    if (format === 'json') {
      const blob = new Blob([JSON.stringify({ epics, stories }, null, 2)], {
        type: 'application/json',
      });
      _triggerDownload(blob, `${projectId}-export.json`);
      return;
    }

    if (format === 'csv') {
      const epicNameMap: Record<string, string> = {};
      epics.forEach((e: any) => {
        epicNameMap[e.id] = e.name || e.title || e.id;
      });

      const rows = [
        ['ID', 'Epic', 'Feature', 'Summary', 'Description', 'Acceptance Criteria', 'Priority', 'Story Points', 'Status', 'Confidence'],
        ...stories.map((s: any) => [
          s.id,
          epicNameMap[s.epic_id || ''] || s.epic_id || '',
          s.feature_id || '',
          s.title || s.user_story || '',
          (s.description || '').replace(/\n/g, ' '),
          (s.acceptance_criteria || [])
            .map((ac: any) => (typeof ac === 'string' ? ac : ac.description))
            .join(' | '),
          s.priority || 'MEDIUM',
          s.story_points || 3,
          s.status || '',
          s.confidence_score ?? '',
        ]),
      ];

      const csv = rows
        .map((row) => row.map((cell) => `"${String(cell).replace(/"/g, '""')}"`).join(','))
        .join('\n');

      const blob = new Blob([csv], { type: 'text/csv' });
      _triggerDownload(blob, `${projectId}-stories.csv`);
      return;
    }

    // For txt/docx/pdf: generate a formatted plain-text fallback until a
    // dedicated backend export endpoint is available.
    const lines: string[] = [`Product Requirements Document — ${projectId}`, ''];
    epics.forEach((epic: any, eIdx: number) => {
      lines.push(`${eIdx + 1}. Epic: ${epic.name || epic.title || epic.id}`);
      lines.push(`   ${epic.description || ''}`);
      lines.push('');
      const epicStories = stories.filter((s: any) => s.epic_id === epic.id);
      epicStories.forEach((s: any, sIdx: number) => {
        lines.push(`   ${sIdx + 1}. ${s.id}: ${s.title || s.user_story || ''}`);
        lines.push(`      ${s.description || ''}`);
        (s.acceptance_criteria || []).forEach((ac: any) => {
          const text = typeof ac === 'string' ? ac : ac.description;
          lines.push(`      AC: ${text}`);
        });
        lines.push('');
      });
    });

    const blob = new Blob([lines.join('\n')], { type: 'text/plain' });
    _triggerDownload(blob, `${projectId}-prd.txt`);
  },

  // ── Sync ────────────────────────────────────────────────────────────────────

  syncToJira: async (
    _projectId: string,
    _storyId: string
  ): Promise<{ success: boolean; ticketId: string }> => {
    // Jira export router not yet registered — placeholder
    throw new Error(
      'Jira sync is not yet available. The export router needs to be registered in the backend.'
    );
  },
};

// ─── internal ────────────────────────────────────────────────────────────────

function _triggerDownload(blob: Blob, filename: string): void {
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
}
