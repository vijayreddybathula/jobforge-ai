import { Routes, Route, Navigate } from 'react-router-dom'
import { useAuth } from './contexts/AuthContext'

import ErrorBoundary  from './components/common/ErrorBoundary'
import Shell          from './components/layout/Shell'
import ProtectedRoute from './components/layout/ProtectedRoute'

import LoginPage       from './pages/LoginPage'
import SignupPage      from './pages/SignupPage'
import DashboardPage   from './pages/DashboardPage'
import ResumePage      from './pages/ResumePage'
import RoleConfirmPage from './pages/RoleConfirmPage'
import PreferencesPage from './pages/PreferencesPage'
import JobsPage        from './pages/JobsPage'
import JobDetailPage   from './pages/JobDetailPage'
import ArtifactsPage   from './pages/ArtifactsPage'
import ApplicationsPage from './pages/ApplicationsPage'

export default function App() {
  const { session } = useAuth()

  return (
    <ErrorBoundary>
      <Routes>
        {/* Public */}
        <Route path="/login"  element={session ? <Navigate to="/dashboard" replace /> : <LoginPage />} />
        <Route path="/signup" element={session ? <Navigate to="/dashboard" replace /> : <SignupPage />} />

        {/* Protected — wrapped in Shell */}
        <Route element={<ProtectedRoute><Shell /></ProtectedRoute>}>
          <Route index                       element={<Navigate to="/dashboard" replace />} />
          <Route path="/dashboard"           element={<ErrorBoundary><DashboardPage /></ErrorBoundary>} />
          <Route path="/resume"              element={<ErrorBoundary><ResumePage /></ErrorBoundary>} />
          <Route path="/resume/:id/roles"    element={<ErrorBoundary><RoleConfirmPage /></ErrorBoundary>} />
          <Route path="/preferences"         element={<ErrorBoundary><PreferencesPage /></ErrorBoundary>} />
          <Route path="/jobs"                element={<ErrorBoundary><JobsPage /></ErrorBoundary>} />
          <Route path="/jobs/:id"            element={<ErrorBoundary><JobDetailPage /></ErrorBoundary>} />
          <Route path="/jobs/:id/artifacts"  element={<ErrorBoundary><ArtifactsPage /></ErrorBoundary>} />
          <Route path="/applications"        element={<ErrorBoundary><ApplicationsPage /></ErrorBoundary>} />
        </Route>

        {/* Fallback */}
        <Route path="*" element={<Navigate to={session ? '/dashboard' : '/login'} replace />} />
      </Routes>
    </ErrorBoundary>
  )
}
