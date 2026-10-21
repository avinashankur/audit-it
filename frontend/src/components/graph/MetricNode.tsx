import React from 'react'
import { Handle, Position } from '@xyflow/react'
import type { GraphNodeDataDto } from '../../types'
import { TrendingUp, AlertCircle, FileText } from 'lucide-react'

interface MetricNodeProps {
  data: GraphNodeDataDto
  selected?: boolean
}

export const MetricNode: React.FC<MetricNodeProps> = ({ data, selected }) => {
  const isConfidenceHigh = (data.confidence ?? 1.0) >= 0.8

  return (
    <div
      className={`relative px-4 py-3 rounded-xl border bg-slate-900/90 backdrop-blur-md shadow-lg transition-all duration-200 min-w-[220px] max-w-[260px] ${
        selected
          ? 'border-indigo-400 ring-2 ring-indigo-500/50 shadow-indigo-500/20'
          : 'border-slate-800 hover:border-slate-700'
      }`}
    >
      <Handle
        type="target"
        position={Position.Left}
        className="w-2.5 h-2.5 bg-indigo-500 border-2 border-slate-900"
      />

      <div className="flex items-start justify-between gap-2 mb-1.5">
        <div className="flex items-center gap-1.5 min-w-0">
          <TrendingUp className="w-3.5 h-3.5 text-indigo-400 shrink-0" />
          <span
            className="text-xs font-semibold text-slate-200 truncate"
            title={data.name}
          >
            {data.name}
          </span>
        </div>
        {data.period && (
          <span className="text-[10px] font-mono px-1.5 py-0.5 rounded bg-slate-800 text-indigo-300 border border-slate-700">
            {data.period}
          </span>
        )}
      </div>

      <div className="flex items-baseline justify-between mt-2">
        <span className="text-lg font-bold tracking-tight text-white font-mono">
          {data.formatted_value || (data.value !== null ? String(data.value) : 'N/A')}
        </span>
        {data.source_page && (
          <span className="text-[10px] text-slate-400 flex items-center gap-0.5">
            <FileText className="w-2.5 h-2.5" /> p.{data.source_page}
          </span>
        )}
      </div>

      {data.statement_type && (
        <div className="mt-1 flex items-center justify-between text-[10px] text-slate-500">
          <span className="truncate">{data.statement_type.replace('_', ' ')}</span>
          {!isConfidenceHigh && (
            <span
              className="text-amber-400 flex items-center gap-0.5"
              title={`Confidence: ${(data.confidence * 100).toFixed(0)}%`}
            >
              <AlertCircle className="w-2.5 h-2.5" />
            </span>
          )}
        </div>
      )}

      <Handle
        type="source"
        position={Position.Right}
        className="w-2.5 h-2.5 bg-emerald-500 border-2 border-slate-900"
      />
    </div>
  )
}
