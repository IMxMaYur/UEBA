// api.js – Axios client with JWT auth header injection
import axios from 'axios'

const api = axios.create({ baseURL: '/api' })

// Attach token from localStorage to every request
api.interceptors.request.use((config) => {
  const token = localStorage.getItem('ueba_token')
  if (token) config.headers.Authorization = `Bearer ${token}`
  return config
})

// On 401, only redirect to login if it's an auth-related endpoint
// (not for data endpoints — they may return 401 transiently without sign-out intent)
api.interceptors.response.use(
  (res) => res,
  (err) => {
    if (err.response?.status === 401) {
      const url = err.config?.url || ''
      // Only sign out if the request was to an auth endpoint or token-check
      const isAuthEndpoint = url.includes('/auth/') || url.includes('/login')
      if (isAuthEndpoint) {
        localStorage.removeItem('ueba_token')
        window.location.href = '/login'
      }
      // For data endpoints (users, stats, etc.) — just reject, let the component handle it
    }
    return Promise.reject(err)
  }
)

export default api
