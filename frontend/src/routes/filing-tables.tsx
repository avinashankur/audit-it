import { useEffect, useMemo, useState } from 'react'
import { useParams, useSearchParams } from 'react-router-dom'
import { api } from '@/api/client'
import { Badge } from '@/components/ui/badge'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { ScrollArea } from '@/components/ui/scroll-area'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Skeleton } from '@/components/ui/skeleton'
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { Empty, EmptyDescription, EmptyHeader, EmptyTitle } from '@/components/ui/empty'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import { Num } from '@/components/app/num'
import { cn } from '@/lib/utils'
import { EMPTY, formatCount } from '@/lib/format'
import type { TableData } from '@/types'

const FIGURE = /^[+\-−(]?[$€£]?\s?\d[\d,.\s%)]*$/
const DASH = /^[-–—]$/

const isFigureColumn = (cells: string[]) => {
  const values = cells.map((c) => (c ?? '').trim()).filter((c) => c !== '' && !DASH.test(c))
  return values.length > 0 && values.every((c) => FIGURE.test(c))
}

export function FilingTables() {
  const { id } = useParams()
  const [searchParams] = useSearchParams()
  const [tables, setTables] = useState<TableData[]>([])
  const [loading, setLoading] = useState(true)
  const [failed, setFailed] = useState(false)
  const [query, setQuery] = useState(searchParams.get('q') || '')

  useEffect(() => {
    if (!id) return
    let mounted = true
    setLoading(true)
    setFailed(false)
    api
      .getDocumentTables(id)
      .then((res) => mounted && setTables(res ?? []))
      .catch((err) => {
        console.error('tables', err)
        if (mounted) setFailed(true)
      })
      .finally(() => mounted && setLoading(false))
    return () => {
      mounted = false
    }
  }, [id])

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase()
    if (!q) return tables
    return tables.filter(
      (t) =>
        (t.title ?? '').toLowerCase().includes(q) ||
        (t.headers ?? []).some((h) => h.toLowerCase().includes(q)) ||
        `page ${t.page_number}`.includes(q),
    )
  }, [tables, query])

  if (loading) {
    return (
      <div className="flex flex-col gap-4">
        {[0, 1].map((i) => (
          <Card key={i}>
            <CardHeader>
              <Skeleton className="h-6 w-1/2" />
              <Skeleton className="h-4 w-1/4" />
            </CardHeader>
            <CardContent className="flex flex-col gap-2">
              {[0, 1, 2, 3, 4].map((j) => (
                <Skeleton key={j} className="h-8 w-full" />
              ))}
            </CardContent>
          </Card>
        ))}
      </div>
    )
  }

  if (failed) {
    return (
      <Alert variant="destructive">
        <AlertTitle>Tables unavailable</AlertTitle>
        <AlertDescription>
          The extracted tables could not be read. Re-open this filing from the library.
        </AlertDescription>
      </Alert>
    )
  }

  if (!tables.length) {
    return (
      <Empty className="border border-dashed py-16">
        <EmptyHeader>
          <EmptyTitle>No structured tables found</EmptyTitle>
          <EmptyDescription>
            This filing had no tabular regions the extractor could read. The causal graph and
            grounded questions still work on its narrative text.
          </EmptyDescription>
        </EmptyHeader>
      </Empty>
    )
  }

  return (
    <>
      <div className="mb-6 flex flex-wrap items-center justify-between gap-4">
        <p className="text-sm text-muted-foreground">
          {query
            ? `${formatCount(filtered.length)} of ${formatCount(tables.length)} tables`
            : `${formatCount(tables.length)} ${tables.length === 1 ? 'table' : 'tables'}`}
        </p>
        <div className="flex flex-wrap items-center gap-3">
          {tables.length > 1 && (
            <Select onValueChange={(val) => setQuery(val === 'all' ? '' : val)}>
              <SelectTrigger className="w-56" aria-label="Jump to table">
                <SelectValue placeholder="Jump to table..." />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">All tables</SelectItem>
                {tables.map((t, idx) => (
                  <SelectItem key={t.table_id ?? idx} value={t.title?.trim() || `Table ${idx + 1}`}>
                    {t.title?.trim() || `Table ${idx + 1}`} (p. {t.page_number})
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          )}
          <Input
            aria-label="Search tables"
            name="table_search"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Search tables"
            className="w-56"
          />
        </div>
      </div>

      <div className="flex flex-col gap-6">
        {filtered.map((t, i) => (
          <ExtractedTable key={t.table_id ?? i} table={t} index={i} />
        ))}
        {!filtered.length && (
          <p className="text-sm text-muted-foreground">No table matches “{query}”.</p>
        )}
      </div>
    </>
  )
}

function ExtractedTable({ table, index }: { table: TableData; index: number }) {
  const headers = table.headers ?? []
  const rows = table.rows ?? []
  const numeric = headers.map((_, c) => isFigureColumn(rows.map((r) => (r ?? [])[c] ?? '')))
  const title = table.title?.trim() || `Table ${index + 1}`

  return (
    <Card>
      <CardHeader>
        <CardTitle>{title}</CardTitle>
        <CardDescription className="flex flex-wrap items-center gap-x-3 gap-y-1">
          <span>Page {table.page_number}</span>
          <Badge variant="outline">
            {formatCount(headers.length)} columns
          </Badge>
          <Badge variant="outline">{formatCount(rows.length)} rows</Badge>
        </CardDescription>
      </CardHeader>
      <CardContent className="p-0">
        {rows.length ? (
          <ScrollArea className="w-full">
            <Table>
              <TableHeader>
                <TableRow>
                  {headers.map((h, c) => (
                    <TableHead
                      key={c}
                      className={cn('max-w-64 truncate', numeric[c] && 'text-right')}
                      title={h}
                    >
                      {h}
                    </TableHead>
                  ))}
                </TableRow>
              </TableHeader>
              <TableBody>
                {rows.map((row, r) => (
                  <TableRow key={r}>
                    {(row ?? []).map((cell, c) => (
                      <TableCell
                        key={c}
                        className={cn(
                          'max-w-80 truncate',
                          c === 0 && 'font-medium',
                          numeric[c] && 'text-right',
                        )}
                        title={cell}
                      >
                        {numeric[c] ? (
                          <Num value={cell?.trim() ? cell : EMPTY} />
                        ) : cell?.trim() ? (
                          cell
                        ) : (
                          <span className="text-muted-foreground">{EMPTY}</span>
                        )}
                      </TableCell>
                    ))}
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </ScrollArea>
        ) : (
          <p className="px-4 pb-4 text-sm text-muted-foreground">
            The header was recognised but no rows came back.
          </p>
        )}
      </CardContent>
    </Card>
  )
}
