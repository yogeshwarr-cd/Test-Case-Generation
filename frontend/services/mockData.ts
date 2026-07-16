// ─── TypeScript interfaces only — no static mock data ────────────────────────
// All data is fetched dynamically from the backend workflow state.

export type EntityStatus =
  | 'ready'
  | 'needs_review'
  | 'flagged'
  | 'approved'
  | 'rejected'
  | 'ready_for_review'
  | 'needs_ba_review';

export interface ExtractedRequirementCategory {
  id: string;
  title: string;
  items: string[];
}

export interface VersionRecord {
  id: string;
  version: string;
  timestamp: string;
  entityId: string;
  entityType: 'epic' | 'feature' | 'story';
  author: string;
  changes: string;
}

export interface Feature {
  id: string;
  sNo: number;
  epicId: string;
  epicName: string;
  title: string;
  summary: string;
  status: EntityStatus;
}

export interface Epic {
  id: string;
  sNo: number;
  title: string;
  summary: string;
  status: EntityStatus;
  confidenceScore: number;
  version?: number;
}

export interface Story {
  id: string;
  sNo: number;
  epicId: string;
  epicName: string;
  feature: string;
  usId: string;
  summary: string;
  description: string;
  acceptanceCriteria: string[];
  businessRules: string[];
  dependencies: string[];
  comments: string[];
  status: EntityStatus;
  confidenceScore: number;
  validationFinding?: string;
  syncedTo?: { system: 'Jira' | 'ADO'; ticketId: string };
  version?: number;
  priority?: 'HIGH' | 'MEDIUM' | 'LOW';
  storyPoints?: number;
  definitionOfDone?: string[];
  assumptions?: string[];
  risks?: string[];
  requirementMapping?: any[];
  sourceChunkReferences?: any[];
}

export interface SegmentationChunk {
  id: string;
  text: string;
  label: string;
  sectionTitle?: string;
  tokenCount?: number;
}

export interface ProjectHistoryEvent {
  id: string;
  timestamp: string;
  actor: string;
  actorType: 'system' | 'ba';
  target: string;
  summary: string;
  telemetry?: any;
}

export interface ProcessLog {
  id: string;
  message: string;
  agent: string;
  status: 'in-progress' | 'success' | 'failed';
  timestamp: string;
}

// Empty arrays kept as typed constants so existing destructuring imports don't break.
// Pages must not render these — they must fetch real data and show an empty state if none.
export const MOCK_EPICS: Epic[] = [];
export const MOCK_STORIES: Story[] = [];
export const MOCK_FEATURES: Feature[] = [];
export const MOCK_VERSIONS: VersionRecord[] = [];
export const MOCK_HISTORY: ProjectHistoryEvent[] = [];
export const MOCK_EXTRACTED_REQUIREMENTS: ExtractedRequirementCategory[] = [];
