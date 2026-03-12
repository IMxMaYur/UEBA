// useAuth.js – decodes JWT from localStorage to get role
export function useAuth() {
  const token = localStorage.getItem('ueba_token')
  if (!token) return { role: null, email: null, isAdmin: false }

  try {
    const payload = JSON.parse(atob(token.split('.')[1]))
    return {
      role: payload.role ?? 'analyst',
      email: payload.sub ?? '',
      isAdmin: payload.role === 'admin',
    }
  } catch {
    return { role: 'analyst', email: '', isAdmin: false }
  }
}
