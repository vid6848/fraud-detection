import { Construction } from 'lucide-react'
import { EmptyState } from '../components/StateViews'
import { PageHeader } from '../components/PageHeader'

/** Temporary page body until the real page lands in a later step. */
export function Placeholder({ title, description }: { title: string; description: string }) {
  return (
    <>
      <PageHeader title={title} description={description} />
      <EmptyState title="Coming soon" icon={<Construction className="size-8" />}>
        This page is built in a later step of Phase 6.
      </EmptyState>
    </>
  )
}
