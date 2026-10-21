import { useMemo, useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import { Loader2, MoreHorizontal } from 'lucide-react'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent } from '@/components/ui/card'
import {
  Dialog,
  DialogClose,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { Input } from '@/components/ui/input'
import { Progress } from '@/components/ui/progress'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Skeleton } from '@/components/ui/skeleton'
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { Empty, EmptyDescription, EmptyHeader, EmptyTitle } from '@/components/ui/empty'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuGroup,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import { Num } from '@/components/app/num'
import { StatStrip } from '@/components/app/stat-strip'
import { PageHeader } from '@/components/app/page-header'
import { useSession } from '@/state/session'
import { formatCount, formatDate, formatKb, plural } from '@/lib/format'

export function Filings() {
  const { documents, samples, busy, job, ingestingName, error, loadSample, upload, remove, clearError } =
    useSession()
  const fileRef = useRef<HTMLInputElement>(null)
  const [query, setQuery] = useState('')
  const [loadingSample, setLoadingSample] = useState<string | null>(null)
  const [deleting, setDeleting] = useState<string | null>(null)
  const [docToDelete, setDocToDelete] = useState<{ id: string; name: string } | null>(null)

  const handleLoadSample = async (val: string) => {
    setLoadingSample(val)
    try {
      await loadSample(val)
    } finally {
      setLoadingSample(null)
    }
  }

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase()
    return q ? documents.filter((d) => d.filename.toLowerCase().includes(q)) : documents
  }, [documents, query])

  const totals = useMemo(
    () =>
      documents.reduce(
        (a, d) => ({
          pages: a.pages + d.total_pages,
          metrics: a.metrics + d.metric_nodes_count,
          tables: a.tables + d.tables_count,
        }),
        { pages: 0, metrics: 0, tables: 0 },
      ),
    [documents],
  )

  const confirmDelete = async (docId: string) => {
    setDeleting(docId)
    await remove(docId)
    setDeleting(null)
  }

  return (
    <>
      <PageHeader
        title="Filings"
        lede="Every document the engine has read in this session, and what it found inside."
        actions={
          <div className="flex flex-wrap items-center gap-2">
            {samples.length > 0 && (
              <Select
                value=""
                disabled={busy || !!loadingSample}
                onValueChange={(val) => val && void handleLoadSample(val)}
              >
                <SelectTrigger
                  className="w-72 sm:w-80 md:w-96 max-w-full rounded-none"
                  aria-label="Load sample filing"
                >
                  {loadingSample || (busy && ingestingName) ? (
                    <div className="flex items-center gap-2 truncate text-foreground font-medium">
                      <Loader2 className="size-4 animate-spin shrink-0 text-muted-foreground" />
                      <span className="truncate">
                        Loading {(loadingSample || ingestingName || 'sample').replace(/\.pdf$/i, '')}...
                      </span>
                    </div>
                  ) : (
                    <SelectValue placeholder="Load sample filing" />
                  )}
                </SelectTrigger>
                <SelectContent>
                  {samples.map((s) => (
                    <SelectItem key={s.name} value={s.name} title={s.name.replace(/\.pdf$/i, '')}>
                      {s.name.replace(/\.pdf$/i, '')}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            )}
            <input
              ref={fileRef}
              id="filing-upload"
              name="filing_upload"
              type="file"
              accept=".pdf"
              className="hidden"
              onChange={(e) => {
                const f = e.target.files?.[0]
                if (f) void upload(f)
                if (fileRef.current) fileRef.current.value = ''
              }}
            />
            <Button
              size="lg"
              className="rounded-none"
              disabled={busy || !!loadingSample}
              onClick={() => fileRef.current?.click()}
            >
              {busy && !loadingSample && ingestingName && !ingestingName.endsWith('.pdf') ? (
                <div className="flex items-center gap-2">
                  <Loader2 className="size-4 animate-spin" />
                  <span>Uploading...</span>
                </div>
              ) : (
                'Upload filing'
              )}
            </Button>
          </div>
        }
      />

      <StatStrip
        stats={[
          { label: 'Filings', value: formatCount(documents.length) },
          { label: 'Pages read', value: formatCount(totals.pages) },
          { label: 'Metrics extracted', value: formatCount(totals.metrics) },
          { label: 'Tables found', value: formatCount(totals.tables) },
        ]}
      />

      {error && (
        <Alert variant="destructive" className="mt-6">
          <AlertTitle>Ingestion problem</AlertTitle>
          <AlertDescription className="flex flex-wrap items-center justify-between gap-4">
            <span>{error}</span>
            <Button variant="ghost" size="sm" onClick={clearError}>
              Dismiss
            </Button>
          </AlertDescription>
        </Alert>
      )}

      {(busy || !!loadingSample || (job && job.status === 'PROCESSING')) && (
        <Card className="mt-6 rounded-none border-hairline bg-card">
          <CardContent className="p-4">
            <div className="flex items-center justify-between gap-4 text-sm">
              <span className="truncate font-medium">
                {loadingSample || ingestingName
                  ? `Loading sample filing: ${(loadingSample || ingestingName || '').replace(/\.pdf$/i, '')}`
                  : `Ingesting ${job?.filename ?? 'filing'}`}
              </span>
              <span className="text-xs text-muted-foreground shrink-0">
                {job?.stage ? `${job.stage} ${job.progress ?? 0}%` : 'Parsing tables & extracting metrics...'}
              </span>
            </div>
            <Progress
              value={job?.progress ?? 35}
              className="mt-3 h-1 rounded-none [&>div]:transition-all [&>div]:duration-300"
            />
          </CardContent>
        </Card>
      )}

      <div className="mt-8 min-w-0">
        <div className="mb-3 flex flex-wrap items-center justify-between gap-4">
            <p className="text-sm text-muted-foreground">
              {query
                ? `${formatCount(filtered.length)} of ${formatCount(documents.length)} match`
                : plural(documents.length, 'filing')}
            </p>
            <Input
              aria-label="Search filings"
              name="filing_search"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Search filings"
              className="w-64"
            />
          </div>

          {busy && !job ? (
            <div className="flex flex-col gap-2">
              {[0, 1, 2, 3].map((i) => (
                <Skeleton key={i} className="h-11 w-full" />
              ))}
            </div>
          ) : filtered.length ? (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Filing</TableHead>
                  <TableHead className="w-24">Status</TableHead>
                  <TableHead className="text-right">Pages</TableHead>
                  <TableHead className="text-right">Metrics</TableHead>
                  <TableHead className="text-right">Footnotes</TableHead>
                  <TableHead className="text-right">Edges</TableHead>
                  <TableHead className="text-right">Tables</TableHead>
                  <TableHead className="text-right">Size</TableHead>
                  <TableHead className="text-right">Ingested</TableHead>
                  <TableHead className="w-12">
                    <span className="sr-only">Actions</span>
                  </TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {filtered.map((d) => (
                  <TableRow key={d.document_id}>
                    <TableCell className="max-w-64 truncate font-medium">
                      <Link to={`/filings/${d.document_id}`} className="hover:underline">
                        {d.filename}
                      </Link>
                    </TableCell>
                    <TableCell>
                      <Badge variant={d.status === 'Ready' ? 'secondary' : 'outline'} className="rounded-none">
                        {d.status}
                      </Badge>
                    </TableCell>
                    <TableCell className="text-right">
                      <Num value={formatCount(d.total_pages)} />
                    </TableCell>
                    <TableCell className="text-right">
                      <Num value={formatCount(d.metric_nodes_count)} />
                    </TableCell>
                    <TableCell className="text-right">
                      <Num
                        value={formatCount(d.disclosure_nodes_count)}
                        muted={!d.disclosure_nodes_count}
                      />
                    </TableCell>
                    <TableCell className="text-right">
                      <Num value={formatCount(d.causal_edges_count)} muted={!d.causal_edges_count} />
                    </TableCell>
                    <TableCell className="text-right">
                      <Num value={formatCount(d.tables_count)} />
                    </TableCell>
                    <TableCell className="text-right">
                      <Num value={formatKb(d.size_kb)} />
                    </TableCell>
                    <TableCell className="text-right">
                      <Num value={formatDate(d.uploaded_at)} muted />
                    </TableCell>
                    <TableCell className="text-right">
                      <DropdownMenu>
                        <DropdownMenuTrigger asChild>
                          <Button variant="ghost" size="icon-sm" aria-label={`Actions for ${d.filename}`}>
                            <MoreHorizontal />
                          </Button>
                        </DropdownMenuTrigger>
                        <DropdownMenuContent align="end">
                          <DropdownMenuGroup>
                            <DropdownMenuItem asChild>
                              <Link to={`/filings/${d.document_id}`}>Open overview</Link>
                            </DropdownMenuItem>
                            <DropdownMenuItem asChild>
                              <Link to={`/filings/${d.document_id}/graph`}>Open causal graph</Link>
                            </DropdownMenuItem>
                            <DropdownMenuItem asChild>
                              <Link to={`/filings/${d.document_id}/tables`}>View tables</Link>
                            </DropdownMenuItem>
                            <DropdownMenuItem asChild>
                              <Link to={`/filings/${d.document_id}/qa`}>Ask questions</Link>
                            </DropdownMenuItem>
                          </DropdownMenuGroup>
                          <DropdownMenuSeparator />
                          <DropdownMenuItem
                            variant="destructive"
                            onSelect={() => setDocToDelete({ id: d.document_id, name: d.filename })}
                          >
                            Remove filing
                          </DropdownMenuItem>
                        </DropdownMenuContent>
                      </DropdownMenu>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          ) : (
            <Empty className="border border-dashed py-16">
              <EmptyHeader>
                <EmptyTitle>{documents.length ? 'No filing matches that search' : 'Nothing ingested yet'}</EmptyTitle>
                <EmptyDescription>
                  {documents.length
                    ? 'Clear the search to see every filing in this session.'
                    : 'Use the “Load sample filing” dropdown above or upload your own PDF to get started.'}
                </EmptyDescription>
                {!documents.length && (
                  <Button variant="outline" className="mt-4" onClick={() => fileRef.current?.click()}>
                    Upload filing
                  </Button>
                )}
              </EmptyHeader>
            </Empty>
          )}
      </div>

      <Dialog open={!!docToDelete} onOpenChange={(open) => !open && setDocToDelete(null)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Remove filing?</DialogTitle>
            <DialogDescription>
              This will remove “{docToDelete?.name}” and all its extracted causal nodes, tables, and evidence from this session.
            </DialogDescription>
          </DialogHeader>
          <DialogFooter className="mt-4 gap-2">
            <DialogClose asChild>
              <Button variant="outline">Cancel</Button>
            </DialogClose>
            <Button
              variant="destructive"
              disabled={deleting === docToDelete?.id}
              onClick={async () => {
                if (docToDelete) {
                  await confirmDelete(docToDelete.id)
                  setDocToDelete(null)
                }
              }}
            >
              {deleting === docToDelete?.id ? 'Removing...' : 'Confirm removal'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  )
}
