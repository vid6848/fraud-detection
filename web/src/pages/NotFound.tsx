import { Link } from 'react-router-dom'
import { EmptyState } from '../components/StateViews'

export function NotFound() {
  return (
    <EmptyState title="Page not found">
      That page doesn’t exist. <Link to="/" className="font-medium text-accent underline">Go to the live feed</Link>
    </EmptyState>
  )
}
