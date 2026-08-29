import axios from 'axios'

const api = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || '/api',
  timeout: Number(import.meta.env.VITE_AXIOS_TIMEOUT_MS) || 30000,
})

api.interceptors.request.use((config) => {
  const token = localStorage.getItem('token')
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

function isPublicAuthPath(url: string | undefined): boolean {
  if (!url) return false
  return (
    url.includes('/auth/login') ||
    url.includes('/auth/register') ||
    url.includes('/auth/me')
  )
}

api.interceptors.response.use(
  (response) => response,
  (error: unknown) => {
    const axiosError = error as {
      response?: { status?: number }
      config?: { url?: string }
    }
    if (
      axiosError.response?.status === 401 &&
      !isPublicAuthPath(axiosError.config?.url)
    ) {
      localStorage.removeItem('token')
      localStorage.removeItem('user')
      window.location.href = '/login?state=need-login'
    }
    return Promise.reject(error)
  },
)

export default api
