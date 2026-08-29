import { defineStore } from 'pinia'
import {
  listKnowledgeDocuments,
  toggleKnowledgeDocument,
  uploadKnowledgeDocument,
} from '@/services/knowledgeService'
import type {
  KnowledgeDocumentListItem,
  KnowledgeUploadResponse,
} from '@/types/knowledge'
import { getApiErrorMessage } from '@/utils/error'

const INGEST_FAILED_HINT = '入库未生效'
const POLL_INTERVAL_MS = 1000
const POLL_MAX_ATTEMPTS = 30

function wait(ms: number): Promise<void> {
  return new Promise((resolve) => {
    window.setTimeout(resolve, ms)
  })
}

export const useKnowledgeStore = defineStore('knowledge', {
  state: () => ({
    items: [] as KnowledgeDocumentListItem[],
    listLoading: false,
    uploading: false,
    togglingId: null as number | null,
    errorMessage: '',
  }),
  actions: {
    setClientError(message: string) {
      this.errorMessage = message
    },
    async loadList() {
      this.listLoading = true
      this.errorMessage = ''
      try {
        const page = await listKnowledgeDocuments()
        this.items = page.items
      } catch (error) {
        this.errorMessage = getApiErrorMessage(error)
        throw error
      } finally {
        this.listLoading = false
      }
    },
    async pollUntilSettled(documentId: number): Promise<KnowledgeUploadResponse | null> {
      for (let attempt = 0; attempt < POLL_MAX_ATTEMPTS; attempt += 1) {
        const page = await listKnowledgeDocuments()
        this.items = page.items
        const current = page.items.find((item) => item.id === documentId)
        if (!current || current.status !== 'processing') {
          return current ?? null
        }
        await wait(POLL_INTERVAL_MS)
      }
      return this.items.find((item) => item.id === documentId) ?? null
    },
    async upload(file: File) {
      this.uploading = true
      this.errorMessage = ''
      try {
        let uploaded = await uploadKnowledgeDocument(file)
        if (uploaded.status === 'processing') {
          const settled = await this.pollUntilSettled(uploaded.id)
          if (settled) uploaded = settled
        } else {
          const page = await listKnowledgeDocuments()
          this.items = page.items
        }
        if (uploaded.status === 'failed') {
          this.errorMessage = INGEST_FAILED_HINT
        }
      } catch (error) {
        this.errorMessage = getApiErrorMessage(error)
        throw error
      } finally {
        this.uploading = false
      }
    },
    async toggle(documentId: number, enabled: boolean) {
      this.togglingId = documentId
      this.errorMessage = ''
      try {
        const updated = await toggleKnowledgeDocument(documentId, enabled)
        const index = this.items.findIndex((item) => item.id === documentId)
        if (index >= 0) {
          this.items[index] = {
            id: updated.id,
            filename: updated.filename,
            status: updated.status,
            updated_at: updated.updated_at,
          }
        }
      } catch (error) {
        this.errorMessage = getApiErrorMessage(error)
        throw error
      } finally {
        this.togglingId = null
      }
    },
  },
})
