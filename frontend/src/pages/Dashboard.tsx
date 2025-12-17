import { useQuery } from '@tanstack/react-query'
import {
  Briefcase,
  MessageSquare,
  UserPlus,
  AlertCircle,
  Clock,
  CheckCircle,
} from 'lucide-react'
import { logsApi, jobsApi } from '../api/client'

function StatCard({
  icon: Icon,
  label,
  value,
  color,
}: {
  icon: React.ElementType
  label: string
  value: number
  color: string
}) {
  return (
    <div className="bg-white rounded-xl shadow-sm p-6 border border-gray-100">
      <div className="flex items-center gap-4">
        <div className={`p-3 rounded-lg ${color}`}>
          <Icon className="w-6 h-6 text-white" />
        </div>
        <div>
          <p className="text-sm text-gray-500">{label}</p>
          <p className="text-2xl font-bold">{value}</p>
        </div>
      </div>
    </div>
  )
}

function RecentActivity() {
  const { data: logs, isLoading } = useQuery({
    queryKey: ['recent-logs'],
    queryFn: () => logsApi.recent(10),
    refetchInterval: 5000,
  })

  if (isLoading) {
    return <div className="animate-pulse bg-gray-100 rounded-lg h-64" />
  }

  return (
    <div className="bg-white rounded-xl shadow-sm border border-gray-100">
      <div className="p-4 border-b border-gray-100">
        <h2 className="font-semibold">Recent Activity</h2>
      </div>
      <div className="divide-y divide-gray-100 max-h-96 overflow-auto">
        {logs?.length === 0 ? (
          <p className="p-4 text-gray-500 text-center">No activity yet</p>
        ) : (
          logs?.map((log: any) => (
            <div key={log.id} className="p-4 flex items-start gap-3">
              <div
                className={`p-2 rounded-lg ${
                  log.action_type === 'error'
                    ? 'bg-red-100 text-red-600'
                    : log.action_type === 'message_sent'
                    ? 'bg-green-100 text-green-600'
                    : 'bg-blue-100 text-blue-600'
                }`}
              >
                {log.action_type === 'error' ? (
                  <AlertCircle className="w-4 h-4" />
                ) : log.action_type === 'message_sent' ? (
                  <MessageSquare className="w-4 h-4" />
                ) : (
                  <Clock className="w-4 h-4" />
                )}
              </div>
              <div className="flex-1 min-w-0">
                <p className="text-sm font-medium truncate">{log.description}</p>
                <p className="text-xs text-gray-500">
                  {new Date(log.created_at).toLocaleString()}
                </p>
              </div>
            </div>
          ))
        )}
      </div>
    </div>
  )
}

function JobQueue() {
  const { data, isLoading } = useQuery({
    queryKey: ['jobs-pending'],
    queryFn: () => jobsApi.list('pending'),
    refetchInterval: 5000,
  })

  if (isLoading) {
    return <div className="animate-pulse bg-gray-100 rounded-lg h-64" />
  }

  const jobs = data?.jobs || []

  return (
    <div className="bg-white rounded-xl shadow-sm border border-gray-100">
      <div className="p-4 border-b border-gray-100">
        <h2 className="font-semibold">Job Queue</h2>
      </div>
      <div className="divide-y divide-gray-100 max-h-96 overflow-auto">
        {jobs.length === 0 ? (
          <p className="p-4 text-gray-500 text-center">No pending jobs</p>
        ) : (
          jobs.map((job: any) => (
            <div key={job.id} className="p-4 flex items-center gap-3">
              <div
                className={`p-2 rounded-lg ${
                  job.status === 'completed'
                    ? 'bg-green-100 text-green-600'
                    : job.status === 'failed'
                    ? 'bg-red-100 text-red-600'
                    : job.status === 'processing'
                    ? 'bg-yellow-100 text-yellow-600'
                    : 'bg-gray-100 text-gray-600'
                }`}
              >
                {job.status === 'completed' ? (
                  <CheckCircle className="w-4 h-4" />
                ) : job.status === 'failed' ? (
                  <AlertCircle className="w-4 h-4" />
                ) : (
                  <Clock className="w-4 h-4" />
                )}
              </div>
              <div className="flex-1 min-w-0">
                <p className="text-sm font-medium truncate">
                  {job.company_name || 'Extracting company...'}
                </p>
                <p className="text-xs text-gray-500 truncate">{job.url}</p>
              </div>
              <span
                className={`text-xs px-2 py-1 rounded-full ${
                  job.status === 'completed'
                    ? 'bg-green-100 text-green-700'
                    : job.status === 'failed'
                    ? 'bg-red-100 text-red-700'
                    : job.status === 'processing'
                    ? 'bg-yellow-100 text-yellow-700'
                    : 'bg-gray-100 text-gray-700'
                }`}
              >
                {job.status}
              </span>
            </div>
          ))
        )}
      </div>
    </div>
  )
}

function Dashboard() {
  const { data: stats } = useQuery({
    queryKey: ['stats'],
    queryFn: logsApi.stats,
  })

  return (
    <div className="p-8">
      <h1 className="text-2xl font-bold mb-6">Dashboard</h1>

      {/* Stats Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
        <StatCard
          icon={Briefcase}
          label="Jobs Submitted"
          value={stats?.jobs_submitted || 0}
          color="bg-blue-500"
        />
        <StatCard
          icon={MessageSquare}
          label="Messages Sent"
          value={stats?.messages_sent || 0}
          color="bg-green-500"
        />
        <StatCard
          icon={UserPlus}
          label="Connection Requests"
          value={stats?.connections_requested || 0}
          color="bg-purple-500"
        />
        <StatCard
          icon={AlertCircle}
          label="Errors"
          value={stats?.errors || 0}
          color="bg-red-500"
        />
      </div>

      {/* Activity and Queue */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <RecentActivity />
        <JobQueue />
      </div>
    </div>
  )
}

export default Dashboard
