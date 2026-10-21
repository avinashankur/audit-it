import React, { useState, useEffect } from 'react'
import { X, FileText, Copy, Check, ShieldCheck } from 'lucide-react'
import type { AuditCitation } from '../../types'

interface CitationModalProps {
  citation: AuditCitation | null
  onClose: () => void
}

export const CitationModal: React.FC<CitationModalProps> = ({ citation, onClose }) => {
  const [copied, setCopied] = useState(false)

  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        onClose()
      }
    }
    if (citation) {
      window.addEventListener('keydown', handleKeyDown)
    }
    return () => {
      window.removeEventListener('keydown', handleKeyDown)
    }
  }, [citation, onClose])

  if (!citation) return null

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(citation.snippet)
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    } catch (err) {
      console.error('Failed to copy snippet', err)
    }
  }

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-950/80 backdrop-blur-sm"
      onClick={onClose}
    >
      <div
        className="relative w-full max-w-2xl bg-slate-900 border border-slate-800 rounded-2xl shadow-2xl overflow-hidden animate-in fade-in zoom-in-95 duration-150"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-slate-800 bg-slate-900/60">
          <div className="flex items-center gap-2.5">
            <div className="w-8 h-8 rounded-lg bg-emerald-500/10 border border-emerald-500/20 flex items-center justify-center text-emerald-400">
              <ShieldCheck className="w-4 h-4" />
            </div>
            <div>
              <h3 className="text-sm font-semibold text-white">Verified Source Evidence</h3>
              <p className="text-xs text-slate-400">
                Grounding citation extracted from {citation.source_filename}
              </p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="p-1.5 rounded-lg text-slate-400 hover:text-white hover:bg-slate-800 transition-colors cursor-pointer"
            title="Close"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* Metadata Badges */}
        <div className="px-6 py-3 bg-slate-950/40 border-b border-slate-800/80 flex flex-wrap items-center gap-2 text-xs">
          <span className="px-2.5 py-1 rounded-md bg-slate-800 border border-slate-700 text-slate-200 font-mono font-medium">
            Page {citation.page_number}
          </span>
          <span className="px-2.5 py-1 rounded-md bg-indigo-950/60 border border-indigo-800 text-indigo-300 font-medium capitalize">
            {String(citation.citation_type).replace('_', ' ')}
          </span>
          {citation.relevance_score !== null && citation.relevance_score !== undefined && (
            <span className="px-2.5 py-1 rounded-md bg-emerald-950/60 border border-emerald-800 text-emerald-300 font-mono">
              Relevance: {(citation.relevance_score * 100).toFixed(0)}%
            </span>
          )}
          {citation.path_id && (
            <span className="px-2.5 py-1 rounded-md bg-slate-800 text-slate-400 font-mono text-[11px]">
              Path: {citation.path_id}
            </span>
          )}
        </div>

        {/* Full Snippet Content */}
        <div className="p-6 space-y-3">
          <div className="flex items-center justify-between text-xs font-semibold uppercase tracking-wider text-slate-400">
            <span className="flex items-center gap-1.5">
              <FileText className="w-3.5 h-3.5 text-emerald-400" /> Source Excerpt
            </span>
            <button
              onClick={handleCopy}
              className="flex items-center gap-1 px-2.5 py-1 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300 hover:text-white transition-colors cursor-pointer text-xs font-normal normal-case"
            >
              {copied ? (
                <>
                  <Check className="w-3 h-3 text-emerald-400" />
                  <span className="text-emerald-400 font-medium">Copied</span>
                </>
              ) : (
                <>
                  <Copy className="w-3 h-3" />
                  <span>Copy</span>
                </>
              )}
            </button>
          </div>

          <div className="p-4 rounded-xl bg-slate-950 border border-slate-800 text-slate-200 text-xs font-mono leading-relaxed whitespace-pre-wrap max-h-80 overflow-y-auto selection:bg-indigo-500/30">
            {citation.snippet}
          </div>
        </div>

        {/* Footer */}
        <div className="px-6 py-3 border-t border-slate-800 bg-slate-900/40 flex justify-end">
          <button
            onClick={onClose}
            className="px-4 py-2 rounded-xl bg-slate-800 hover:bg-slate-700 text-slate-200 text-xs font-medium transition-colors cursor-pointer"
          >
            Close
          </button>
        </div>
      </div>
    </div>
  )
}
