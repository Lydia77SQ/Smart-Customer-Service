import { defineStore } from 'pinia'
import { getTicket, listMyTickets, sendEmployeeMessage, transferTicket } from '@/services/ticketService'
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
      this.detail = await getTicket(ticketId)
    },
    async send(content: string) {
      this.sending = true
      this.errorMessage = ''
      try {
        const ticketId = this.composingNew ? null : (this.detail?.id ?? null)
        const result = await sendEmployeeMessage({ content, ticket_id: ticketId })
        this.composingNew = false
        await this.loadMine()
        await this.openTicket(result.ticket.id)
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
