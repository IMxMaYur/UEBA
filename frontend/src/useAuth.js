// useAuth.js – decodes JWT from localStorage to get role
// Fixes base64-padding issue that caused atob() to throw and sign out users

function safeBase64Decode(str) {
  // Add padding if needed
  const padded = str.replace(/-/g, '+').replace(/_/g, '/')
  const pad = padded.length % 4
  const s = pad ? padded + '='.repeat(4 - pad) : padded
  try {
    return JSON.parse(atob(s))
  } catch {
    return null
  }
}

export function useAuth() {
  const token = localStorage.getItem('ueba_token')
  if (!token) return { role: null, email: null, isAdmin: false, isManager: false, isViewer: false }

  const parts = token.split('.')
  if (parts.length !== 3) return { role: null, email: null, isAdmin: false, isManager: false, isViewer: false }

  const payload = safeBase64Decode(parts[1])
  if (!payload) return { role: null, email: null, isAdmin: false, isManager: false, isViewer: false }

  const role = payload.role ?? 'analyst'
  const email = payload.sub ?? ''

  return {
    role,
    email,
    isAdmin:   role === 'admin',
    isManager: role === 'manager',
    isAnalyst: role === 'analyst',
    isViewer:  role === 'viewer',
  }
}
