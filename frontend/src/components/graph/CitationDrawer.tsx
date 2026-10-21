import React from 'react'
import { X, FileText, TrendingUp, BookOpen, ArrowRight, ArrowLeft } from 'lucide-react'
import type { GraphNodeDto, SubgraphResponseDto } from '../../types'

interface CitationDrawerProps {
  node: GraphNodeDto | null
  subgraph: SubgraphResponseDto | null
  onClose: () => void
  onSelectNode: (nodeId: string) => void
}

export const CitationDrawer: React.FC<CitationDrawerProps> = ({
  node,
  subgraph,
  onClose,
  onSelectNode,
}) => {
  if (!node) return null

  const isMetric = node.type === 'metricNode'
  const data = node.data

  const upstreamIds = subgraph?.upstream_node_ids || []
  const downstreamIds = subgraph?.downstream_node_ids || []
  const subNodes = subgraph?.nodes || []

  return (
    <div className="fixed inset-y-0 right-0 w-96 bg-slate-900 border-l border-slate-800 shadow-2xl z-50 flex flex-col transform transition-transform duration-300 ease-in-out">
      {/* Header */}
      <div className="flex items-center justify-between px-5 py-4 border-b border-slate-800">
        <div className="flex items-center gap-2">
          {isMetric ? (
            <TrendingUp className="w-5 h-5 text-indigo-400" />
          ) : (
            <BookOpen className="w-5 h-5 text-purple-400" />
          )}
          <span className="font-semibold text-slate-100 text-sm">
            {isMetric ? 'Financial Metric' : 'Disclosure Node'}
          </span>
        </div>
        <button
          onClick={onClose}
          className="p-1 rounded-lg text-slate-400 hover:text-white hover:bg-slate-800 transition-colors cursor-pointer"
        >
          <X className="w-5 h-5" />
        </button>
      </div>

      {/* Content */}
      <div className="flex-1 overflow-y-auto p-5 space-y-5">
        <div>
          <h3 className="text-lg font-bold text-white tracking-tight">{data.name}</h3>
          {data.period && (
            <span className="inline-block mt-1 text-xs font-mono px-2 py-0.5 rounded bg-slate-800 text-indigo-300 border border-slate-700">
              {data.period}
            </span>
          )}
        </div>

        {/* Primary Value Card */}
        {isMetric && (
          <div className="p-4 rounded-xl bg-slate-950/60 border border-slate-800">
            <div className="text-xs text-slate-400 mb-1">Reported Value</div>
            <div className="text-2xl font-bold font-mono text-emerald-400">
              {data.formatted_value || (data.value !== null && data.value !== undefined ? String(data.value) : 'N/A')}
            </div>
            {data.statement_type && (
              <div className="mt-2 text-xs text-slate-400 flex items-center justify-between">
                <span>Statement:</span>
                <span className="text-slate-200 font-medium">
                  {data.statement_type.replace('_', ' ')}
                </span>
              </div>
            )}
            {data.source_page && (
              <div className="mt-1 text-xs text-slate-400 flex items-center justify-between">
                <span>Report Page:</span>
                <span className="text-slate-200 font-mono">Page {data.source_page}</span>
              </div>
            )}
          </div>
        )}

        {/* Evidence / Footnote Text */}
        {(data.snippet || data.raw_text || data.summary) && (
          <div>
            <h4 className="text-xs font-semibold uppercase tracking-wider text-slate-400 mb-2 flex items-center gap-1.5">
              <FileText className="w-3.5 h-3.5" /> Source Citation & Context
            </h4>
            <div className="p-3.5 rounded-lg bg-slate-950/40 border border-slate-800 text-xs text-slate-300 leading-relaxed font-mono whitespace-pre-wrap">
              {data.snippet || data.raw_text || data.summary}
            </div>
          </div>
        )}

        {/* Causal Dependencies (Upstream & Downstream) */}
        {subgraph && (
          <div className="space-y-4">
            {/* Upstream Root Drivers */}
            <div>
              <h4 className="text-xs font-semibold uppercase tracking-wider text-slate-400 mb-2 flex items-center gap-1.5">
                <ArrowLeft className="w-3.5 h-3.5 text-indigo-400" /> Causal Drivers (Inputs)
              </h4>
              {upstreamIds.length === 0 ? (
                <p className="text-xs text-slate-500 italic">No direct upstream drivers detected.</p>
              ) : (
                <div className="space-y-1.5">
                  {upstreamIds.map((id) => {
                    const peer = subNodes.find((n) => n.id === id)
                    return (
                      <button
                        key={id}
                        onClick={() => onSelectNode(id)}
                        className="w-full text-left p-2.5 rounded-lg bg-slate-800/60 hover:bg-slate-800 border border-slate-700/60 transition-colors flex items-center justify-between cursor-pointer"
                      >
                        <span className="text-xs font-medium text-slate-200 truncate">
                          {peer?.data.name || id}
                        </span>
                        <span className="text-xs font-mono text-emerald-400">
                          {peer?.data.formatted_value}
                        </span>
                      </button>
                    )
                  })}
                </div>
              )}
            </div>

            {/* Downstream Impacts */}
            <div>
              <h4 className="text-xs font-semibold uppercase tracking-wider text-slate-400 mb-2 flex items-center gap-1.5">
                <ArrowRight className="w-3.5 h-3.5 text-emerald-400" /> Downstream Impacts (Outcomes)
              </h4>
              {downstreamIds.length === 0 ? (
                <p className="text-xs text-slate-500 italic">No downstream impacts detected.</p>
              ) : (
                <div className="space-y-1.5">
                  {downstreamIds.map((id) => {
                    const peer = subNodes.find((n) => n.id === id)
                    return (
                      <button
                        key={id}
                        onClick={() => onSelectNode(id)}
                        className="w-full text-left p-2.5 rounded-lg bg-slate-800/60 hover:bg-slate-800 border border-slate-700/60 transition-colors flex items-center justify-between cursor-pointer"
                      >
                        <span className="text-xs font-medium text-slate-200 truncate">
                          {peer?.data.name || id}
                        </span>
                        <span className="text-xs font-mono text-emerald-400">
                          {peer?.data.formatted_value}
                        </span>
                      </button>
                    )
                  })}
                </div>
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
