import { Navigate } from 'react-router-dom'
import { useAuth } from '../useAuth'

/**
 * RoleGuard – wraps a route/component with RBAC enforcement.
 * Usage: <RoleGuard roles={['admin']}><AdminPage /></RoleGuard>
 *
 * If the user has NO role (JWT missing/invalid) → redirect to /login
 * If the user has a role but it's not in the allowed list → redirect to /dashboard
 */
export default function RoleGuard({ roles = [], children }) {
  const { role } = useAuth()

  // No valid token / JWT decode failed → send to login
  if (!role) return <Navigate to="/login" replace />

  // Role not in allowed list → send to dashboard
  const allowed = roles.includes(role)
  return allowed ? children : <Navigate to="/dashboard" replace />
}
