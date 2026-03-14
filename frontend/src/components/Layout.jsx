import { Outlet, NavLink, useNavigate } from 'react-router-dom'
import {
  Shield, LayoutDashboard, Bell, Zap, LogOut, UserCircle,
  Users, TrendingUp, Network, AlertOctagon, FileBarChart,
  Settings2, Settings, ChevronRight,
} from 'lucide-react'
import { useAuth } from '../useAuth'
import { useState, useEffect } from 'react'
import api from '../api'

export default function Layout() {
  const navigate = useNavigate()
  const { role, email, isAdmin } = useAuth()
  const [alertCount, setAlertCount] = useState(0)
  const logout = () => { localStorage.removeItem('ueba_token'); navigate('/login') }

  useEffect(() => {
    api.get('/alerts?status=OPEN&limit=1')
      .then(r => {
        // Try to get total from header or just show if any
        setAlertCount(r.data?.length > 0 ? '!' : 0)
      })
      .catch(() => {})
  }, [])

  const navItems = [
    { to: '/dashboard',           icon: LayoutDashboard, label: 'Dashboard',          allowed: true        },
    { to: '/alerts',              icon: Bell,            label: 'Alerts',              allowed: true,  badge: alertCount },
    { to: '/users',               icon: Users,           label: 'Users',               allowed: true        },
    { to: '/behavior-analytics',  icon: TrendingUp,      label: 'Behavior Analytics',  allowed: true        },
    { to: '/network-graph',       icon: Network,         label: 'Network Graph',        allowed: true        },
    { to: '/incidents',           icon: AlertOctagon,    label: 'Incidents',            allowed: true        },
    { to: '/reports',             icon: FileBarChart,    label: 'Reports',              allowed: true        },
    { to: '/simulate',            icon: Zap,             label: 'Simulate',             allowed: isAdmin     },
    { to: '/system-controls',     icon: Settings2,       label: 'System Controls',      allowed: isAdmin     },
  ]

  const roleColor = role === 'admin' ? '#8b5cf6' : role === 'manager' ? '#06b6d4' : role === 'analyst' ? '#3b82f6' : '#475569'
  const roleBg    = role === 'admin' ? 'rgba(139,92,246,0.15)' : role === 'manager' ? 'rgba(6,182,212,0.15)' : 'rgba(59,130,246,0.15)'

  return (
    <div style={{ display: 'flex', height: '100vh', overflow: 'hidden' }}>
      {/* Sidebar */}
      <aside style={{
        width: 240, minWidth: 240,
        background: 'var(--bg-secondary)',
        borderRight: '1px solid var(--border)',
        display: 'flex', flexDirection: 'column',
        padding: '20px 12px',
        overflowY: 'auto',
      }}>
        {/* Logo */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 28, paddingLeft: 4 }}>
          <div style={{ padding: 8, borderRadius: 10, background: 'rgba(59,130,246,0.15)', border: '1px solid rgba(59,130,246,0.25)' }}>
            <Shield size={20} color="#3b82f6" />
          </div>
          <div>
            <div style={{ fontSize: 15, fontWeight: 800, color: 'var(--text-primary)', letterSpacing: '-0.02em' }}>UEBA</div>
            <div style={{ fontSize: 10, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.08em' }}>Insider Threat</div>
          </div>
        </div>

        {/* Section: MONITORING */}
        <div style={{ fontSize: 10, fontWeight: 700, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.1em', paddingLeft: 8, marginBottom: 6 }}>Monitoring</div>
        <nav style={{ display: 'flex', flexDirection: 'column', gap: 2, marginBottom: 16 }}>
          {navItems.slice(0, 3).filter(n => n.allowed).map(({ to, icon: Icon, label, badge }) => (
            <NavLink key={to} to={to} className={({ isActive }) => `nav-item ${isActive ? 'active' : ''}`}>
              <Icon size={15} />
              <span style={{ flex: 1 }}>{label}</span>
              {badge ? (
                <span style={{ fontSize: 9, fontWeight: 800, background: '#ef4444', color: 'white', borderRadius: 999, padding: '1px 6px' }}>{badge}</span>
              ) : null}
            </NavLink>
          ))}
        </nav>

        {/* Section: ANALYTICS */}
        <div style={{ fontSize: 10, fontWeight: 700, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.1em', paddingLeft: 8, marginBottom: 6 }}>Analytics</div>
        <nav style={{ display: 'flex', flexDirection: 'column', gap: 2, marginBottom: 16 }}>
          {navItems.slice(3, 7).filter(n => n.allowed).map(({ to, icon: Icon, label }) => (
            <NavLink key={to} to={to} className={({ isActive }) => `nav-item ${isActive ? 'active' : ''}`}>
              <Icon size={15} />
              {label}
            </NavLink>
          ))}
        </nav>

        {/* Section: ADMIN (only if isAdmin) */}
        {isAdmin && (
          <>
            <div style={{ fontSize: 10, fontWeight: 700, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.1em', paddingLeft: 8, marginBottom: 6 }}>Administration</div>
            <nav style={{ display: 'flex', flexDirection: 'column', gap: 2, marginBottom: 16 }}>
              {navItems.slice(7).filter(n => n.allowed).map(({ to, icon: Icon, label }) => (
                <NavLink key={to} to={to} className={({ isActive }) => `nav-item ${isActive ? 'active' : ''}`}>
                  <Icon size={15} />
                  {label}
                </NavLink>
              ))}
            </nav>
          </>
        )}

        {/* User info */}
        <div style={{ marginTop: 'auto', borderTop: '1px solid var(--border)', paddingTop: 14 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 10, padding: '8px 4px', marginBottom: 6 }}>
            <div style={{ width: 30, height: 30, borderRadius: '50%', background: roleBg, border: `1px solid ${roleColor}40`, display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0 }}>
              <UserCircle size={16} color={roleColor} />
            </div>
            <div style={{ minWidth: 0 }}>
              <div style={{ fontSize: 11, fontWeight: 600, color: 'var(--text-secondary)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{email}</div>
              <span style={{
                fontSize: 9, fontWeight: 800, textTransform: 'uppercase', letterSpacing: '0.07em',
                padding: '1px 7px', borderRadius: 999,
                background: roleBg, color: roleColor, border: `1px solid ${roleColor}40`,
              }}>
                {role}
              </span>
            </div>
          </div>

          <button className="nav-item" onClick={logout}
            style={{ border: 'none', background: 'none', width: '100%', textAlign: 'left', cursor: 'pointer', color: '#475569' }}>
            <LogOut size={15} />
            Sign out
          </button>
        </div>
      </aside>

      {/* Main content area */}
      <div style={{ flex: 1, display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
        {/* Top Navigation Bar */}
        <header style={{
          height: 54, minHeight: 54,
          background: 'var(--bg-secondary)',
          borderBottom: '1px solid var(--border)',
          display: 'flex', alignItems: 'center',
          padding: '0 24px', gap: 16,
        }}>
          {/* System name */}
          <div style={{ fontSize: 13, fontWeight: 700, color: 'var(--text-muted)', letterSpacing: '0.04em' }}>
            🛡️ UEBA — Insider Threat Detection Platform
          </div>

          <div style={{ flex: 1 }} />

          {/* Live indicator */}
          <div style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 11, color: '#10b981' }}>
            <span style={{ display: 'inline-block', width: 7, height: 7, borderRadius: '50%', background: '#10b981', boxShadow: '0 0 6px #10b981' }} />
            System Active
          </div>

          {/* Alert bell */}
          <button
            onClick={() => navigate('/alerts')}
            style={{ position: 'relative', background: 'none', border: '1px solid var(--border)', borderRadius: 8, padding: '6px 10px', cursor: 'pointer', display: 'flex', alignItems: 'center', gap: 6, color: 'var(--text-secondary)', fontSize: 12, fontWeight: 600 }}>
            <Bell size={14} color={alertCount ? '#ef4444' : 'var(--text-muted)'} />
            Alerts
            {alertCount ? (
              <span style={{ position: 'absolute', top: -4, right: -4, fontSize: 9, fontWeight: 800, background: '#ef4444', color: 'white', borderRadius: '50%', width: 14, height: 14, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>!</span>
            ) : null}
          </button>

          {/* Role badge */}
          <span style={{ fontSize: 10, fontWeight: 800, textTransform: 'uppercase', letterSpacing: '0.07em', padding: '3px 10px', borderRadius: 999, background: roleBg, color: roleColor, border: `1px solid ${roleColor}40` }}>
            {role}
          </span>

          {/* Profile */}
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: 12, color: 'var(--text-muted)' }}>
            <UserCircle size={18} />
            <span style={{ maxWidth: 120, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{email}</span>
          </div>
        </header>

        {/* Page content */}
        <main style={{ flex: 1, overflow: 'auto', padding: '28px 32px' }}>
          <Outlet />
        </main>
      </div>
    </div>
  )
}
