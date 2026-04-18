// api.js – Axios client with JWT auth header injection
import axios from 'axios'

const api = axios.create({ baseURL: '/api' })

// Attach token from sessionStorage to every request
api.interceptors.request.use((config) => {
  const token = sessionStorage.getItem('ueba_token')
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
      if (!url.includes('/auth/login')) {
        sessionStorage.removeItem('ueba_token')
        window.location.href = '/login'
      }
    }
    return Promise.reject(err)
  }
)

export default api
