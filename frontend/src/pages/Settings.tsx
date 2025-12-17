import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import {
  Linkedin,
  CheckCircle,
  XCircle,
  LogOut,
  Trash2,
  Globe,
  Loader2,
  Building2,
  Lock,
  ExternalLink,
} from 'lucide-react'
import { authApi, selectorsApi } from '../api/client'

function LinkedInSection() {
  const queryClient = useQueryClient()
  const [error, setError] = useState<string | null>(null)

  const { data: authStatus, isLoading } = useQuery({
    queryKey: ['auth-status'],
    queryFn: authApi.status,
  })

  const logoutMutation = useMutation({
    mutationFn: () => authApi.logout(),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['auth-status'] })
    },
  })

  const browserLoginMutation = useMutation({
    mutationFn: () => authApi.loginWithBrowser(),
    onSuccess: (data) => {
      if (data.logged_in) {
        setError(null)
      } else {
        setError(data.message || 'Login failed or cancelled')
      }
      queryClient.invalidateQueries({ queryKey: ['auth-status'] })
    },
    onError: (err: any) => {
      setError(err.response?.data?.detail || 'Browser login failed')
    },
  })

  return (
    <div className="bg-white rounded-xl shadow-sm border border-gray-100 p-6">
      <div className="flex items-center gap-3 mb-4">
        <div className="p-2 bg-blue-100 rounded-lg">
          <Linkedin className="w-6 h-6 text-blue-600" />
        </div>
        <div>
          <h2 className="font-semibold">LinkedIn Connection</h2>
          <p className="text-sm text-gray-500">Connect your LinkedIn account</p>
        </div>
      </div>

      {isLoading ? (
        <div className="flex items-center gap-2 text-gray-500">
          <Loader2 className="w-4 h-4 animate-spin" />
          Checking status...
        </div>
      ) : authStatus?.logged_in ? (
        <div className="space-y-4">
          <div className="flex items-center gap-2 text-green-600">
            <CheckCircle className="w-5 h-5" />
            <span>Connected{authStatus.name && ` as ${authStatus.name}`}</span>
          </div>
          {authStatus.email && (
            <p className="text-sm text-gray-500">Email: {authStatus.email}</p>
          )}
          <button
            onClick={() => logoutMutation.mutate()}
            disabled={logoutMutation.isPending}
            className="flex items-center gap-2 px-4 py-2 border border-red-300 text-red-600 rounded-lg hover:bg-red-50"
          >
            {logoutMutation.isPending ? (
              <Loader2 className="w-4 h-4 animate-spin" />
            ) : (
              <LogOut className="w-4 h-4" />
            )}
            Disconnect
          </button>
        </div>
      ) : (
        <div className="space-y-4">
          <div className="flex items-center gap-2 text-red-600">
            <XCircle className="w-5 h-5" />
            <span>Not connected</span>
          </div>

          <div className="p-4 bg-blue-50 border border-blue-200 rounded-lg">
            <p className="text-sm text-blue-800 mb-3">
              Click the button below to open a browser window. Log in to LinkedIn normally, and the app will automatically capture your session when you're done.
            </p>
            <p className="text-xs text-blue-600">
              The browser will close automatically after successful login.
            </p>
          </div>

          {error && (
            <div className="p-3 bg-red-50 text-red-700 text-sm rounded-lg">
              {error}
            </div>
          )}

          <button
            type="button"
            onClick={() => browserLoginMutation.mutate()}
            disabled={browserLoginMutation.isPending}
            className="flex items-center gap-2 px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50"
          >
            {browserLoginMutation.isPending ? (
              <>
                <Loader2 className="w-4 h-4 animate-spin" />
                Waiting for login...
              </>
            ) : (
              <>
                <ExternalLink className="w-4 h-4" />
                Open Browser to Login
              </>
            )}
          </button>

          {browserLoginMutation.isPending && (
            <p className="text-sm text-gray-500">
              A browser window should have opened. Please log in to LinkedIn there.
            </p>
          )}
        </div>
      )}
    </div>
  )
}

// Pre-configured platforms that are built into the system
const PRECONFIGURED_PLATFORMS = [
  { domain: 'greenhouse.io', name: 'Greenhouse', pattern: 'boards.greenhouse.io/{company}' },
  { domain: 'lever.co', name: 'Lever', pattern: 'jobs.lever.co/{company}' },
  { domain: 'myworkdayjobs.com', name: 'Workday', pattern: '{company}.wd*.myworkdayjobs.com' },
  { domain: 'ashbyhq.com', name: 'Ashby', pattern: 'jobs.ashbyhq.com/{company}' },
  { domain: 'smartrecruiters.com', name: 'SmartRecruiters', pattern: 'jobs.smartrecruiters.com/{company}' },
  { domain: 'breezy.hr', name: 'Breezy HR', pattern: '{company}.breezy.hr' },
  { domain: 'bamboohr.com', name: 'BambooHR', pattern: '{company}.bamboohr.com' },
  { domain: 'recruitee.com', name: 'Recruitee', pattern: '{company}.recruitee.com' },
  { domain: 'applytojob.com', name: 'ApplyToJob', pattern: '{company}.applytojob.com' },
  { domain: 'icims.com', name: 'iCIMS', pattern: 'careers-{company}.icims.com' },
]

function JobSitesSection() {
  const queryClient = useQueryClient()

  const { data: selectors, isLoading } = useQuery({
    queryKey: ['selectors'],
    queryFn: selectorsApi.list,
  })

  const deleteMutation = useMutation({
    mutationFn: (id: number) => selectorsApi.delete(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['selectors'] })
    },
  })

  return (
    <div className="bg-white rounded-xl shadow-sm border border-gray-100 p-6">
      <div className="flex items-center gap-3 mb-4">
        <div className="p-2 bg-purple-100 rounded-lg">
          <Globe className="w-6 h-6 text-purple-600" />
        </div>
        <div>
          <h2 className="font-semibold">Known Job Sites</h2>
          <p className="text-sm text-gray-500">Platforms and sites the bot can extract company names from</p>
        </div>
      </div>

      {/* Pre-configured Platforms */}
      <div className="mb-6">
        <h3 className="text-sm font-medium text-gray-700 mb-2 flex items-center gap-2">
          <Lock className="w-4 h-4" />
          Pre-configured Platforms
        </h3>
        <p className="text-xs text-gray-500 mb-3">
          These platforms are built-in and automatically recognized.
        </p>
        <div className="grid grid-cols-2 gap-2">
          {PRECONFIGURED_PLATFORMS.map((platform) => (
            <div
              key={platform.domain}
              className="flex items-center gap-2 p-2 bg-gray-50 rounded-lg"
            >
              <Globe className="w-4 h-4 text-purple-500" />
              <div className="min-w-0">
                <p className="font-medium text-sm truncate">{platform.name}</p>
                <p className="text-xs text-gray-400 truncate">{platform.domain}</p>
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Learned Sites */}
      <div>
        <h3 className="text-sm font-medium text-gray-700 mb-2">Learned Sites</h3>
        <p className="text-xs text-gray-500 mb-3">
          When you add a job from an unknown site, the bot learns the URL pattern for future use.
        </p>

        {isLoading ? (
          <div className="text-center py-4">
            <Loader2 className="w-6 h-6 animate-spin mx-auto text-gray-400" />
          </div>
        ) : selectors?.length === 0 ? (
          <p className="text-gray-500 text-sm bg-gray-50 p-4 rounded-lg">
            No sites learned yet. Add a job URL from an unknown site and the bot will ask you to help identify it.
          </p>
        ) : (
          <div className="space-y-2">
            {selectors?.map((selector: any) => (
              <div
                key={selector.id}
                className="flex items-center justify-between p-3 bg-gray-50 rounded-lg"
              >
                <div className="flex items-center gap-3">
                  {selector.site_type === 'platform' ? (
                    <Globe className="w-5 h-5 text-blue-500" />
                  ) : (
                    <Building2 className="w-5 h-5 text-green-500" />
                  )}
                  <div>
                    <p className="font-medium text-sm">{selector.domain}</p>
                    <div className="flex items-center gap-2 text-xs text-gray-500">
                      <span className={`px-1.5 py-0.5 rounded ${
                        selector.site_type === 'platform'
                          ? 'bg-blue-100 text-blue-700'
                          : 'bg-green-100 text-green-700'
                      }`}>
                        {selector.site_type === 'platform' ? 'Platform' : 'Company'}
                      </span>
                      {selector.platform_name && (
                        <span>{selector.platform_name}</span>
                      )}
                      {selector.company_name && selector.site_type === 'company' && (
                        <span>→ {selector.company_name}</span>
                      )}
                    </div>
                    {selector.url_pattern && (
                      <p className="text-xs text-gray-400 font-mono truncate max-w-md mt-1">
                        Pattern: {selector.url_pattern}
                      </p>
                    )}
                  </div>
                </div>
                <button
                  onClick={() => deleteMutation.mutate(selector.id)}
                  disabled={deleteMutation.isPending}
                  className="p-2 text-gray-400 hover:text-red-600 hover:bg-red-50 rounded"
                  title="Delete learned site"
                >
                  <Trash2 className="w-4 h-4" />
                </button>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}

function Settings() {
  return (
    <div className="p-8">
      <h1 className="text-2xl font-bold mb-6">Settings</h1>

      <div className="space-y-6 max-w-3xl">
        <LinkedInSection />
        <JobSitesSection />
      </div>
    </div>
  )
}

export default Settings
