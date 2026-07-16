export interface ApprovalStatus {
  id: string;
  entity_type: 'requirement' | 'user_story';
  entity_id: string;
  status: 'pending' | 'approved' | 'rejected' | 'modify';
  reviewer_id: string;
}
