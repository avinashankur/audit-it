import type { ReactNode } from 'react'
import { cn } from '@/lib/utils'

export function PageHeader({
  title,
  lede,
  actions,
  className,
}: {
  title: string
  lede?: string
  actions?: ReactNode
  className?: string
}) {
  return (
    <div className={cn('mb-8 flex flex-wrap items-end justify-between gap-x-8 gap-y-4', className)}>
      <div className="min-w-0">
        <h1 className="font-serif text-2xl leading-tight font-normal lg:text-3xl">
          {title}
        </h1>
        {lede && <p className="mt-3 max-w-prose text-sm text-muted-foreground">{lede}</p>}
      </div>
      {actions && <div className="flex flex-wrap items-center justify-end gap-2">{actions}</div>}
    </div>
  )
}

export function StatusBar({ left, right }: { left: ReactNode; right: ReactNode }) {
  return (
    <div className="flex flex-wrap items-center justify-between gap-x-4 gap-y-1 border-b border-border px-6 py-3 font-mono text-xs text-muted-foreground lg:px-10">
      <span>{left}</span>
      <span>{right}</span>
    </div>
  )
}

export function SectionHeading({
  children,
  className,
}: {
  children: ReactNode
  className?: string
}) {
  return (
    <h2 className={cn('font-serif text-2xl leading-snug', className)}>{children}</h2>
  )
}
