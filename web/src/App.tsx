import { BrowserRouter, Route, Routes } from 'react-router-dom'
import { AuthProvider } from './auth/AuthProvider'
import { ProtectedRoute } from './auth/ProtectedRoute'
import { Layout } from './components/Layout'
import { Login } from './pages/Login'
import { NotFound } from './pages/NotFound'
import { Placeholder } from './pages/Placeholder'

export function AppRoutes() {
  return (
    <Routes>
      <Route path="/login" element={<Login />} />
      <Route element={<ProtectedRoute />}>
        <Route element={<Layout />}>
          <Route index element={<Placeholder title="Live feed" description="Transactions scored by the API, as they arrive." />} />
          <Route path="alerts" element={<Placeholder title="Alerts" description="Review flagged transactions." />} />
          <Route path="model" element={<Placeholder title="Model & system" description="Model quality and API health." />} />
          <Route path="*" element={<NotFound />} />
        </Route>
      </Route>
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
