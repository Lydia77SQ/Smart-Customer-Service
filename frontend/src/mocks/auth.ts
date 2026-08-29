import type { ApiEnvelope, ApiErrorBody } from '@/types/api'
import type {
  AuthLoginRequest,
  AuthRegisterRequest,
  AuthRegisterResponse,
  AuthSessionResponse,
  UserPublic,
} from '@/types/auth'

interface MockAccount {
  id: number
  account: string
  password: string
  display_name: string
}

const ACCOUNT_MIN_LENGTH = 3
const ACCOUNT_MAX_LENGTH = 64
const PASSWORD_MIN_LENGTH = 6
const PASSWORD_MAX_LENGTH = 128

const accounts: MockAccount[] = [
  {
    id: 1,
    account: 'wang.li',
    password: 'pass-word-6',
    display_name: '王丽',
  },
  {
    id: 2,
    account: 'chen.hao',
    password: 'pass-word-6',
    display_name: '陈浩',
  },
]

let nextAccountId = 3

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

function isValidAccount(account: string): boolean {
  return account.length >= ACCOUNT_MIN_LENGTH && account.length <= ACCOUNT_MAX_LENGTH
}

function isValidPassword(password: string): boolean {
  return password.length >= PASSWORD_MIN_LENGTH && password.length <= PASSWORD_MAX_LENGTH
}

export function mockLogin(body: AuthLoginRequest): ApiEnvelope<AuthSessionResponse> {
  const matched = accounts.find(
    (item) => item.account === body.account && item.password === body.password,
  )
  if (!matched) {
    httpError(401, {
      code: 'UNAUTHORIZED',
      message: '账号或密码不正确',
      data: null,
    })
  }
  const user: UserPublic = {
    id: matched.id,
    account: matched.account,
    display_name: matched.display_name,
  }
  const data: AuthSessionResponse = {
    token: `mock-session-${matched.id}`,
    user,
  }
  return success(data)
}

export function getMockUserByToken(token: string | null): UserPublic | null {
  if (!token || !token.startsWith('mock-session-')) return null
  const id = Number(token.slice('mock-session-'.length))
  if (!Number.isInteger(id)) return null
  const matched = accounts.find((item) => item.id === id)
  if (!matched) return null
  return {
    id: matched.id,
    account: matched.account,
    display_name: matched.display_name,
  }
}

export function getMockUserPublic(id: number): UserPublic | null {
  const matched = accounts.find((item) => item.id === id)
  if (!matched) return null
  return {
    id: matched.id,
    account: matched.account,
    display_name: matched.display_name,
  }
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

export function mockMe(): ApiEnvelope<UserPublic> {
  return success(requireUser())
}

export function mockLogout(): ApiEnvelope<null> {
  requireUser()
  return success(null)
}

export function mockRegister(body: AuthRegisterRequest): ApiEnvelope<AuthRegisterResponse> {
  if (!isValidAccount(body.account) || !isValidPassword(body.password)) {
    httpError(400, {
      code: 'VALIDATION_ERROR',
      message: '参数验证失败',
      data: null,
    })
  }
  if (accounts.some((item) => item.account === body.account)) {
    httpError(409, {
      code: 'CONFLICT',
      message: '该账号名已被占用',
      data: null,
    })
  }
  const created: MockAccount = {
    id: nextAccountId,
    account: body.account,
    password: body.password,
    display_name: body.account,
  }
  nextAccountId += 1
  accounts.push(created)
  const data: AuthRegisterResponse = {
    id: created.id,
    account: created.account,
    display_name: created.display_name,
  }
  return success(data)
}
