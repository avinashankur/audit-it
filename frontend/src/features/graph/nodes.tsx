import { Handle, Position } from '@xyflow/react'
import { cn } from '@/lib/utils'
import { EMPTY } from '@/lib/format'
import { Num } from '@/components/app/num'
import type { GraphNodeDataDto } from '@/types'

export type AuditNodeData = GraphNodeDataDto & { dimmed?: boolean }

export const cleanName = (name: string) => name.replace(/\s[\d,\s]{4,}$/, '').trim()

const handle = { width: 6, height: 6, background: 'transparent', border: 0 }

function Shell({
  selected,
  dimmed,
  children,
}: {
  selected?: boolean
  dimmed?: boolean
  children: React.ReactNode
}) {
  return (
    <div
      className={cn(
        'relative flex h-10 w-56 items-center gap-2 rounded-none border px-4 text-xs whitespace-nowrap transition-opacity duration-200',
        selected
          ? 'border-inverse-foreground bg-inverse-foreground font-semibold text-inverse'
          : 'border-inverse-foreground/45 bg-inverse text-inverse-foreground',
        dimmed && 'opacity-20',
      )}
    >
      <Handle type="target" position={Position.Left} style={handle} isConnectable={false} />
      {children}
      <Handle type="source" position={Position.Right} style={handle} isConnectable={false} />
    </div>
  )
}

export function MetricNode({ data, selected }: { data: AuditNodeData; selected?: boolean }) {
  return (
    <Shell selected={selected} dimmed={data.dimmed}>
      <span className="truncate">{cleanName(data.name)}</span>
      <span className="ml-auto shrink-0">
        <Num
          value={
            data.formatted_value?.replace(/\$/g, '') ??
            (data.value == null ? EMPTY : data.value.toLocaleString('en-US'))
          }
        />
      </span>
    </Shell>
  )
}

export function DisclosureNode({ data, selected }: { data: AuditNodeData; selected?: boolean }) {
  return (
    <Shell selected={selected} dimmed={data.dimmed}>
      <span
        aria-hidden="true"
        className={cn('size-1.5 shrink-0 rounded-none', selected ? 'bg-brand' : 'bg-brand/70')}
      />
      <span className="truncate">{data.name}</span>
      {data.source_page != null && (
        <Num className="ml-auto shrink-0 opacity-70" value={`p ${data.source_page}`} />
      )}
    </Shell>
  )
}
