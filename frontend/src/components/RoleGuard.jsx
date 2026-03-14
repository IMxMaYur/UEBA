import { Navigate } from 'react-router-dom'
import { useAuth } from '../useAuth'

/**
 * RoleGuard – wraps a route/component with RBAC enforcement.
 * Usage: <RoleGuard roles={['admin']}><AdminPage /></RoleGuard>
 */
export default function RoleGuard({ roles = [], children, fallback = <Navigate to="/dashboard" replace /> }) {
  const { role } = useAuth()
  if (!role) return fallback
  const allowed = roles.includes(role)
  return allowed ? children : fallback
}
