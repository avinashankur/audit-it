import { useEffect, useRef, useState, type ReactNode } from 'react'
import { useParams, useSearchParams } from 'react-router-dom'
import { api } from '@/api/client'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Separator } from '@/components/ui/separator'
import { Skeleton } from '@/components/ui/skeleton'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { FlowChain } from '@/components/app/inverse-panel'
import { Num } from '@/components/app/num'
import { cleanName } from '@/features/graph/nodes'
import { EMPTY } from '@/lib/format'
import { useSession } from '@/state/session'
import { formatTime } from '@/lib/format'
import { cn } from '@/lib/utils'
import type { AuditCitation, CausalGraphPath } from '@/types'

interface Turn {
  id: string
  question: string
  answer: string
  chain: string[]
  citations: AuditCitation[]
  at: string
  pending?: boolean
  provider?: string
  latencyMs?: number
}

const STARTERS = [
  'What drove the change in operating income?',
  'Trace the factors behind gross margin.',
  'Summarize the liquidity footnotes.',
]

function formatInline(text: string): ReactNode[] {
  const regex = /(\*\*[^*]+\*\*|\*[^*]+\*|`[^`]+`)/g
  const parts = text.split(regex)
  return parts.map((part, i) => {
    if (part.startsWith('**') && part.endsWith('**')) {
      return (
        <strong key={i} className="font-semibold text-foreground">
          {part.slice(2, -2)}
        </strong>
      )
    }
    if (part.startsWith('*') && part.endsWith('*')) {
      return (
        <em key={i} className="italic text-muted-foreground">
          {part.slice(1, -1)}
        </em>
      )
    }
    if (part.startsWith('`') && part.endsWith('`')) {
      return (
        <code key={i} className="rounded-none bg-muted px-1.5 py-0.5 font-mono text-xs text-foreground">
          {part.slice(1, -1)}
        </code>
      )
    }
    return part
  })
}

function MarkdownAnswer({ content }: { content: string }) {
  if (!content) return null
  const rawBlocks = content.split(/\n\s*\n/)

  return (
    <div className="space-y-3 font-sans text-sm sm:text-base leading-relaxed text-foreground/90">
      {rawBlocks.map((block, idx) => {
        const trimmed = block.trim()
        if (!trimmed) return null

        const lines = trimmed.split('\n')
        const isBulletList = lines.every((l) => /^\s*[-*•]\s+/.test(l))
        const isNumberedList = lines.every((l) => /^\s*\d+\.\s+/.test(l))

        if (isBulletList) {
          return (
            <ul key={idx} className="my-2.5 list-disc space-y-1.5 pl-5 text-sm sm:text-base leading-relaxed">
              {lines.map((l, liIdx) => (
                <li key={liIdx}>{formatInline(l.replace(/^\s*[-*•]\s+/, ''))}</li>
              ))}
            </ul>
          )
        }

        if (isNumberedList) {
          return (
            <ol key={idx} className="my-2.5 list-decimal space-y-1.5 pl-5 text-sm sm:text-base leading-relaxed">
              {lines.map((l, liIdx) => (
                <li key={liIdx}>{formatInline(l.replace(/^\s*\d+\.\s+/, ''))}</li>
              ))}
            </ol>
          )
        }

        if (trimmed.startsWith('### ') || trimmed.startsWith('## ') || trimmed.startsWith('# ')) {
          const headingText = trimmed.replace(/^#+\s*/, '')
          return (
            <h4 key={idx} className="pt-2 font-medium text-foreground text-sm uppercase tracking-wide">
              {formatInline(headingText)}
            </h4>
          )
        }

        if (trimmed.startsWith('> ') || trimmed.startsWith('*(Note:')) {
          return (
            <div
              key={idx}
              className="border-l-2 border-border bg-muted/20 px-3 py-2 text-xs sm:text-sm text-muted-foreground my-2"
            >
              {lines.map((l, lIdx) => (
                <p key={lIdx} className={lIdx > 0 ? 'mt-1' : ''}>
                  {formatInline(l.replace(/^>\s*/, ''))}
                </p>
              ))}
            </div>
          )
        }

        return (
          <p key={idx} className="leading-relaxed">
            {lines.map((l, lIdx) => (
              <span key={lIdx}>
                {lIdx > 0 && <br />}
                {formatInline(l)}
              </span>
            ))}
          </p>
        )
      })}
    </div>
  )
}

export function FilingQA() {
  const { id } = useParams()
  const [searchParams, setSearchParams] = useSearchParams()
  const { documents, settings } = useSession()
  const filing = documents.find((d) => d.document_id === id)
  const [turns, setTurns] = useState<Turn[]>([])
  const [query, setQuery] = useState('')
  const [streaming, setStreaming] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const abort = useRef<AbortController | null>(null)
  const endRef = useRef<HTMLDivElement>(null)
  const queryParamProcessed = useRef(false)

  useEffect(() => {
    endRef.current?.scrollIntoView({ block: 'nearest' })
  }, [turns])

  useEffect(() => () => abort.current?.abort(), [id])

  const ask = async (text: string) => {
    const q = text.trim()
    if (!q || !id || streaming) return
    abort.current?.abort()
    const c = new AbortController()
    abort.current = c
    setError(null)
    setQuery('')

    const turnId = `t${Date.now()}`
    setTurns((prev) => [
      ...prev,
      { id: turnId, question: q, answer: '', chain: [], citations: [], at: formatTime(), pending: true },
    ])
    setStreaming(true)

    const patch = (fn: (t: Turn) => Turn) =>
      setTurns((prev) => prev.map((t) => (t.id === turnId ? fn(t) : t)))

    const pathsToChain = (paths: CausalGraphPath[]) => paths[0]?.node_sequence ?? []

    try {
      await api.streamQuery(
        id,
        { query_text: q },
        (token) => !c.signal.aborted && patch((t) => ({ ...t, answer: t.answer + token })),
        (citations) => !c.signal.aborted && patch((t) => ({ ...t, citations })),
        (paths) => !c.signal.aborted && patch((t) => ({ ...t, chain: pathsToChain(paths) })),
        (info) => {
          if (c.signal.aborted) return
          const rawLat = info?.latency_ms
          const latency =
            typeof rawLat === 'number'
              ? rawLat
              : typeof rawLat === 'object' && rawLat !== null && 'total' in rawLat
              ? (rawLat as Record<string, number>).total
              : undefined
          patch((t) => ({
            ...t,
            pending: false,
            provider: info?.model_provider ?? settings.provider,
            latencyMs: latency,
          }))
        },
        c.signal,
      )
    } catch (err) {
      if (err instanceof Error && (err.name === 'AbortError' || c.signal.aborted)) return
      setError(err instanceof Error ? err.message : 'The reasoning engine could not be reached.')
      patch((t) => ({ ...t, pending: false }))
    } finally {
      if (!c.signal.aborted) setStreaming(false)
    }
  }

  useEffect(() => {
    const qParam = searchParams.get('q')
    if (qParam && !queryParamProcessed.current && !streaming) {
      queryParamProcessed.current = true
      void ask(qParam)
      setSearchParams({}, { replace: true })
    }
  }, [searchParams])

  return (
    <div className="flex flex-col gap-10 lg:flex-row">
      <div className="min-w-0 flex-1">
        {error && (
          <Alert variant="destructive" className="mb-6">
            <AlertDescription>{error}</AlertDescription>
          </Alert>
        )}

        {turns.length === 0 && (
          <div className="border-t border-foreground py-6">
            <p className="text-sm text-muted-foreground">
              Answers come only from ingested filings, with the causal chain and the page cited.
              {settings.provider === 'Offline Grounded' &&
                ' Offline grounded mode cites without a model call.'}
            </p>
            <div className="mt-5 flex flex-col">
              {STARTERS.map((s) => (
                <Button
                  key={s}
                  variant="ghost"
                  onClick={() => void ask(s)}
                  className="h-auto w-full items-center justify-between rounded-none border-t border-hairline px-2 py-3 text-left font-normal hover:bg-muted/50"
                >
                  <span>{s}</span>
                  <span aria-hidden="true" className="text-muted-foreground">
                    +
                  </span>
                </Button>
              ))}
            </div>
          </div>
        )}

        {turns.map((t) => (
          <article key={t.id} className="border-t border-foreground py-6 first:border-t-0">
            <h2 className="font-serif text-2xl leading-snug lg:text-3xl text-foreground">{t.question}</h2>
            <div className="mt-4 max-w-prose">
              {t.answer ? (
                <MarkdownAnswer content={t.answer} />
              ) : t.pending ? (
                <div className="flex flex-col gap-2 py-2">
                  <Skeleton className="h-4 w-full rounded-none" />
                  <Skeleton className="h-4 w-5/6 rounded-none" />
                  <Skeleton className="h-4 w-2/3 rounded-none" />
                </div>
              ) : (
                <span className="text-sm text-muted-foreground">The engine returned no answer.</span>
              )}
            </div>

            {t.chain.length > 0 && (
              <div className="mt-5">
                <FlowChain steps={t.chain.map(cleanName)} />
              </div>
            )}

            {t.citations.length > 0 && (
              <div className="mt-5">
                <p className="text-xs text-muted-foreground">Source evidence</p>
                <ul className="mt-1">
                  {t.citations.map((c) => (
                    <li
                      key={c.citation_id ?? `${c.page_number}-${c.snippet.slice(0, 8)}`}
                      className="flex items-baseline gap-4 border-t border-hairline py-2 text-sm"
                    >
                      <span className="min-w-0 flex-1 truncate" title={c.snippet}>
                        {c.snippet.slice(0, 160)}
                      </span>
                      <Num value={`p ${c.page_number}`} muted />
                    </li>
                  ))}
                </ul>
              </div>
            )}

            <div className="mt-4 flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
              <Num value={t.at} />
              <span>·</span>
              <span className={cn(t.provider === 'Gemini' && 'font-medium text-brand')}>
                {t.provider ? `Synthesized by ${t.provider}` : settings.provider}
              </span>
              {t.latencyMs != null && (
                <>
                  <span>·</span>
                  <Num value={`${Math.round(t.latencyMs)}ms`} />
                </>
              )}
            </div>
          </article>
        ))}

        <div className="sticky bottom-3 z-10 flex gap-2 bg-background py-2">
          <form
            className="flex min-w-0 flex-1 gap-2"
            onSubmit={(e) => {
              e.preventDefault()
              void ask(query)
            }}
          >
            <label htmlFor="audit-query" className="sr-only">
              Ask about a balance, a change, or a cause
            </label>
            <Input
              id="audit-query"
              name="audit_query"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Ask about a balance, a change, or a cause"
              disabled={streaming}
              className="h-11 flex-1 bg-card"
            />
            <Button type="submit" size="lg" disabled={!query.trim() || streaming}>
              {streaming ? 'Answering' : 'Ask'}
            </Button>
          </form>
        </div>
      </div>

      <aside className="w-full min-w-0 shrink-0 lg:w-64">
        <Separator className="mb-4 bg-foreground" />
        <h2 className="font-serif text-lg">This filing</h2>
        <dl className="mt-3 grid grid-cols-2 gap-y-2 text-sm">
          <dt className="text-muted-foreground">Document</dt>
          <dd className="truncate text-right" title={filing?.filename}>
            {filing?.tables_count != null ? `${filing.tables_count} tables` : '—'}
          </dd>
          <dt className="text-muted-foreground">Metrics</dt>
          <dd className="text-right"><Num value={filing?.metric_nodes_count ?? EMPTY} /></dd>
          <dt className="text-muted-foreground">Edges</dt>
          <dd className="text-right">
            <Num muted={!filing?.causal_edges_count} value={filing?.causal_edges_count ?? EMPTY} />
          </dd>
          <dt className="text-muted-foreground">Reasoning</dt>
          <dd className={cn('text-right', settings.provider === 'Gemini' && 'font-medium text-brand')}>
            {settings.provider}
          </dd>
          {settings.provider !== 'Offline Grounded' && (
            <>
              <dt className="text-muted-foreground">Key source</dt>
              <dd className="text-right text-xs text-muted-foreground">
                {settings.apiKey ? 'Browser header' : 'Server environment'}
              </dd>
            </>
          )}
        </dl>
      </aside>
    </div>
  )
}
