import { cn } from '@/lib/utils'
import { Num } from './num'

export function StatStrip({
  stats,
  className,
}: {
  stats: Array<{ label: string; value: string | number; note?: string }>
  className?: string
}) {
  return (
    <dl className={cn('grid grid-cols-2 border-t border-foreground md:grid-cols-4', className)}>
      {stats.map((s, i) => (
        <div
          key={s.label}
          className={cn(
            'flex flex-col gap-1 px-5 py-4 first:pl-0',
            i > 0 && 'border-l border-border',
            i === 2 && 'pl-0 md:pl-5',
          )}
        >
          <dd
            className={cn(
              'font-serif text-4xl leading-none tabular-nums lg:text-5xl',
              s.note ? 'font-normal text-muted-foreground' : 'font-normal text-foreground',
            )}
          >
            {s.value}
          </dd>
          <dt className="text-xs text-muted-foreground">{s.label}</dt>
          {s.note && <p className="text-xs text-muted-foreground">{s.note}</p>}
        </div>
      ))}
    </dl>
  )
}

export function BarList({
  items,
  unit = '%',
}: {
  items: Array<{ label: string; value: number; display?: string }>
  unit?: string
}) {
  const max = Math.max(...items.map((i) => i.value), 1)
  return (
    <div className="flex flex-col">
      {items.map((item) => (
        <div
          key={item.label}
          className="flex items-center gap-4 border-b border-hairline py-2.5 last:border-b-0"
        >
          <span className="w-36 shrink-0 truncate text-sm" title={item.label}>
            {item.label}
          </span>
          <span className="h-1.5 flex-1 bg-hairline">
            <span
              className="block h-full bg-primary"
              style={{
                width: `${Math.max(2, (item.value / max) * 100)}%`,
                opacity: 0.35 + (item.value / max) * 0.65,
              }}
            />
          </span>
          <Num className="w-16 shrink-0" value={item.display ?? `${item.value.toFixed(1)}${unit}`} />
        </div>
      ))}
      {items.length === 0 && (
        <p className="py-3 text-sm text-muted-foreground">Nothing to rank yet.</p>
      )}
    </div>
  )
}
