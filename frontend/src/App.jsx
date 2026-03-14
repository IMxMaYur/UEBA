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
import NetworkGraphPage from './pages/NetworkGraphPage'
import IncidentsPage from './pages/IncidentsPage'
import ReportsPage from './pages/ReportsPage'
import SystemControlsPage from './pages/SystemControlsPage'

function ProtectedRoute({ children }) {
  const token = localStorage.getItem('ueba_token')
  return token ? children : <Navigate to="/login" replace />
}

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/login" element={<LoginPage />} />
        <Route path="/" element={<ProtectedRoute><Layout /></ProtectedRoute>}>
          <Route index element={<Navigate to="/dashboard" replace />} />
          <Route path="dashboard"                    element={<DashboardPage />} />
          <Route path="alerts"                       element={<RoleGuard roles={['admin','manager','analyst']}><AlertsPage /></RoleGuard>} />
          <Route path="alerts/:alertId/investigate"  element={<RoleGuard roles={['admin','manager','analyst']}><InvestigationPage /></RoleGuard>} />
          <Route path="users"                        element={<RoleGuard roles={['admin','manager','analyst']}><UsersPage /></RoleGuard>} />
          <Route path="users/:userId"                element={<RoleGuard roles={['admin','manager','analyst']}><UserBehaviorPage /></RoleGuard>} />
          <Route path="behavior-analytics"           element={<RoleGuard roles={['admin','analyst']}><BehaviorAnalyticsPage /></RoleGuard>} />
          <Route path="network-graph"                element={<RoleGuard roles={['admin','analyst']}><NetworkGraphPage /></RoleGuard>} />
          <Route path="incidents"                    element={<RoleGuard roles={['admin','manager','analyst']}><IncidentsPage /></RoleGuard>} />
          <Route path="reports"                      element={<RoleGuard roles={['admin','manager']}><ReportsPage /></RoleGuard>} />
          <Route path="simulate"                     element={<RoleGuard roles={['admin']}><SimulatePage /></RoleGuard>} />
          <Route path="system-controls"              element={<RoleGuard roles={['admin']}><SystemControlsPage /></RoleGuard>} />
        </Route>
      </Routes>
    </BrowserRouter>
  )
}
