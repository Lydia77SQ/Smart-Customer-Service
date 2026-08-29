export type KnowledgeDocumentStatus = 'enabled' | 'disabled' | 'failed' | 'processing'

export interface KnowledgeUploadResponse {
  id: number
  filename: string
  status: KnowledgeDocumentStatus
  updated_at: string
}

export interface KnowledgeDocumentListItem {
  id: number
  filename: string
  status: KnowledgeDocumentStatus
  updated_at: string
}

export interface KnowledgeDocumentStatusResponse {
  id: number
  filename: string
  status: KnowledgeDocumentStatus
  updated_at: string
}

export interface PaginatedKnowledgeDocumentOut {
  items: KnowledgeDocumentListItem[]
  page: number
  page_size: number
  total_items: number
}

export interface KnowledgeDocumentStatusUpdate {
  enabled: boolean
}
