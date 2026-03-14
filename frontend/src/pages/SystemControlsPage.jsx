import { useState, useEffect } from 'react'
import { Settings2, Play, Upload, UserPlus, Trash2, RefreshCw, CheckCircle, XCircle, Activity } from 'lucide-react'
import api from '../api'
import { useAuth } from '../useAuth'

function StatusPill({ ok }) {
  return ok
    ? <span style={{ display: 'inline-flex', alignItems: 'center', gap: 5, fontSize: 11, fontWeight: 700, color: '#10b981', padding: '2px 10px', borderRadius: 999, background: 'rgba(16,185,129,0.12)', border: '1px solid rgba(16,185,129,0.3)' }}><CheckCircle size={11} /> Online</span>
    : <span style={{ display: 'inline-flex', alignItems: 'center', gap: 5, fontSize: 11, fontWeight: 700, color: '#ef4444', padding: '2px 10px', borderRadius: 999, background: 'rgba(239,68,68,0.12)', border: '1px solid rgba(239,68,68,0.3)' }}><XCircle size={11} /> Offline</span>
}

export default function SystemControlsPage() {
  const { isAdmin } = useAuth()
  const [health, setHealth]         = useState(null)
  const [metrics, setMetrics]       = useState(null)
  const [runStatus, setRunStatus]   = useState(null)
  const [running, setRunning]       = useState(false)
  const [uploading, setUploading]   = useState(false)
  const [uploadMsg, setUploadMsg]   = useState(null)
  const [users, setUsers]           = useState([])
  const [newUser, setNewUser]       = useState({ email: '', password: '', role: 'analyst' })
  const [saving, setSaving]         = useState(false)
  const [saveMsg, setSaveMsg]       = useState(null)

  useEffect(() => {
    api.get('/health').then(r => setHealth(r.data)).catch(() => setHealth(null))
    api.get('/stats/model-metrics').then(r => setMetrics(r.data)).catch(() => setMetrics(null))
    if (isAdmin) {
      api.get('/users/').then(r => setUsers(r.data || [])).catch(() => setUsers([]))
    }
  }, [isAdmin])

  const runDetection = async () => {
    setRunning(true); setRunStatus(null)
    try {
      const r = await api.post('/simulate/run-detection')
      setRunStatus({ ok: true, msg: r.data?.message || 'Pipeline executed successfully.' })
    } catch (e) {
      setRunStatus({ ok: false, msg: e.response?.data?.detail || 'Pipeline execution failed.' })
    }
    setRunning(false)
  }

  const handleUpload = async (e) => {
    const file = e.target.files[0]
    if (!file) return
    setUploading(true); setUploadMsg(null)
    const form = new FormData()
    form.append('file', file)
    try {
      const r = await api.post('/simulate/upload-dataset', form, { headers: { 'Content-Type': 'multipart/form-data' } })
      setUploadMsg({ ok: true, msg: r.data?.message || 'Dataset uploaded successfully.' })
    } catch (e) {
      setUploadMsg({ ok: false, msg: e.response?.data?.detail || 'Upload failed.' })
    }
    setUploading(false)
    e.target.value = null
  }

  const createUser = async () => {
    if (!newUser.email || !newUser.password) return
    setSaving(true); setSaveMsg(null)
    try {
      await api.post('/auth/register', newUser)
      setSaveMsg({ ok: true, msg: `User ${newUser.email} created.` })
      setNewUser({ email: '', password: '', role: 'analyst' })
      const r = await api.get('/users/')
      setUsers(r.data || [])
    } catch (e) {
      setSaveMsg({ ok: false, msg: e.response?.data?.detail || 'Failed to create user.' })
    }
    setSaving(false)
  }

  const deleteUser = async (email) => {
    if (!window.confirm(`Delete user ${email}?`)) return
    try {
      await api.delete(`/users/${email}`)
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

        {/* ML metrics */}
        {metrics && metrics.roc_auc > 0 && (
          <div className="card">
            <div style={{ fontSize: 13, fontWeight: 700, color: 'var(--text-secondary)', marginBottom: 14 }}>ML MODEL METRICS</div>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10 }}>
              {[
                { label: 'ROC-AUC', value: metrics.roc_auc, color: '#10b981' },
                { label: 'Precision', value: metrics.precision, color: '#3b82f6' },
                { label: 'Recall', value: metrics.recall, color: '#f59e0b' },
                { label: 'F1-Score', value: metrics.f1_score, color: '#8b5cf6' },
              ].map(m => (
                <div key={m.label} style={{ textAlign: 'center', padding: '10px', background: 'var(--bg-secondary)', borderRadius: 8 }}>
                  <div style={{ fontSize: 20, fontWeight: 800, color: m.color }}>{(m.value * 100).toFixed(1)}%</div>
                  <div style={{ fontSize: 10, color: 'var(--text-muted)', marginTop: 2 }}>{m.label}</div>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 20, marginBottom: 20 }}>
        {/* Run detection pipeline */}
        <div className="card">
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 14 }}>
            <Play size={15} color="#3b82f6" />
            <h3 style={{ fontSize: 13, fontWeight: 700, color: 'var(--text-secondary)' }}>RUN ML DETECTION PIPELINE</h3>
          </div>
          <p style={{ fontSize: 12, color: 'var(--text-muted)', marginBottom: 14 }}>
            Trigger anomaly detection on current dataset. Scores and alerts will be updated in the dashboard.
          </p>
          <button onClick={runDetection} disabled={running} className="btn btn-primary" style={{ fontSize: 12 }}>
            {running ? <><RefreshCw size={14} style={{ animation: 'spin 1s linear infinite' }} /> Running...</> : <><Play size={14} /> Run Detection Pipeline</>}
          </button>
          {runStatus && (
            <div style={{ marginTop: 12, fontSize: 12, padding: '8px 12px', borderRadius: 8, background: runStatus.ok ? 'rgba(16,185,129,0.1)' : 'rgba(239,68,68,0.1)', color: runStatus.ok ? '#10b981' : '#ef4444', border: `1px solid ${runStatus.ok ? 'rgba(16,185,129,0.3)' : 'rgba(239,68,68,0.3)'}` }}>
              {runStatus.ok ? '✅' : '❌'} {runStatus.msg}
            </div>
          )}
        </div>

        {/* Dataset upload */}
        <div className="card">
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 14 }}>
            <Upload size={15} color="#8b5cf6" />
            <h3 style={{ fontSize: 13, fontWeight: 700, color: 'var(--text-secondary)' }}>UPLOAD DATASET</h3>
          </div>
          <p style={{ fontSize: 12, color: 'var(--text-muted)', marginBottom: 14 }}>
            Upload a CERT-format CSV file to update the detection dataset.
          </p>
          <label style={{ display: 'inline-flex', alignItems: 'center', gap: 8, padding: '8px 16px', borderRadius: 8, fontSize: 12, fontWeight: 600, cursor: uploading ? 'wait' : 'pointer', border: '1px solid var(--border)', background: 'var(--bg-secondary)', color: 'var(--text-secondary)' }}>
            <Upload size={13} /> {uploading ? 'Uploading...' : 'Choose CSV file'}
            <input type="file" accept=".csv" onChange={handleUpload} hidden disabled={uploading} />
          </label>
          {uploadMsg && (
            <div style={{ marginTop: 12, fontSize: 12, padding: '8px 12px', borderRadius: 8, background: uploadMsg.ok ? 'rgba(16,185,129,0.1)' : 'rgba(239,68,68,0.1)', color: uploadMsg.ok ? '#10b981' : '#ef4444', border: `1px solid ${uploadMsg.ok ? 'rgba(16,185,129,0.3)' : 'rgba(239,68,68,0.3)'}` }}>
              {uploadMsg.ok ? '✅' : '❌'} {uploadMsg.msg}
            </div>
          )}
        </div>
      </div>

      {/* User management */}
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
