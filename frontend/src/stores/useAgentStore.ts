import { defineStore } from 'pinia'
import {
  acceptTicket,
  closeTicket,
  createSuggestion,
  getTicket,
  listAgentQueue,
  sendAgentReply,
  updateTicketCategory,
} from '@/services/ticketService'
import type {
  AgentQueueStatus,
  AgentTicketSummary,
  SuggestionOut,
  TicketCategory,
  TicketDetail,
} from '@/types/ticket'
import { getApiErrorMessage } from '@/utils/error'

export const useAgentStore = defineStore('agent', {
  state: () => ({
    queueItems: [] as AgentTicketSummary[],
    queueStatus: 'pending' as AgentQueueStatus,
    detail: null as TicketDetail | null,
    suggestion: null as SuggestionOut | null,
    suggestionFailed: false,
    queueLoading: false,
    accepting: false,
    sending: false,
    suggesting: false,
    classifying: false,
    closing: false,
    errorMessage: '',
  }),
  actions: {
    async loadQueue(options: { showLoading?: boolean } = {}) {
      const showLoading = options.showLoading ?? true
      if (showLoading) this.queueLoading = true
      this.errorMessage = ''
      try {
        const page = await listAgentQueue(this.queueStatus)
        this.queueItems = page.items.filter(
          (item) => item.status === 'pending' || item.status === 'in_progress',
        )
      } catch (error) {
        this.errorMessage = getApiErrorMessage(error)
        throw error
      } finally {
        this.queueLoading = false
      }
    },
    async switchQueue(status: AgentQueueStatus) {
      this.queueStatus = status
      this.suggestion = null
      this.suggestionFailed = false
      this.queueItems = []
      this.detail = null
      await this.loadQueue()
      const first = this.queueItems[0]
      if (first) {
        await this.openTicket(first.id)
      }
    },
    async openTicket(ticketId: number) {
      this.errorMessage = ''
      this.suggestion = null
      this.suggestionFailed = false
      try {
        this.detail = await getTicket(ticketId)
      } catch (error) {
        this.errorMessage = getApiErrorMessage(error)
        throw error
      }
    },
    async accept() {
      if (!this.detail) return
      this.accepting = true
      this.errorMessage = ''
      try {
        this.detail = await acceptTicket(this.detail.id)
        this.queueStatus = 'in_progress'
        const accepted: AgentTicketSummary = {
          id: this.detail.id,
          title: this.detail.title,
          status: 'in_progress',
          requester: this.detail.requester,
          waiting_minutes: 0,
          updated_at: this.detail.updated_at,
        }
        this.queueItems = [accepted]
        await this.loadQueue({ showLoading: false })
        if (!this.queueItems.some((item) => item.id === accepted.id)) {
          this.queueItems = [accepted, ...this.queueItems]
        }
      } catch (error) {
        this.errorMessage = getApiErrorMessage(error)
        throw error
      } finally {
        this.accepting = false
      }
    },
    async send(content: string) {
      if (!this.detail) return
      if (this.detail.status === 'closed') {
        this.errorMessage = '已完结，不能再发送'
        throw new Error('已完结，不能再发送')
      }
      if (this.detail.status !== 'in_progress') {
        this.errorMessage = '请先接入后再回复'
        throw new Error('请先接入后再回复')
      }
      this.sending = true
      this.errorMessage = ''
      try {
        const message = await sendAgentReply(this.detail.id, content)
        this.detail.messages.push(message)
      } catch (error) {
        this.errorMessage = getApiErrorMessage(error)
        throw error
      } finally {
        this.sending = false
      }
    },
    async fetchSuggestion() {
      if (!this.detail) return
      this.suggesting = true
      this.errorMessage = ''
      this.suggestion = null
      this.suggestionFailed = false
      try {
        const result = await createSuggestion(this.detail.id)
        this.suggestion = result
        this.suggestionFailed = result.result_type === 'degraded'
      } catch (error) {
        this.errorMessage = getApiErrorMessage(error)
        throw error
      } finally {
        this.suggesting = false
      }
    },
    async classify(category: TicketCategory) {
      if (!this.detail) return
      this.classifying = true
      this.errorMessage = ''
      try {
        const summary = await updateTicketCategory(this.detail.id, category)
        this.detail.category = summary.category
        this.detail.updated_at = summary.updated_at
      } catch (error) {
        this.errorMessage = getApiErrorMessage(error)
        throw error
      } finally {
        this.classifying = false
      }
    },
    async close() {
      if (!this.detail) return
      this.closing = true
      this.errorMessage = ''
      try {
        const summary = await closeTicket(this.detail.id)
        this.detail.status = summary.status
        this.detail.updated_at = summary.updated_at
        this.detail.category = summary.category
        await this.loadQueue({ showLoading: false })
      } catch (error) {
        this.errorMessage = getApiErrorMessage(error)
        throw error
      } finally {
        this.closing = false
      }
    },
  },
})
