import type { components } from '../api/schema'

export type Schemas = components['schemas']

export type HealthResponse = Schemas['HealthResponse']
export type SampleReportDto = Schemas['SampleReportDto']
export type IngestJobResponse = Schemas['IngestJobResponse']
export type IngestJobStatus = Schemas['IngestJobStatus']
export type DocumentSummaryDto = Schemas['DocumentSummaryDto']
export type GraphNodeDto = Schemas['GraphNodeDto']
export type GraphNodeDataDto = Schemas['GraphNodeDataDto']
export type GraphEdgeDto = Schemas['GraphEdgeDto']
export type GraphEdgeDataDto = Schemas['GraphEdgeDataDto']
export type GraphResponseDto = Schemas['GraphResponseDto']
export type SubgraphResponseDto = Schemas['SubgraphResponseDto']
export type QueryResponseDto = Schemas['QueryResponseDto']
export type AuditCitation = Schemas['AuditCitation']
export type CausalGraphPath = Schemas['CausalGraphPath']
export type TableData = Schemas['TableData']
export type TextChunk = Schemas['TextChunk']

export interface QueryRequestDto {
  query_text: string
  target_period?: string | null
  focus_metric?: string | null
  model_provider?: string
  top_k?: number
}

export interface ChatMessage {
  id: string
  role: 'user' | 'assistant'
  content: string
  citations?: AuditCitation[]
  causalPaths?: CausalGraphPath[]
  timestamp: string
}

export interface UserSettings {
  provider: 'Offline Grounded' | 'Gemini' | 'OpenAI' | 'Anthropic'
  apiKey: string
  graphBackend: 'networkx' | 'neo4j'
}
