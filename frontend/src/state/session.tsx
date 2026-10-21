import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from 'react'
import { api } from '../api/client'
import type {
  DocumentSummaryDto,
  HealthResponse,
  IngestJobStatus,
  SampleReportDto,
  UserSettings,
} from '../types'

export const readSettings = (): UserSettings => {
  try {
    const raw = localStorage.getItem('auditit_user_settings')
    if (raw) {
      const parsed = JSON.parse(raw) as Partial<UserSettings>
      return {
        provider: parsed.provider ?? 'Offline Grounded',
        apiKey: parsed.apiKey ?? '',
        graphBackend: parsed.graphBackend === 'neo4j' ? 'neo4j' : 'networkx',
        showFootnotes: parsed.showFootnotes ?? true,
        hops: parsed.hops === 1 || parsed.hops === 3 ? parsed.hops : 2,
      }
    }
  } catch (err) {
    console.error('Failed to read user settings', err)
  }
  return {
    provider: 'Offline Grounded',
    apiKey: '',
    graphBackend: 'networkx',
    showFootnotes: true,
    hops: 2,
  }
}

interface Session {
  health: HealthResponse | null
  documents: DocumentSummaryDto[]
  samples: SampleReportDto[]
  job: IngestJobStatus | null
  ingestingName: string | null
  busy: boolean
  error: string | null
  refresh: () => Promise<void>
  loadSample: (name: string) => Promise<string | null>
  upload: (file: File) => Promise<string | null>
  remove: (docId: string) => Promise<void>
  clearError: () => void
  settings: UserSettings
  saveSettings: (next: UserSettings) => void
}

const SessionContext = createContext<Session | null>(null)

export const useSession = (): Session => {
  const ctx = useContext(SessionContext)
  if (!ctx) throw new Error('useSession must be used inside SessionProvider')
  return ctx
}

export const SessionProvider = ({ children }: { children: ReactNode }) => {
  const [health, setHealth] = useState<HealthResponse | null>(null)
  const [documents, setDocuments] = useState<DocumentSummaryDto[]>([])
  const [samples, setSamples] = useState<SampleReportDto[]>([])
  const [job, setJob] = useState<IngestJobStatus | null>(null)
  const [ingestingName, setIngestingName] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [settings, setSettings] = useState<UserSettings>(readSettings)
  const pollRef = useRef<number | null>(null)

  const refresh = useCallback(async () => {
    try {
      const [docs, list] = await Promise.all([api.listDocuments(), api.listSamples()])
      setDocuments(docs)
      setSamples(list)
    } catch (err) {
      console.error('Failed to load filings', err)
      setError('The engine could not be reached.')
    }
  }, [])

  useEffect(() => {
    api.getHealth().then(setHealth).catch(() => setHealth(null))
    refresh()
  }, [refresh])

  const track = useCallback(
    (initial: IngestJobStatus) => {
      setJob(initial)
      if (pollRef.current) window.clearInterval(pollRef.current)
      pollRef.current = window.setInterval(async () => {
        try {
          const next = await api.getJobStatus(initial.job_id)
          setJob(next)
          if (next.status === 'COMPLETED') {
            if (pollRef.current) window.clearInterval(pollRef.current)
            pollRef.current = null
            await refresh()
          } else if (next.status === 'FAILED') {
            if (pollRef.current) window.clearInterval(pollRef.current)
            pollRef.current = null
            setError(next.error || 'Ingestion failed.')
          }
        } catch (err) {
          if (pollRef.current) window.clearInterval(pollRef.current)
          pollRef.current = null
          console.error('Job polling error', err)
        }
      }, 800)
    },
    [refresh],
  )

  useEffect(
    () => () => {
      if (pollRef.current) window.clearInterval(pollRef.current)
    },
    [],
  )

  const start = useCallback(
    async (
      run: () => Promise<{ job_id: string; document_id: string; filename: string; status: string }>,
      hint?: string,
    ) => {
      setError(null)
      setIngestingName(hint ?? 'filing')
      try {
        const res = await run()
        if (res.status === 'COMPLETED') {
          setIngestingName(null)
          await refresh()
          return res.document_id
        }
        track({
          job_id: res.job_id,
          document_id: res.document_id,
          filename: res.filename,
          status: res.status,
          stage: 'parsing',
          progress: 15,
        })
        return res.document_id
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Ingestion failed.')
        return null
      } finally {
        setIngestingName(null)
      }
    },
    [track, refresh],
  )

  const value = useMemo<Session>(
    () => ({
      health,
      documents,
      samples,
      job,
      ingestingName,
      busy: ingestingName !== null || (job !== null && job.status === 'PROCESSING'),
      error,
      refresh,
      loadSample: (name) => start(() => api.loadSample(name, settings.graphBackend), name),
      upload: (file) => start(() => api.uploadDocument(file, settings.graphBackend), file.name),
      remove: async (docId) => {
        try {
          await api.deleteDocument(docId)
          await refresh()
        } catch (err) {
          console.error('Delete failed', err)
          setError('The filing could not be removed.')
        }
      },
      clearError: () => setError(null),
      settings,
      saveSettings: (next) => {
        localStorage.setItem('auditit_user_settings', JSON.stringify(next))
        setSettings(next)
      },
    }),
    [health, documents, samples, job, ingestingName, error, refresh, start, settings],
  )

  return <SessionContext.Provider value={value}>{children}</SessionContext.Provider>
}
