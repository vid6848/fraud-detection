import { Navigate, Outlet, useLocation } from 'react-router-dom'
import { FullPageSpinner } from '../components/StateViews'
import { useAuth } from './context'

/** Renders the child routes only for a signed-in analyst; otherwise goes to /login. */
export function ProtectedRoute() {
  const { session, loading } = useAuth()
  const location = useLocation()
  if (loading) return <FullPageSpinner label="Checking your session…" />
  if (!session) return <Navigate to="/login" replace state={{ from: location.pathname + location.search }} />
  return <Outlet />
}
