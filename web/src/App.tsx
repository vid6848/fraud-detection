import { BrowserRouter, Route, Routes } from 'react-router-dom'
import { AuthProvider } from './auth/AuthProvider'
import { ProtectedRoute } from './auth/ProtectedRoute'
import { Layout } from './components/Layout'
import { Landing } from './pages/Landing'
import { LiveFeed } from './pages/LiveFeed'
import { Login } from './pages/Login'
import { NotFound } from './pages/NotFound'
import { Placeholder } from './pages/Placeholder'

export function AppRoutes() {
  return (
    <Routes>
      <Route path="/" element={<Landing />} />
      <Route path="/login" element={<Login />} />
      <Route path="/app" element={<ProtectedRoute />}>
        <Route element={<Layout />}>
          <Route index element={<LiveFeed />} />
          <Route path="alerts" element={<Placeholder title="Alerts" description="Review flagged transactions." />} />
          <Route path="model" element={<Placeholder title="Model & system" description="Model quality and API health." />} />
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
        <AppRoutes />
      </AuthProvider>
    </BrowserRouter>
  )
}
