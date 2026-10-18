import { lazy, Suspense } from 'react'
import { BrowserRouter, Route, Routes } from 'react-router-dom'
import { AuthProvider } from './auth/AuthProvider'
import { ProtectedRoute } from './auth/ProtectedRoute'
import { Layout } from './components/Layout'
import { FullPageSpinner } from './components/StateViews'
import { Landing } from './pages/Landing'
import { Login } from './pages/Login'
import { NotFound } from './pages/NotFound'

// Dashboard pages load on demand, so the landing and login pages stay small.
const LiveFeed = lazy(() => import('./pages/LiveFeed').then((m) => ({ default: m.LiveFeed })))
const ModelSystem = lazy(() => import('./pages/ModelSystem').then((m) => ({ default: m.ModelSystem })))
const Alerts = lazy(() => import('./pages/Alerts').then((m) => ({ default: m.Alerts })))

export function AppRoutes() {
  return (
    <Routes>
      <Route path="/" element={<Landing />} />
      <Route path="/login" element={<Login />} />
      <Route path="/app" element={<ProtectedRoute />}>
        <Route element={<Layout />}>
          <Route index element={<LiveFeed />} />
          <Route path="alerts" element={<Alerts />} />
          <Route path="model" element={<ModelSystem />} />
          <Route path="*" element={<NotFound />} />
        </Route>
      </Route>
      <Route path="*" element={<NotFound home="/" homeLabel="Go to the home page" />} />
    </Routes>
  )
}

export default function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <Suspense fallback={<FullPageSpinner label="Loading…" />}>
          <AppRoutes />
        </Suspense>
      </AuthProvider>
    </BrowserRouter>
  )
}
