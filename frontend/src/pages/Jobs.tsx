import { useState, useEffect } from 'react'
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
  Users,
  Search,
  MessageCircle,
  RotateCcw,
  UserPlus,
  Pencil,
  Check,
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
  last_reply_check_at: string | null
  created_at: string
}

interface Template {
  id: number
  name: string
  content_male: string
  content_female: string
  is_default: boolean
}

interface Contact {
  id: number
  name: string
  linkedin_url: string
  company: string | null
  position: string | null
  message_sent_at: string | null
  reply_received_at: string | null
}

function JobSubmitForm({ onSuccess }: { onSuccess: () => void }) {
  const [url, setUrl] = useState('')
  const [error, setError] = useState<string | null>(null)
  const queryClient = useQueryClient()

  const createMutation = useMutation({
    mutationFn: (url: string) => jobsApi.create(url),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['jobs'] })
      setUrl('')
      setError(null)
      onSuccess()
    },
    onError: (err: any) => {
      // Handle duplicate URL error (409 Conflict)
      if (err?.response?.status === 409) {
        setError(err.response.data?.detail || 'This URL has already been submitted')
      } else {
        setError(err?.response?.data?.detail || 'Failed to submit job')
      }
    },
  })

  const submitUrl = (urlToSubmit: string) => {
    const trimmed = urlToSubmit.trim()
    if (trimmed && !createMutation.isPending) {
      setError(null)
      createMutation.mutate(trimmed)
    }
  }

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    submitUrl(url)
  }

  const handlePaste = (e: React.ClipboardEvent<HTMLInputElement>) => {
    const pastedText = e.clipboardData.getData('text')
    // Auto-submit if pasted text looks like a URL
    if (pastedText && (pastedText.startsWith('http://') || pastedText.startsWith('https://'))) {
      e.preventDefault() // Prevent default paste behavior
      setUrl(pastedText)
      // Use setTimeout to ensure state is updated before submitting
      setTimeout(() => submitUrl(pastedText), 0)
    }
  }

  return (
    <div className="space-y-2">
      <div className="flex gap-2">
        <input
          type="url"
          value={url}
          onChange={e => {
            setUrl(e.target.value)
            if (error) setError(null)
          }}
          onPaste={handlePaste}
          placeholder="Paste job URL here..."
          className={`flex-1 px-4 py-2 border rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent ${
            error ? 'border-red-300 bg-red-50' : 'border-gray-300'
          }`}
          disabled={createMutation.isPending}
        />
        {createMutation.isPending && (
          <div className="flex items-center px-3">
            <Loader2 className="w-5 h-5 animate-spin text-blue-600" />
          </div>
        )}
      </div>
      {error && (
        <div className="flex items-center gap-2 text-sm text-red-600">
          <XCircle className="w-4 h-4 flex-shrink-0" />
          <span>{error}</span>
        </div>
      )}
    </div>
  )
}

function StatusBadge({ status, isWaiting, isProcessing, isQueued }: { status: string; isWaiting?: boolean; isProcessing?: boolean; isQueued?: boolean }) {
  // If job is queued (waiting in queue), show purple "Queued"
  if (isQueued) {
    return (
      <span className="inline-flex items-center gap-1 px-2 py-1 rounded-full text-xs font-medium bg-purple-100 text-purple-700">
        <Clock className="w-3 h-3" />
        Queued
      </span>
    )
  }

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
    done: { icon: CheckCircle, color: 'bg-green-100 text-green-700', label: 'Done' },
    rejected: { icon: XCircle, color: 'bg-red-100 text-red-700', label: 'Rejected' },
  }

  const { icon: Icon, color, label } = config[status] || config.pending

  return (
    <span className={`inline-flex items-center gap-1 px-2 py-1 rounded-full text-xs font-medium ${color}`}>
      <Icon className={`w-3 h-3 ${status === 'processing' ? 'animate-spin' : ''}`} />
      {label}
    </span>
  )
}

function formatTimeAgo(dateStr: string | null): string | null {
  if (!dateStr) return null
  const date = new Date(dateStr)
  const now = new Date()
  const diffMs = now.getTime() - date.getTime()
  const diffMins = Math.floor(diffMs / 60000)
  const diffHours = Math.floor(diffMs / 3600000)
  const diffDays = Math.floor(diffMs / 86400000)

  if (diffMins < 1) return 'just now'
  if (diffMins < 60) return `${diffMins}m ago`
  if (diffHours < 24) return `${diffHours}h ago`
  return `${diffDays}d ago`
}

function WorkflowBadge({ step, isProcessing, isQueued, lastReplyCheckAt }: { step: string; isProcessing?: boolean; isQueued?: boolean; lastReplyCheckAt?: string | null }) {
  // When queued, show "In Queue" with clock icon
  if (isQueued) {
    return (
      <span className="inline-flex items-center gap-1 px-2 py-1 rounded-full text-xs font-medium bg-purple-100 text-purple-700">
        <Clock className="w-3 h-3" />
        In Queue
      </span>
    )
  }

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
    waiting_for_reply: { label: 'Waiting for Reply', color: 'bg-amber-100 text-amber-700', icon: 'clock' },
    search_linkedin: { label: 'Ready', color: 'bg-blue-100 text-blue-700', icon: 'play' },
    send_requests: { label: 'Ready', color: 'bg-blue-100 text-blue-700', icon: 'play' },
    waiting_for_accept: { label: 'Waiting for Accept', color: 'bg-amber-100 text-amber-700', icon: 'clock' },
    done: { label: 'Done', color: 'bg-green-100 text-green-700', icon: 'check' },
  }

  const { label, color, icon } = stepLabels[step] || { label: step, color: 'bg-gray-100 text-gray-700', icon: 'play' }

  // Show last check time for waiting states
  const timeAgo = (step === 'waiting_for_reply' || step === 'waiting_for_accept') ? formatTimeAgo(lastReplyCheckAt || null) : null
  const displayLabel = timeAgo ? `No reply (checked ${timeAgo})` : label

  return (
    <span className={`inline-flex items-center gap-1 px-2 py-1 rounded-full text-xs font-medium ${color}`}>
      {icon === 'check' && <CheckCircle className="w-3 h-3" />}
      {icon === 'play' && <Play className="w-3 h-3" />}
      {icon === 'language' && <Languages className="w-3 h-3" />}
      {icon === 'clock' && <Clock className="w-3 h-3" />}
      {displayLabel}
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

function EditCompanyModal({
  job,
  onClose,
  onSubmit,
  isPending,
}: {
  job: Job
  onClose: () => void
  onSubmit: (companyName: string) => void
  isPending: boolean
}) {
  const [companyName, setCompanyName] = useState(job.company_name || '')

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    if (companyName.trim() && companyName.trim() !== job.company_name) {
      onSubmit(companyName.trim())
    }
  }

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
      <div className="bg-white rounded-xl shadow-xl w-full max-w-md mx-4">
        <div className="flex items-center justify-between p-4 border-b">
          <h3 className="text-lg font-semibold flex items-center gap-2">
            <Pencil className="w-5 h-5 text-blue-500" />
            Edit Company Name
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
            Change the company name for this job. This is useful if the bot extracted the wrong name.
          </p>

          <div className="mb-4">
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Company Name
            </label>
            <input
              type="text"
              value={companyName}
              onChange={e => setCompanyName(e.target.value)}
              placeholder="Enter company name"
              className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
              autoFocus
              required
            />
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
              disabled={isPending || !companyName.trim() || companyName.trim() === job.company_name}
              className="flex-1 px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50 flex items-center justify-center gap-2"
            >
              {isPending ? (
                <Loader2 className="w-4 h-4 animate-spin" />
              ) : (
                <CheckCircle className="w-4 h-4" />
              )}
              Save
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}

function WaitingContactsModal({
  job,
  onClose,
  onSearchMore,
  isSearching,
}: {
  job: Job
  onClose: () => void
  onSearchMore: () => void
  isSearching: boolean
}) {
  const queryClient = useQueryClient()

  const { data, isLoading } = useQuery({
    queryKey: ['job-contacts', job.id],
    queryFn: () => jobsApi.getContacts(job.id),
  })

  const markRepliedMutation = useMutation({
    mutationFn: (contactId: number) => jobsApi.markContactReplied(job.id, contactId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['jobs'] })
      queryClient.invalidateQueries({ queryKey: ['job-contacts', job.id] })
      onClose()
    },
  })

  const deleteContactMutation = useMutation({
    mutationFn: (contactId: number) => jobsApi.deleteContact(job.id, contactId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['jobs'] })
      queryClient.invalidateQueries({ queryKey: ['job-contacts', job.id] })
    },
  })

  const contacts: Contact[] = data?.contacts || []
  const isWaitingForReply = job.workflow_step === 'waiting_for_reply'

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
      <div className="bg-white rounded-xl shadow-xl w-full max-w-md mx-4">
        <div className="flex items-center justify-between p-4 border-b">
          <h3 className="text-lg font-semibold flex items-center gap-2">
            <Users className="w-5 h-5 text-amber-500" />
            {isWaitingForReply ? 'Waiting for Reply' : 'Contacts'}
          </h3>
          <button
            onClick={onClose}
            className="p-1 hover:bg-gray-100 rounded"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        <div className="p-4">
          {isLoading ? (
            <div className="flex justify-center py-8">
              <Loader2 className="w-6 h-6 animate-spin text-gray-400" />
            </div>
          ) : contacts.length === 0 ? (
            <p className="text-sm text-gray-500 text-center py-4">
              No contacts messaged yet.
            </p>
          ) : (
            <>
              <p className="text-sm text-gray-600 mb-3">
                {isWaitingForReply
                  ? `Waiting for a reply from ${contacts.length} contact${contacts.length > 1 ? 's' : ''}:`
                  : `${contacts.length} contact${contacts.length > 1 ? 's' : ''} messaged:`}
              </p>
              <ul className="space-y-2 max-h-64 overflow-y-auto">
                {contacts.map(contact => (
                  <li
                    key={contact.id}
                    className="flex items-center justify-between p-2 bg-gray-50 rounded-lg"
                  >
                    <div>
                      <a
                        href={contact.linkedin_url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="font-medium text-blue-600 hover:underline flex items-center gap-1"
                      >
                        {contact.name}
                        <ExternalLink className="w-3 h-3" />
                      </a>
                      {contact.position && (
                        <p className="text-xs text-gray-500">{contact.position}</p>
                      )}
                    </div>
                    <div className="flex items-center gap-2">
                      {contact.reply_received_at ? (
                        <span className="text-xs text-green-600 flex items-center gap-1">
                          <CheckCircle className="w-3 h-3" />
                          Replied
                        </span>
                      ) : (
                        <>
                          <span className="text-xs text-amber-600 flex items-center gap-1">
                            <Clock className="w-3 h-3" />
                            Waiting
                          </span>
                          <button
                            onClick={() => markRepliedMutation.mutate(contact.id)}
                            disabled={markRepliedMutation.isPending}
                            className="text-xs text-green-600 hover:text-green-700 hover:bg-green-50 px-2 py-1 rounded flex items-center gap-1 disabled:opacity-50"
                            title="Mark this contact as replied"
                          >
                            {markRepliedMutation.isPending ? (
                              <Loader2 className="w-3 h-3 animate-spin" />
                            ) : (
                              <CheckCircle className="w-3 h-3" />
                            )}
                            Replied
                          </button>
                        </>
                      )}
                      <button
                        onClick={() => deleteContactMutation.mutate(contact.id)}
                        disabled={deleteContactMutation.isPending}
                        className="text-xs text-red-500 hover:text-red-700 hover:bg-red-50 px-2 py-1 rounded flex items-center gap-1 disabled:opacity-50"
                        title="Remove this contact from the list"
                      >
                        {deleteContactMutation.isPending ? (
                          <Loader2 className="w-3 h-3 animate-spin" />
                        ) : (
                          <Trash2 className="w-3 h-3" />
                        )}
                      </button>
                    </div>
                  </li>
                ))}
              </ul>
            </>
          )}

          <div className="mt-4 pt-4 border-t">
            <button
              onClick={onSearchMore}
              disabled={isSearching}
              className="w-full px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50 flex items-center justify-center gap-2"
            >
              {isSearching ? (
                <Loader2 className="w-4 h-4 animate-spin" />
              ) : (
                <Search className="w-4 h-4" />
              )}
              Search for More Candidates
            </button>
            <p className="text-xs text-gray-500 text-center mt-2">
              This will search LinkedIn for additional people at {job.company_name}
            </p>
          </div>
        </div>
      </div>
    </div>
  )
}

function Jobs() {
  const [statusFilter, setStatusFilter] = useState<string | undefined>()
  const [selectedJob, setSelectedJob] = useState<Job | null>(null)
  const [hebrewNamesJob, setHebrewNamesJob] = useState<Job | null>(null)
  const [waitingContactsJob, setWaitingContactsJob] = useState<Job | null>(null)
  const [editCompanyJob, setEditCompanyJob] = useState<Job | null>(null)
  const [showLoginModal, setShowLoginModal] = useState(false)
  const [showNoTemplateModal, setShowNoTemplateModal] = useState(false)
  const [isAborting, setIsAborting] = useState(false)
  const [isRunningAll, setIsRunningAll] = useState(false)
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

  // Check if there's a currently running job and queued jobs
  const { data: currentJobData } = useQuery({
    queryKey: ['current-job'],
    queryFn: () => jobsApi.getCurrent(),
    refetchInterval: 2000, // Poll every 2 seconds when workflow is running
  })

  const isLinkedInLoggedIn = authStatus?.logged_in === true
  const currentRunningJobId = currentJobData?.job_id
  const queuedJobIds: number[] = currentJobData?.queued_jobs || []

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
    mutationFn: ({ jobId, forceSearch, firstDegreeOnly }: { jobId: number; forceSearch?: boolean; firstDegreeOnly?: boolean }) => {
      if (!defaultTemplate) {
        throw new Error('No default template')
      }
      return jobsApi.triggerWorkflow(jobId, defaultTemplate.id, forceSearch, firstDegreeOnly)
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['jobs'] })
    },
  })

  const resetMutation = useMutation({
    mutationFn: (id: number) => jobsApi.reset(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['jobs'] })
    },
  })

  const findMoreMutation = useMutation({
    mutationFn: (id: number) => jobsApi.findMore(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['jobs'] })
    },
  })

  const updateCompanyMutation = useMutation({
    mutationFn: ({ id, companyName }: { id: number; companyName: string }) =>
      jobsApi.updateCompanyName(id, companyName),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['jobs'] })
      setEditCompanyJob(null)
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

  // Abort workflow mutation (for aborting all)
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
      // Also reset isRunningAll since we're aborting
      setIsRunningAll(false)
    },
    onError: () => {
      setIsAborting(false)
    },
  })

  // Abort specific job mutation (for aborting a single job - running or queued)
  const abortJobMutation = useMutation({
    mutationFn: (jobId: number) => jobsApi.abortJob(jobId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['jobs'] })
      queryClient.invalidateQueries({ queryKey: ['current-job'] })
    },
  })

  // Mark job as done mutation
  const markDoneMutation = useMutation({
    mutationFn: (id: number) => jobsApi.markDone(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['jobs'] })
    },
  })

  // Mark job as rejected mutation
  const markRejectedMutation = useMutation({
    mutationFn: (id: number) => jobsApi.markRejected(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['jobs'] })
    },
  })

  const jobs: Job[] = data?.jobs || []

  // Count jobs needing input
  const needsInputCount = jobs.filter(j => j.status === 'needs_input').length

  // State for Run All filter
  const [runAllFilter, setRunAllFilter] = useState<string>('search_message')

  // Get jobs by action type for Run All
  // 1. Search & Message - completed jobs ready to search for new people
  const searchMessageJobs = jobs.filter(
    j => j.status === 'completed' &&
         j.company_name &&
         j.workflow_step !== 'done' &&
         j.workflow_step !== 'waiting_for_accept' &&
         j.workflow_step !== 'waiting_for_reply'
  )
  // 2. Check Accepts - jobs waiting for connection accepts
  const checkAcceptsJobs = jobs.filter(
    j => j.workflow_step === 'waiting_for_accept' && j.status !== 'processing'
  )
  // 3. Check Replies - jobs waiting for message replies
  const checkRepliesJobs = jobs.filter(
    j => j.workflow_step === 'waiting_for_reply' && j.status !== 'processing'
  )
  // 4. Resume Failed - failed/aborted jobs that can be resumed
  const resumeFailedJobs = jobs.filter(
    j => (j.status === 'failed' || j.status === 'aborted') &&
         j.company_name &&
         j.workflow_step !== 'company_extraction'
  )
  // 5. Re-search Accepts - waiting_for_accept jobs to search for more people
  const researchAcceptsJobs = jobs.filter(
    j => j.workflow_step === 'waiting_for_accept' &&
         j.status === 'completed' &&
         j.company_name
  )
  // 6. Re-search Replies - waiting_for_reply jobs to search for more people
  const researchRepliesJobs = jobs.filter(
    j => j.workflow_step === 'waiting_for_reply' &&
         j.status === 'completed' &&
         j.company_name
  )

  // Get jobs to run based on filter
  const getJobsToRun = () => {
    switch (runAllFilter) {
      case 'search_message': return searchMessageJobs
      case 'check_accepts': return checkAcceptsJobs
      case 'check_replies': return checkRepliesJobs
      case 'resume_failed': return resumeFailedJobs
      case 'research_accepts': return researchAcceptsJobs
      case 'research_replies': return researchRepliesJobs
      default: return searchMessageJobs
    }
  }
  const runnableJobs = getJobsToRun()

  // Auto-select first available filter if current selection has no jobs
  useEffect(() => {
    const currentJobs = getJobsToRun()
    if (currentJobs.length === 0) {
      // Find first filter with available jobs
      if (searchMessageJobs.length > 0) setRunAllFilter('search_message')
      else if (checkAcceptsJobs.length > 0) setRunAllFilter('check_accepts')
      else if (checkRepliesJobs.length > 0) setRunAllFilter('check_replies')
      else if (resumeFailedJobs.length > 0) setRunAllFilter('resume_failed')
      else if (researchAcceptsJobs.length > 0) setRunAllFilter('research_accepts')
      else if (researchRepliesJobs.length > 0) setRunAllFilter('research_replies')
    }
  }, [searchMessageJobs.length, checkAcceptsJobs.length, checkRepliesJobs.length, resumeFailedJobs.length, researchAcceptsJobs.length, researchRepliesJobs.length])

  // Run all jobs mutation
  const runAllMutation = useMutation({
    mutationFn: async () => {
      if (!defaultTemplate) {
        throw new Error('No default template')
      }
      setIsRunningAll(true)
      // Run jobs sequentially in FIFO order (oldest first)
      const fifoJobs = [...runnableJobs].reverse()
      for (const job of fifoJobs) {
        switch (runAllFilter) {
          case 'check_accepts':
            // Check for accepted connections only
            await jobsApi.triggerWorkflow(job.id, defaultTemplate.id, false, true)
            break
          case 'check_replies':
            // Check for replies only
            await jobsApi.triggerWorkflow(job.id, defaultTemplate.id, false)
            break
          case 'resume_failed':
            // Resume failed/aborted jobs
            await jobsApi.retryJob(job.id)
            break
          case 'research_accepts':
            // Re-search for more people (force search)
            await jobsApi.triggerWorkflow(job.id, defaultTemplate.id, true)
            break
          case 'research_replies':
            // Re-search for more people (force search)
            await jobsApi.triggerWorkflow(job.id, defaultTemplate.id, true)
            break
          case 'search_message':
          default:
            // Search for new people
            await jobsApi.triggerWorkflow(job.id, defaultTemplate.id, true)
            break
        }
      }
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['jobs'] })
      // Don't reset isRunningAll here - wait for jobs to actually finish
    },
    onError: () => {
      setIsRunningAll(false)
    },
  })

  // Reset isRunningAll when no jobs are processing anymore
  useEffect(() => {
    if (isRunningAll && !currentRunningJobId && !runAllMutation.isPending) {
      // Small delay to ensure backend has finished
      const timer = setTimeout(() => {
        setIsRunningAll(false)
      }, 1000)
      return () => clearTimeout(timer)
    }
  }, [isRunningAll, currentRunningJobId, runAllMutation.isPending])

  return (
    <div className="p-8">
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold">Jobs</h1>
        <div className="flex items-center gap-2">
          {/* Run All Jobs Button with Filter */}
          <div className="flex items-center gap-1">
            {/* Show Abort button when Run All is running, any job is processing, or jobs are queued */}
            {(runAllMutation.isPending || currentRunningJobId || isRunningAll || queuedJobIds.length > 0) ? (
              <button
                onClick={() => abortMutation.mutate()}
                disabled={isAborting}
                className="px-4 py-2 bg-red-600 text-white rounded-lg hover:bg-red-700 disabled:opacity-50 flex items-center gap-2 text-sm"
                title="Stop all running workflows"
              >
                {isAborting ? (
                  <Loader2 className="w-4 h-4 animate-spin" />
                ) : (
                  <StopCircle className="w-4 h-4" />
                )}
                Abort
              </button>
            ) : (
              <>
                {!isLinkedInLoggedIn ? (
                  <button
                    onClick={() => setShowLoginModal(true)}
                    className="px-4 py-2 bg-yellow-100 text-yellow-700 rounded-l-lg hover:bg-yellow-200 flex items-center gap-2 text-sm"
                    title="LinkedIn login required"
                  >
                    <AlertTriangle className="w-4 h-4" />
                    Run All ({runnableJobs.length})
                  </button>
                ) : !defaultTemplate ? (
                  <button
                    onClick={() => setShowNoTemplateModal(true)}
                    className="px-4 py-2 bg-yellow-100 text-yellow-700 rounded-l-lg hover:bg-yellow-200 flex items-center gap-2 text-sm"
                    title="No default template set"
                  >
                    <AlertTriangle className="w-4 h-4" />
                    Run All ({runnableJobs.length})
                  </button>
                ) : (
                  <button
                    onClick={() => runAllMutation.mutate()}
                    disabled={runAllMutation.isPending || runnableJobs.length === 0}
                    className="px-4 py-2 bg-green-600 text-white rounded-l-lg hover:bg-green-700 disabled:opacity-50 flex items-center gap-2 text-sm"
                    title={runnableJobs.length > 0 ? `Run workflow for ${runnableJobs.length} jobs` : 'No jobs to run'}
                  >
                    {runAllMutation.isPending ? (
                      <Loader2 className="w-4 h-4 animate-spin" />
                    ) : (
                      <Play className="w-4 h-4" />
                    )}
                    Run All ({runnableJobs.length})
                  </button>
                )}
                <select
                  value={runAllFilter}
                  onChange={e => setRunAllFilter(e.target.value)}
                  className="px-2 py-2 bg-green-600 text-white rounded-r-lg hover:bg-green-700 text-sm border-l border-green-500 cursor-pointer"
                >
                  {searchMessageJobs.length > 0 && (
                    <option value="search_message">Search & Message ({searchMessageJobs.length})</option>
                  )}
                  {checkAcceptsJobs.length > 0 && (
                    <option value="check_accepts">Check Accepts ({checkAcceptsJobs.length})</option>
                  )}
                  {checkRepliesJobs.length > 0 && (
                    <option value="check_replies">Check Replies ({checkRepliesJobs.length})</option>
                  )}
                  {resumeFailedJobs.length > 0 && (
                    <option value="resume_failed">Resume Failed ({resumeFailedJobs.length})</option>
                  )}
                  {researchAcceptsJobs.length > 0 && (
                    <option value="research_accepts">Re-search Accepts ({researchAcceptsJobs.length})</option>
                  )}
                  {researchRepliesJobs.length > 0 && (
                    <option value="research_replies">Re-search Replies ({researchRepliesJobs.length})</option>
                  )}
                </select>
              </>
            )}
          </div>
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
            <option value="done">Done</option>
            <option value="rejected">Rejected</option>
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
                <th className="text-center px-4 py-3 text-sm font-medium text-gray-500">Mark</th>
                <th className="text-right px-4 py-3 text-sm font-medium text-gray-500">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {jobs.map((job: Job) => {
                // Determine row background color based on status
                const isJobDone = job.status === 'done'
                const isJobRejected = job.status === 'rejected'
                const isJobFinal = isJobDone || isJobRejected

                let rowBgClass = 'hover:bg-gray-50'
                if (isJobDone) {
                  rowBgClass = 'bg-green-200 hover:bg-green-300'
                } else if (isJobRejected) {
                  rowBgClass = 'bg-red-200 hover:bg-red-300'
                } else if (job.status === 'needs_input' && job.workflow_step !== 'needs_hebrew_names') {
                  rowBgClass = 'bg-orange-50 hover:bg-orange-100'
                } else if (job.workflow_step === 'needs_hebrew_names' && job.status === 'needs_input') {
                  rowBgClass = 'bg-purple-50 hover:bg-purple-100'
                }

                return (
                <tr key={job.id} className={rowBgClass}>
                  <td className="px-4 py-3">
                    {job.workflow_step === 'needs_hebrew_names' && job.status === 'needs_input' ? (
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
                      <div className="flex items-center gap-1 group">
                        <span className="font-medium">
                          {job.company_name || (job.status === 'processing' || job.status === 'pending' ? 'Extracting...' : '-')}
                        </span>
                        {job.company_name && job.status !== 'processing' && job.id !== currentRunningJobId && (
                          <button
                            onClick={() => setEditCompanyJob(job)}
                            className="p-1 text-gray-400 hover:text-blue-600 hover:bg-blue-50 rounded opacity-0 group-hover:opacity-100 transition-opacity"
                            title="Edit company name"
                          >
                            <Pencil className="w-3 h-3" />
                          </button>
                        )}
                        {job.job_title && (
                          <p className="text-sm text-gray-500">{job.job_title}</p>
                        )}
                      </div>
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
                      isWaiting={!!job.company_name && job.workflow_step !== 'done' && job.status !== 'processing' && job.status !== 'needs_input' && job.id !== currentRunningJobId && !queuedJobIds.includes(job.id)}
                      isProcessing={job.status === 'processing' || job.id === currentRunningJobId}
                      isQueued={queuedJobIds.includes(job.id)}
                    />
                    {job.error_message && job.status !== 'processing' && job.id !== currentRunningJobId && !queuedJobIds.includes(job.id) && (
                      <p className="text-xs text-red-500 mt-1">{job.error_message}</p>
                    )}
                  </td>
                  <td className="px-4 py-3">
                    <WorkflowBadge step={job.workflow_step} isProcessing={job.status === 'processing' || job.id === currentRunningJobId} isQueued={queuedJobIds.includes(job.id)} lastReplyCheckAt={job.last_reply_check_at} />
                  </td>
                  <td className="px-4 py-3 text-sm text-gray-500">
                    {new Date(job.created_at).toLocaleDateString()}
                  </td>
                  <td className="px-4 py-3">
                    <div className="flex items-center justify-center gap-2">
                      {/* Good/Bad buttons - always visible except when processing, queued, or already final */}
                      {!isJobFinal && job.status !== 'processing' && job.id !== currentRunningJobId && !queuedJobIds.includes(job.id) && (
                        <>
                          <button
                            onClick={() => markDoneMutation.mutate(job.id)}
                            disabled={markDoneMutation.isPending}
                            className="p-2 text-green-500 hover:text-green-700 hover:bg-green-100 rounded border border-green-300"
                            title="Mark as done (success)"
                          >
                            <Check className="w-4 h-4" />
                          </button>
                          <button
                            onClick={() => markRejectedMutation.mutate(job.id)}
                            disabled={markRejectedMutation.isPending}
                            className="p-2 text-red-500 hover:text-red-700 hover:bg-red-100 rounded border border-red-300"
                            title="Mark as rejected"
                          >
                            <X className="w-4 h-4" />
                          </button>
                        </>
                      )}
                    </div>
                  </td>
                  <td className="px-4 py-3">
                    <div className="flex items-center justify-end gap-2">
                      {/* All other buttons only show when job is NOT in final state */}
                      {!isJobFinal && (
                        <>
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
                          {job.workflow_step === 'needs_hebrew_names' && job.status === 'needs_input' && (
                            <button
                              onClick={() => setHebrewNamesJob(job)}
                              className="p-2 text-purple-500 hover:text-purple-700 hover:bg-purple-50 rounded"
                              title="Enter Hebrew name translations"
                            >
                              <Languages className="w-4 h-4" />
                            </button>
                          )}
                          {/* Show Abort button when this job is currently running or queued */}
                          {(job.status === 'processing' || job.id === currentRunningJobId || queuedJobIds.includes(job.id)) && (
                            <button
                              onClick={(e) => {
                                e.stopPropagation()
                                abortJobMutation.mutate(job.id)
                              }}
                              disabled={abortJobMutation.isPending}
                              className="p-2 text-red-500 hover:text-red-700 hover:bg-red-50 rounded"
                              title={queuedJobIds.includes(job.id) ? "Remove from queue" : "Stop this workflow"}
                            >
                              {abortJobMutation.isPending ? (
                                <Loader2 className="w-4 h-4 animate-spin" />
                              ) : (
                                <StopCircle className="w-4 h-4" />
                              )}
                            </button>
                          )}
                          {/* Show Users button for jobs waiting for reply (not waiting_for_accept) */}
                          {job.workflow_step === 'waiting_for_reply' && job.status !== 'processing' && job.id !== currentRunningJobId && !queuedJobIds.includes(job.id) && (
                            <button
                              onClick={() => setWaitingContactsJob(job)}
                              className="p-2 text-amber-500 hover:text-amber-700 hover:bg-amber-50 rounded"
                              title="View contacts we're waiting on"
                            >
                              <Users className="w-4 h-4" />
                            </button>
                          )}
                          {/* Show Check Replies button for jobs waiting for reply only */}
                          {job.status !== 'processing' && job.id !== currentRunningJobId && !queuedJobIds.includes(job.id) && job.company_name &&
                           job.workflow_step === 'waiting_for_reply' && (
                            !isLinkedInLoggedIn ? (
                              <button
                                onClick={() => setShowLoginModal(true)}
                                className="p-2 text-yellow-500 hover:text-yellow-700 hover:bg-yellow-50 rounded"
                                title="LinkedIn login required"
                              >
                                <AlertTriangle className="w-4 h-4" />
                              </button>
                            ) : (
                              <>
                                <button
                                  onClick={() => workflowMutation.mutate({ jobId: job.id, forceSearch: false })}
                                  disabled={workflowMutation.isPending}
                                  className="p-2 text-blue-500 hover:text-blue-700 hover:bg-blue-50 rounded"
                                  title="Check for replies"
                                >
                                  <MessageCircle className="w-4 h-4" />
                                </button>
                                <button
                                  onClick={() => workflowMutation.mutate({ jobId: job.id, forceSearch: true })}
                                  disabled={workflowMutation.isPending}
                                  className="p-2 text-green-500 hover:text-green-700 hover:bg-green-50 rounded"
                                  title="Search for more people to message"
                                >
                                  <Play className="w-4 h-4" />
                                </button>
                              </>
                            )
                          )}
                          {/* Show Check Accepts button for jobs waiting for accept only */}
                          {job.status !== 'processing' && job.id !== currentRunningJobId && !queuedJobIds.includes(job.id) && job.company_name &&
                           job.workflow_step === 'waiting_for_accept' && (
                            !isLinkedInLoggedIn ? (
                              <button
                                onClick={() => setShowLoginModal(true)}
                                className="p-2 text-yellow-500 hover:text-yellow-700 hover:bg-yellow-50 rounded"
                                title="LinkedIn login required"
                              >
                                <AlertTriangle className="w-4 h-4" />
                              </button>
                            ) : (
                              <button
                                onClick={() => workflowMutation.mutate({ jobId: job.id, firstDegreeOnly: true })}
                                disabled={workflowMutation.isPending}
                                className="p-2 text-purple-500 hover:text-purple-700 hover:bg-purple-50 rounded"
                                title="Check if connection requests were accepted"
                              >
                                <UserPlus className="w-4 h-4" />
                              </button>
                            )
                          )}
                          {/* Resume button for failed/aborted jobs - resumes from where it left off */}
                          {job.status !== 'processing' && job.id !== currentRunningJobId && !queuedJobIds.includes(job.id) && (job.status === 'failed' || job.status === 'aborted') && job.company_name && job.workflow_step !== 'company_extraction' && (
                            <button
                              onClick={() => retryMutation.mutate(job.id)}
                              disabled={retryMutation.isPending}
                              className="p-2 text-blue-500 hover:text-blue-700 hover:bg-blue-50 rounded"
                              title={`Resume from ${job.workflow_step.replace(/_/g, ' ')}`}
                            >
                              <RefreshCw className="w-4 h-4" />
                            </button>
                          )}
                          {/* Show Play button for completed jobs that have company_name */}
                          {job.status !== 'processing' && job.id !== currentRunningJobId && !queuedJobIds.includes(job.id) && job.status === 'completed' && job.company_name && job.workflow_step !== 'done' && job.workflow_step !== 'waiting_for_accept' && job.workflow_step !== 'waiting_for_reply' && (
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
                                onClick={() => workflowMutation.mutate({ jobId: job.id, forceSearch: true })}
                                disabled={workflowMutation.isPending}
                                className="p-2 text-green-500 hover:text-green-700 hover:bg-green-50 rounded"
                                title={`Search for contacts at ${job.company_name}`}
                              >
                                <Play className="w-4 h-4" />
                              </button>
                            )
                          )}
                          {/* Show Re-search button for jobs that have already sent connection requests (waiting_for_accept) */}
                          {job.status !== 'processing' && job.id !== currentRunningJobId && !queuedJobIds.includes(job.id) && job.status === 'completed' && job.company_name && job.workflow_step === 'waiting_for_accept' && (
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
                                onClick={() => workflowMutation.mutate({ jobId: job.id, forceSearch: true })}
                                disabled={workflowMutation.isPending}
                                className="p-2 text-amber-500 hover:text-amber-700 hover:bg-amber-50 rounded"
                                title={`Re-search for more contacts at ${job.company_name}`}
                              >
                                <RotateCw className="w-4 h-4" />
                              </button>
                            )
                          )}
                          {/* Buttons for completed jobs (workflow_step === 'done') - but not status done/rejected */}
                          {job.workflow_step === 'done' && job.status !== 'processing' && job.id !== currentRunningJobId && !queuedJobIds.includes(job.id) && job.status === 'completed' && (
                            <>
                              {/* Find More - search for other people (remove replier) */}
                              <button
                                onClick={() => findMoreMutation.mutate(job.id)}
                                disabled={findMoreMutation.isPending}
                                className="p-2 text-indigo-500 hover:text-indigo-700 hover:bg-indigo-50 rounded"
                                title="Find more people (conversation didn't go well)"
                              >
                                <Search className="w-4 h-4" />
                              </button>
                              {/* Reset - start workflow from scratch */}
                              <button
                                onClick={() => resetMutation.mutate(job.id)}
                                disabled={resetMutation.isPending}
                                className="p-2 text-orange-500 hover:text-orange-700 hover:bg-orange-50 rounded"
                                title="Reset job - start from scratch"
                              >
                                <RotateCcw className="w-4 h-4" />
                              </button>
                            </>
                          )}
                          {/* Retry button: for failed/aborted jobs without company (needs company extraction retry) */}
                          {(job.status === 'failed' || job.status === 'aborted') && !job.company_name && !queuedJobIds.includes(job.id) && (
                            <button
                              onClick={() => retryMutation.mutate(job.id)}
                              disabled={retryMutation.isPending}
                              className="p-2 text-blue-400 hover:text-blue-600 hover:bg-blue-50 rounded"
                              title="Retry company extraction"
                            >
                              <RefreshCw className="w-4 h-4" />
                            </button>
                          )}
                        </>
                      )}

                      {/* Delete button - always visible */}
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
              )})}

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

      {/* Waiting Contacts Modal */}
      {waitingContactsJob && (
        <WaitingContactsModal
          job={waitingContactsJob}
          onClose={() => setWaitingContactsJob(null)}
          onSearchMore={() => {
            workflowMutation.mutate({ jobId: waitingContactsJob.id, forceSearch: true })
            setWaitingContactsJob(null)
          }}
          isSearching={workflowMutation.isPending}
        />
      )}

      {/* Edit Company Modal */}
      {editCompanyJob && (
        <EditCompanyModal
          job={editCompanyJob}
          onClose={() => setEditCompanyJob(null)}
          onSubmit={(companyName) =>
            updateCompanyMutation.mutate({
              id: editCompanyJob.id,
              companyName,
            })
          }
          isPending={updateCompanyMutation.isPending}
        />
      )}
    </div>
  )
}

export default Jobs
