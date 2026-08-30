import { defineStore } from 'pinia'
import { getTicket, listMyTickets, sendEmployeeMessage, transferTicket } from '@/services/ticketService'
import { useAuthStore } from '@/stores/useAuthStore'
import type { TicketDetail, TicketSummary } from '@/types/ticket'
import { getApiErrorMessage } from '@/utils/error'

export const useTicketStore = defineStore('ticket', {
  state: () => ({
    items: [] as TicketSummary[],
    detail: null as TicketDetail | null,
    composingNew: false,
    listLoading: false,
    sending: false,
    transferring: false,
    errorMessage: '',
  }),
  actions: {
    async loadMine() {
      this.listLoading = true
      this.errorMessage = ''
      try {
        const page = await listMyTickets()
        this.items = page.items
      } catch (error) {
        this.errorMessage = getApiErrorMessage(error)
        throw error
      } finally {
        this.listLoading = false
      }
    },
    startNewConsult() {
      this.composingNew = true
      this.detail = null
      this.errorMessage = ''
    },
    async openTicket(ticketId: number) {
      this.composingNew = false
      this.errorMessage = ''
      try {
        const detail = await getTicket(ticketId)
        const auth = useAuthStore()
        if (auth.user && detail.requester.id !== auth.user.id) {
          this.errorMessage = '资源不存在'
          throw new Error('资源不存在')
        }
        this.detail = detail
      } catch (error) {
        this.errorMessage = getApiErrorMessage(error)
        throw error
      }
    },
    async send(content: string) {
      this.sending = true
      this.errorMessage = ''
      try {
        if (!this.composingNew && this.detail?.status === 'closed') {
          this.errorMessage = '已完结，不能再发送'
          throw new Error('已完结，不能再发送')
        }
        const ticketId = this.composingNew ? null : (this.detail?.id ?? null)
        const result = await sendEmployeeMessage({ content, ticket_id: ticketId })
        this.composingNew = false
        const prior =
          this.detail && this.detail.id === result.ticket.id ? this.detail.messages : []
        const auth = useAuthStore()
        this.detail = {
          ...result.ticket,
          requester: this.detail?.requester ??
            auth.user ?? { id: 0, account: '', display_name: '' },
          messages: [
            ...prior,
            result.employee_message,
            ...(result.system_message ? [result.system_message] : []),
          ],
        }
        await this.loadMine()
        try {
          await this.openTicket(result.ticket.id)
        } catch {
          /* 保留 POST 响应气泡，避免首问对话被详情刷新失败冲掉 */
        }
      } catch (error) {
        this.errorMessage = getApiErrorMessage(error)
        throw error
      } finally {
        this.sending = false
      }
    },
    async transfer() {
      if (!this.detail) return
      this.transferring = true
      this.errorMessage = ''
      try {
        await transferTicket(this.detail.id)
        await this.loadMine()
        await this.openTicket(this.detail.id)
      } catch (error) {
        this.errorMessage = getApiErrorMessage(error)
        throw error
      } finally {
        this.transferring = false
      }
    },
  },
})
