import React, { useState, useEffect, useRef, useCallback } from 'react'
import {
  UploadCloud,
  FileText,
  AlertTriangle,
  Loader2,
  ChevronDown,
  Trash2,
} from 'lucide-react'
import { api } from '../../api/client'
import type {
  DocumentSummaryDto,
  IngestJobStatus,
  SampleReportDto,
  UserSettings,
} from '../../types'

function getSavedGraphBackend(): 'networkx' | 'neo4j' {
  try {
    const stored = localStorage.getItem('auditit_user_settings')
    if (stored) {
      const parsed: UserSettings = JSON.parse(stored)
      if (parsed.graphBackend === 'neo4j' || parsed.graphBackend === 'networkx') {
        return parsed.graphBackend
      }
    }
  } catch (err) {
    console.error('Failed to read graphBackend from settings', err)
  }
  return 'networkx'
}

interface DocumentSelectorProps {
  activeDocumentId: string | null
  onSelectDocument: (docId: string | null) => void
  onDocumentAdded?: (docId: string) => void
}

export const DocumentSelector: React.FC<DocumentSelectorProps> = ({
  activeDocumentId,
  onSelectDocument,
  onDocumentAdded,
}) => {
  const [samples, setSamples] = useState<SampleReportDto[]>([])
  const [documents, setDocuments] = useState<DocumentSummaryDto[]>([])
  const [isLoading, setIsLoading] = useState<boolean>(false)
  const [activeJob, setActiveJob] = useState<IngestJobStatus | null>(null)
  const [errorMessage, setErrorMessage] = useState<string | null>(null)
  const fileInputRef = useRef<HTMLInputElement>(null)

  // Fetch samples and active documents on mount
  const refresh = useCallback(async () => {
    try {
      const [sampleList, docList] = await Promise.all([
        api.listSamples(),
        api.listDocuments(),
      ])
      setSamples(sampleList)
      setDocuments(docList)

      // If no active document, select first available
      if (!activeDocumentId && docList.length > 0) {
        onSelectDocument(docList[0].document_id)
      }
    } catch (err: any) {
      console.error('Failed to load documents/samples', err)
    }
  }, [activeDocumentId, onSelectDocument])

  useEffect(() => {
    refresh()
  }, [refresh])

  // Unified handler for job updates (initial response or polling)
  const handleJobUpdate = useCallback(async (job: IngestJobStatus) => {
    setActiveJob(job)
    if (job.status === 'COMPLETED') {
      setIsLoading(false)
      await refresh()
      onSelectDocument(job.document_id)
      if (onDocumentAdded) onDocumentAdded(job.document_id)
    } else if (job.status === 'FAILED') {
      setIsLoading(false)
      setErrorMessage(job.error || 'Ingestion failed.')
    }
  }, [refresh, onSelectDocument, onDocumentAdded])

  // Poll active ingestion job
  useEffect(() => {
    if (!activeJob || activeJob.status === 'COMPLETED' || activeJob.status === 'FAILED') {
      return
    }

    const interval = setInterval(async () => {
      try {
        const updated = await api.getJobStatus(activeJob.job_id)
        await handleJobUpdate(updated)
      } catch (err: any) {
        console.error('Job polling error', err)
      }
    }, 800)

    return () => clearInterval(interval)
  }, [activeJob, handleJobUpdate])

  const handleLoadSample = async (sampleName: string) => {
    try {
      setErrorMessage(null)
      setIsLoading(true)
      const backendType = getSavedGraphBackend()
      const res = await api.loadSample(sampleName, backendType)
      const initialJob: IngestJobStatus = {
        job_id: res.job_id,
        document_id: res.document_id,
        filename: res.filename,
        status: res.status,
        stage: res.status === 'COMPLETED' ? 'completed' : 'parsing',
        progress: res.status === 'COMPLETED' ? 100 : 15,
      }
      if (res.status === 'FAILED') {
        const fullJob = await api.getJobStatus(res.job_id).catch(() => null)
        initialJob.error = fullJob?.error || res.message || 'Ingestion failed.'
      } else if (res.status === 'COMPLETED') {
        const fullJob = await api.getJobStatus(res.job_id).catch(() => null)
        if (fullJob?.stats) {
          initialJob.stats = fullJob.stats
        }
      }
      await handleJobUpdate(initialJob)
    } catch (err: any) {
      setIsLoading(false)
      setErrorMessage(err.message || 'Failed to trigger sample load')
    }
  }

  const handleFileUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (!file) return

    try {
      setErrorMessage(null)
      setIsLoading(true)
      const backendType = getSavedGraphBackend()
      const res = await api.uploadDocument(file, backendType)
      const initialJob: IngestJobStatus = {
        job_id: res.job_id,
        document_id: res.document_id,
        filename: res.filename,
        status: res.status,
        stage: res.status === 'COMPLETED' ? 'completed' : 'parsing',
        progress: res.status === 'COMPLETED' ? 100 : 15,
      }
      if (res.status === 'FAILED') {
        const fullJob = await api.getJobStatus(res.job_id).catch(() => null)
        initialJob.error = fullJob?.error || res.message || 'Ingestion failed.'
      } else if (res.status === 'COMPLETED') {
        const fullJob = await api.getJobStatus(res.job_id).catch(() => null)
        if (fullJob?.stats) {
          initialJob.stats = fullJob.stats
        }
      }
      await handleJobUpdate(initialJob)
    } catch (err: any) {
      setIsLoading(false)
      setErrorMessage(err.message || 'File upload failed')
    } finally {
      if (fileInputRef.current) fileInputRef.current.value = ''
    }
  }

  const handleDelete = async (e: React.MouseEvent, docId: string) => {
    e.stopPropagation()
    try {
      await api.deleteDocument(docId)
      await refresh()
      if (activeDocumentId === docId) {
        const remaining = documents.filter((d) => d.document_id !== docId)
        if (remaining.length > 0) {
          onSelectDocument(remaining[0].document_id)
        } else {
          onSelectDocument(null)
        }
      }
    } catch (err: any) {
      console.error('Delete failed', err)
    }
  }

  return (
    <div className="space-y-4">
      {/* Upload & Sample Bar */}
      <div className="flex flex-wrap items-center justify-between gap-4 p-4 rounded-xl bg-slate-900 border border-slate-800">
        <div className="flex flex-wrap items-center gap-3">
          {/* Sample Loader Dropdown */}
          <div className="relative">
            <select
              onChange={(e) => {
                if (e.target.value) {
                  handleLoadSample(e.target.value)
                  e.target.value = ''
                }
              }}
              defaultValue=""
              disabled={isLoading}
              className="appearance-none px-4 py-2.5 pr-9 rounded-xl bg-slate-950 border border-slate-800 text-xs font-medium text-slate-200 hover:border-slate-700 focus:outline-none focus:border-indigo-500 cursor-pointer disabled:opacity-50"
            >
              <option value="" disabled>
                📑 Load Sample Financial Report...
              </option>
              {samples.map((s) => (
                <option key={s.name} value={s.name}>
                  {s.name} ({s.size_kb} KB)
                </option>
              ))}
            </select>
            <ChevronDown className="w-4 h-4 text-slate-400 absolute right-3 top-3 pointer-events-none" />
          </div>

          <span className="text-xs text-slate-500">or</span>

          {/* Custom PDF Upload */}
          <input
            ref={fileInputRef}
            type="file"
            accept=".pdf"
            onChange={handleFileUpload}
            className="hidden"
          />
          <button
            onClick={() => fileInputRef.current?.click()}
            disabled={isLoading}
            className="flex items-center gap-2 px-4 py-2.5 rounded-xl bg-indigo-600 hover:bg-indigo-500 text-white text-xs font-medium transition-colors shadow-md shadow-indigo-600/20 disabled:opacity-50 cursor-pointer"
          >
            <UploadCloud className="w-4 h-4" />
            <span>Upload Financial PDF</span>
          </button>
        </div>

        {/* Status messages */}
        {errorMessage && (
          <div className="text-xs text-red-400 flex items-center gap-1.5 bg-red-950/40 border border-red-900/50 px-3 py-1.5 rounded-lg">
            <AlertTriangle className="w-3.5 h-3.5 shrink-0" />
            <span>{errorMessage}</span>
          </div>
        )}
      </div>

      {/* Ingestion Progress Bar (When processing) */}
      {activeJob && activeJob.status === 'PROCESSING' && (
        <div className="p-4 rounded-xl bg-slate-900 border border-indigo-500/30 shadow-lg">
          <div className="flex items-center justify-between mb-2">
            <div className="flex items-center gap-2">
              <Loader2 className="w-4 h-4 text-indigo-400 animate-spin" />
              <span className="text-xs font-semibold text-white">
                Ingesting {activeJob.filename}...
              </span>
            </div>
            <span className="text-xs font-mono text-indigo-300 capitalize">
              {activeJob.stage} ({activeJob.progress}%)
            </span>
          </div>
          <div className="w-full h-1.5 bg-slate-950 rounded-full overflow-hidden">
            <div
              className="h-full bg-gradient-to-r from-indigo-500 to-emerald-400 transition-all duration-300"
              style={{ width: `${activeJob.progress}%` }}
            />
          </div>
        </div>
      )}

      {/* Active Documents Grid / Selector */}
      {documents.length > 0 && (
        <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-3">
          {documents.map((doc) => {
            const isSelected = doc.document_id === activeDocumentId
            return (
              <div
                key={doc.document_id}
                onClick={() => onSelectDocument(doc.document_id)}
                className={`p-3.5 rounded-xl border cursor-pointer transition-all ${
                  isSelected
                    ? 'bg-slate-900 border-indigo-500 ring-2 ring-indigo-500/30 shadow-lg'
                    : 'bg-slate-950/80 border-slate-800 hover:border-slate-700 hover:bg-slate-900/50'
                }`}
              >
                <div className="flex items-start justify-between gap-2">
                  <div className="flex items-center gap-2 min-w-0">
                    <FileText
                      className={`w-4 h-4 shrink-0 ${
                        isSelected ? 'text-indigo-400' : 'text-slate-400'
                      }`}
                    />
                    <h4 className="text-xs font-semibold text-slate-200 truncate" title={doc.filename}>
                      {doc.filename}
                    </h4>
                  </div>
                  <button
                    onClick={(e) => handleDelete(e, doc.document_id)}
                    className="text-slate-500 hover:text-red-400 p-1 rounded transition-colors cursor-pointer"
                    title="Delete document"
                  >
                    <Trash2 className="w-3.5 h-3.5" />
                  </button>
                </div>

                <div className="mt-2.5 flex flex-wrap gap-2 text-[10px] text-slate-400">
                  <span className="px-1.5 py-0.5 rounded bg-slate-900 border border-slate-800">
                    {doc.total_pages} Pages
                  </span>
                  <span className="px-1.5 py-0.5 rounded bg-slate-900 border border-slate-800">
                    {doc.metric_nodes_count} Metrics
                  </span>
                  <span className="px-1.5 py-0.5 rounded bg-slate-900 border border-slate-800">
                    {doc.causal_edges_count} Edges
                  </span>
                  <span className="px-1.5 py-0.5 rounded bg-slate-900 border border-slate-800">
                    {doc.tables_count} Tables
                  </span>
                </div>
              </div>
            )
          })}
        </div>
      )}
    </div>
  )
}
