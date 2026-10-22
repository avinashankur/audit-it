import { NavLink } from 'react-router-dom'
import {
  Sidebar,
  SidebarContent,
  SidebarGroup,
  SidebarGroupLabel,
  SidebarHeader,
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
  SidebarRail,
} from '@/components/ui/sidebar'
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

        <SidebarGroup className="mt-auto">
          <SidebarMenu className="gap-0.5">
            <NavItem to="/settings">Settings</NavItem>
          </SidebarMenu>
        </SidebarGroup>
      </SidebarContent>

      <SidebarRail />
    </Sidebar>
  )
}
