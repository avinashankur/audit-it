import { useEffect, useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { ArrowRight, FileSpreadsheet, GitFork, MessageSquareText, Search } from 'lucide-react'
import { api } from '@/api/client'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Skeleton } from '@/components/ui/skeleton'
import { Num } from '@/components/app/num'
import { useSession } from '@/state/session'
import { formatCount } from '@/lib/format'
import type { TableData } from '@/types'

const QUICK_QUESTIONS = [
  'What drove the change in operating income?',
  'Trace the factors behind gross margin.',
  'Summarize liquidity and footnote disclosures.',
]

export function FilingOverview() {
  const { id } = useParams()
  const navigate = useNavigate()
  const { documents, settings } = useSession()
  const filing = documents.find((d) => d.document_id === id)

  const [tables, setTables] = useState<TableData[]>([])
  const [loadingTables, setLoadingTables] = useState(true)
  const [inquiry, setInquiry] = useState('')

  useEffect(() => {
    if (!id) return
    let mounted = true
    setLoadingTables(true)
    api
      .getDocumentTables(id)
      .then((res) => {
        if (mounted) setTables(res ?? [])
      })
      .catch((err) => {
        console.error('Failed to load tables preview', err)
      })
      .finally(() => {
        if (mounted) setLoadingTables(false)
      })
    return () => {
      mounted = false
    }
  }, [id])

  if (!filing) return null

  const handleAsk = (text: string) => {
    const q = text.trim()
    if (!q || !id) return
    navigate(`/filings/${id}/qa?q=${encodeURIComponent(q)}`)
  }

  const modelLabel =
    settings.provider === 'Gemini'
      ? 'Gemini 3.8 Flash'
      : settings.provider === 'Offline Grounded'
      ? 'Offline Grounded'
      : settings.provider

  return (
    <div className="flex flex-col gap-10">
      <section aria-labelledby="features-heading">
        <h2 id="features-heading" className="sr-only">
          Analysis Features
        </h2>
        <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
          <Card className="rounded-none border-hairline flex flex-col justify-between">
            <CardHeader className="p-5 pb-3">
              <div className="flex items-center justify-between">
                <span className="inline-flex size-8 items-center justify-center border border-hairline bg-muted/30">
                  <GitFork className="size-4 text-brand" />
                </span>
                <Badge variant="outline" className="rounded-none text-xs">
                  {formatCount(filing.causal_edges_count)} edges
                </Badge>
              </div>
              <CardTitle className="font-serif text-xl mt-3">Causal Graph</CardTitle>
              <CardDescription className="text-xs leading-relaxed">
                Trace causal paths and dependencies connecting financial metrics, revenue drivers, and footnote citations.
              </CardDescription>
            </CardHeader>
            <CardContent className="p-5 pt-0">
              <div className="mb-4 text-xs text-muted-foreground">
                <Num value={formatCount(filing.metric_nodes_count)} /> metric nodes extracted
              </div>
              <Button asChild variant="outline" className="w-full rounded-none justify-between hover:border-brand hover:text-brand">
                <Link to="graph">
                  <span>Explore causal graph</span>
                  <ArrowRight className="size-3.5" />
                </Link>
              </Button>
            </CardContent>
          </Card>

          <Card className="rounded-none border-hairline flex flex-col justify-between">
            <CardHeader className="p-5 pb-3">
              <div className="flex items-center justify-between">
                <span className="inline-flex size-8 items-center justify-center border border-hairline bg-muted/30">
                  <MessageSquareText className="size-4 text-brand" />
                </span>
                <Badge variant="outline" className="rounded-none text-xs">
                  {modelLabel}
                </Badge>
              </div>
              <CardTitle className="font-serif text-xl mt-3">Ask Questions (Q&amp;A)</CardTitle>
              <CardDescription className="text-xs leading-relaxed">
                Query this filing with grounded reasoning. Every answer synthesizes exact page citations without hallucinations.
              </CardDescription>
            </CardHeader>
            <CardContent className="p-5 pt-0">
              <div className="mb-4 text-xs text-muted-foreground">
                {settings.apiKey ? 'BYOK API Key active' : 'Grounding & citations verified'}
              </div>
              <Button asChild variant="outline" className="w-full rounded-none justify-between hover:border-brand hover:text-brand">
                <Link to="qa">
                  <span>Open Q&amp;A console</span>
                  <ArrowRight className="size-3.5" />
                </Link>
              </Button>
            </CardContent>
          </Card>

          <Card className="rounded-none border-hairline flex flex-col justify-between">
            <CardHeader className="p-5 pb-3">
              <div className="flex items-center justify-between">
                <span className="inline-flex size-8 items-center justify-center border border-hairline bg-muted/30">
                  <FileSpreadsheet className="size-4 text-brand" />
                </span>
                <Badge variant="outline" className="rounded-none text-xs">
                  {formatCount(filing.tables_count)} tables
                </Badge>
              </div>
              <CardTitle className="font-serif text-xl mt-3">Financial Tables</CardTitle>
              <CardDescription className="text-xs leading-relaxed">
                Inspect structured balance sheets, income statements, and cash flows with aligned figures and headers.
              </CardDescription>
            </CardHeader>
            <CardContent className="p-5 pt-0">
              <div className="mb-4 text-xs text-muted-foreground">
                {loadingTables ? 'Scanning tables...' : `${tables.length} tables parsed and searchable`}
              </div>
              <Button asChild variant="outline" className="w-full rounded-none justify-between hover:border-brand hover:text-brand">
                <Link to="tables">
                  <span>View financial tables</span>
                  <ArrowRight className="size-3.5" />
                </Link>
              </Button>
            </CardContent>
          </Card>
        </div>
      </section>

      <section aria-labelledby="inquiry-heading" className="border-t border-hairline pt-8">
        <h3 id="inquiry-heading" className="font-serif text-xl">
          Ask an audit question about this filing
        </h3>
        <p className="mt-1 text-xs text-muted-foreground">
          Submit any balance or causal query to jump into Q&amp;A with citations and synthesized analysis.
        </p>

        <form
          className="mt-4 flex gap-2"
          onSubmit={(e) => {
            e.preventDefault()
            handleAsk(inquiry)
          }}
        >
          <div className="relative flex-1">
            <Search className="absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" />
            <Input
              id="filing-quick-inquiry"
              name="filing_quick_inquiry"
              value={inquiry}
              onChange={(e) => setInquiry(e.target.value)}
              placeholder="Ask about a balance, driver, or footnote citation..."
              className="h-11 rounded-none pl-9"
            />
          </div>
          <Button type="submit" size="lg" className="rounded-none" disabled={!inquiry.trim()}>
            Ask
          </Button>
        </form>

        <div className="mt-3 flex flex-wrap items-center gap-2">
          <span className="text-xs text-muted-foreground">Try asking:</span>
          {QUICK_QUESTIONS.map((q) => (
            <button
              key={q}
              type="button"
              onClick={() => handleAsk(q)}
              className="border border-hairline bg-muted/20 px-2.5 py-1 text-xs text-muted-foreground transition-colors hover:border-brand hover:text-foreground cursor-pointer"
            >
              {q}
            </button>
          ))}
        </div>
      </section>

      <section aria-labelledby="tables-heading" className="border-t border-hairline pt-8">
        <div className="flex items-center justify-between">
          <div>
            <h3 id="tables-heading" className="font-serif text-xl">
              Extracted Financial Statements &amp; Tables
            </h3>
            <p className="mt-1 text-xs text-muted-foreground">
              Direct access to all statements identified in this filing.
            </p>
          </div>
          <Button asChild variant="ghost" size="sm" className="rounded-none text-xs">
            <Link to="tables">
              <span>See all {filing.tables_count} tables</span>
              <ArrowRight className="ml-1 size-3.5" />
            </Link>
          </Button>
        </div>

        {loadingTables ? (
          <div className="mt-4 flex flex-col gap-2">
            {[0, 1, 2].map((i) => (
              <Skeleton key={i} className="h-12 w-full rounded-none" />
            ))}
          </div>
        ) : tables.length > 0 ? (
          <div className="mt-4 divide-y divide-hairline border border-hairline">
            {tables.slice(0, 6).map((t, idx) => (
              <div
                key={`${t.page_number}-${idx}`}
                className="flex items-center justify-between p-3.5 text-sm transition-colors hover:bg-muted/30"
              >
                <div className="min-w-0 flex-1 pr-4">
                  <p className="truncate font-medium text-foreground">
                    {t.title || `Table on Page ${t.page_number}`}
                  </p>
                  <p className="text-xs text-muted-foreground">
                    Page {t.page_number} · {t.rows?.length ?? 0} rows · {t.headers?.length ?? 0} columns
                  </p>
                </div>
                <Button asChild variant="outline" size="xs" className="rounded-none text-xs shrink-0">
                  <Link to={`tables?q=${encodeURIComponent(t.title || `page ${t.page_number}`)}`}>
                    View table
                  </Link>
                </Button>
              </div>
            ))}
          </div>
        ) : (
          <p className="mt-4 text-xs text-muted-foreground">No financial tables were identified in this document.</p>
        )}
      </section>
    </div>
  )
}
