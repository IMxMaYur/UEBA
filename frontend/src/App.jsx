import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import Layout from './components/Layout'
import LoginPage from './pages/LoginPage'
import DashboardPage from './pages/DashboardPage'
import AlertsPage from './pages/AlertsPage'
import UserBehaviorPage from './pages/UserBehaviorPage'
import UsersPage from './pages/UsersPage'
import SimulatePage from './pages/SimulatePage'
import InvestigationPage from './pages/InvestigationPage'

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
          <Route path="alerts"                       element={<AlertsPage />} />
          <Route path="alerts/:alertId/investigate"  element={<InvestigationPage />} />
          <Route path="users"                        element={<UsersPage />} />
          <Route path="users/:userId"                element={<UserBehaviorPage />} />
          <Route path="simulate"                     element={<SimulatePage />} />
        </Route>
      </Routes>
    </BrowserRouter>
  )
}
