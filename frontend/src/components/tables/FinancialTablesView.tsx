import React, { useState, useEffect } from 'react'
import { FileSpreadsheet, Search, ChevronRight, Table } from 'lucide-react'
import { api } from '../../api/client'
import type { TableData } from '../../types'

interface FinancialTablesViewProps {
  documentId: string
  documentName: string
}

export const FinancialTablesView: React.FC<FinancialTablesViewProps> = ({
  documentId,
  documentName,
}) => {
  const [tables, setTables] = useState<TableData[]>([])
  const [selectedTableIndex, setSelectedTableIndex] = useState<number>(0)
  const [isLoading, setIsLoading] = useState<boolean>(true)
  const [searchTerm, setSearchTerm] = useState<string>('')

  useEffect(() => {
    let isMounted = true
    api
      .getDocumentTables(documentId)
      .then((res) => {
        if (isMounted) {
          setTables(res || [])
          setSelectedTableIndex(0)
          setIsLoading(false)
        }
      })
      .catch((err) => {
        console.error('Failed to fetch tables', err)
        if (isMounted) setIsLoading(false)
      })

    return () => {
      isMounted = false
    }
  }, [documentId])

  const filteredTables = tables.filter((t) => {
    if (!searchTerm) return true
    const term = searchTerm.toLowerCase()
    return (
      (t.title && t.title.toLowerCase().includes(term)) ||
      (t.headers || []).some((h) => h.toLowerCase().includes(term)) ||
      `page ${t.page_number}`.includes(term)
    )
  })

  // Ensure index is within filtered range and choose strictly from filteredTables
  const safeIndex =
    filteredTables.length > 0 && selectedTableIndex < filteredTables.length
      ? selectedTableIndex
      : 0
  const currentTable = filteredTables.length > 0 ? filteredTables[safeIndex] : null

  if (isLoading) {
    return (
      <div className="flex flex-col items-center justify-center h-[calc(100vh-140px)] bg-slate-950 rounded-2xl border border-slate-800 text-slate-400">
        <Table className="w-8 h-8 animate-pulse text-indigo-400 mb-2" />
        <span className="text-xs">Loading extracted financial tables...</span>
      </div>
    )
  }

  if (tables.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center h-[calc(100vh-140px)] bg-slate-950 rounded-2xl border border-slate-800 text-center px-4">
        <FileSpreadsheet className="w-12 h-12 text-slate-700 mb-3" />
        <h3 className="text-sm font-semibold text-slate-300">No Financial Tables Extracted</h3>
        <p className="text-xs text-slate-500 max-w-sm mt-1">
          This report either did not contain structured tables or tabular extraction produced raw text chunks.
        </p>
      </div>
    )
  }

  const currentRows = currentTable?.rows || []
  const currentHeaders = currentTable?.headers || []

  return (
    <div className="grid grid-cols-1 md:grid-cols-4 gap-4 h-[calc(100vh-140px)]">
      {/* Sidebar Table List */}
      <div className="md:col-span-1 bg-slate-950 rounded-2xl border border-slate-800 p-4 flex flex-col overflow-hidden">
        <div className="relative mb-3">
          <Search className="w-3.5 h-3.5 text-slate-400 absolute left-2.5 top-2.5 pointer-events-none" />
          <input
            type="text"
            placeholder="Search tables..."
            value={searchTerm}
            onChange={(e) => {
              setSearchTerm(e.target.value)
              setSelectedTableIndex(0)
            }}
            className="w-full pl-8 pr-3 py-1.5 text-xs rounded-xl bg-slate-900 border border-slate-800 text-white placeholder-slate-500 focus:outline-none focus:border-indigo-500"
          />
        </div>

        <div className="flex-1 overflow-y-auto space-y-1.5 pr-1">
          {filteredTables.length === 0 ? (
            <div className="p-4 text-center text-slate-500 text-xs">
              No matching tables
            </div>
          ) : (
            filteredTables.map((t, idx) => {
              const isSelected = currentTable?.table_id === t.table_id
              const rowsCount = (t.rows || []).length
              return (
                <button
                  key={t.table_id || idx}
                  onClick={() => setSelectedTableIndex(idx)}
                  className={`w-full text-left p-3 rounded-xl border transition-all text-xs flex items-center justify-between cursor-pointer ${
                    isSelected
                      ? 'bg-indigo-600/10 border-indigo-500/50 text-white'
                      : 'bg-slate-900/60 border-slate-800 text-slate-400 hover:text-slate-200 hover:border-slate-700'
                  }`}
                >
                  <div className="min-w-0 pr-2">
                    <div className="font-medium truncate">
                      {t.title || `Financial Table #${idx + 1}`}
                    </div>
                    <div className="text-[10px] text-slate-500 mt-0.5">
                      Page {t.page_number} • {rowsCount} rows
                    </div>
                  </div>
                  <ChevronRight className="w-3.5 h-3.5 shrink-0 opacity-60" />
                </button>
              )
            })
          )}
        </div>
      </div>

      {/* Main Table Viewer */}
      <div className="md:col-span-3 bg-slate-950 rounded-2xl border border-slate-800 p-6 flex flex-col overflow-hidden shadow-2xl">
        {currentTable ? (
          <>
            <div className="flex items-center justify-between pb-4 border-b border-slate-800 mb-4">
              <div>
                <h3 className="text-base font-bold text-white">
                  {currentTable.title || 'Financial Disclosure Table'}
                </h3>
                <span className="text-xs text-indigo-400 font-mono">
                  Source: {documentName} (Page {currentTable.page_number})
                </span>
              </div>
              <div className="text-xs font-mono px-3 py-1 rounded-lg bg-slate-900 border border-slate-800 text-slate-300">
                {currentHeaders.length} Columns • {currentRows.length} Rows
              </div>
            </div>

            <div className="flex-1 overflow-auto rounded-xl border border-slate-800 bg-slate-900/40">
              <table className="w-full text-left text-xs border-collapse">
                <thead className="sticky top-0 bg-slate-900 border-b border-slate-800 text-slate-300 font-semibold uppercase tracking-wider text-[11px]">
                  <tr>
                    {currentHeaders.map((h, i) => (
                      <th key={i} className="px-4 py-3 border-r border-slate-800/60 last:border-r-0">
                        {h}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-800/60 text-slate-300 font-mono">
                  {currentRows.map((row, rIdx) => (
                    <tr
                      key={rIdx}
                      className="hover:bg-slate-800/40 transition-colors odd:bg-slate-950/40"
                    >
                      {(row || []).map((cell, cIdx) => (
                        <td
                          key={cIdx}
                          className="px-4 py-2.5 border-r border-slate-800/40 last:border-r-0 whitespace-nowrap"
                        >
                          {cell}
                        </td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </>
        ) : (
          <div className="flex-1 flex flex-col items-center justify-center text-slate-500 text-xs">
            <FileSpreadsheet className="w-8 h-8 text-slate-700 mb-2" />
            <span>{searchTerm ? `No tables match "${searchTerm}"` : 'Select a table to view'}</span>
          </div>
        )}
      </div>
    </div>
  )
}
