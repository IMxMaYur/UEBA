import { useState, useEffect } from 'react'
import { Settings2, UserPlus, Trash2, RefreshCw, CheckCircle, XCircle, Activity, Database } from 'lucide-react'
import api from '../api'


function StatusPill({ ok }) {
  return ok
    ? <span style={{ display: 'inline-flex', alignItems: 'center', gap: 5, fontSize: 11, fontWeight: 700, color: '#10b981', padding: '2px 10px', borderRadius: 999, background: 'rgba(16,185,129,0.12)', border: '1px solid rgba(16,185,129,0.3)' }}><CheckCircle size={11} /> Online</span>
    : <span style={{ display: 'inline-flex', alignItems: 'center', gap: 5, fontSize: 11, fontWeight: 700, color: '#ef4444', padding: '2px 10px', borderRadius: 999, background: 'rgba(239,68,68,0.12)', border: '1px solid rgba(239,68,68,0.3)' }}><XCircle size={11} /> Offline</span>
}

export default function SystemControlsPage() {
  const [health, setHealth]         = useState(null)
  const [metrics, setMetrics]       = useState(null)
  const [users, setUsers]           = useState([])
  const [newUser, setNewUser]       = useState({ email: '', password: '', role: 'analyst' })
  const [saving, setSaving]         = useState(false)
  const [saveMsg, setSaveMsg]       = useState(null)
  const [resetting, setResetting]   = useState(false)
  const [resetMsg, setResetMsg]     = useState(null)
  const [confirmReset, setConfirmReset] = useState(false)

  useEffect(() => {
    api.get('/health').then(r => setHealth(r.data)).catch(() => setHealth(null))
    api.get('/stats/model-metrics').then(r => setMetrics(r.data)).catch(() => setMetrics(null))
    api.get('/auth/users').then(r => setUsers(r.data || [])).catch(() => setUsers([]))
  }, [])

  const resetData = async () => {
    setResetting(true); setResetMsg(null); setConfirmReset(false)
    try {
      const r = await api.post('/seed/reset')
      setResetMsg({ ok: true, msg: r.data?.message || 'Reset complete.' })
      api.get('/stats/model-metrics').then(r => setMetrics(r.data)).catch(() => {})
    } catch (e) {
      setResetMsg({ ok: false, msg: e.response?.data?.detail || 'Reset failed.' })
    }
    setResetting(false)
  }

  const createUser = async () => {
    if (!newUser.email || !newUser.password) return
    setSaving(true); setSaveMsg(null)
    try {
      await api.post('/auth/users', newUser)
      setSaveMsg({ ok: true, msg: `User ${newUser.email} created.` })
      setNewUser({ email: '', password: '', role: 'analyst' })
      const r = await api.get('/auth/users')
      setUsers(r.data || [])
    } catch (e) {
      setSaveMsg({ ok: false, msg: e.response?.data?.detail || 'Failed to create user.' })
    }
    setSaving(false)
  }

  const deleteUser = async (email) => {
    if (!window.confirm(`Delete user ${email}?`)) return
    try {
      await api.delete(`/auth/users/${email}`)
      setUsers(u => u.filter(x => x.email !== email))
    } catch (e) { console.error(e) }
  }

  const inputStyle = { padding: '8px 12px', background: 'var(--bg-secondary)', border: '1px solid var(--border)', borderRadius: 8, color: 'var(--text-primary)', fontSize: 13, outline: 'none', width: '100%', boxSizing: 'border-box' }

  return (
    <div className="animate-in" style={{ maxWidth: 1100 }}>
      <div style={{ marginBottom: 24 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 4 }}>
          <Settings2 size={20} color="#f97316" />
          <h1 style={{ fontSize: 22, fontWeight: 800 }}>System Controls</h1>
          <span className="badge badge-high">Admin Only</span>
        </div>
        <p style={{ color: 'var(--text-muted)', fontSize: 13 }}>Configure system components, run pipelines, manage users, and upload datasets</p>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 20, marginBottom: 20 }}>
        {/* System health */}
        <div className="card">
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 14 }}>
            <Activity size={15} color="#10b981" />
            <h3 style={{ fontSize: 13, fontWeight: 700, color: 'var(--text-secondary)' }}>SYSTEM HEALTH</h3>
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
              <span style={{ fontSize: 13, color: 'var(--text-secondary)' }}>API Server</span>
              <StatusPill ok={!!health} />
            </div>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
              <span style={{ fontSize: 13, color: 'var(--text-secondary)' }}>ML Models</span>
              <StatusPill ok={!!(metrics && metrics.roc_auc > 0)} />
            </div>
            {metrics && metrics.last_trained && (
              <div style={{ fontSize: 11, color: 'var(--text-muted)', paddingTop: 6, borderTop: '1px solid var(--border)' }}>
                Models last trained: {new Date(metrics.last_trained).toLocaleString()}
              </div>
            )}
          </div>
        </div>

      </div>



      <div className="card" style={{ padding: 0 }}>
        <div style={{ padding: '14px 20px', borderBottom: '1px solid var(--border)', display: 'flex', alignItems: 'center', gap: 8 }}>
          <UserPlus size={15} color="#06b6d4" />
          <h3 style={{ fontSize: 13, fontWeight: 700, color: 'var(--text-secondary)' }}>USER MANAGEMENT</h3>
        </div>

        {/* Create user form */}
        <div style={{ padding: '16px 20px', borderBottom: '1px solid var(--border)' }}>
          <div style={{ fontSize: 12, fontWeight: 600, color: 'var(--text-muted)', marginBottom: 10 }}>CREATE NEW USER</div>
          <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap', alignItems: 'flex-end' }}>
            <div style={{ flex: 1, minWidth: 180 }}>
              <div style={{ fontSize: 11, color: 'var(--text-muted)', marginBottom: 4 }}>Email</div>
              <input style={inputStyle} placeholder="user@company.com" value={newUser.email} onChange={e => setNewUser(u => ({ ...u, email: e.target.value }))} />
            </div>
            <div style={{ flex: 1, minWidth: 140 }}>
              <div style={{ fontSize: 11, color: 'var(--text-muted)', marginBottom: 4 }}>Password</div>
              <input style={inputStyle} type="password" placeholder="••••••••" value={newUser.password} onChange={e => setNewUser(u => ({ ...u, password: e.target.value }))} />
            </div>
            <div style={{ minWidth: 120 }}>
              <div style={{ fontSize: 11, color: 'var(--text-muted)', marginBottom: 4 }}>Role</div>
              <select style={{ ...inputStyle, width: 'auto' }} value={newUser.role} onChange={e => setNewUser(u => ({ ...u, role: e.target.value }))}>
                <option value="analyst">Analyst</option>
                <option value="manager">Manager</option>
                <option value="admin">Admin</option>
                <option value="viewer">Viewer</option>
              </select>
            </div>
            <button onClick={createUser} disabled={saving || !newUser.email || !newUser.password} className="btn btn-primary" style={{ fontSize: 12, padding: '9px 16px' }}>
              <UserPlus size={13} /> {saving ? 'Creating...' : 'Create'}
            </button>
          </div>
          {saveMsg && (
            <div style={{ marginTop: 10, fontSize: 12, padding: '7px 12px', borderRadius: 8, background: saveMsg.ok ? 'rgba(16,185,129,0.1)' : 'rgba(239,68,68,0.1)', color: saveMsg.ok ? '#10b981' : '#ef4444' }}>
              {saveMsg.msg}
            </div>
          )}
        </div>

        {/* User list */}
        <table className="data-table">
          <thead>
            <tr>
              <th>Email</th>
              <th>Role</th>
              <th>Actions</th>
            </tr>
          </thead>
          <tbody>
            {users.length === 0 && (
              <tr><td colSpan={3} style={{ textAlign: 'center', color: 'var(--text-muted)', padding: 32 }}>No users found.</td></tr>
            )}
            {users.map(u => (
              <tr key={u.email}>
                <td style={{ fontFamily: 'JetBrains Mono, monospace', fontSize: 12 }}>{u.email}</td>
                <td>
                  <span style={{ fontSize: 11, fontWeight: 700, textTransform: 'uppercase', padding: '2px 8px', borderRadius: 999,
                    background: u.role === 'admin' ? 'rgba(139,92,246,0.15)' : 'rgba(59,130,246,0.12)',
                    color: u.role === 'admin' ? '#8b5cf6' : '#3b82f6', border: `1px solid ${u.role === 'admin' ? 'rgba(139,92,246,0.3)' : 'rgba(59,130,246,0.3)'}` }}>
                    {u.role}
                  </span>
                </td>
                <td>
                  <button className="btn btn-danger" style={{ fontSize: 11, padding: '4px 10px' }} onClick={() => deleteUser(u.email)}>
                    <Trash2 size={11} /> Delete
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}
