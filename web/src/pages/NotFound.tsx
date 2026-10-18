import { Link } from 'react-router-dom'
import { EmptyState } from '../components/StateViews'

export function NotFound({ home = '/app', homeLabel = 'Go to the live feed' }: { home?: string; homeLabel?: string }) {
  return (
    <div className="mx-auto max-w-xl py-16">
      <EmptyState title="Page not found" level={1}>
        That page doesn’t exist. <Link to={home} className="font-medium text-accent underline">{homeLabel}</Link>
      </EmptyState>
    </div>
  )
}
