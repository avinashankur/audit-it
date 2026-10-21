import { BrowserRouter, Navigate, Outlet, Route, Routes, useLocation } from 'react-router-dom'
import { SidebarProvider, SidebarInset, SidebarTrigger } from '@/components/ui/sidebar'
import { TooltipProvider } from '@/components/ui/tooltip'
import { AppSidebar } from '@/components/app/app-sidebar'
import { AppBreadcrumbs } from '@/components/app/breadcrumbs'
import { StatusBar } from '@/components/app/page-header'
import { SessionProvider, useSession } from '@/state/session'
import { ThemeProvider } from '@/components/theme-provider'
import { formatTime, plural } from '@/lib/format'
import { Overview } from '@/routes/overview'
import { Filings } from '@/routes/filings'
import { FilingLayout } from '@/routes/filing-layout'
import { FilingOverview } from '@/routes/filing-overview'
import { FilingGraph } from '@/routes/filing-graph'
import { FilingQA } from '@/routes/filing-qa'
import { FilingTables } from '@/routes/filing-tables'
import { Settings } from '@/routes/settings'

function Shell() {
  const { documents, health } = useSession()
  const location = useLocation()
  const match = location.pathname.match(/^\/filings\/([^/]+)/)
  const id = match ? decodeURIComponent(match[1]) : undefined
  const filing = documents.find((d) => d.document_id === id)

  const right = health ? (
    <span className="inline-flex items-center gap-2"><span className="size-1.5 shrink-0 bg-brand" aria-hidden="true" /><span>Engine ready · synced {formatTime()}</span></span>
  ) : (
    <span className="inline-flex items-center gap-2 text-destructive"><span className="size-1.5 shrink-0 bg-destructive" aria-hidden="true" /><span>Engine unreachable</span></span>
  )

  return (
    <SidebarInset className="min-w-0">
      <StatusBar
        left={
          filing ? (
            <>
              {filing.filename.replace(/\.pdf$/i, '')} · {plural(documents.length, 'filing')} indexed
            </>
          ) : (
            <span className="flex items-center gap-3">
              <SidebarTrigger className="-ml-1 size-7" />
              {plural(documents.length, 'filing')} indexed
            </span>
          )
        }
        right={right}
      />
      <main className="mx-auto w-full max-w-6xl p-5 lg:p-10">
        <AppBreadcrumbs />
        <Outlet />
      </main>
    </SidebarInset>
  )
}

export function App() {
  return (
    <ThemeProvider>
      <SessionProvider>
        <BrowserRouter>
          <TooltipProvider>
            <SidebarProvider>
              <AppSidebar />
              <Routes>
                <Route element={<Shell />}>
                  <Route path="/" element={<Overview />} />
                  <Route path="/filings" element={<Filings />} />
                  <Route path="/filings/:id" element={<FilingLayout />}>
                    <Route index element={<FilingOverview />} />
                    <Route path="graph" element={<FilingGraph />} />
                    <Route path="qa" element={<FilingQA />} />
                    <Route path="tables" element={<FilingTables />} />
                  </Route>
                  <Route path="/settings" element={<Settings />} />
                  <Route path="*" element={<Navigate to="/" replace />} />
                </Route>
              </Routes>
            </SidebarProvider>
          </TooltipProvider>
        </BrowserRouter>
      </SessionProvider>
    </ThemeProvider>
  )
}

export default App
