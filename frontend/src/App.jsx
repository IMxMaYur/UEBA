import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import Layout from './components/Layout'
import RoleGuard from './components/RoleGuard'
import LoginPage from './pages/LoginPage'
import DashboardPage from './pages/DashboardPage'
import AlertsPage from './pages/AlertsPage'
import UserBehaviorPage from './pages/UserBehaviorPage'
import UsersPage from './pages/UsersPage'
import SimulatePage from './pages/SimulatePage'
import InvestigationPage from './pages/InvestigationPage'
import BehaviorAnalyticsPage from './pages/BehaviorAnalyticsPage'
import IncidentsPage from './pages/IncidentsPage'
import ReportsPage from './pages/ReportsPage'
import SystemControlsPage from './pages/SystemControlsPage'

function ProtectedRoute({ children }) {
  const token = localStorage.getItem('ueba_token')
  // No token → always go to login
  return token ? children : <Navigate to="/login" replace />
}

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        {/* Public: login */}
        <Route path="/login" element={<LoginPage />} />

        {/* Redirect bare root → login (LoginPage will redirect to dashboard after auth) */}
        <Route path="/" element={<Navigate to="/login" replace />} />

        {/* Protected app shell */}
        <Route path="/app" element={<ProtectedRoute><Layout /></ProtectedRoute>}>
          <Route index element={<Navigate to="/app/dashboard" replace />} />
          <Route path="dashboard"                    element={<DashboardPage />} />
          <Route path="alerts"                       element={<RoleGuard roles={['admin','manager','analyst']}><AlertsPage /></RoleGuard>} />
          <Route path="alerts/:alertId/investigate"  element={<RoleGuard roles={['admin','manager','analyst']}><InvestigationPage /></RoleGuard>} />
          <Route path="users"                        element={<RoleGuard roles={['admin','manager','analyst']}><UsersPage /></RoleGuard>} />
          <Route path="users/:userId"                element={<RoleGuard roles={['admin','manager','analyst']}><UserBehaviorPage /></RoleGuard>} />
          <Route path="behavior-analytics"           element={<RoleGuard roles={['admin','analyst']}><BehaviorAnalyticsPage /></RoleGuard>} />
          <Route path="incidents"                    element={<RoleGuard roles={['admin','manager','analyst']}><IncidentsPage /></RoleGuard>} />
          <Route path="reports"                      element={<RoleGuard roles={['admin','manager']}><ReportsPage /></RoleGuard>} />
          <Route path="simulate"                     element={<RoleGuard roles={['admin']}><SimulatePage /></RoleGuard>} />
          <Route path="system-controls"              element={<RoleGuard roles={['admin']}><SystemControlsPage /></RoleGuard>} />
        </Route>

        {/* Legacy paths → redirect to new /app/ prefix */}
        <Route path="/dashboard"         element={<Navigate to="/app/dashboard" replace />} />
        <Route path="/alerts/*"          element={<Navigate to="/app/alerts" replace />} />
        <Route path="/users/*"           element={<Navigate to="/app/users" replace />} />
        <Route path="/behavior-analytics" element={<Navigate to="/app/behavior-analytics" replace />} />
        <Route path="/incidents"         element={<Navigate to="/app/incidents" replace />} />
        <Route path="/reports"           element={<Navigate to="/app/reports" replace />} />
        <Route path="/simulate"          element={<Navigate to="/app/simulate" replace />} />
        <Route path="/system-controls"   element={<Navigate to="/app/system-controls" replace />} />

        {/* Catch-all */}
        <Route path="*" element={<Navigate to="/login" replace />} />
      </Routes>
    </BrowserRouter>
  )
}
