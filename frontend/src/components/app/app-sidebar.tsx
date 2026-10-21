import { NavLink, useLocation } from 'react-router-dom'
import {
  Sidebar,
  SidebarContent,
  SidebarFooter,
  SidebarGroup,
  SidebarGroupLabel,
  SidebarHeader,
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
  SidebarRail,
} from '@/components/ui/sidebar'
import { useSession } from '@/state/session'
import { cn } from '@/lib/utils'

function NavItem({
  to,
  end,
  children,
}: {
  to: string
  end?: boolean
  children: React.ReactNode
}) {
  return (
    <SidebarMenuItem>
      <SidebarMenuButton asChild variant="editorial" isActive={false} className="gap-2.5">
        <NavLink to={to} end={end}>
          {({ isActive }) => (
            <>
              <span
                aria-hidden="true"
                className={cn(
                'h-2 shrink-0 bg-brand transition-[width] duration-200 motion-reduce:transition-none',
                isActive ? 'w-2' : 'w-0',
              )}
              />
              <span className={cn('text-xl transition-colors', isActive && 'text-primary')}>{children}</span>
            </>
          )}
        </NavLink>
      </SidebarMenuButton>
    </SidebarMenuItem>
  )
}

export function AppSidebar() {
  const { documents } = useSession()
  const location = useLocation()
  const match = location.pathname.match(/^\/filings\/([^/]+)/)
  const id = match ? decodeURIComponent(match[1]) : undefined
  const filing = documents.find((d) => d.document_id === id)

  return (
    <Sidebar collapsible="offcanvas">
      <SidebarHeader className="px-6 pt-7 pb-0">
        <div className="font-serif text-2xl leading-none">
          Audit<span className="italic text-brand">It</span>
        </div>
      </SidebarHeader>

      <SidebarContent className="gap-0 px-6">
        <SidebarGroup className="p-0 pt-11">
          <SidebarGroupLabel className="sr-only">Workspace</SidebarGroupLabel>
          <SidebarMenu className="gap-0.5">
            <NavItem to="/" end>
              Overview
            </NavItem>
            <NavItem to="/filings">Filings</NavItem>
          </SidebarMenu>
        </SidebarGroup>

        {filing && (
          <SidebarGroup className="p-0 pt-11">
            <SidebarGroupLabel className="truncate px-0 pb-1 text-xs font-normal" title={filing.filename}>
              {filing.filename.replace(/\.pdf$/i, '')}
            </SidebarGroupLabel>
            <SidebarMenu className="gap-0.5">
              <NavItem to={`/filings/${filing.document_id}`} end>Overview</NavItem>
              <NavItem to={`/filings/${filing.document_id}/graph`}>Causal graph</NavItem>
              <NavItem to={`/filings/${filing.document_id}/qa`}>Q&amp;A</NavItem>
              <NavItem to={`/filings/${filing.document_id}/tables`}>Tables</NavItem>
            </SidebarMenu>
          </SidebarGroup>
        )}

        <SidebarGroup className="mt-auto">
          <SidebarMenu className="gap-0.5">
            <NavItem to="/settings">Settings</NavItem>
          </SidebarMenu>
        </SidebarGroup>
      </SidebarContent>

      <SidebarFooter className="space-y-3 border-t border-sidebar-border px-6 py-4">
        <div>
          <p className="text-xs font-medium text-foreground truncate" title={filing?.filename}>
            {filing ? filing.filename.replace(/\.pdf$/i, '') : 'No filing open'}
          </p>
          <p className="mt-0.5 text-xs text-muted-foreground">
            {filing ? 'Audit workspace' : 'Load one from the filings library'}
          </p>
        </div>
      </SidebarFooter>

      <SidebarRail />
    </Sidebar>
  )
}
