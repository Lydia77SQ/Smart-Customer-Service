import type { UserPublic } from '@/types/auth'

export type TicketStatus = 'ai_assisting' | 'pending' | 'in_progress' | 'closed'

export type MessageSenderType = 'employee' | 'system' | 'agent'

export type TicketCategory = 'IT-网络' | 'IT-账号' | '行政-工牌' | '行政-场地'

export type QaResultType =
  | 'direct_answer'
  | 'clarification'
  | 'generated_answer'
  | 'degraded'
  | 'none'

export type SuggestionResultType = Exclude<QaResultType, 'none'>

export type AgentQueueStatus = 'pending' | 'in_progress'

export interface TicketSummary {
  id: number
  title: string
  status: TicketStatus
  category: TicketCategory | null
  created_at: string
  updated_at: string
}

export interface MessageOut {
  id: number
  sender_type: MessageSenderType
  content: string
  created_at: string
}

export interface TicketDetail {
  id: number
  title: string
  status: TicketStatus
  category: TicketCategory | null
  created_at: string
  updated_at: string
  requester: UserPublic
  messages: MessageOut[]
}

export interface PaginatedTicketSummary {
  items: TicketSummary[]
  page: number
  page_size: number
  total_items: number
}

export interface EmployeeMessageCreate {
  content: string
  ticket_id: number | null
}

export interface EmployeeMessageResponse {
  ticket: TicketSummary
  employee_message: MessageOut
  system_message: MessageOut | null
  qa_result_type: QaResultType
}

export interface AgentTicketSummary {
  id: number
  title: string
  status: AgentQueueStatus
  requester: UserPublic
  waiting_minutes: number
  updated_at: string
}

export interface PaginatedAgentTicketSummary {
  items: AgentTicketSummary[]
  page: number
  page_size: number
  total_items: number
}

export interface AgentReplyCreate {
  content: string
}

export interface SuggestionCreate {
  focus_message_id: number | null
}

export interface SuggestionOut {
  id: number
  content: string
  result_type: SuggestionResultType
  created_at: string
}

export interface TicketCategoryUpdate {
  category: TicketCategory
}
