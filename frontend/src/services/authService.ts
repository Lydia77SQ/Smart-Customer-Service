import api from '@/services/api'
import { mockLogin, mockLogout, mockMe } from '@/mocks/auth'
import type { ApiEnvelope } from '@/types/api'
import type {
  AuthLoginRequest,
  AuthRegisterRequest,
  AuthRegisterResponse,
  AuthSessionResponse,
  UserPublic,
} from '@/types/auth'
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

export async function login(body: AuthLoginRequest): Promise<AuthSessionResponse> {
  if (isMockEnabled()) {
    return unwrap(mockLogin(body))
  }
  const response = await api.post<ApiEnvelope<AuthSessionResponse>>('/auth/login', body)
  return unwrap(response.data)
}

export async function register(body: AuthRegisterRequest): Promise<AuthRegisterResponse> {
  const response = await api.post<ApiEnvelope<AuthRegisterResponse>>('/auth/register', body)
  return unwrap(response.data)
}

export async function fetchMe(): Promise<UserPublic> {
  if (isMockEnabled()) {
    return unwrap(mockMe())
  }
  const response = await api.get<ApiEnvelope<UserPublic>>('/auth/me')
  return unwrap(response.data)
}

export async function logout(): Promise<void> {
  if (isMockEnabled()) {
    mockLogout()
    return
  }
  await api.post<ApiEnvelope<null>>('/auth/logout')
}
