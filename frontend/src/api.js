// api.js – Axios client with JWT auth header injection
import axios from 'axios'

const api = axios.create({ baseURL: '/api' })

// Attach token from localStorage to every request
api.interceptors.request.use((config) => {
  const token = localStorage.getItem('ueba_token')
  if (token) config.headers.Authorization = `Bearer ${token}`
  return config
})

// On 401, redirect to login
api.interceptors.response.use(
  (res) => res,
  (err) => {
    if (err.response?.status === 401) {
      localStorage.removeItem('ueba_token')
      window.location.href = '/login'
    }
    return Promise.reject(err)
  }
)

export default api
