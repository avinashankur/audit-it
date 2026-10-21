import { useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { api } from '@/api/client'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { Empty, EmptyDescription, EmptyHeader, EmptyTitle } from '@/components/ui/empty'
import { BarList, } from '@/components/app/stat-strip'
import { StatStrip } from '@/components/app/stat-strip'
import { InversePanel } from '@/components/app/inverse-panel'
import { Num } from '@/components/app/num'
import { PageHeader, SectionHeading } from '@/components/app/page-header'
import { useSession } from '@/state/session'
import { formatCount, formatDate, plural } from '@/lib/format'
import type { GraphResponseDto } from '@/types'

export function Overview() {
  const { documents, health, settings } = useSession()
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const lead = documents.find((d) => d.document_id === selectedId) ?? documents[0]
  const [graph, setGraph] = useState<GraphResponseDto | null>(null)

  useEffect(() => {
    if (!lead) return setGraph(null)
    const c = new AbortController()
    api
      .getDocumentGraph(lead.document_id, undefined, 1, c.signal)
      .then(setGraph)
      .catch((err) => err?.name !== 'AbortError' && console.error('balances', err))
    return () => c.abort()
  }, [lead?.document_id])

  const totals = useMemo(
    () =>
      documents.reduce(
        (a, d) => ({
          metrics: a.metrics + d.metric_nodes_count,
          footnotes: a.footnotes + d.disclosure_nodes_count,
          edges: a.edges + d.causal_edges_count,
        }),
        { metrics: 0, footnotes: 0, edges: 0 },
      ),
    [documents],
  )

  const balances = useMemo(
    () =>
      (graph?.nodes ?? [])
        .filter((n) => n.type === 'metricNode' && n.data.value != null)
        .sort((a, b) => (b.data.value ?? 0) - (a.data.value ?? 0))
        .slice(0, 6)
        .map((n) => ({
          label: n.data.name.replace(/\s[\d,\s]{4,}$/, ''),
          value: n.data.value ?? 0,
          display: n.data.formatted_value?.replace(/\$/g, '') ?? '',
        })),
    [graph],
  )

  const top = balances[0]

  return (
    <>
      <PageHeader
        title="Overview"
        lede="What the engine has read, and what it found inside it."
        actions={
          documents.length > 1 ? (
            <Select
              value={lead?.document_id}
              onValueChange={(id) => setSelectedId(id)}
            >
              <SelectTrigger className="w-72 sm:w-80 md:w-96 max-w-full" aria-label="Select filing for overview">
                <SelectValue placeholder="Select filing" />
              </SelectTrigger>
              <SelectContent>
                {documents.map((d) => (
                  <SelectItem key={d.document_id} value={d.document_id} title={d.filename.replace(/\.pdf$/i, '')}>
                    {d.filename.replace(/\.pdf$/i, '')}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          ) : undefined
        }
      />

      <InversePanel className="px-6 py-8 lg:px-8">
        <p className="text-xs text-inverse-muted">Headline finding</p>
        <h2 className="mt-4 max-w-md font-serif text-4xl leading-none lg:text-5xl">
          {lead && top
            ? `${top.label} is the largest balance at ${top.display}.`
            : 'Nothing has been read yet.'}
        </h2>
        <p className="mt-3 max-w-prose text-sm text-inverse-muted">
          {lead
            ? `${plural(lead.metric_nodes_count, 'metric')} and ${plural(
                lead.causal_edges_count,
                'causal edge',
              )} extracted from ${lead.filename}.`
            : 'Load a filing to build its graph, extract its tables and enable grounded questions.'}
        </p>
        <div className="mt-6 flex flex-wrap gap-2">
          {lead && (
            <Button
              asChild
              size="lg"
              className="bg-inverse-foreground text-inverse hover:bg-inverse-foreground/85"
            >
              <Link to={`/filings/${lead.document_id}/graph`}>Explore the causal graph</Link>
            </Button>
          )}
          <Button
            asChild
            variant="outline"
            size="lg"
            className="border-inverse-border bg-transparent text-inverse-foreground hover:bg-inverse-foreground/10 dark:bg-transparent"
          >
            <Link to="/filings">Open the filings library</Link>
          </Button>
        </div>
      </InversePanel>

      <StatStrip
        className="mt-8"
        stats={[
          { label: 'Filings ingested', value: formatCount(documents.length) },
          { label: 'Metrics extracted', value: formatCount(totals.metrics) },
          { label: 'Footnotes linked', value: formatCount(totals.footnotes) },
          {
            label: 'Causal edges',
            value: formatCount(totals.edges),
            note: totals.edges === 0 ? 'Set a model provider in Settings' : undefined,
          },
        ]}
      />

      <div className="mt-10 grid grid-cols-1 gap-8 lg:grid-cols-3">
        <section className="min-w-0 lg:col-span-2">
          <SectionHeading>Where the money sits</SectionHeading>
          <CardDescription className="mt-1">
            {lead ? `Largest balances in ${lead.filename}` : 'No filing selected'}
          </CardDescription>
          <div className="mt-4">
            <BarList items={balances} unit="" />
          </div>
        </section>

        <InversePanel className="min-w-0 p-6">
          <SectionHeading>Engine</SectionHeading>
          <p className="mt-1 text-xs text-inverse-muted">
            {health ? 'All services responding' : 'Unreachable at ' + (settings.graphBackend ?? '')}
          </p>
          <dl className="mt-5 grid grid-cols-2 gap-x-4 gap-y-2.5 text-sm">
            {[
              ['Parser', health ? 'Running' : 'Offline'],
              ['Graph builder', health ? 'Running' : 'Offline'],
              ['Adapter', health?.backends_available?.join(', ') ?? '—'],
              ['Reasoning', settings.provider],
              ['Version', health?.version ?? '—'],
            ].map(([k, v]) => (
              <div key={k} className="contents">
                <dt className="text-inverse-muted">{k}</dt>
                <dd className="min-w-0 text-right">{v}</dd>
              </div>
            ))}
          </dl>
        </InversePanel>
      </div>

      <SectionHeading className="mt-12">Recent filings</SectionHeading>
      {documents.length ? (
        <Card className="mt-3 border-0 bg-transparent p-0">
          <CardHeader className="sr-only">
            <CardTitle>Recent filings</CardTitle>
          </CardHeader>
          <CardContent className="p-0">
            <Table>
              <TableHeader>
                <TableRow className="border-border">
                  <TableHead>Filing</TableHead>
                  <TableHead>Period</TableHead>
                  <TableHead className="text-right">Metrics</TableHead>
                  <TableHead className="text-right">Edges</TableHead>
                  <TableHead className="text-right">Ingested</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {documents.slice(0, 5).map((d) => (
                  <TableRow key={d.document_id}>
                    <TableCell className="font-medium">
                      <Link to={`/filings/${d.document_id}`} className="hover:underline">
                        {d.filename.replace(/\.pdf$/i, '')}
                      </Link>
                    </TableCell>
                    <TableCell className="text-muted-foreground">{d.status}</TableCell>
                    <TableCell className="p-0 text-right">
                      <Num value={formatCount(d.metric_nodes_count)} />
                    </TableCell>
                    <TableCell className="p-0 text-right">
                      <Num value={formatCount(d.causal_edges_count)} muted={!d.causal_edges_count} />
                    </TableCell>
                    <TableCell className="p-0 text-right">
                      <Num value={formatDate(d.uploaded_at)} />
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </CardContent>
        </Card>
      ) : (
        <Empty className="mt-3 border border-dashed">
          <EmptyHeader>
            <EmptyTitle>No filings in this session</EmptyTitle>
            <EmptyDescription>
              Ingestion is scoped to the session. Open the library to load a sample or upload a PDF.
            </EmptyDescription>
          </EmptyHeader>
        </Empty>
      )}

      {health === null && (
        <Alert variant="destructive" className="mt-6">
          <AlertDescription>
            The engine could not be reached. Check that the API is running before loading filings.
          </AlertDescription>
        </Alert>
      )}
    </>
  )
}
