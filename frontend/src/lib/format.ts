export const formatCount = (n: number): string => n.toLocaleString('en-US')

export const formatFigure = (n: number, decimals = 0): string =>
  n.toLocaleString('en-US', { minimumFractionDigits: decimals, maximumFractionDigits: decimals })

export const formatKb = (kb: number): string =>
  kb >= 1024 ? `${(kb / 1024).toFixed(1)} MB` : `${formatCount(Math.round(kb))} KB`

export const formatDate = (iso: string): string => {
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return EMPTY
  return d.toLocaleDateString('en-GB', { day: '2-digit', month: 'short', year: 'numeric' })
}

export const formatTime = (d: Date = new Date()): string =>
  d.toLocaleTimeString('en-GB', { hour: '2-digit', minute: '2-digit' })

export const plural = (n: number, one: string, many?: string): string =>
  `${formatCount(n)} ${n === 1 ? one : (many ?? `${one}s`)}`

export const EMPTY = '—'

export const signedPercent = (current: number, prior: number): string => {
  if (!prior) return EMPTY
  const pct = ((current - prior) / prior) * 100
  return `${pct > 0 ? '+' : ''}${pct.toFixed(1)}%`
}
