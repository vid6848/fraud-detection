import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import App from './App'
import './index.css'
import { env } from './lib/env'
import { ConfigMissing } from './pages/ConfigMissing'
import { ThemeProvider } from './theme/ThemeProvider'

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <ThemeProvider>
      {env.ok ? <App /> : <ConfigMissing missing={env.missing} />}
    </ThemeProvider>
  </StrictMode>,
)
