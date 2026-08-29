import { getMockUserByToken, getMockUserPublic } from '@/mocks/auth'
import type { ApiEnvelope, ApiErrorBody } from '@/types/api'
import type { UserPublic } from '@/types/auth'
import type {
  AgentQueueStatus,
  AgentReplyCreate,
  AgentTicketSummary,
  EmployeeMessageCreate,
  EmployeeMessageResponse,
  MessageOut,
  PaginatedAgentTicketSummary,
  PaginatedTicketSummary,
  QaResultType,
  SuggestionCreate,
  SuggestionOut,
  SuggestionResultType,
  TicketCategory,
  TicketCategoryUpdate,
  TicketDetail,
  TicketStatus,
  TicketSummary,
} from '@/types/ticket'
import { isoAtShanghai } from '@/utils/datetime'

const TICKET_TITLE_MAX_LENGTH = 80
const EMPLOYEE_MESSAGE_MAX_LENGTH = 4000
const AGENT_MESSAGE_MAX_LENGTH = 4000
const TICKET_LIST_PAGE_DEFAULT = 1
const TICKET_LIST_PAGE_SIZE = 20
const TICKET_LIST_PAGE_SIZE_MAX = 100
const DEGRADED_QA_MESSAGE = '暂时无法自动答疑，请稍后再试，或转人工等待对接人。'
const DEGRADED_SUGGESTION_MESSAGE =
  '暂时无法生成建议。请手写回复，不要向员工发送自动消息。'
const TRANSFER_SUCCESS_MESSAGE = '已提交，等待对接人'
const DIRECT_ANSWER_BADGE = '请到行政前台提交补办申请，携带身份证复印件。'
const CLARIFICATION_VPN = '请补充你用的是 Windows 还是 Mac，以及大约从什么时候开始失败。'
const GENERATED_MEETING =
  '请确认会议室是否已在门户完成预约，并检查投影仪电源与 HDMI 是否接好。'
const VPN_SUGGESTION =
  '请确认是否使用公司门户的 VPN 客户端，并尝试忘记密码后用邮箱验证码重置。'
const TICKET_CATEGORIES: TicketCategory[] = ['IT-网络', 'IT-账号', '行政-工牌', '行政-场地']

interface SuggestionRecord {
  id: number
  ticket_id: number
  content: string
  result_type: SuggestionResultType
  created_at: string
}

interface TicketRecord {
  id: number
  requester_id: number
  title: string
  status: TicketStatus
  category: TicketCategory | null
  created_at: string
  updated_at: string
  messages: MessageOut[]
}

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

function minutesAgoIso(minutes: number): string {
  return new Date(Date.now() - minutes * 60 * 1000).toISOString().replace(/\.\d{3}Z$/, 'Z')
}

function waitingMinutes(updatedAt: string): number {
  return Math.max(0, Math.floor((Date.now() - Date.parse(updatedAt)) / 60000))
}

function toTicketSummary(ticket: TicketRecord): TicketSummary {
  return {
    id: ticket.id,
    title: ticket.title,
    status: ticket.status,
    category: ticket.category,
    created_at: ticket.created_at,
    updated_at: ticket.updated_at,
  }
}

function toMessageOut(message: MessageOut): MessageOut {
  return {
    id: message.id,
    sender_type: message.sender_type,
    content: message.content,
    created_at: message.created_at,
  }
}

function toTicketDetail(ticket: TicketRecord, requester: UserPublic): TicketDetail {
  return {
    id: ticket.id,
    title: ticket.title,
    status: ticket.status,
    category: ticket.category,
    created_at: ticket.created_at,
    updated_at: ticket.updated_at,
    requester: {
      id: requester.id,
      account: requester.account,
      display_name: requester.display_name,
    },
    messages: ticket.messages.map(toMessageOut),
  }
}

function toAgentTicketSummary(ticket: TicketRecord, requester: UserPublic): AgentTicketSummary {
  if (ticket.status !== 'pending' && ticket.status !== 'in_progress') {
    httpError(400, {
      code: 'VALIDATION_ERROR',
      message: '参数验证失败',
      data: null,
    })
  }
  return {
    id: ticket.id,
    title: ticket.title,
    status: ticket.status,
    requester: {
      id: requester.id,
      account: requester.account,
      display_name: requester.display_name,
    },
    waiting_minutes: waitingMinutes(ticket.updated_at),
    updated_at: ticket.updated_at,
  }
}

function toSuggestionOut(record: SuggestionRecord): SuggestionOut {
  return {
    id: record.id,
    content: record.content,
    result_type: record.result_type,
    created_at: record.created_at,
  }
}

function requireRequester(ticket: TicketRecord): UserPublic {
  const owner = getMockUserPublic(ticket.requester_id)
  if (!owner) {
    httpError(404, {
      code: 'NOT_FOUND',
      message: '资源不存在',
      data: null,
    })
  }
  return owner
}

function findTicket(ticketId: number): TicketRecord {
  const ticket = tickets.find((item) => item.id === ticketId)
  if (!ticket) {
    httpError(404, {
      code: 'NOT_FOUND',
      message: '资源不存在',
      data: null,
    })
  }
  return ticket
}

function assertVisibleTicket(ticket: TicketRecord, userId: number): void {
  if (ticket.requester_id === userId) return
  if (ticket.status === 'ai_assisting') {
    httpError(404, {
      code: 'NOT_FOUND',
      message: '资源不存在',
      data: null,
    })
  }
}

const tickets: TicketRecord[] = [
  {
    id: 12,
    requester_id: 1,
    title: 'VPN 连不上公司内网',
    status: 'pending',
    category: null,
    created_at: isoAtShanghai(0, 14, 0, 0),
    updated_at: minutesAgoIso(12),
    messages: [
      {
        id: 101,
        sender_type: 'employee',
        content: '公司 VPN 连不上，提示认证失败。',
        created_at: isoAtShanghai(0, 14, 0, 1),
      },
      {
        id: 102,
        sender_type: 'system',
        content: CLARIFICATION_VPN,
        created_at: isoAtShanghai(0, 14, 0, 8),
      },
      {
        id: 103,
        sender_type: 'employee',
        content: 'Windows。今天早上开始的。',
        created_at: isoAtShanghai(0, 14, 6, 0),
      },
    ],
  },
  {
    id: 8,
    requester_id: 1,
    title: '工牌补办要找谁',
    status: 'closed',
    category: '行政-工牌',
    created_at: isoAtShanghai(1, 9, 40, 0),
    updated_at: isoAtShanghai(1, 9, 40, 0),
    messages: [
      {
        id: 81,
        sender_type: 'employee',
        content: '工牌丢了，补办要找谁？',
        created_at: isoAtShanghai(1, 9, 30, 0),
      },
      {
        id: 82,
        sender_type: 'system',
        content: DIRECT_ANSWER_BADGE,
        created_at: isoAtShanghai(1, 9, 40, 0),
      },
    ],
  },
  {
    id: 99,
    requester_id: 99,
    title: '他不该看见的咨询',
    status: 'ai_assisting',
    category: null,
    created_at: isoAtShanghai(0, 11, 0, 0),
    updated_at: isoAtShanghai(0, 11, 0, 0),
    messages: [
      {
        id: 9901,
        sender_type: 'employee',
        content: '这是其他账号的咨询。',
        created_at: isoAtShanghai(0, 11, 0, 0),
      },
    ],
  },
  {
    id: 15,
    requester_id: 2,
    title: '会议室投影仪没有画面',
    status: 'pending',
    category: null,
    created_at: minutesAgoIso(20),
    updated_at: minutesAgoIso(3),
    messages: [
      {
        id: 151,
        sender_type: 'employee',
        content: '会议室投影仪没有画面。',
        created_at: minutesAgoIso(20),
      },
      {
        id: 152,
        sender_type: 'system',
        content: GENERATED_MEETING,
        created_at: minutesAgoIso(19),
      },
      {
        id: 153,
        sender_type: 'employee',
        content: '已经预约了，还是没画面。',
        created_at: minutesAgoIso(3),
      },
    ],
  },
]

const suggestions: SuggestionRecord[] = []

let nextTicketId = 100
let nextMessageId = 1000
let nextSuggestionId = 1

function findOwnTicket(ticketId: number, userId: number): TicketRecord {
  const ticket = tickets.find((item) => item.id === ticketId)
  if (!ticket || ticket.requester_id !== userId) {
    httpError(404, {
      code: 'NOT_FOUND',
      message: '资源不存在',
      data: null,
    })
  }
  return ticket
}

function inferQa(content: string): { qa_result_type: QaResultType; reply: string } {
  if (content.includes('打印机')) {
    return { qa_result_type: 'degraded', reply: DEGRADED_QA_MESSAGE }
  }
  if (content.includes('工牌')) {
    return { qa_result_type: 'direct_answer', reply: DIRECT_ANSWER_BADGE }
  }
  if (content.includes('会议室')) {
    return { qa_result_type: 'generated_answer', reply: GENERATED_MEETING }
  }
  return { qa_result_type: 'clarification', reply: CLARIFICATION_VPN }
}

export function mockListMine(page = TICKET_LIST_PAGE_DEFAULT, pageSize = TICKET_LIST_PAGE_SIZE): ApiEnvelope<PaginatedTicketSummary> {
  const user = requireUser()
  const size = Math.min(Math.max(pageSize, 1), TICKET_LIST_PAGE_SIZE_MAX)
  const currentPage = Math.max(page, 1)
  const owned = tickets
    .filter((item) => item.requester_id === user.id)
    .sort((a, b) => (a.updated_at < b.updated_at ? 1 : -1))
  const start = (currentPage - 1) * size
  const slice = owned.slice(start, start + size)
  const data: PaginatedTicketSummary = {
    items: slice.map(toTicketSummary),
    page: currentPage,
    page_size: size,
    total_items: owned.length,
  }
  return success(data)
}

export function mockGetTicket(ticketId: number): ApiEnvelope<TicketDetail> {
  const user = requireUser()
  const ticket = findTicket(ticketId)
  assertVisibleTicket(ticket, user.id)
  const owner = requireRequester(ticket)
  return success(toTicketDetail(ticket, owner))
}

export function mockSendEmployeeMessage(
  body: EmployeeMessageCreate,
): ApiEnvelope<EmployeeMessageResponse> {
  const user = requireUser()
  const content = body.content.trim()
  if (!content || content.length > EMPLOYEE_MESSAGE_MAX_LENGTH) {
    httpError(400, {
      code: 'VALIDATION_ERROR',
      message: '参数验证失败',
      data: null,
    })
  }

  const timestamp = nowIso()
  let ticket: TicketRecord
  if (body.ticket_id === null || body.ticket_id === undefined) {
    ticket = {
      id: nextTicketId,
      requester_id: user.id,
      title: content.slice(0, TICKET_TITLE_MAX_LENGTH),
      status: 'ai_assisting',
      category: null,
      created_at: timestamp,
      updated_at: timestamp,
      messages: [],
    }
    nextTicketId += 1
    tickets.push(ticket)
  } else {
    ticket = findOwnTicket(body.ticket_id, user.id)
    if (ticket.status === 'closed') {
      httpError(409, {
        code: 'CONFLICT',
        message: '已完结，不能再发送',
        data: null,
      })
    }
  }

  const employeeMessage: MessageOut = {
    id: nextMessageId,
    sender_type: 'employee',
    content,
    created_at: timestamp,
  }
  nextMessageId += 1
  ticket.messages.push(employeeMessage)
  ticket.updated_at = timestamp

  let systemMessage: MessageOut | null = null
  let qaResultType: QaResultType = 'none'
  if (ticket.status === 'ai_assisting') {
    const inferred = inferQa(content)
    qaResultType = inferred.qa_result_type
    systemMessage = {
      id: nextMessageId,
      sender_type: 'system',
      content: inferred.reply,
      created_at: nowIso(),
    }
    nextMessageId += 1
    ticket.messages.push(systemMessage)
    ticket.updated_at = systemMessage.created_at
  }

  const data: EmployeeMessageResponse = {
    ticket: toTicketSummary(ticket),
    employee_message: toMessageOut(employeeMessage),
    system_message: systemMessage ? toMessageOut(systemMessage) : null,
    qa_result_type: qaResultType,
  }
  return success(data)
}

export function mockTransferTicket(ticketId: number): ApiEnvelope<TicketSummary> {
  const user = requireUser()
  const ticket = findOwnTicket(ticketId, user.id)
  if (ticket.status === 'closed') {
    httpError(409, {
      code: 'CONFLICT',
      message: '已完结，不能转人工',
      data: null,
    })
  }
  if (ticket.status === 'pending' || ticket.status === 'in_progress') {
    httpError(409, {
      code: 'CONFLICT',
      message: '已在人工流程中',
      data: null,
    })
  }
  const timestamp = nowIso()
  ticket.status = 'pending'
  ticket.updated_at = timestamp
  ticket.messages.push({
    id: nextMessageId,
    sender_type: 'system',
    content: TRANSFER_SUCCESS_MESSAGE,
    created_at: timestamp,
  })
  nextMessageId += 1
  return success(toTicketSummary(ticket))
}

export function mockListAgentQueue(
  status: string,
  page = TICKET_LIST_PAGE_DEFAULT,
  pageSize = TICKET_LIST_PAGE_SIZE,
): ApiEnvelope<PaginatedAgentTicketSummary> {
  requireUser()
  if (status !== 'pending' && status !== 'in_progress') {
    httpError(400, {
      code: 'VALIDATION_ERROR',
      message: '参数验证失败',
      data: null,
    })
  }
  const queueStatus = status as AgentQueueStatus
  const size = Math.min(Math.max(pageSize, 1), TICKET_LIST_PAGE_SIZE_MAX)
  const currentPage = Math.max(page, 1)
  const matched = tickets
    .filter(
      (item) =>
        item.status === queueStatus &&
        (item.status === 'pending' || item.status === 'in_progress'),
    )
    .sort((a, b) => (a.updated_at < b.updated_at ? -1 : 1))
  const start = (currentPage - 1) * size
  const slice = matched.slice(start, start + size)
  const items: AgentTicketSummary[] = slice.map((item) =>
    toAgentTicketSummary(item, requireRequester(item)),
  )
  const data: PaginatedAgentTicketSummary = {
    items,
    page: currentPage,
    page_size: size,
    total_items: matched.length,
  }
  return success(data)
}

export function mockAcceptTicket(ticketId: number): ApiEnvelope<TicketDetail> {
  const user = requireUser()
  const ticket = findTicket(ticketId)
  assertVisibleTicket(ticket, user.id)
  if (ticket.status === 'closed' || ticket.status === 'ai_assisting') {
    httpError(409, {
      code: 'CONFLICT',
      message: '当前状态不可接入',
      data: null,
    })
  }
  if (ticket.status === 'pending') {
    ticket.status = 'in_progress'
    ticket.updated_at = nowIso()
  }
  return success(toTicketDetail(ticket, requireRequester(ticket)))
}

export function mockSendAgentReply(
  ticketId: number,
  body: AgentReplyCreate,
): ApiEnvelope<MessageOut> {
  const user = requireUser()
  const content = body.content.trim()
  if (!content || content.length > AGENT_MESSAGE_MAX_LENGTH) {
    httpError(400, {
      code: 'VALIDATION_ERROR',
      message: '参数验证失败',
      data: null,
    })
  }
  const ticket = findTicket(ticketId)
  assertVisibleTicket(ticket, user.id)
  if (ticket.status === 'closed') {
    httpError(409, {
      code: 'CONFLICT',
      message: '已完结，不能再发送',
      data: null,
    })
  }
  if (ticket.status !== 'in_progress') {
    httpError(409, {
      code: 'CONFLICT',
      message: '请先接入后再回复',
      data: null,
    })
  }
  const message: MessageOut = {
    id: nextMessageId,
    sender_type: 'agent',
    content,
    created_at: nowIso(),
  }
  nextMessageId += 1
  ticket.messages.push(message)
  ticket.updated_at = message.created_at
  return success(toMessageOut(message))
}

function inferSuggestion(content: string): { result_type: SuggestionResultType; reply: string } {
  if (content.includes('打印机')) {
    return { result_type: 'degraded', reply: DEGRADED_SUGGESTION_MESSAGE }
  }
  if (content.includes('工牌')) {
    return { result_type: 'direct_answer', reply: DIRECT_ANSWER_BADGE }
  }
  if (content.includes('会议室') || content.includes('投影仪')) {
    return { result_type: 'generated_answer', reply: GENERATED_MEETING }
  }
  return { result_type: 'generated_answer', reply: VPN_SUGGESTION }
}

export function mockCreateSuggestion(
  ticketId: number,
  body: SuggestionCreate,
): ApiEnvelope<SuggestionOut> {
  const user = requireUser()
  const ticket = findTicket(ticketId)
  assertVisibleTicket(ticket, user.id)
  if (ticket.status !== 'in_progress') {
    httpError(409, {
      code: 'CONFLICT',
      message: '仅处理中可获取建议',
      data: null,
    })
  }
  const focused =
    body.focus_message_id === null
      ? [...ticket.messages].reverse().find((item) => item.sender_type === 'employee')
      : ticket.messages.find((item) => item.id === body.focus_message_id)
  const inferred = inferSuggestion(`${focused?.content ?? ''} ${ticket.title}`)
  const record: SuggestionRecord = {
    id: nextSuggestionId,
    ticket_id: ticket.id,
    content: inferred.reply,
    result_type: inferred.result_type,
    created_at: nowIso(),
  }
  nextSuggestionId += 1
  suggestions.push(record)
  return success(toSuggestionOut(record))
}

export function mockUpdateCategory(
  ticketId: number,
  body: TicketCategoryUpdate,
): ApiEnvelope<TicketSummary> {
  const user = requireUser()
  const ticket = findTicket(ticketId)
  assertVisibleTicket(ticket, user.id)
  if (!TICKET_CATEGORIES.includes(body.category)) {
    httpError(400, {
      code: 'VALIDATION_ERROR',
      message: '参数验证失败',
      data: null,
    })
  }
  if (ticket.status !== 'pending' && ticket.status !== 'in_progress') {
    httpError(409, {
      code: 'CONFLICT',
      message: '已完结不能改分类',
      data: null,
    })
  }
  ticket.category = body.category
  ticket.updated_at = nowIso()
  return success(toTicketSummary(ticket))
}

export function mockCloseTicket(ticketId: number): ApiEnvelope<TicketSummary> {
  const user = requireUser()
  const ticket = findTicket(ticketId)
  assertVisibleTicket(ticket, user.id)
  if (ticket.status === 'pending') {
    httpError(409, {
      code: 'CONFLICT',
      message: '未接入不能结单',
      data: null,
    })
  }
  if (ticket.status === 'ai_assisting') {
    httpError(409, {
      code: 'CONFLICT',
      message: '当前状态不可结单',
      data: null,
    })
  }
  if (ticket.status === 'in_progress') {
    ticket.status = 'closed'
    ticket.updated_at = nowIso()
  }
  return success(toTicketSummary(ticket))
}
