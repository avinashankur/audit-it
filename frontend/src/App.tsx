import { useState, useEffect, useCallback } from 'react'
import { Navbar } from './components/layout/Navbar'
import { SettingsModal } from './components/layout/SettingsModal'
import { DocumentSelector } from './components/ingestion/DocumentSelector'
import { CausalGraphCanvas } from './components/graph/CausalGraphCanvas'
import { AuditChat } from './components/chat/AuditChat'
import { FinancialTablesView } from './components/tables/FinancialTablesView'
import { api } from './api/client'
import type {
  DocumentSummaryDto,
  GraphResponseDto,
  HealthResponse,
} from './types'
import { GitBranch, MessageSquare, Table, FileSpreadsheet } from 'lucide-react'

export function App() {
  const [health, setHealth] = useState<HealthResponse | null>(null)
  const [activeDocId, setActiveDocId] = useState<string | null>(null)
  const [activeDoc, setActiveDoc] = useState<DocumentSummaryDto | null>(null)
  const [rawGraph, setRawGraph] = useState<GraphResponseDto | null>(null)
  const [activeTab, setActiveTab] = useState<'graph' | 'chat' | 'tables'>('graph')
  const [isSettingsOpen, setIsSettingsOpen] = useState<boolean>(false)

  // Fetch system health on mount
  useEffect(() => {
    api
      .getHealth()
      .then(setHealth)
      .catch((err) => console.error('Health check failed', err))
  }, [])

  // When active document changes, fetch metadata and graph
  const loadDocumentData = useCallback(async (docId: string) => {
    try {
      const [summary, graph] = await Promise.all([
        api.getDocument(docId),
        api.getDocumentGraph(docId),
      ])
      setActiveDoc(summary)
      setRawGraph(graph)
    } catch (err) {
      console.error('Failed to load active document data', docId, err)
    }
  }, [])

  useEffect(() => {
    if (activeDocId) {
      loadDocumentData(activeDocId)
    } else {
      setActiveDoc(null)
      setRawGraph(null)
    }
  }, [activeDocId, loadDocumentData])

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 flex flex-col font-sans selection:bg-indigo-500/30 selection:text-indigo-200">
      <Navbar
        activeDoc={activeDoc}
        health={health}
        onOpenSettings={() => setIsSettingsOpen(true)}
      />

      <main className="flex-1 max-w-7xl w-full mx-auto p-6 space-y-6">
        {/* Document Ingestion & Selector */}
        <DocumentSelector
          activeDocumentId={activeDocId}
          onSelectDocument={(id) => setActiveDocId(id)}
          onDocumentAdded={(id) => setActiveDocId(id)}
        />

        {/* Tab Navigation */}
        {activeDocId && (
          <div className="flex items-center justify-between border-b border-slate-800 pb-2">
            <div className="flex items-center gap-2">
              <button
                onClick={() => setActiveTab('graph')}
                className={`flex items-center gap-2 px-4 py-2 rounded-xl text-xs font-semibold transition-all ${
                  activeTab === 'graph'
                    ? 'bg-indigo-600 text-white shadow-lg shadow-indigo-600/20'
                    : 'text-slate-400 hover:text-white hover:bg-slate-900'
                }`}
              >
                <GitBranch className="w-4 h-4" />
                <span>Causal Graph Explorer</span>
              </button>

              <button
                onClick={() => setActiveTab('chat')}
                className={`flex items-center gap-2 px-4 py-2 rounded-xl text-xs font-semibold transition-all ${
                  activeTab === 'chat'
                    ? 'bg-indigo-600 text-white shadow-lg shadow-indigo-600/20'
                    : 'text-slate-400 hover:text-white hover:bg-slate-900'
                }`}
              >
                <MessageSquare className="w-4 h-4" />
                <span>Grounded Audit Q&A</span>
              </button>

              <button
                onClick={() => setActiveTab('tables')}
                className={`flex items-center gap-2 px-4 py-2 rounded-xl text-xs font-semibold transition-all ${
                  activeTab === 'tables'
                    ? 'bg-indigo-600 text-white shadow-lg shadow-indigo-600/20'
                    : 'text-slate-400 hover:text-white hover:bg-slate-900'
                }`}
              >
                <Table className="w-4 h-4" />
                <span>Financial Tables ({activeDoc?.tables_count ?? 0})</span>
              </button>
            </div>

            {activeDoc && (
              <div className="hidden md:flex items-center gap-3 text-xs text-slate-500 font-mono">
                <span>{activeDoc.size_kb} KB</span>
                <span>•</span>
                <span>{activeDoc.total_pages} Pages</span>
                <span>•</span>
                <span className="text-emerald-400">Ready</span>
              </div>
            )}
          </div>
        )}

        {/* Main Content Area */}
        {activeDocId ? (
          <div>
            {activeTab === 'graph' && (
              <CausalGraphCanvas
                documentId={activeDocId}
                rawGraph={rawGraph}
                onRefresh={() => loadDocumentData(activeDocId)}
              />
            )}

            {activeTab === 'chat' && (
              <AuditChat
                documentId={activeDocId}
                documentName={activeDoc?.filename || 'Financial Report'}
              />
            )}

            {activeTab === 'tables' && (
              <FinancialTablesView
                documentId={activeDocId}
                documentName={activeDoc?.filename || 'Financial Report'}
              />
            )}
          </div>
        ) : (
          <div className="flex flex-col items-center justify-center py-24 rounded-2xl bg-slate-900/30 border border-slate-800/80 text-center px-4">
            <div className="w-16 h-16 rounded-2xl bg-indigo-500/10 border border-indigo-500/20 flex items-center justify-center text-indigo-400 mb-4 shadow-xl">
              <FileSpreadsheet className="w-8 h-8" />
            </div>
            <h2 className="text-lg font-bold text-white tracking-tight">No Financial Report Selected</h2>
            <p className="text-xs text-slate-400 max-w-md mt-1 mb-6 leading-relaxed">
              Load a sample 10-K report above or upload your own corporate financial statement PDF to extract the causal knowledge graph and begin grounded audit inquiries.
            </p>
          </div>
        )}
      </main>

      {/* Settings Modal */}
      <SettingsModal
        isOpen={isSettingsOpen}
        onClose={() => setIsSettingsOpen(false)}
      />
    </div>
  )
}

export default App
