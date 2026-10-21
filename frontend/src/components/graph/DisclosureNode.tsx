import React from 'react'
import { Handle, Position } from '@xyflow/react'
import type { GraphNodeDataDto } from '../../types'
import { BookOpen, FileText } from 'lucide-react'

interface DisclosureNodeProps {
  data: GraphNodeDataDto
  selected?: boolean
}

export const DisclosureNode: React.FC<DisclosureNodeProps> = ({ data, selected }) => {
  return (
    <div
      className={`relative px-4 py-3 rounded-xl border bg-slate-900/90 backdrop-blur-md shadow-lg transition-all duration-200 min-w-[220px] max-w-[260px] ${
        selected
          ? 'border-purple-400 ring-2 ring-purple-500/50 shadow-purple-500/20'
          : 'border-slate-800 hover:border-slate-700'
      }`}
    >
      <Handle
        type="target"
        position={Position.Left}
        className="w-2.5 h-2.5 bg-purple-500 border-2 border-slate-900"
      />

      <div className="flex items-center gap-1.5 mb-1.5">
        <BookOpen className="w-3.5 h-3.5 text-purple-400 shrink-0" />
        <span
          className="text-xs font-semibold text-purple-200 truncate"
          title={data.name}
        >
          {data.name}
        </span>
      </div>

      <p className="text-[11px] text-slate-400 line-clamp-2 mt-1 leading-snug">
        {data.summary || data.snippet || 'Footnote narrative disclosure'}
      </p>

      {data.source_page && (
        <div className="mt-2 flex items-center justify-end text-[10px] text-slate-500">
          <span className="flex items-center gap-0.5">
            <FileText className="w-2.5 h-2.5" /> Page {data.source_page}
          </span>
        </div>
      )}

      <Handle
        type="source"
        position={Position.Right}
        className="w-2.5 h-2.5 bg-purple-400 border-2 border-slate-900"
      />
    </div>
  )
}
