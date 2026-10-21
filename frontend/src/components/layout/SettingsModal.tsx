import React, { useState, useEffect } from 'react'
import { X, Key, Cpu, Database, Check } from 'lucide-react'
import type { UserSettings } from '../../types'

interface SettingsModalProps {
  isOpen: boolean
  onClose: () => void
  onSaved?: (settings: UserSettings) => void
}

export const SettingsModal: React.FC<SettingsModalProps> = ({
  isOpen,
  onClose,
  onSaved,
}) => {
  const [provider, setProvider] = useState<UserSettings['provider']>('Offline Grounded')
  const [apiKey, setApiKey] = useState<string>('')
  const [graphBackend, setGraphBackend] = useState<'networkx' | 'neo4j'>('networkx')
  const [savedNotice, setSavedNotice] = useState<boolean>(false)

  useEffect(() => {
    try {
      const stored = localStorage.getItem('auditit_user_settings')
      if (stored) {
        const parsed: UserSettings = JSON.parse(stored)
        if (parsed.provider) setProvider(parsed.provider)
        if (parsed.apiKey) setApiKey(parsed.apiKey)
        if (parsed.graphBackend) setGraphBackend(parsed.graphBackend)
      }
    } catch (e) {
      console.error('Failed to load settings', e)
    }
  }, [isOpen])

  if (!isOpen) return null

  const handleSave = () => {
    const settings: UserSettings = {
      provider,
      apiKey: apiKey.trim(),
      graphBackend,
    }
    localStorage.setItem('auditit_user_settings', JSON.stringify(settings))
    setSavedNotice(true)
    if (onSaved) onSaved(settings)
    setTimeout(() => {
      setSavedNotice(false)
      onClose()
    }, 600)
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-950/80 backdrop-blur-sm">
      <div className="relative w-full max-w-md bg-slate-900 border border-slate-800 rounded-2xl shadow-2xl overflow-hidden">
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-slate-800">
          <div className="flex items-center gap-2">
            <Cpu className="w-5 h-5 text-indigo-400" />
            <h3 className="text-base font-semibold text-white">System & Model Settings</h3>
          </div>
          <button
            onClick={onClose}
            className="p-1 text-slate-400 hover:text-white rounded-lg hover:bg-slate-800 transition-colors"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Form Body */}
        <div className="p-6 space-y-5">
          {/* Provider Selection */}
          <div>
            <label className="block text-xs font-semibold text-slate-300 uppercase tracking-wider mb-2">
              LLM Reasoning Engine
            </label>
            <div className="grid grid-cols-2 gap-2">
              {(['Offline Grounded', 'Gemini', 'OpenAI', 'Anthropic'] as const).map(
                (p) => (
                  <button
                    key={p}
                    type="button"
                    onClick={() => setProvider(p)}
                    className={`px-3 py-2.5 rounded-xl border text-xs font-medium text-left transition-all ${
                      provider === p
                        ? 'bg-indigo-600/20 border-indigo-500 text-white'
                        : 'bg-slate-950 border-slate-800 text-slate-400 hover:border-slate-700 hover:text-slate-200'
                    }`}
                  >
                    {p}
                  </button>
                )
              )}
            </div>
            <p className="text-[11px] text-slate-500 mt-1.5 leading-snug">
              Offline mode runs 100% locally with zero external network calls. Gemini, OpenAI, and Anthropic require a BYOK API key below.
            </p>
          </div>

          {/* BYOK API Key */}
          {provider !== 'Offline Grounded' && (
            <div>
              <label className="block text-xs font-semibold text-slate-300 uppercase tracking-wider mb-2 flex items-center gap-1.5">
                <Key className="w-3.5 h-3.5 text-indigo-400" /> {provider} API Key
              </label>
              <input
                type="password"
                placeholder={`Enter your ${provider} API Key...`}
                value={apiKey}
                onChange={(e) => setApiKey(e.target.value)}
                className="w-full px-4 py-2.5 rounded-xl bg-slate-950 border border-slate-800 text-xs text-white placeholder-slate-600 focus:outline-none focus:border-indigo-500 font-mono"
              />
              <p className="text-[10px] text-slate-500 mt-1">
                Keys are stored only in your browser's local session storage and transmitted per-query via header.
              </p>
            </div>
          )}

          {/* Graph Storage Backend */}
          <div>
            <label className="block text-xs font-semibold text-slate-300 uppercase tracking-wider mb-2 flex items-center gap-1.5">
              <Database className="w-3.5 h-3.5 text-emerald-400" /> Graph Storage Adapter
            </label>
            <div className="grid grid-cols-2 gap-2">
              <button
                type="button"
                onClick={() => setGraphBackend('networkx')}
                className={`px-3 py-2.5 rounded-xl border text-xs font-medium text-left transition-all ${
                  graphBackend === 'networkx'
                    ? 'bg-emerald-600/20 border-emerald-500 text-white'
                    : 'bg-slate-950 border-slate-800 text-slate-400 hover:border-slate-700'
                }`}
              >
                NetworkX (In-Memory)
              </button>
              <button
                type="button"
                onClick={() => setGraphBackend('neo4j')}
                className={`px-3 py-2.5 rounded-xl border text-xs font-medium text-left transition-all ${
                  graphBackend === 'neo4j'
                    ? 'bg-emerald-600/20 border-emerald-500 text-white'
                    : 'bg-slate-950 border-slate-800 text-slate-400 hover:border-slate-700'
                }`}
              >
                Neo4j (Persistent)
              </button>
            </div>
          </div>
        </div>

        {/* Footer */}
        <div className="flex items-center justify-between px-6 py-4 border-t border-slate-800 bg-slate-950/50">
          <span className="text-xs text-emerald-400 flex items-center gap-1">
            {savedNotice && (
              <>
                <Check className="w-3.5 h-3.5" /> Saved settings!
              </>
            )}
          </span>
          <div className="flex items-center gap-2">
            <button
              onClick={onClose}
              className="px-4 py-2 rounded-xl text-xs font-medium text-slate-400 hover:text-white transition-colors"
            >
              Cancel
            </button>
            <button
              onClick={handleSave}
              className="px-5 py-2 rounded-xl bg-indigo-600 hover:bg-indigo-500 text-white text-xs font-medium transition-colors shadow-lg shadow-indigo-600/20"
            >
              Save Changes
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}
