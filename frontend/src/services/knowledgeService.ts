import api from '@/services/api'
import {
  mockListKnowledgeDocuments,
  mockToggleKnowledgeDocument,
  mockUploadKnowledgeDocument,
} from '@/mocks/knowledge'
import type { ApiEnvelope } from '@/types/api'
import type {
  KnowledgeDocumentStatusResponse,
  KnowledgeDocumentStatusUpdate,
  KnowledgeUploadResponse,
  PaginatedKnowledgeDocumentOut,
} from '@/types/knowledge'
import { isMockEnabled } from '@/utils/env'

const KNOWLEDGE_LIST_PAGE_DEFAULT = 1
const KNOWLEDGE_LIST_PAGE_SIZE = 50

function unwrap<T>(envelope: ApiEnvelope<T>): T {
  if (envelope.code !== 200 || envelope.data === null) {
    const error = new Error(envelope.message) as Error & {
      response: { status: number; data: ApiEnvelope<T> }
    }
    error.response = { status: 400, data: envelope }
    throw error
  }
  return envelope.data
}

export async function listKnowledgeDocuments(
  page = KNOWLEDGE_LIST_PAGE_DEFAULT,
  pageSize = KNOWLEDGE_LIST_PAGE_SIZE,
): Promise<PaginatedKnowledgeDocumentOut> {
  if (isMockEnabled()) {
    return unwrap(mockListKnowledgeDocuments(page, pageSize))
  }
  const response = await api.get<ApiEnvelope<PaginatedKnowledgeDocumentOut>>(
    '/knowledge_documents',
    { params: { page, page_size: pageSize } },
  )
  return unwrap(response.data)
}

export async function uploadKnowledgeDocument(file: File): Promise<KnowledgeUploadResponse> {
  if (isMockEnabled()) {
    return unwrap(mockUploadKnowledgeDocument(file))
  }
  const body = new FormData()
  body.append('file', file)
  const response = await api.post<ApiEnvelope<KnowledgeUploadResponse>>(
    '/knowledge_documents',
    body,
  )
  return unwrap(response.data)
}

export async function toggleKnowledgeDocument(
  documentId: number,
  enabled: boolean,
): Promise<KnowledgeDocumentStatusResponse> {
  const body: KnowledgeDocumentStatusUpdate = { enabled }
  if (isMockEnabled()) {
    return unwrap(mockToggleKnowledgeDocument(documentId, body))
  }
  const response = await api.patch<ApiEnvelope<KnowledgeDocumentStatusResponse>>(
    `/knowledge_documents/${documentId}`,
    body,
  )
  return unwrap(response.data)
}
