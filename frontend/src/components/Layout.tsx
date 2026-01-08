import { Outlet, NavLink } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import {
  Briefcase,
  MessageSquare,
  ScrollText,
  Settings,
  Linkedin,
  CheckCircle,
  XCircle,
  BarChart3,
} from 'lucide-react'
import { authApi } from '../api/client'

const navItems = [
  { to: '/', icon: Briefcase, label: 'Jobs' },
  { to: '/templates', icon: MessageSquare, label: 'Templates' },
  { to: '/logs', icon: ScrollText, label: 'Activity Logs' },
  { to: '/stats', icon: BarChart3, label: 'Stats' },
  { to: '/settings', icon: Settings, label: 'Settings' },
]

function Layout() {
  const { data: authStatus } = useQuery({
    queryKey: ['auth-status'],
    queryFn: authApi.status,
    refetchInterval: 30000, // Check every 30 seconds
  })

  return (
    <div className="min-h-screen flex">
      {/* Sidebar */}
      <aside className="w-64 bg-gray-900 text-white flex flex-col">
        {/* Logo */}
        <div className="p-4 border-b border-gray-800">
          <h1 className="text-2xl font-bold flex items-center gap-2">
            <Briefcase className="w-8 h-8 text-blue-500" />
            JobiAI
          </h1>
          <p className="text-sm text-gray-400 mt-1">LinkedIn Job Bot</p>
        </div>

        {/* Navigation */}
        <nav className="flex-1 p-4">
          <ul className="space-y-2">
            {navItems.map(({ to, icon: Icon, label }) => (
              <li key={to}>
                <NavLink
                  to={to}
                  className={({ isActive }) =>
                    `flex items-center gap-3 px-4 py-2 rounded-lg transition-colors ${
                      isActive
                        ? 'bg-blue-600 text-white'
                        : 'text-gray-300 hover:bg-gray-800'
                    }`
                  }
                >
                  <Icon className="w-5 h-5" />
                  {label}
                </NavLink>
              </li>
            ))}
          </ul>
        </nav>

        {/* LinkedIn Status */}
        <div className="p-4 border-t border-gray-800">
          <div className="flex items-center gap-3 px-4 py-2 bg-gray-800 rounded-lg">
            <Linkedin className="w-5 h-5 text-blue-500" />
            <div className="flex-1">
              <p className="text-sm font-medium">LinkedIn</p>
              <p className="text-xs text-gray-400 flex items-center gap-1">
                {authStatus?.logged_in ? (
                  <>
                    <CheckCircle className="w-3 h-3 text-green-500" />
                    Connected
                  </>
                ) : (
                  <>
                    <XCircle className="w-3 h-3 text-red-500" />
                    Not connected
                  </>
                )}
              </p>
            </div>
          </div>
        </div>
      </aside>

      {/* Main Content */}
      <main className="flex-1 overflow-auto">
        <Outlet />
      </main>
    </div>
  )
}

export default Layout
