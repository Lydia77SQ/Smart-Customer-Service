import { defineStore } from 'pinia'
import { fetchMe } from '@/services/authService'
import type { UserPublic } from '@/types/auth'

const TOKEN_KEY = 'token'
const USER_KEY = 'user'

function readStoredUser(): UserPublic | null {
  const raw = localStorage.getItem(USER_KEY)
  if (!raw) return null
  try {
    const parsed = JSON.parse(raw) as UserPublic
    if (
      typeof parsed.id === 'number' &&
      typeof parsed.account === 'string' &&
      typeof parsed.display_name === 'string'
    ) {
      return parsed
    }
    return null
  } catch {
    return null
  }
}

export const useAuthStore = defineStore('auth', {
  state: () => ({
    token: localStorage.getItem(TOKEN_KEY) || '',
    user: readStoredUser() as UserPublic | null,
  }),
  getters: {
    isAuthenticated: (state) => Boolean(state.token),
  },
  actions: {
    setSession(token: string, user: UserPublic) {
      this.token = token
      this.user = user
      localStorage.setItem(TOKEN_KEY, token)
      localStorage.setItem(USER_KEY, JSON.stringify(user))
    },
    clearSession() {
      this.token = ''
      this.user = null
      localStorage.removeItem(TOKEN_KEY)
      localStorage.removeItem(USER_KEY)
    },
    async restoreSession(): Promise<boolean> {
      const token = this.token || localStorage.getItem(TOKEN_KEY) || ''
      if (!token) {
        this.clearSession()
        return false
      }
      try {
        const user = await fetchMe()
        this.setSession(token, user)
        return true
      } catch (error) {
        const status = (error as { response?: { status?: number } }).response?.status
        if (status === 401 || !this.user) {
          this.clearSession()
          return false
        }
        return true
      }
    },
  },
})
