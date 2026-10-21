import { useCallback, useEffect, useRef, useState } from 'react'
import { useParams } from 'react-router-dom'
import { api } from '@/api/client'
import { CausalGraph } from '@/features/graph/causal-graph'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { Skeleton } from '@/components/ui/skeleton'
import { useSession } from '@/state/session'
import type { GraphResponseDto, SubgraphResponseDto } from '@/types'

export function FilingGraph() {
  const { id } = useParams()
  const { settings } = useSession()
  const [graph, setGraph] = useState<GraphResponseDto | null>(null)
  const [sub, setSub] = useState<SubgraphResponseDto | null>(null)
  const [hops, setHops] = useState<number>(settings.hops)
  const [failed, setFailed] = useState(false)
  const abort = useRef<AbortController | null>(null)

  useEffect(() => {
    if (!id) return
    const c = new AbortController()
    setGraph(null)
    setSub(null)
    setFailed(false)
    api
      .getDocumentGraph(id, undefined, 3, c.signal)
      .then(setGraph)
      .catch((err) => err?.name !== 'AbortError' && setFailed(true))
    return () => c.abort()
  }, [id])

  const select = useCallback(
    async (nodeId: string | null) => {
      abort.current?.abort()
      if (!nodeId || !id) {
        setSub(null)
        return
      }
      const c = new AbortController()
      abort.current = c
      setSub(null)
      try {
        const next = await api.getNodeDependencies(id, nodeId, c.signal)
        if (!c.signal.aborted && next.root_node_id === nodeId) setSub(next)
      } catch (err) {
        if (err instanceof Error && err.name === 'AbortError') return
        console.error('dependencies', err)
      }
    },
    [id],
  )

  useEffect(() => () => abort.current?.abort(), [])

  if (failed) {
    return (
      <Alert variant="destructive">
        <AlertDescription>
          The graph for this filing could not be loaded. Re-open it from the filings library.
        </AlertDescription>
      </Alert>
    )
  }

  if (!graph) {
    return (
      <div className="flex flex-col border border-border lg:flex-row">
        <Skeleton className="h-96 w-full rounded-none bg-inverse lg:flex-1" />
        <div className="flex w-full flex-col gap-3 bg-card p-6 lg:w-80">
          {[0, 1, 2, 3, 4].map((i) => (
            <Skeleton key={i} className="h-4 w-full" />
          ))}
        </div>
      </div>
    )
  }

  return (
    <CausalGraph
      graph={graph}
      subgraph={sub}
      onSelect={(nodeId) => void select(nodeId)}
      showFootnotes={settings.showFootnotes}
      hops={hops}
      onHops={setHops}
    />
  )
}
