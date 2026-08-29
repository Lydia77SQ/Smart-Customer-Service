import api from '@/services/api'
import {
  mockAcceptTicket,
  mockCloseTicket,
  mockCreateSuggestion,
  mockGetTicket,
  mockListAgentQueue,
  mockListMine,
  mockSendAgentReply,
  mockSendEmployeeMessage,
  mockTransferTicket,
  mockUpdateCategory,
} from '@/mocks/tickets'
import type { ApiEnvelope } from '@/types/api'
import type {
  AgentQueueStatus,
  AgentReplyCreate,
  EmployeeMessageCreate,
  EmployeeMessageResponse,
  MessageOut,
  PaginatedAgentTicketSummary,
  PaginatedTicketSummary,
  SuggestionCreate,
  SuggestionOut,
  TicketCategory,
  TicketDetail,
  TicketSummary,
} from '@/types/ticket'
import { isMockEnabled } from '@/utils/env'

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

export async function listMyTickets(
  page = 1,
  pageSize = 20,
): Promise<PaginatedTicketSummary> {
  if (isMockEnabled()) {
    return unwrap(mockListMine(page, pageSize))
  }
  const response = await api.get<ApiEnvelope<PaginatedTicketSummary>>('/tickets/mine', {
    params: { page, page_size: pageSize },
  })
  return unwrap(response.data)
}

export async function getTicket(ticketId: number): Promise<TicketDetail> {
  if (isMockEnabled()) {
    return unwrap(mockGetTicket(ticketId))
  }
  const response = await api.get<ApiEnvelope<TicketDetail>>(`/tickets/${ticketId}`)
  return unwrap(response.data)
}

export async function sendEmployeeMessage(
  body: EmployeeMessageCreate,
): Promise<EmployeeMessageResponse> {
  if (isMockEnabled()) {
    return unwrap(mockSendEmployeeMessage(body))
  }
  const response = await api.post<ApiEnvelope<EmployeeMessageResponse>>('/tickets/messages', body)
  return unwrap(response.data)
}

export async function transferTicket(ticketId: number): Promise<TicketSummary> {
  if (isMockEnabled()) {
    return unwrap(mockTransferTicket(ticketId))
  }
  const response = await api.post<ApiEnvelope<TicketSummary>>(`/tickets/${ticketId}/transfer`)
  return unwrap(response.data)
}

export async function listAgentQueue(
  status: AgentQueueStatus,
  page = 1,
  pageSize = 20,
): Promise<PaginatedAgentTicketSummary> {
  if (isMockEnabled()) {
    return unwrap(mockListAgentQueue(status, page, pageSize))
  }
  const response = await api.get<ApiEnvelope<PaginatedAgentTicketSummary>>('/tickets/agent-queue', {
    params: { status, page, page_size: pageSize },
  })
  return unwrap(response.data)
}

export async function acceptTicket(ticketId: number): Promise<TicketDetail> {
  if (isMockEnabled()) {
    return unwrap(mockAcceptTicket(ticketId))
  }
  const response = await api.post<ApiEnvelope<TicketDetail>>(`/tickets/${ticketId}/accept`)
  return unwrap(response.data)
}

export async function sendAgentReply(ticketId: number, content: string): Promise<MessageOut> {
  const body: AgentReplyCreate = { content }
  if (isMockEnabled()) {
    return unwrap(mockSendAgentReply(ticketId, body))
  }
  const response = await api.post<ApiEnvelope<MessageOut>>(
    `/tickets/${ticketId}/agent-replies`,
    body,
  )
  return unwrap(response.data)
}

export async function createSuggestion(
  ticketId: number,
  focusMessageId: number | null = null,
): Promise<SuggestionOut> {
  const body: SuggestionCreate = { focus_message_id: focusMessageId }
  if (isMockEnabled()) {
    return unwrap(mockCreateSuggestion(ticketId, body))
  }
  const response = await api.post<ApiEnvelope<SuggestionOut>>(
    `/tickets/${ticketId}/suggestions`,
    body,
  )
  return unwrap(response.data)
}

export async function updateTicketCategory(
  ticketId: number,
  category: TicketCategory,
): Promise<TicketSummary> {
  if (isMockEnabled()) {
    return unwrap(mockUpdateCategory(ticketId, { category }))
  }
  const response = await api.put<ApiEnvelope<TicketSummary>>(`/tickets/${ticketId}/category`, {
    category,
  })
  return unwrap(response.data)
}

export async function closeTicket(ticketId: number): Promise<TicketSummary> {
  if (isMockEnabled()) {
    return unwrap(mockCloseTicket(ticketId))
  }
  const response = await api.post<ApiEnvelope<TicketSummary>>(`/tickets/${ticketId}/close`)
  return unwrap(response.data)
}
