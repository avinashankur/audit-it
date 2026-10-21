import type {
  AuditCitation,
  CausalGraphPath,
  DocumentSummaryDto,
  GraphResponseDto,
  HealthResponse,
  IngestJobResponse,
  IngestJobStatus,
  QueryRequestDto,
  QueryResponseDto,
  SampleReportDto,
  SubgraphResponseDto,
  TableData,
  UserSettings,
} from '../types'

const BASE_URL = import.meta.env.VITE_API_BASE_URL || '' // Uses env var in production; defaults to '' (Vite proxy) in dev

function getAuthHeaders(): Record<string, string> {
  const headers: Record<string, string> = {}
  try {
    const rawSettings = localStorage.getItem('auditit_user_settings')
    if (rawSettings) {
      const settings: UserSettings = JSON.parse(rawSettings)
      if (settings.provider) {
        headers['X-LLM-Provider'] = settings.provider
      }
      if (settings.apiKey) {
        headers['X-LLM-Key'] = settings.apiKey
      }
    }
  } catch (err) {
    console.error('Failed to read user settings from localStorage', err)
  }
  return headers
}

export const api = {
  async getHealth(): Promise<HealthResponse> {
    const res = await fetch(`${BASE_URL}/api/health`)
    if (!res.ok) throw new Error(`Health check failed: ${res.statusText}`)
    return res.json()
  },

  async listSamples(): Promise<SampleReportDto[]> {
    const res = await fetch(`${BASE_URL}/api/samples`)
    if (!res.ok) throw new Error(`Failed to list samples: ${res.statusText}`)
    return res.json()
  },

  async loadSample(
    filename: string,
    backendType: 'networkx' | 'neo4j' = 'networkx'
  ): Promise<IngestJobResponse> {
    const res = await fetch(
      `${BASE_URL}/api/samples/${encodeURIComponent(filename)}/load?backend_type=${backendType}`,
      { method: 'POST' }
    )
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: res.statusText }))
      throw new Error(err.detail || 'Failed to load sample')
    }
    return res.json()
  },

  async uploadDocument(
    file: File,
    backendType: 'networkx' | 'neo4j' = 'networkx'
  ): Promise<IngestJobResponse> {
    const formData = new FormData()
    formData.append('file', file)
    formData.append('backend_type', backendType)

    const res = await fetch(`${BASE_URL}/api/documents/upload`, {
      method: 'POST',
      body: formData,
    })
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: res.statusText }))
      throw new Error(err.detail || 'Upload failed')
    }
    return res.json()
  },

  async getJobStatus(jobId: string): Promise<IngestJobStatus> {
    const res = await fetch(`${BASE_URL}/api/documents/jobs/${jobId}`)
    if (!res.ok) throw new Error(`Failed to get job status: ${res.statusText}`)
    return res.json()
  },

  async listDocuments(): Promise<DocumentSummaryDto[]> {
    const res = await fetch(`${BASE_URL}/api/documents`)
    if (!res.ok) throw new Error(`Failed to list documents: ${res.statusText}`)
    return res.json()
  },

  async getDocument(docId: string): Promise<DocumentSummaryDto> {
    const res = await fetch(`${BASE_URL}/api/documents/${docId}`)
    if (!res.ok) throw new Error(`Failed to get document: ${res.statusText}`)
    return res.json()
  },

  async deleteDocument(docId: string): Promise<void> {
    const res = await fetch(`${BASE_URL}/api/documents/${docId}`, {
      method: 'DELETE',
    })
    if (!res.ok) throw new Error(`Failed to delete document: ${res.statusText}`)
  },

  async getDocumentTables(docId: string): Promise<TableData[]> {
    const res = await fetch(`${BASE_URL}/api/documents/${docId}/tables`)
    if (!res.ok) throw new Error(`Failed to fetch tables: ${res.statusText}`)
    return res.json()
  },

  async getDocumentGraph(
    docId: string,
    rootNode?: string,
    hops: number = 2
  ): Promise<GraphResponseDto> {
    let url = `${BASE_URL}/api/documents/${docId}/graph?hops=${hops}`
    if (rootNode) {
      url += `&root_node=${encodeURIComponent(rootNode)}`
    }
    const res = await fetch(url)
    if (!res.ok) throw new Error(`Failed to fetch graph: ${res.statusText}`)
    return res.json()
  },

  async getNodeDependencies(
    docId: string,
    nodeId: string
  ): Promise<SubgraphResponseDto> {
    const res = await fetch(
      `${BASE_URL}/api/documents/${docId}/graph/dependencies/${encodeURIComponent(nodeId)}`
    )
    if (!res.ok) throw new Error(`Failed to fetch node dependencies: ${res.statusText}`)
    return res.json()
  },

  async postQuery(
    docId: string,
    payload: QueryRequestDto
  ): Promise<QueryResponseDto> {
    const res = await fetch(`${BASE_URL}/api/documents/${docId}/query`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        ...getAuthHeaders(),
      },
      body: JSON.stringify(payload),
    })
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: res.statusText }))
      throw new Error(err.detail || 'Query execution failed')
    }
    return res.json()
  },

  async streamQuery(
    docId: string,
    payload: QueryRequestDto,
    onToken: (token: string) => void,
    onCitations?: (citations: AuditCitation[]) => void,
    onCausalPaths?: (paths: CausalGraphPath[]) => void,
    onDone?: (info: { query_id: string; latency_ms: Record<string, number> }) => void
  ): Promise<void> {
    const res = await fetch(`${BASE_URL}/api/documents/${docId}/query/stream`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        ...getAuthHeaders(),
      },
      body: JSON.stringify(payload),
    })

    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: res.statusText }))
      throw new Error(err.detail || 'Streaming query failed')
    }

    const reader = res.body?.getReader()
    if (!reader) throw new Error('No readable stream available in response')

    const decoder = new TextDecoder()
    let buffer = ''

    while (true) {
      const { done, value } = await reader.read()
      if (done) break

      buffer += decoder.decode(value, { stream: true })
      const lines = buffer.split('\n\n')
      buffer = lines.pop() || ''

      for (const block of lines) {
        if (!block.trim()) continue
        const eventMatch = block.match(/^event:\s*(\w+)/m)
        const dataMatch = block.match(/^data:\s*(.+)$/m)

        if (eventMatch && dataMatch) {
          const eventType = eventMatch[1]
          try {
            const data = JSON.parse(dataMatch[1])
            if (eventType === 'token' && data.delta) {
              onToken(data.delta)
            } else if (eventType === 'citations' && onCitations) {
              onCitations(data)
            } else if (eventType === 'causal_paths' && onCausalPaths) {
              onCausalPaths(data)
            } else if (eventType === 'done' && onDone) {
              onDone(data)
            }
          } catch (e) {
            console.error('Failed to parse SSE payload', e, dataMatch[1])
          }
        }
      }
    }
  },
}
