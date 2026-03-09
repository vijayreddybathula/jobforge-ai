import { Routes, Route, Navigate } from 'react-router-dom'
import { useAuth } from './contexts/AuthContext'

import Shell         from './components/layout/Shell'
import ProtectedRoute from './components/layout/ProtectedRoute'

import LoginPage      from './pages/LoginPage'
import SignupPage     from './pages/SignupPage'
import DashboardPage  from './pages/DashboardPage'
import ResumePage     from './pages/ResumePage'
import RoleConfirmPage from './pages/RoleConfirmPage'
import PreferencesPage from './pages/PreferencesPage'
import JobsPage       from './pages/JobsPage'
import JobDetailPage  from './pages/JobDetailPage'
import ArtifactsPage  from './pages/ArtifactsPage'
import ApplicationsPage from './pages/ApplicationsPage'

export default function App() {
  const { session } = useAuth()

  return (
    <Routes>
      {/* Public */}
      <Route path="/login"  element={session ? <Navigate to="/dashboard" replace /> : <LoginPage />} />
      <Route path="/signup" element={session ? <Navigate to="/dashboard" replace /> : <SignupPage />} />

      {/* Protected — wrapped in Shell */}
      <Route element={<ProtectedRoute><Shell /></ProtectedRoute>}>
        <Route index                         element={<Navigate to="/dashboard" replace />} />
        <Route path="/dashboard"             element={<DashboardPage />} />
        <Route path="/resume"                element={<ResumePage />} />
        <Route path="/resume/:id/roles"      element={<RoleConfirmPage />} />
        <Route path="/preferences"           element={<PreferencesPage />} />
        <Route path="/jobs"                  element={<JobsPage />} />
        <Route path="/jobs/:id"              element={<JobDetailPage />} />
        <Route path="/jobs/:id/artifacts"    element={<ArtifactsPage />} />
        <Route path="/applications"          element={<ApplicationsPage />} />
      </Route>

      {/* Fallback */}
      <Route path="*" element={<Navigate to={session ? '/dashboard' : '/login'} replace />} />
    </Routes>
  )
}
