export interface DocumentChunk {
  id: string;
  document_id: string;
  content: string;
  chunk_index: number;
  confidence_score: number;
}
