import { Fragment } from 'react'
import { Link, useLocation } from 'react-router-dom'
import {
  Breadcrumb,
  BreadcrumbItem,
  BreadcrumbLink,
  BreadcrumbList,
  BreadcrumbPage,
  BreadcrumbSeparator,
} from '@/components/ui/breadcrumb'
import { useSession } from '@/state/session'

const SECTION_LABELS: Record<string, string> = {
  graph: 'Causal graph',
  qa: 'Q&A',
  tables: 'Tables',
}

interface Crumb {
  label: string
  to?: string
}

export function AppBreadcrumbs() {
  const { pathname } = useLocation()
  const { documents } = useSession()

  if (pathname === '/') return null

  const segments = pathname.split('/').filter(Boolean)
  const match = pathname.match(/^\/filings\/([^/]+)/)
  const id = match ? decodeURIComponent(match[1]) : undefined
  const filing = id ? documents.find((d) => d.document_id === id) : undefined
  const section = segments[0] === 'filings' && id ? segments[2] : undefined
  const sectionLabel = section ? SECTION_LABELS[section] : undefined
  const crumbs: Crumb[] = [{ label: 'Overview', to: '/' }]

  if (segments[0] === 'filings') {
    crumbs.push({ label: 'Filings', to: '/filings' })

    if (id) {
      crumbs.push({
        label: filing?.filename.replace(/\.pdf$/i, '') ?? 'Filing',
        to: `/filings/${id}`,
      })

      if (sectionLabel) crumbs.push({ label: sectionLabel })
    }
  } else if (segments[0] === 'settings') {
    crumbs.push({ label: 'Settings' })
  }

  if (crumbs.length < 2) return null

  return (
    <Breadcrumb className="mb-6">
      <BreadcrumbList>
        {crumbs.map((crumb, index) => {
          const current = index === crumbs.length - 1

          return (
            <Fragment key={`${crumb.label}-${index}`}>
              <BreadcrumbItem>
                {current || !crumb.to ? (
                  <BreadcrumbPage>{crumb.label}</BreadcrumbPage>
                ) : (
                  <BreadcrumbLink asChild>
                    <Link to={crumb.to}>{crumb.label}</Link>
                  </BreadcrumbLink>
                )}
              </BreadcrumbItem>
              {!current && <BreadcrumbSeparator />}
            </Fragment>
          )
        })}
      </BreadcrumbList>
    </Breadcrumb>
  )
}
