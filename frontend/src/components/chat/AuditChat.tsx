import React, { useState, useRef, useEffect } from 'react'
import {
  Send,
  Sparkles,
  Bot,
  User,
  FileText,
  GitCommit,
  Trash2,
  Loader2,
  ChevronRight,
} from 'lucide-react'
import { api } from '../../api/client'
import type { AuditCitation, ChatMessage } from '../../types'

interface AuditChatProps {
  documentId: string
  documentName: string
  onInspectCitation?: (citation: AuditCitation) => void
}

const STARTER_QUERIES = [
  'What factors drove changes in gross margin and revenue?',
  'Analyze operating expenses and operating income drivers.',
  'Summarize cash flows and liquidity footnotes.',
  'Trace the primary drivers impacting net income.',
]

export const AuditChat: React.FC<AuditChatProps> = ({
  documentId,
  documentName,
  onInspectCitation,
}) => {
  const [messages, setMessages] = useState<ChatMessage[]>([
    {
      id: 'init-1',
      role: 'assistant',
      content: `Hello! I have audited **${documentName}**. You can ask any question regarding financial metrics, ratios, causal drivers, or footnote disclosures.`,
      timestamp: new Date().toLocaleTimeString(),
    },
  ])
  const [inputQuery, setInputQuery] = useState('')
  const [isStreaming, setIsStreaming] = useState(false)
  const messagesEndRef = useRef<HTMLDivElement>(null)

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }

  useEffect(() => {
    scrollToBottom()
  }, [messages, isStreaming])

  const handleSend = async (queryText?: string) => {
    const text = (queryText || inputQuery).trim()
    if (!text || isStreaming) return

    const userMsg: ChatMessage = {
      id: `u-${Date.now()}`,
      role: 'user',
      content: text,
      timestamp: new Date().toLocaleTimeString(),
    }

    const assistantMsgId = `a-${Date.now()}`
    const placeholderMsg: ChatMessage = {
      id: assistantMsgId,
      role: 'assistant',
      content: '',
      citations: [],
      causalPaths: [],
      timestamp: new Date().toLocaleTimeString(),
    }

    setMessages((prev) => [...prev, userMsg, placeholderMsg])
    setInputQuery('')
    setIsStreaming(true)

    try {
      await api.streamQuery(
        documentId,
        { query_text: text },
        // onToken
        (token) => {
          setMessages((prev) =>
            prev.map((msg) =>
              msg.id === assistantMsgId
                ? { ...msg, content: msg.content + token }
                : msg
            )
          )
        },
        // onCitations
        (citations) => {
          setMessages((prev) =>
            prev.map((msg) =>
              msg.id === assistantMsgId ? { ...msg, citations } : msg
            )
          )
        },
        // onCausalPaths
        (causalPaths) => {
          setMessages((prev) =>
            prev.map((msg) =>
              msg.id === assistantMsgId ? { ...msg, causalPaths } : msg
            )
          )
        },
        // onDone
        () => {
          setIsStreaming(false)
        }
      )
    } catch (err: any) {
      console.error('Chat error', err)
      setMessages((prev) =>
        prev.map((msg) =>
          msg.id === assistantMsgId
            ? {
                ...msg,
                content:
                  msg.content ||
                  `⚠️ **Query failed**: ${err.message || 'Error communicating with reasoning engine.'}`,
              }
            : msg
        )
      )
    } finally {
      setIsStreaming(false)
    }
  }

  return (
    <div className="flex flex-col h-[calc(100vh-140px)] bg-slate-950 rounded-2xl border border-slate-800 shadow-2xl overflow-hidden">
      {/* Header */}
      <div className="flex items-center justify-between px-6 py-4 border-b border-slate-800 bg-slate-900/50 backdrop-blur-sm">
        <div className="flex items-center gap-3">
          <div className="w-9 h-9 rounded-xl bg-indigo-500/10 border border-indigo-500/20 flex items-center justify-center text-indigo-400">
            <Sparkles className="w-5 h-5" />
          </div>
          <div>
            <h3 className="text-sm font-semibold text-white">Grounded Audit Assistant</h3>
            <p className="text-xs text-slate-400">
              Tracing causal metrics and citations for <strong className="text-slate-200">{documentName}</strong>
            </p>
          </div>
        </div>

        <button
          onClick={() =>
            setMessages([
              {
                id: 'init-reset',
                role: 'assistant',
                content: 'Chat cleared. Ask a new audit inquiry below.',
                timestamp: new Date().toLocaleTimeString(),
              },
            ])
          }
          className="p-2 text-slate-400 hover:text-red-400 hover:bg-slate-800 rounded-lg transition-colors"
          title="Clear Conversation"
        >
          <Trash2 className="w-4 h-4" />
        </button>
      </div>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto p-6 space-y-6">
        {messages.map((msg) => {
          const isUser = msg.role === 'user'
          return (
            <div
              key={msg.id}
              className={`flex gap-4 ${isUser ? 'justify-end' : 'justify-start'}`}
            >
              {!isUser && (
                <div className="w-8 h-8 rounded-lg bg-indigo-600/20 border border-indigo-500/30 flex items-center justify-center text-indigo-400 shrink-0 mt-0.5">
                  <Bot className="w-4 h-4" />
                </div>
              )}

              <div
                className={`max-w-[80%] rounded-2xl px-5 py-4 ${
                  isUser
                    ? 'bg-indigo-600 text-white shadow-lg shadow-indigo-600/10'
                    : 'bg-slate-900/80 border border-slate-800 text-slate-200 shadow-lg'
                }`}
              >
                <div className="text-sm leading-relaxed whitespace-pre-wrap font-sans">
                  {msg.content || (
                    <span className="flex items-center gap-2 text-slate-400 italic">
                      <Loader2 className="w-3.5 h-3.5 animate-spin" /> Reasoning over knowledge graph...
                    </span>
                  )}
                </div>

                {/* Causal Paths */}
                {msg.causalPaths && msg.causalPaths.length > 0 && (
                  <div className="mt-4 pt-3 border-t border-slate-800/80 space-y-2">
                    <span className="text-xs font-semibold uppercase tracking-wider text-indigo-300 flex items-center gap-1.5">
                      <GitCommit className="w-3.5 h-3.5" /> Causal Dependency Sequence
                    </span>
                    {msg.causalPaths.map((p, idx) => (
                      <div
                        key={p.path_id || idx}
                        className="p-2.5 rounded-lg bg-slate-950/60 border border-slate-800 text-xs"
                      >
                        <div className="flex flex-wrap items-center gap-1 text-slate-300 font-mono">
                          {(p.node_sequence || []).map((n, i) => (
                            <React.Fragment key={i}>
                              <span className="px-1.5 py-0.5 rounded bg-slate-800 text-white">
                                {n}
                              </span>
                              {i < (p.node_sequence || []).length - 1 && (
                                <ChevronRight className="w-3 h-3 text-emerald-400 shrink-0" />
                              )}
                            </React.Fragment>
                          ))}
                        </div>
                        {p.narrative_explanation && (
                          <p className="mt-1.5 text-slate-400 text-[11px] leading-normal">
                            {p.narrative_explanation}
                          </p>
                        )}
                      </div>
                    ))}
                  </div>
                )}

                {/* Source Citations */}
                {msg.citations && msg.citations.length > 0 && (
                  <div className="mt-4 pt-3 border-t border-slate-800/80 space-y-2">
                    <span className="text-xs font-semibold uppercase tracking-wider text-emerald-400 flex items-center gap-1.5">
                      <FileText className="w-3.5 h-3.5" /> Source Footnotes & Citations
                    </span>
                    <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                      {msg.citations.map((c) => (
                        <div
                          key={c.citation_id}
                          onClick={() => onInspectCitation && onInspectCitation(c)}
                          className="p-2.5 rounded-lg bg-slate-950/60 border border-slate-800 hover:border-slate-700 cursor-pointer transition-colors text-xs"
                        >
                          <div className="flex items-center justify-between text-[11px] text-slate-400 font-medium mb-1">
                            <span>Page {c.page_number}</span>
                            <span className="px-1.5 py-0.2 rounded bg-slate-800 text-slate-300 text-[10px]">
                              {c.citation_type}
                            </span>
                          </div>
                          <p className="text-slate-300 line-clamp-2 text-[11px] leading-snug">
                            {c.snippet}
                          </p>
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                <div
                  className={`text-[10px] mt-2 text-right ${
                    isUser ? 'text-indigo-200' : 'text-slate-500'
                  }`}
                >
                  {msg.timestamp}
                </div>
              </div>

              {isUser && (
                <div className="w-8 h-8 rounded-lg bg-indigo-600 flex items-center justify-center text-white shrink-0 mt-0.5 shadow-md">
                  <User className="w-4 h-4" />
                </div>
              )}
            </div>
          )
        })}
        <div ref={messagesEndRef} />
      </div>

      {/* Starter suggestions if only initial message */}
      {messages.length <= 1 && (
        <div className="px-6 py-2 flex flex-wrap gap-2">
          {STARTER_QUERIES.map((q, i) => (
            <button
              key={i}
              onClick={() => handleSend(q)}
              className="text-xs px-3 py-1.5 rounded-full bg-slate-900 border border-slate-800 hover:border-indigo-500 text-slate-300 hover:text-white transition-all shadow-sm cursor-pointer"
            >
              {q}
            </button>
          ))}
        </div>
      )}

      {/* Input */}
      <div className="p-4 border-t border-slate-800 bg-slate-900/60 backdrop-blur-md">
        <form
          onSubmit={(e) => {
            e.preventDefault()
            handleSend()
          }}
          className="flex items-center gap-3"
        >
          <input
            type="text"
            placeholder="Ask anything about financial metrics, footnotes, or causal drivers..."
            value={inputQuery}
            onChange={(e) => setInputQuery(e.target.value)}
            disabled={isStreaming}
            className="flex-1 px-4 py-3 rounded-xl bg-slate-950 border border-slate-800 text-sm text-white placeholder-slate-500 focus:outline-none focus:border-indigo-500 transition-colors disabled:opacity-50"
          />
          <button
            type="submit"
            disabled={!inputQuery.trim() || isStreaming}
            className="px-5 py-3 rounded-xl bg-indigo-600 hover:bg-indigo-500 text-white font-medium text-sm flex items-center gap-2 transition-colors disabled:opacity-50 disabled:cursor-not-allowed shadow-lg shadow-indigo-600/20 cursor-pointer"
          >
            {isStreaming ? (
              <Loader2 className="w-4 h-4 animate-spin" />
            ) : (
              <Send className="w-4 h-4" />
            )}
            <span>Send</span>
          </button>
        </form>
      </div>
    </div>
  )
}
