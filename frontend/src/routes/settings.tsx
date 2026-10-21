import { useState } from 'react'
import { Button } from '@/components/ui/button'
import {
  Dialog,
  DialogClose,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from '@/components/ui/dialog'
import { Field, FieldDescription, FieldLabel } from '@/components/ui/field'
import { Input } from '@/components/ui/input'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Switch } from '@/components/ui/switch'
import { PageHeader } from '@/components/app/page-header'
import { ModeToggleGroup } from '@/components/mode-toggle'
import { useSession } from '@/state/session'
import { formatCount } from '@/lib/format'
import type { UserSettings } from '@/types'

const PROVIDERS = ['Offline Grounded', 'Gemini', 'OpenAI', 'Anthropic'] as const
const HOPS = [1, 2, 3] as const

function Row({
  title,
  description,
  htmlFor,
  children,
}: {
  title: string
  description?: string
  htmlFor?: string
  children: React.ReactNode
}) {
  return (
    <div className="grid grid-cols-1 items-center gap-x-12 gap-y-3 border-b border-hairline py-5 sm:grid-cols-[minmax(0,1fr)_auto]">
      <Field className="gap-0 border-0 p-0">
        <FieldLabel htmlFor={htmlFor} className="text-sm font-medium">
          {title}
        </FieldLabel>
        {description && <FieldDescription>{description}</FieldDescription>}
      </Field>
      <div className="sm:justify-self-end">{children}</div>
    </div>
  )
}

export function Settings() {
  const { settings, saveSettings, documents } = useSession()
  const [draft, setDraft] = useState<UserSettings>(settings)
  const dirty = JSON.stringify(draft) !== JSON.stringify(settings)

  const set = <K extends keyof UserSettings>(key: K, value: UserSettings[K]) =>
    setDraft((d) => ({ ...d, [key]: value }))

  const clearStored = () => {
    const cleared: UserSettings = {
      provider: 'Offline Grounded',
      apiKey: '',
      graphBackend: 'networkx',
      showFootnotes: true,
      hops: 2,
    }
    setDraft(cleared)
    saveSettings(cleared)
  }

  return (
    <>
      <PageHeader
        title="Settings"
        lede="Control how the engine reads filings and shows evidence."
        actions={
          <>
            {dirty && (
              <Button variant="ghost" onClick={() => setDraft(settings)}>
                Discard
              </Button>
            )}
            <Button disabled={!dirty} onClick={() => saveSettings(draft)}>
              Save changes
            </Button>
          </>
        }
      />

      <div className="border-t border-foreground">
        <Row title="Theme" description="Follows your system by default.">
          <ModeToggleGroup />
        </Row>

        <Row
          title="LLM reasoning engine"
          description="Offline mode runs locally with no external calls. The rest need a key."
          htmlFor="provider"
        >
          <Select
            value={draft.provider}
            onValueChange={(v) => set('provider', v as UserSettings['provider'])}
          >
            <SelectTrigger id="provider" className="w-48">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {PROVIDERS.map((p) => (
                <SelectItem key={p} value={p}>
                  {p}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </Row>

        {draft.provider !== 'Offline Grounded' && (
          <Row
            title={`${draft.provider} API key`}
            description={
              settings.apiKey
                ? 'Active in this browser session. Sent per query as a header.'
                : 'Not saved in browser. Will use backend GEMINI_API_KEY from environment if available.'
            }
            htmlFor="api-key"
          >
            <div className="flex flex-col items-end gap-1.5">
              <Input
                id="api-key"
                name="llm_api_key"
                type="password"
                autoComplete="off"
                placeholder={settings.apiKey ? '••••••••••••••••' : 'Enter API key...'}
                value={draft.apiKey}
                onChange={(e) => set('apiKey', e.target.value)}
                className="w-64"
              />
              {dirty && (
                <span className="text-xs font-medium text-brand">
                  Unsaved changes — remember to click "Save changes" above
                </span>
              )}
            </div>
          </Row>
        )}

        <Row
          title="Graph storage adapter"
          description="NetworkX is in-memory. Neo4j persists across restarts."
          htmlFor="backend"
        >
          <Select
            value={draft.graphBackend}
            onValueChange={(v) => set('graphBackend', v as UserSettings['graphBackend'])}
          >
            <SelectTrigger id="backend" className="w-48">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="networkx">NetworkX</SelectItem>
              <SelectItem value="neo4j">Neo4j</SelectItem>
            </SelectContent>
          </Select>
        </Row>

        <Row
          title="Show footnote nodes"
          description="Include narrative disclosure nodes in the causal graph."
        >
          <Switch
            checked={draft.showFootnotes}
            onCheckedChange={(v) => set('showFootnotes', v)}
            aria-label="Show footnote nodes"
          />
        </Row>

        <Row title="Default hop depth" description="How far the graph expands from a node." htmlFor="hop-depth">
          <Select
            value={String(draft.hops)}
            onValueChange={(v) => v && set('hops', Number(v) as UserSettings['hops'])}
          >
            <SelectTrigger id="hop-depth" className="w-48">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {HOPS.map((h) => (
                <SelectItem key={h} value={String(h)}>
                  {h} hop{h > 1 ? 's' : ''}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </Row>

        <Row title="Session" description="Filings are scoped to this browser session.">
          <p className="font-mono text-sm tabular-nums text-muted-foreground">
            {formatCount(documents.length)} open
          </p>
        </Row>

        <Row
          title="Clear stored settings"
          description="Removes the provider, key and adapter saved in this browser. Ingested filings are untouched."
        >
          <Dialog>
            <DialogTrigger asChild>
              <Button variant="destructive">Clear stored settings</Button>
            </DialogTrigger>
            <DialogContent>
              <DialogHeader>
                <DialogTitle>Clear stored settings?</DialogTitle>
                <DialogDescription>
                  This will reset your model provider, API key, and graph storage backend to defaults. Ingested filings in this session are untouched.
                </DialogDescription>
              </DialogHeader>
              <DialogFooter className="mt-4 gap-2">
                <DialogClose asChild>
                  <Button variant="outline">Cancel</Button>
                </DialogClose>
                <DialogClose asChild>
                  <Button variant="destructive" onClick={clearStored}>
                    Confirm reset
                  </Button>
                </DialogClose>
              </DialogFooter>
            </DialogContent>
          </Dialog>
        </Row>
      </div>
    </>
  )
}
