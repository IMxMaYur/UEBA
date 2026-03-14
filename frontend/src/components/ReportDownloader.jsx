import { useState } from 'react'
import { Download, FileText, Table2, Braces } from 'lucide-react'
import api from '../api'

/**
 * ReportDownloader – downloads analytics reports in PDF/CSV/JSON.
 * Props: endpoint (string), reportName (string), data (array, optional – for client-side export)
 */
export default function ReportDownloader({ endpoint, reportName = 'report', data }) {
  const [loading, setLoading] = useState(null)

  const downloadCSV = () => {
    if (!data || data.length === 0) return
    setLoading('csv')
    const keys = Object.keys(data[0])
    const csv = [keys.join(','), ...data.map(row => keys.map(k => JSON.stringify(row[k] ?? '')).join(','))].join('\n')
    const blob = new Blob([csv], { type: 'text/csv' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url; a.download = `${reportName}.csv`; a.click()
    URL.revokeObjectURL(url)
    setLoading(null)
  }

  const downloadJSON = () => {
    if (!data || data.length === 0) return
    setLoading('json')
    const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url; a.download = `${reportName}.json`; a.click()
    URL.revokeObjectURL(url)
    setLoading(null)
  }

  const downloadPDF = async () => {
    if (!endpoint) return
    setLoading('pdf')
    try {
      const res = await api.get(endpoint, { responseType: 'blob' })
      const blob = new Blob([res.data], { type: 'application/pdf' })
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url; a.download = `${reportName}.pdf`; a.click()
      URL.revokeObjectURL(url)
    } catch {
      // If no PDF endpoint available, generate a basic printable HTML report
      window.print()
    }
    setLoading(null)
  }

  const btnStyle = (active) => ({
    display: 'inline-flex', alignItems: 'center', gap: 6,
    padding: '7px 14px', borderRadius: 8, fontSize: 12, fontWeight: 600,
    cursor: active ? 'wait' : 'pointer', border: '1px solid var(--border)',
    background: 'var(--bg-card)', color: 'var(--text-secondary)',
    transition: 'all 0.15s',
  })

  return (
    <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
      <button style={btnStyle(loading === 'pdf')} onClick={downloadPDF} disabled={!!loading}>
        <FileText size={13} color="#ef4444" />
        {loading === 'pdf' ? 'Generating...' : 'Export PDF'}
      </button>
      <button style={btnStyle(loading === 'csv')} onClick={downloadCSV} disabled={!!loading || !data}>
        <Table2 size={13} color="#10b981" />
        {loading === 'csv' ? 'Exporting...' : 'Export CSV'}
      </button>
      <button style={btnStyle(loading === 'json')} onClick={downloadJSON} disabled={!!loading || !data}>
        <Braces size={13} color="#3b82f6" />
        {loading === 'json' ? 'Exporting...' : 'Export JSON'}
      </button>
    </div>
  )
}
