import React from 'react'
import { BarChart3, Settings, FileSpreadsheet } from 'lucide-react'
import type { DocumentSummaryDto, HealthResponse } from '../../types'

interface NavbarProps {
  activeDoc: DocumentSummaryDto | null
  health: HealthResponse | null
  onOpenSettings: () => void
}

export const Navbar: React.FC<NavbarProps> = ({
  activeDoc,
  health,
  onOpenSettings,
}) => {
  return (
    <header className="sticky top-0 z-40 w-full border-b border-slate-800 bg-slate-950/80 backdrop-blur-md">
      <div className="flex h-16 items-center justify-between px-6 max-w-7xl mx-auto">
        {/* Brand */}
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-xl bg-gradient-to-tr from-indigo-600 to-emerald-400 flex items-center justify-center text-white shadow-lg shadow-indigo-600/20">
            <BarChart3 className="w-5 h-5" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <span className="font-bold text-base tracking-tight text-white">
                AuditIt
              </span>
              <span className="text-[10px] uppercase font-mono px-1.5 py-0.5 rounded bg-indigo-500/10 text-indigo-400 border border-indigo-500/20">
                v0.1.0
              </span>
            </div>
            <p className="text-[11px] text-slate-400">
              Causal Financial Audit & Disclosure Intelligence
            </p>
          </div>
        </div>

        {/* Right Status & Actions */}
        <div className="flex items-center gap-4">
          {/* Active document pill */}
          {activeDoc && (
            <div className="hidden sm:flex items-center gap-2 px-3 py-1.5 rounded-full bg-slate-900 border border-slate-800 text-xs">
              <FileSpreadsheet className="w-3.5 h-3.5 text-indigo-400" />
              <span className="text-slate-300 font-medium truncate max-w-xs">
                {activeDoc.filename}
              </span>
            </div>
          )}

          {/* Health indicator */}
          <div
            className="flex items-center gap-1.5 text-xs px-2.5 py-1 rounded-full bg-slate-900 border border-slate-800 text-slate-400"
            title={health ? `API Online (${health.active_documents_count} active documents)` : 'Connecting...'}
          >
            <span
              className={`w-2 h-2 rounded-full ${
                health?.status === 'ok' ? 'bg-emerald-400 animate-pulse' : 'bg-amber-400'
              }`}
            />
            <span className="hidden md:inline font-mono text-[11px]">
              {health?.status === 'ok' ? 'Backend Live' : 'Connecting'}
            </span>
          </div>

          {/* Settings button */}
          <button
            onClick={onOpenSettings}
            className="p-2 text-slate-400 hover:text-white hover:bg-slate-900 rounded-xl border border-transparent hover:border-slate-800 transition-all cursor-pointer"
            title="System & Model Settings"
          >
            <Settings className="w-5 h-5" />
          </button>
        </div>
      </div>
    </header>
  )
}
