import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import {
  Plus,
  Trash2,
  RefreshCw,
  ExternalLink,
  CheckCircle,
  XCircle,
  Clock,
  Loader2,
  HelpCircle,
  X,
  Building2,
  Globe,
  Play,
  AlertTriangle,
  LogIn,
  Languages,
  StopCircle,
  RotateCw,
  Ban,
} from 'lucide-react'
import { jobsApi, authApi, templatesApi } from '../api/client'
import { useNavigate } from 'react-router-dom'

interface Job {
  id: number
  url: string
  company_name: string | null
  job_title: string | null
  status: string
  workflow_step: string
  error_message: string | null
  pending_hebrew_names: string[] | null
  created_at: string
}

interface Template {
  id: number
  name: string
  content_male: string
  content_female: string
  is_default: boolean
}

function JobSubmitForm({ onSuccess }: { onSuccess: () => void }) {
  const [url, setUrl] = useState('')
  const queryClient = useQueryClient()

  const createMutation = useMutation({
    mutationFn: (url: string) => jobsApi.create(url),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['jobs'] })
      setUrl('')
      onSuccess()
    },
  })

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    if (url.trim()) {
      createMutation.mutate(url.trim())
    }
  }

  return (
    <form onSubmit={handleSubmit} className="flex gap-2">
      <input
        type="url"
        value={url}
        onChange={e => setUrl(e.target.value)}
        placeholder="Paste job URL here..."
        className="flex-1 px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
        required
      />
      <button
        type="submit"
        disabled={createMutation.isPending}
        className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50 flex items-center gap-2"
      >
        {createMutation.isPending ? (
          <Loader2 className="w-4 h-4 animate-spin" />
        ) : (
          <Plus className="w-4 h-4" />
        )}
        Add Job
      </button>
    </form>
  )
}

function StatusBadge({ status, isWaiting, isProcessing }: { status: string; isWaiting?: boolean; isProcessing?: boolean }) {
  // If job is waiting (ready to run), show blue "Waiting"
  if (isWaiting) {
    return (
      <span className="inline-flex items-center gap-1 px-2 py-1 rounded-full text-xs font-medium bg-blue-100 text-blue-700">
        <Clock className="w-3 h-3" />
        Waiting
      </span>
    )
  }

  // If job is currently processing, show yellow "Processing" (no spinning icon - the workflow badge has it)
  if (isProcessing) {
    return (
      <span className="inline-flex items-center gap-1 px-2 py-1 rounded-full text-xs font-medium bg-yellow-100 text-yellow-700">
        Processing
      </span>
    )
  }

  const config: Record<string, { icon: typeof Clock; color: string; label: string }> = {
    pending: { icon: Clock, color: 'bg-gray-100 text-gray-700', label: 'Pending' },
    processing: { icon: Loader2, color: 'bg-yellow-100 text-yellow-700', label: 'Processing' },
    needs_input: { icon: HelpCircle, color: 'bg-orange-100 text-orange-700', label: 'Needs Input' },
    completed: { icon: CheckCircle, color: 'bg-green-100 text-green-700', label: 'Completed' },
    failed: { icon: XCircle, color: 'bg-red-100 text-red-700', label: 'Failed' },
    aborted: { icon: Ban, color: 'bg-gray-100 text-gray-600', label: 'Aborted' },
  }

  const { icon: Icon, color, label } = config[status] || config.pending

  return (
    <span className={`inline-flex items-center gap-1 px-2 py-1 rounded-full text-xs font-medium ${color}`}>
      <Icon className={`w-3 h-3 ${status === 'processing' ? 'animate-spin' : ''}`} />
      {label}
    </span>
  )
}

function WorkflowBadge({ step, isProcessing }: { step: string; isProcessing?: boolean }) {
  // When processing, show "Working" with spinning arrows
  if (isProcessing) {
    return (
      <span className="inline-flex items-center gap-1 px-2 py-1 rounded-full text-xs font-medium bg-yellow-100 text-yellow-700">
        <RotateCw className="w-3 h-3 animate-spin" />
        Working
      </span>
    )
  }

  const stepLabels: Record<string, { label: string; color: string; icon?: string }> = {
    company_extraction: { label: 'Ready', color: 'bg-blue-100 text-blue-700', icon: 'play' },
    search_connections: { label: 'Ready', color: 'bg-blue-100 text-blue-700', icon: 'play' },
    needs_hebrew_names: { label: 'Needs Names', color: 'bg-purple-100 text-purple-700', icon: 'language' },
    message_connections: { label: 'Ready', color: 'bg-blue-100 text-blue-700', icon: 'play' },
    search_linkedin: { label: 'Ready', color: 'bg-blue-100 text-blue-700', icon: 'play' },
    send_requests: { label: 'Ready', color: 'bg-blue-100 text-blue-700', icon: 'play' },
    done: { label: 'Done', color: 'bg-green-100 text-green-700', icon: 'check' },
  }

  const { label, color, icon } = stepLabels[step] || { label: step, color: 'bg-gray-100 text-gray-700', icon: 'play' }

  return (
    <span className={`inline-flex items-center gap-1 px-2 py-1 rounded-full text-xs font-medium ${color}`}>
      {icon === 'check' && <CheckCircle className="w-3 h-3" />}
      {icon === 'play' && <Play className="w-3 h-3" />}
      {icon === 'language' && <Languages className="w-3 h-3" />}
      {label}
    </span>
  )
}

function CompanyInputModal({
  job,
  onClose,
  onSubmit,
  isPending,
}: {
  job: Job
  onClose: () => void
  onSubmit: (companyName: string, siteType: 'company' | 'platform', platformName?: string) => void
  isPending: boolean
}) {
  const [companyName, setCompanyName] = useState('')
  const [siteType, setSiteType] = useState<'company' | 'platform'>('company')
  const [platformName, setPlatformName] = useState('')

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    if (companyName.trim()) {
      onSubmit(
        companyName.trim(),
        siteType,
        siteType === 'platform' ? platformName.trim() : undefined
      )
    }
  }

  // Extract domain from URL for display
  let domain = ''
  try {
    domain = new URL(job.url).hostname
  } catch {
    domain = job.url
  }

  const isValid = companyName.trim() && (siteType === 'company' || platformName.trim())

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
      <div className="bg-white rounded-xl shadow-xl w-full max-w-md mx-4">
        <div className="flex items-center justify-between p-4 border-b">
          <h3 className="text-lg font-semibold flex items-center gap-2">
            <Building2 className="w-5 h-5 text-orange-500" />
            New Job Site Detected
          </h3>
          <button
            onClick={onClose}
            className="p-1 hover:bg-gray-100 rounded"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        <form onSubmit={handleSubmit} className="p-4">
          <p className="text-sm text-gray-600 mb-4">
            We don't recognize <strong>{domain}</strong>.
            Help us learn about this site so we can recognize it in the future.
          </p>

          {/* Site Type Selection */}
          <div className="mb-4">
            <label className="block text-sm font-medium text-gray-700 mb-2">
              What type of site is this?
            </label>
            <div className="grid grid-cols-2 gap-2">
              <button
                type="button"
                onClick={() => setSiteType('company')}
                className={`p-3 rounded-lg border-2 text-left transition-colors ${
                  siteType === 'company'
                    ? 'border-blue-500 bg-blue-50'
                    : 'border-gray-200 hover:border-gray-300'
                }`}
              >
                <Building2 className={`w-5 h-5 mb-1 ${siteType === 'company' ? 'text-blue-600' : 'text-gray-400'}`} />
                <div className="font-medium text-sm">Company Website</div>
                <div className="text-xs text-gray-500">Company's own career page</div>
              </button>
              <button
                type="button"
                onClick={() => setSiteType('platform')}
                className={`p-3 rounded-lg border-2 text-left transition-colors ${
                  siteType === 'platform'
                    ? 'border-blue-500 bg-blue-50'
                    : 'border-gray-200 hover:border-gray-300'
                }`}
              >
                <Globe className={`w-5 h-5 mb-1 ${siteType === 'platform' ? 'text-blue-600' : 'text-gray-400'}`} />
                <div className="font-medium text-sm">Job Platform</div>
                <div className="text-xs text-gray-500">Hosts jobs for many companies</div>
              </button>
            </div>
          </div>

          {/* Platform Name (only if platform selected) */}
          {siteType === 'platform' && (
            <div className="mb-4">
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Platform Name
              </label>
              <input
                type="text"
                value={platformName}
                onChange={e => setPlatformName(e.target.value)}
                placeholder="e.g., Greenhouse, Lever, Workday"
                className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                required={siteType === 'platform'}
              />
              <p className="text-xs text-gray-500 mt-1">
                The name of the job platform hosting this listing
              </p>
            </div>
          )}

          {/* Company Name */}
          <div className="mb-4">
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Company Name
            </label>
            <input
              type="text"
              value={companyName}
              onChange={e => setCompanyName(e.target.value)}
              placeholder="e.g., Google, Microsoft, Startup Inc."
              className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
              autoFocus
              required
            />
            <p className="text-xs text-gray-500 mt-1">
              {siteType === 'company'
                ? 'This company will be associated with this domain'
                : 'The company name from this specific job posting'}
            </p>
          </div>

          <div className="bg-gray-50 rounded-lg p-3 mb-4">
            <p className="text-xs text-gray-500">
              <strong>Job URL:</strong>{' '}
              <a
                href={job.url}
                target="_blank"
                rel="noopener noreferrer"
                className="text-blue-600 hover:underline"
              >
                {job.url.length > 50 ? job.url.substring(0, 50) + '...' : job.url}
              </a>
            </p>
            {siteType === 'platform' && (
              <p className="text-xs text-gray-500 mt-2">
                <strong>Note:</strong> The system will learn the URL pattern to automatically
                extract company names from future {platformName || 'this platform'} URLs.
              </p>
            )}
          </div>

          <div className="flex gap-2">
            <button
              type="button"
              onClick={onClose}
              className="flex-1 px-4 py-2 border border-gray-300 text-gray-700 rounded-lg hover:bg-gray-50"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={isPending || !isValid}
              className="flex-1 px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50 flex items-center justify-center gap-2"
            >
              {isPending ? (
                <Loader2 className="w-4 h-4 animate-spin" />
              ) : (
                <CheckCircle className="w-4 h-4" />
              )}
              Save & Learn
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}

function LinkedInLoginModal({
  onClose,
  onGoToSettings,
}: {
  onClose: () => void
  onGoToSettings: () => void
}) {
  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
      <div className="bg-white rounded-xl shadow-xl w-full max-w-md mx-4">
        <div className="flex items-center justify-between p-4 border-b">
          <h3 className="text-lg font-semibold flex items-center gap-2">
            <AlertTriangle className="w-5 h-5 text-yellow-500" />
            LinkedIn Login Required
          </h3>
          <button
            onClick={onClose}
            className="p-1 hover:bg-gray-100 rounded"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        <div className="p-4">
          <p className="text-sm text-gray-600 mb-4">
            You need to be logged into LinkedIn to run the workflow.
            The workflow will search for connections and send messages on your behalf.
          </p>

          <div className="bg-yellow-50 border border-yellow-200 rounded-lg p-3 mb-4">
            <p className="text-sm text-yellow-800">
              <strong>Note:</strong> You'll need to log in manually in the browser window that opens.
              Your session will be saved for future use.
            </p>
          </div>

          <div className="flex gap-2">
            <button
              type="button"
              onClick={onClose}
              className="flex-1 px-4 py-2 border border-gray-300 text-gray-700 rounded-lg hover:bg-gray-50"
            >
              Cancel
            </button>
            <button
              type="button"
              onClick={onGoToSettings}
              className="flex-1 px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 flex items-center justify-center gap-2"
            >
              <LogIn className="w-4 h-4" />
              Go to Settings
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}

function NoDefaultTemplateModal({
  onClose,
  onGoToTemplates,
}: {
  onClose: () => void
  onGoToTemplates: () => void
}) {
  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
      <div className="bg-white rounded-xl shadow-xl w-full max-w-md mx-4">
        <div className="flex items-center justify-between p-4 border-b">
          <h3 className="text-lg font-semibold flex items-center gap-2">
            <AlertTriangle className="w-5 h-5 text-yellow-500" />
            No Default Template
          </h3>
          <button onClick={onClose} className="p-1 hover:bg-gray-100 rounded">
            <X className="w-5 h-5" />
          </button>
        </div>
        <div className="p-4">
          <p className="text-sm text-gray-600 mb-4">
            Please go to the Templates page and set a default template before running the workflow.
          </p>
          <div className="flex gap-2">
            <button
              type="button"
              onClick={onClose}
              className="flex-1 px-4 py-2 border border-gray-300 text-gray-700 rounded-lg hover:bg-gray-50"
            >
              Cancel
            </button>
            <button
              type="button"
              onClick={onGoToTemplates}
              className="flex-1 px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700"
            >
              Go to Templates
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}

function HebrewNamesInputModal({
  job,
  onClose,
  onSubmit,
  isPending,
}: {
  job: Job
  onClose: () => void
  onSubmit: (names: { english_name: string; hebrew_name: string }[]) => void
  isPending: boolean
}) {
  const pendingNames = job.pending_hebrew_names || []
  const [translations, setTranslations] = useState<Record<string, string>>(
    Object.fromEntries(pendingNames.map(name => [name, '']))
  )

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    const names = Object.entries(translations)
      .filter(([_, hebrew]) => hebrew.trim())
      .map(([english, hebrew]) => ({
        english_name: english,
        hebrew_name: hebrew.trim(),
      }))
    if (names.length > 0) {
      onSubmit(names)
    }
  }

  const allFilled = pendingNames.every(name => translations[name]?.trim())

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
      <div className="bg-white rounded-xl shadow-xl w-full max-w-md mx-4">
        <div className="flex items-center justify-between p-4 border-b">
          <h3 className="text-lg font-semibold flex items-center gap-2">
            <Languages className="w-5 h-5 text-purple-500" />
            Hebrew Name Translations
          </h3>
          <button
            onClick={onClose}
            className="p-1 hover:bg-gray-100 rounded"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        <form onSubmit={handleSubmit} className="p-4">
          <p className="text-sm text-gray-600 mb-4">
            The following names need Hebrew translations for personalized messages.
            Please provide the Hebrew spelling for each name.
          </p>

          <div className="space-y-3 mb-4">
            {pendingNames.map(name => (
              <div key={name} className="flex items-center gap-2">
                <div className="w-24 text-sm font-medium text-gray-700 capitalize">
                  {name}
                </div>
                <span className="text-gray-400">→</span>
                <input
                  type="text"
                  value={translations[name] || ''}
                  onChange={e => setTranslations(prev => ({
                    ...prev,
                    [name]: e.target.value,
                  }))}
                  placeholder="Hebrew spelling"
                  className="flex-1 px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-purple-500 focus:border-transparent text-right"
                  dir="rtl"
                  required
                />
              </div>
            ))}
          </div>

          <div className="bg-purple-50 border border-purple-200 rounded-lg p-3 mb-4">
            <p className="text-xs text-purple-800">
              <strong>Note:</strong> These translations will be saved for future use.
              Names like "David" → "דוד" will be remembered automatically.
            </p>
          </div>

          <div className="flex gap-2">
            <button
              type="button"
              onClick={onClose}
              className="flex-1 px-4 py-2 border border-gray-300 text-gray-700 rounded-lg hover:bg-gray-50"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={isPending || !allFilled}
              className="flex-1 px-4 py-2 bg-purple-600 text-white rounded-lg hover:bg-purple-700 disabled:opacity-50 flex items-center justify-center gap-2"
            >
              {isPending ? (
                <Loader2 className="w-4 h-4 animate-spin" />
              ) : (
                <CheckCircle className="w-4 h-4" />
              )}
              Save & Continue
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}

function Jobs() {
  const [statusFilter, setStatusFilter] = useState<string | undefined>()
  const [selectedJob, setSelectedJob] = useState<Job | null>(null)
  const [hebrewNamesJob, setHebrewNamesJob] = useState<Job | null>(null)
  const [showLoginModal, setShowLoginModal] = useState(false)
  const [showNoTemplateModal, setShowNoTemplateModal] = useState(false)
  const [isAborting, setIsAborting] = useState(false)
  const queryClient = useQueryClient()
  const navigate = useNavigate()

  const { data, isLoading } = useQuery({
    queryKey: ['jobs', statusFilter],
    queryFn: () => jobsApi.list(statusFilter),
    refetchInterval: 5000, // Poll every 5 seconds for status updates
  })

  // Check LinkedIn login status
  const { data: authStatus } = useQuery({
    queryKey: ['auth-status'],
    queryFn: () => authApi.status(),
    refetchInterval: 30000, // Check every 30 seconds
  })

  // Get templates list
  const { data: templates = [] } = useQuery<Template[]>({
    queryKey: ['templates'],
    queryFn: () => templatesApi.list(),
  })

  // Check if there's a currently running job
  const { data: currentJobData } = useQuery({
    queryKey: ['current-job'],
    queryFn: () => jobsApi.getCurrent(),
    refetchInterval: 2000, // Poll every 2 seconds when workflow is running
  })

  const isLinkedInLoggedIn = authStatus?.logged_in === true
  const currentRunningJobId = currentJobData?.job_id

  const deleteMutation = useMutation({
    mutationFn: (id: number) => jobsApi.delete(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['jobs'] })
    },
  })

  const retryMutation = useMutation({
    mutationFn: (id: number) => jobsApi.retry(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['jobs'] })
    },
  })

  const submitCompanyMutation = useMutation({
    mutationFn: ({
      id,
      companyName,
      siteType,
      platformName,
    }: {
      id: number
      companyName: string
      siteType: 'company' | 'platform'
      platformName?: string
    }) => jobsApi.submitCompany(id, companyName, siteType, platformName),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['jobs'] })
      setSelectedJob(null)
    },
  })

  // Get the default template
  const defaultTemplate = templates.find(t => t.is_default)

  const workflowMutation = useMutation({
    mutationFn: (jobId: number) => {
      if (!defaultTemplate) {
        throw new Error('No default template')
      }
      return jobsApi.triggerWorkflow(jobId, defaultTemplate.id)
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['jobs'] })
    },
  })

  const submitHebrewNamesMutation = useMutation({
    mutationFn: ({
      id,
      names,
    }: {
      id: number
      names: { english_name: string; hebrew_name: string }[]
    }) => jobsApi.submitHebrewNames(id, names),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['jobs'] })
      setHebrewNamesJob(null)
    },
  })

  // Abort workflow mutation
  const abortMutation = useMutation({
    mutationFn: () => {
      setIsAborting(true)
      return jobsApi.abort()
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['jobs'] })
      queryClient.invalidateQueries({ queryKey: ['current-job'] })
      // Keep isAborting true longer - workflow needs time to actually stop
      // Reset after 10 seconds max, but job status change will hide button anyway
      setTimeout(() => setIsAborting(false), 10000)
    },
    onError: () => {
      setIsAborting(false)
    },
  })

  const jobs: Job[] = data?.jobs || []

  // Count jobs needing input
  const needsInputCount = jobs.filter(j => j.status === 'needs_input').length

  // Get jobs ready to run (completed, failed, or aborted with company_name and not done)
  const runnableJobs = jobs.filter(
    j => (j.status === 'completed' || j.status === 'failed' || j.status === 'aborted') && j.company_name && j.workflow_step !== 'done'
  )

  // Run all jobs mutation
  const runAllMutation = useMutation({
    mutationFn: async () => {
      if (!defaultTemplate) {
        throw new Error('No default template')
      }
      // Run jobs sequentially in FIFO order (oldest first)
      const fifoJobs = [...runnableJobs].reverse()
      for (const job of fifoJobs) {
        await jobsApi.triggerWorkflow(job.id, defaultTemplate.id)
      }
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['jobs'] })
    },
  })

  return (
    <div className="p-8">
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold">Jobs</h1>
        <div className="flex items-center gap-2">
          {/* Run All Jobs Button */}
          {runnableJobs.length > 0 && (
            !isLinkedInLoggedIn ? (
              <button
                onClick={() => setShowLoginModal(true)}
                className="px-4 py-2 bg-yellow-100 text-yellow-700 rounded-lg hover:bg-yellow-200 flex items-center gap-2 text-sm"
                title="LinkedIn login required"
              >
                <AlertTriangle className="w-4 h-4" />
                Run All ({runnableJobs.length})
              </button>
            ) : !defaultTemplate ? (
              <button
                onClick={() => setShowNoTemplateModal(true)}
                className="px-4 py-2 bg-yellow-100 text-yellow-700 rounded-lg hover:bg-yellow-200 flex items-center gap-2 text-sm"
                title="No default template set"
              >
                <AlertTriangle className="w-4 h-4" />
                Run All ({runnableJobs.length})
              </button>
            ) : (
              <button
                onClick={() => runAllMutation.mutate()}
                disabled={runAllMutation.isPending}
                className="px-4 py-2 bg-green-600 text-white rounded-lg hover:bg-green-700 disabled:opacity-50 flex items-center gap-2 text-sm"
                title={`Run workflow for ${runnableJobs.length} jobs with "${defaultTemplate.name}"`}
              >
                {runAllMutation.isPending ? (
                  <Loader2 className="w-4 h-4 animate-spin" />
                ) : (
                  <Play className="w-4 h-4" />
                )}
                Run All ({runnableJobs.length})
              </button>
            )
          )}
          <select
            value={statusFilter || ''}
            onChange={e => setStatusFilter(e.target.value || undefined)}
            className="px-3 py-2 border border-gray-300 rounded-lg text-sm"
          >
            <option value="">All Status</option>
            <option value="pending">Pending</option>
            <option value="processing">Processing</option>
            <option value="needs_input">Needs Input {needsInputCount > 0 ? `(${needsInputCount})` : ''}</option>
            <option value="completed">Completed</option>
            <option value="failed">Failed</option>
            <option value="aborted">Aborted</option>
          </select>
        </div>
      </div>

      {/* Alert for jobs needing input */}
      {needsInputCount > 0 && !statusFilter && (
        <div className="bg-orange-50 border border-orange-200 rounded-lg p-4 mb-6 flex items-center gap-3">
          <HelpCircle className="w-5 h-5 text-orange-500 flex-shrink-0" />
          <div className="flex-1">
            <p className="text-sm text-orange-800">
              <strong>{needsInputCount} job{needsInputCount > 1 ? 's' : ''}</strong> need{needsInputCount === 1 ? 's' : ''} your input.
              The bot doesn't recognize the job site and needs you to provide information.
            </p>
          </div>
          <button
            onClick={() => setStatusFilter('needs_input')}
            className="px-3 py-1 bg-orange-100 text-orange-700 rounded text-sm hover:bg-orange-200"
          >
            View
          </button>
        </div>
      )}

      {/* Add Job Form */}
      <div className="bg-white rounded-xl shadow-sm border border-gray-100 p-4 mb-6">
        <h2 className="font-medium mb-3">Add New Job</h2>
        <JobSubmitForm onSuccess={() => {}} />
      </div>

      {/* Jobs List */}
      <div className="bg-white rounded-xl shadow-sm border border-gray-100">
        {isLoading ? (
          <div className="p-8 text-center">
            <Loader2 className="w-8 h-8 animate-spin mx-auto text-gray-400" />
          </div>
        ) : jobs.length === 0 ? (
          <div className="p-8 text-center text-gray-500">
            No jobs found. Add a job URL above to get started.
          </div>
        ) : (
          <table className="w-full">
            <thead className="bg-gray-50 border-b border-gray-100">
              <tr>
                <th className="text-left px-4 py-3 text-sm font-medium text-gray-500">Company</th>
                <th className="text-left px-4 py-3 text-sm font-medium text-gray-500">URL</th>
                <th className="text-left px-4 py-3 text-sm font-medium text-gray-500">Status</th>
                <th className="text-left px-4 py-3 text-sm font-medium text-gray-500">Workflow</th>
                <th className="text-left px-4 py-3 text-sm font-medium text-gray-500">Created</th>
                <th className="text-right px-4 py-3 text-sm font-medium text-gray-500">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {jobs.map((job: Job) => (
                <tr key={job.id} className={`hover:bg-gray-50 ${job.status === 'needs_input' && job.workflow_step !== 'needs_hebrew_names' ? 'bg-orange-50' : ''} ${job.workflow_step === 'needs_hebrew_names' ? 'bg-purple-50' : ''}`}>
                  <td className="px-4 py-3">
                    {job.workflow_step === 'needs_hebrew_names' ? (
                      <button
                        onClick={() => setHebrewNamesJob(job)}
                        className="text-purple-600 hover:text-purple-800 font-medium flex items-center gap-1"
                      >
                        <Languages className="w-4 h-4" />
                        Click to enter Hebrew names
                      </button>
                    ) : job.status === 'needs_input' ? (
                      <button
                        onClick={() => setSelectedJob(job)}
                        className="text-orange-600 hover:text-orange-800 font-medium flex items-center gap-1"
                      >
                        <HelpCircle className="w-4 h-4" />
                        Click to enter company
                      </button>
                    ) : (
                      <>
                        <span className="font-medium">
                          {job.company_name || (job.status === 'processing' || job.status === 'pending' ? 'Extracting...' : '-')}
                        </span>
                        {job.job_title && (
                          <p className="text-sm text-gray-500">{job.job_title}</p>
                        )}
                      </>
                    )}
                  </td>
                  <td className="px-4 py-3">
                    <a
                      href={job.url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="text-blue-600 hover:underline flex items-center gap-1 text-sm max-w-xs truncate"
                    >
                      {new URL(job.url).hostname}
                      <ExternalLink className="w-3 h-3" />
                    </a>
                  </td>
                  <td className="px-4 py-3">
                    <StatusBadge
                      status={job.status}
                      isWaiting={!!job.company_name && job.workflow_step !== 'done' && job.status !== 'processing' && job.status !== 'needs_input' && job.id !== currentRunningJobId}
                      isProcessing={job.status === 'processing' || job.id === currentRunningJobId}
                    />
                    {job.error_message && job.status !== 'processing' && job.id !== currentRunningJobId && (
                      <p className="text-xs text-red-500 mt-1">{job.error_message}</p>
                    )}
                  </td>
                  <td className="px-4 py-3">
                    <WorkflowBadge step={job.workflow_step} isProcessing={job.status === 'processing' || job.id === currentRunningJobId} />
                  </td>
                  <td className="px-4 py-3 text-sm text-gray-500">
                    {new Date(job.created_at).toLocaleDateString()}
                  </td>
                  <td className="px-4 py-3">
                    <div className="flex items-center justify-end gap-2">
                      {job.status === 'needs_input' && job.workflow_step !== 'needs_hebrew_names' && (
                        <button
                          onClick={() => setSelectedJob(job)}
                          className="p-2 text-orange-500 hover:text-orange-700 hover:bg-orange-50 rounded"
                          title="Enter company name"
                        >
                          <Building2 className="w-4 h-4" />
                        </button>
                      )}
                      {/* Show Hebrew names button for jobs needing translations */}
                      {job.workflow_step === 'needs_hebrew_names' && (
                        <button
                          onClick={() => setHebrewNamesJob(job)}
                          className="p-2 text-purple-500 hover:text-purple-700 hover:bg-purple-50 rounded"
                          title="Enter Hebrew name translations"
                        >
                          <Languages className="w-4 h-4" />
                        </button>
                      )}
                      {/* Show Abort button when this job is currently running (processing status or currentRunningJobId) */}
                      {(job.status === 'processing' || job.id === currentRunningJobId) && (
                        <button
                          onClick={(e) => {
                            e.stopPropagation()
                            abortMutation.mutate()
                          }}
                          disabled={isAborting}
                          className="p-2 text-red-500 hover:text-red-700 hover:bg-red-50 rounded"
                          title="Stop this workflow"
                        >
                          {isAborting ? (
                            <Loader2 className="w-4 h-4 animate-spin" />
                          ) : (
                            <StopCircle className="w-4 h-4" />
                          )}
                        </button>
                      )}
                      {/* Show Play button for completed, failed, or aborted jobs that have company_name (workflow retry) */}
                      {job.status !== 'processing' && job.id !== currentRunningJobId && (job.status === 'completed' || job.status === 'failed' || job.status === 'aborted') && job.company_name && job.workflow_step !== 'done' && (
                        !isLinkedInLoggedIn ? (
                          <button
                            onClick={() => setShowLoginModal(true)}
                            className="p-2 text-yellow-500 hover:text-yellow-700 hover:bg-yellow-50 rounded"
                            title="LinkedIn login required"
                          >
                            <AlertTriangle className="w-4 h-4" />
                          </button>
                        ) : !defaultTemplate ? (
                          <button
                            onClick={() => setShowNoTemplateModal(true)}
                            className="p-2 text-yellow-500 hover:text-yellow-700 hover:bg-yellow-50 rounded"
                            title="No default template set"
                          >
                            <AlertTriangle className="w-4 h-4" />
                          </button>
                        ) : (
                          <button
                            onClick={() => workflowMutation.mutate(job.id)}
                            disabled={workflowMutation.isPending}
                            className="p-2 text-green-500 hover:text-green-700 hover:bg-green-50 rounded"
                            title={`Run workflow with "${defaultTemplate.name}"`}
                          >
                            <Play className="w-4 h-4" />
                          </button>
                        )
                      )}
                      {/* Retry button: only for failed jobs without company (needs company extraction retry) */}
                      {job.status === 'failed' && !job.company_name && (
                        <button
                          onClick={() => retryMutation.mutate(job.id)}
                          disabled={retryMutation.isPending}
                          className="p-2 text-gray-400 hover:text-blue-600 hover:bg-blue-50 rounded"
                          title="Retry company extraction"
                        >
                          <RefreshCw className="w-4 h-4" />
                        </button>
                      )}
                      <button
                        onClick={() => deleteMutation.mutate(job.id)}
                        disabled={deleteMutation.isPending}
                        className="p-2 text-gray-400 hover:text-red-600 hover:bg-red-50 rounded"
                        title="Delete"
                      >
                        <Trash2 className="w-4 h-4" />
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      {/* Company Input Modal */}
      {selectedJob && (
        <CompanyInputModal
          job={selectedJob}
          onClose={() => setSelectedJob(null)}
          onSubmit={(companyName, siteType, platformName) =>
            submitCompanyMutation.mutate({
              id: selectedJob.id,
              companyName,
              siteType,
              platformName,
            })
          }
          isPending={submitCompanyMutation.isPending}
        />
      )}

      {/* LinkedIn Login Modal */}
      {showLoginModal && (
        <LinkedInLoginModal
          onClose={() => setShowLoginModal(false)}
          onGoToSettings={() => {
            setShowLoginModal(false)
            navigate('/settings')
          }}
        />
      )}

      {/* No Default Template Modal */}
      {showNoTemplateModal && (
        <NoDefaultTemplateModal
          onClose={() => setShowNoTemplateModal(false)}
          onGoToTemplates={() => {
            setShowNoTemplateModal(false)
            navigate('/templates')
          }}
        />
      )}

      {/* Hebrew Names Input Modal */}
      {hebrewNamesJob && (
        <HebrewNamesInputModal
          job={hebrewNamesJob}
          onClose={() => setHebrewNamesJob(null)}
          onSubmit={(names) =>
            submitHebrewNamesMutation.mutate({
              id: hebrewNamesJob.id,
              names,
            })
          }
          isPending={submitHebrewNamesMutation.isPending}
        />
      )}
    </div>
  )
}

export default Jobs
