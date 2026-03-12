import { Outlet, NavLink, useNavigate } from 'react-router-dom'
import { Shield, LayoutDashboard, Bell, Zap, LogOut, UserCircle, Users, Search } from 'lucide-react'
import { useAuth } from '../useAuth'

export default function Layout() {
  const navigate = useNavigate()
  const { role, email, isAdmin } = useAuth()
  const logout = () => { localStorage.removeItem('ueba_token'); navigate('/login') }

  const navItems = [
    { to: '/dashboard', icon: LayoutDashboard, label: 'Dashboard',   allowed: true },
    { to: '/alerts',    icon: Bell,            label: 'Alerts',       allowed: true },
    { to: '/users',     icon: Users,           label: 'Users',        allowed: true },
    { to: '/simulate',  icon: Zap,             label: 'Simulate',     allowed: isAdmin },
  ]

  return (
    <div style={{ display: 'flex', height: '100vh', overflow: 'hidden' }}>
      {/* Sidebar */}
      <aside style={{
        width: 240, minWidth: 240,
        background: 'var(--bg-secondary)',
        borderRight: '1px solid var(--border)',
        display: 'flex', flexDirection: 'column',
        padding: '20px 12px',
      }}>
        {/* Logo */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 32, paddingLeft: 4 }}>
          <Shield size={24} color="#3b82f6" />
          <div>
            <div style={{ fontSize: 16, fontWeight: 700, color: 'var(--text-primary)' }}>UEBA</div>
            <div style={{ fontSize: 11, color: 'var(--text-muted)' }}>Insider Threat Platform</div>
          </div>
        </div>

        {/* Navigation */}
        <nav style={{ flex: 1, display: 'flex', flexDirection: 'column', gap: 4 }}>
          {navItems.filter(n => n.allowed).map(({ to, icon: Icon, label }) => (
            <NavLink key={to} to={to} className={({ isActive }) => `nav-item ${isActive ? 'active' : ''}`}>
              <Icon size={16} />
              {label}
            </NavLink>
          ))}
        </nav>

        {/* User info */}
        <div style={{ marginTop: 'auto', borderTop: '1px solid var(--border)', paddingTop: 16 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 10, padding: '8px 4px', marginBottom: 8 }}>
            <UserCircle size={18} color="var(--text-muted)" />
            <div>
              <div style={{ fontSize: 12, fontWeight: 600, color: 'var(--text-secondary)' }}>{email}</div>
              <div style={{ display: 'inline-flex', alignItems: 'center', gap: 4, marginTop: 2 }}>
                <span style={{
                  fontSize: 10, fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.07em',
                  padding: '1px 7px', borderRadius: 999,
                  background: isAdmin ? 'rgba(139,92,246,0.15)' : 'rgba(59,130,246,0.15)',
                  color: isAdmin ? '#8b5cf6' : '#3b82f6',
                  border: `1px solid ${isAdmin ? 'rgba(139,92,246,0.3)' : 'rgba(59,130,246,0.3)'}`,
                }}>
                  {role}
                </span>
              </div>
            </div>
          </div>

          {!isAdmin && (
            <div style={{ fontSize: 10, color: 'var(--text-muted)', padding: '4px 4px 8px', lineHeight: 1.5 }}>
              ⚠ Simulate & admin controls are restricted to admin role.
            </div>
          )}

          <button className="nav-item" onClick={logout}
            style={{ border: 'none', background: 'none', width: '100%', textAlign: 'left', cursor: 'pointer' }}>
            <LogOut size={16} />
            Sign out
          </button>
        </div>
      </aside>

      {/* Main content */}
      <main style={{ flex: 1, overflow: 'auto', padding: '28px 32px' }}>
        <Outlet />
      </main>
    </div>
  )
}
