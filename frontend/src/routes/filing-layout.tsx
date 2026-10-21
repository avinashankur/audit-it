import { Outlet, Link, NavLink, useParams } from 'react-router-dom'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Empty, EmptyDescription, EmptyHeader, EmptyTitle } from '@/components/ui/empty'
import { StatStrip } from '@/components/app/stat-strip'
import { PageHeader } from '@/components/app/page-header'
import { useSession } from '@/state/session'
import { formatCount, formatDate, formatKb, plural } from '@/lib/format'
import { cn } from '@/lib/utils'

export function FilingLayout() {
  const { id } = useParams()
  const { documents } = useSession()
  const filing = documents.find((d) => d.document_id === id)

  if (!filing) {
    return (
      <Empty className="border border-dashed py-16">
        <EmptyHeader>
          <EmptyTitle>Filing not in this session</EmptyTitle>
          <EmptyDescription>
            Ingestion is scoped to the session that performed it. Open the library to load a filing,
            then its graph, tables and questions become available.
          </EmptyDescription>
          <Button asChild className="mt-4">
            <Link to="/filings">Go to filings</Link>
          </Button>
        </EmptyHeader>
      </Empty>
    )
  }

  return (
    <>
      <PageHeader
        title={filing.filename.replace(/\.pdf$/i, '')}
        lede={`${plural(filing.total_pages, 'page')} · ${formatKb(filing.size_kb)} · ingested ${formatDate(
          filing.uploaded_at,
        )}`}
        actions={<Badge variant="secondary">{filing.status}</Badge>}
      />

      <StatStrip
        stats={[
          { label: 'Metrics extracted', value: formatCount(filing.metric_nodes_count) },
          { label: 'Footnotes linked', value: formatCount(filing.disclosure_nodes_count) },
          {
            label: 'Causal edges',
            value: formatCount(filing.causal_edges_count),
            note: filing.causal_edges_count === 0 ? 'No relationships built yet' : undefined,
          },
          { label: 'Tables found', value: formatCount(filing.tables_count) },
        ]}
      />

      <nav aria-label="Filing sections" className="mt-8 flex gap-2 border-b border-hairline">
        <NavLink
          to={`/filings/${filing.document_id}`}
          end
          className={({ isActive }) =>
            cn(
              'border-b-2 px-4 py-2.5 text-sm font-medium transition-colors',
              isActive
                ? 'border-brand font-semibold text-foreground'
                : 'border-transparent text-muted-foreground hover:text-foreground',
            )
          }
        >
          Overview
        </NavLink>
        <NavLink
          to={`/filings/${filing.document_id}/graph`}
          className={({ isActive }) =>
            cn(
              'border-b-2 px-4 py-2.5 text-sm font-medium transition-colors',
              isActive
                ? 'border-brand font-semibold text-foreground'
                : 'border-transparent text-muted-foreground hover:text-foreground',
            )
          }
        >
          Causal graph
        </NavLink>
        <NavLink
          to={`/filings/${filing.document_id}/qa`}
          className={({ isActive }) =>
            cn(
              'border-b-2 px-4 py-2.5 text-sm font-medium transition-colors',
              isActive
                ? 'border-brand font-semibold text-foreground'
                : 'border-transparent text-muted-foreground hover:text-foreground',
            )
          }
        >
          Ask questions (Q&amp;A)
        </NavLink>
        <NavLink
          to={`/filings/${filing.document_id}/tables`}
          className={({ isActive }) =>
            cn(
              'border-b-2 px-4 py-2.5 text-sm font-medium transition-colors',
              isActive
                ? 'border-brand font-semibold text-foreground'
                : 'border-transparent text-muted-foreground hover:text-foreground',
            )
          }
        >
          View tables
        </NavLink>
      </nav>

      <div className="mt-8">
        <Outlet />
      </div>
    </>
  )
}
