import { getMockUserByToken } from '@/mocks/auth'
import type { ApiEnvelope, ApiErrorBody } from '@/types/api'
import type { UserPublic } from '@/types/auth'
import type {
  KnowledgeDocumentListItem,
  KnowledgeDocumentStatus,
  KnowledgeDocumentStatusResponse,
  KnowledgeDocumentStatusUpdate,
  KnowledgeUploadResponse,
  PaginatedKnowledgeDocumentOut,
} from '@/types/knowledge'

const KNOWLEDGE_LIST_PAGE_DEFAULT = 1
const KNOWLEDGE_LIST_PAGE_SIZE = 50
const KNOWLEDGE_MAX_SIZE_BYTES = 20971520

interface KnowledgeDocumentEntity {
  id: number
  filename: string
  status: KnowledgeDocumentStatus
  updated_at: string
  storage_path: string
  created_at: string
}

const documents: KnowledgeDocumentEntity[] = [
  {
    id: 1,
    filename: 'VPN 接入说明.md',
    status: 'enabled',
    updated_at: '2026-08-28T10:20:00Z',
    storage_path: 'data/uploads/1.md',
    created_at: '2026-08-28T10:20:00Z',
  },
  {
    id: 2,
    filename: '工牌补办流程.md',
    status: 'disabled',
    updated_at: '2026-08-27T03:05:00Z',
    storage_path: 'data/uploads/2.md',
    created_at: '2026-08-27T03:05:00Z',
  },
  {
    id: 3,
    filename: '会议室预约须知.md',
    status: 'enabled',
    updated_at: '2026-08-26T01:12:00Z',
    storage_path: 'data/uploads/3.md',
    created_at: '2026-08-26T01:12:00Z',
  },
]

let nextDocumentId = 4

function success<T>(data: T): ApiEnvelope<T> {
  return { code: 200, message: 'ok', data }
}

function httpError(status: number, body: ApiErrorBody): never {
  const error = new Error(body.message) as Error & {
    response: { status: number; data: ApiErrorBody }
  }
  error.response = { status, data: body }
  throw error
}

function requireUser(): UserPublic {
  const user = getMockUserByToken(localStorage.getItem('token'))
  if (!user) {
    httpError(401, {
      code: 'UNAUTHORIZED',
      message: '未认证',
      data: null,
    })
  }
  return user
}

function nowIso(): string {
  return new Date().toISOString().replace(/\.\d{3}Z$/, 'Z')
}

function isMarkdownFilename(filename: string): boolean {
  return filename.toLowerCase().endsWith('.md')
}

function toListItem(doc: KnowledgeDocumentEntity): KnowledgeDocumentListItem {
  return {
    id: doc.id,
    filename: doc.filename,
    status: doc.status,
    updated_at: doc.updated_at,
  }
}

function toUploadResponse(doc: KnowledgeDocumentEntity): KnowledgeUploadResponse {
  return {
    id: doc.id,
    filename: doc.filename,
    status: doc.status,
    updated_at: doc.updated_at,
  }
}

function toStatusResponse(doc: KnowledgeDocumentEntity): KnowledgeDocumentStatusResponse {
  return {
    id: doc.id,
    filename: doc.filename,
    status: doc.status,
    updated_at: doc.updated_at,
  }
}

export function mockListKnowledgeDocuments(
  page = KNOWLEDGE_LIST_PAGE_DEFAULT,
  pageSize = KNOWLEDGE_LIST_PAGE_SIZE,
): ApiEnvelope<PaginatedKnowledgeDocumentOut> {
  requireUser()
  const safePage = page < 1 ? KNOWLEDGE_LIST_PAGE_DEFAULT : page
  const safeSize = pageSize < 1 ? KNOWLEDGE_LIST_PAGE_SIZE : pageSize
  const sorted = [...documents].sort((a, b) => {
    if (a.created_at === b.created_at) return a.id - b.id
    return a.created_at < b.created_at ? -1 : 1
  })
  const start = (safePage - 1) * safeSize
  const items = sorted.slice(start, start + safeSize).map(toListItem)
  const data: PaginatedKnowledgeDocumentOut = {
    items,
    page: safePage,
    page_size: safeSize,
    total_items: documents.length,
  }
  return success(data)
}

export function mockUploadKnowledgeDocument(file: File): ApiEnvelope<KnowledgeUploadResponse> {
  requireUser()
  if (!isMarkdownFilename(file.name)) {
    httpError(400, {
      code: 'VALIDATION_ERROR',
      message: '仅支持 Markdown',
      data: null,
    })
  }
  if (file.size <= 0 || file.size > KNOWLEDGE_MAX_SIZE_BYTES) {
    httpError(400, {
      code: 'VALIDATION_ERROR',
      message: '参数验证失败',
      data: null,
    })
  }
  const createdAt = nowIso()
  const created: KnowledgeDocumentEntity = {
    id: nextDocumentId,
    filename: file.name,
    status: 'enabled',
    updated_at: createdAt,
    storage_path: `data/uploads/${nextDocumentId}.md`,
    created_at: createdAt,
  }
  nextDocumentId += 1
  documents.push(created)
  return success(toUploadResponse(created))
}

export function mockToggleKnowledgeDocument(
  documentId: number,
  body: KnowledgeDocumentStatusUpdate,
): ApiEnvelope<KnowledgeDocumentStatusResponse> {
  requireUser()
  const doc = documents.find((item) => item.id === documentId)
  if (!doc) {
    httpError(404, {
      code: 'NOT_FOUND',
      message: '资源不存在',
      data: null,
    })
  }
  if (doc.status === 'failed' || doc.status === 'processing') {
    httpError(409, {
      code: 'CONFLICT',
      message: '未生效文档不能启停',
      data: null,
    })
  }
  const nextStatus: KnowledgeDocumentStatus = body.enabled ? 'enabled' : 'disabled'
  if (doc.status !== nextStatus) {
    doc.status = nextStatus
    doc.updated_at = nowIso()
  }
  return success(toStatusResponse(doc))
}
