import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import {
  Filter,
  RefreshCw,
  AlertCircle,
  MessageSquare,
  UserPlus,
  Search,
  Briefcase,
  Loader2,
} from 'lucide-react'
import { logsApi } from '../api/client'

const actionIcons: Record<string, React.ElementType> = {
  job_submitted: Briefcase,
  company_extracted: Search,
  selector_learned: Filter,
  connection_search: Search,
  connection_found: UserPlus,
  connection_request_sent: UserPlus,
  message_sent: MessageSquare,
  linkedin_search: Search,
  error: AlertCircle,
}

const actionColors: Record<string, string> = {
  job_submitted: 'bg-blue-100 text-blue-600',
  company_extracted: 'bg-green-100 text-green-600',
  selector_learned: 'bg-purple-100 text-purple-600',
  connection_search: 'bg-gray-100 text-gray-600',
  connection_found: 'bg-green-100 text-green-600',
  connection_request_sent: 'bg-purple-100 text-purple-600',
  message_sent: 'bg-green-100 text-green-600',
  linkedin_search: 'bg-blue-100 text-blue-600',
  error: 'bg-red-100 text-red-600',
}

function Logs() {
  const [actionFilter, setActionFilter] = useState<string>('')
  const [page, setPage] = useState(0)
  const limit = 50

  const { data, isLoading, refetch, isFetching } = useQuery({
    queryKey: ['logs', actionFilter, page],
    queryFn: () =>
      logsApi.list({
        action_type: actionFilter || undefined,
        skip: page * limit,
        limit,
      }),
  })

  const logs = data?.logs || []
  const total = data?.total || 0

  return (
    <div className="p-8">
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold">Activity Logs</h1>
        <div className="flex items-center gap-2">
          <select
            value={actionFilter}
            onChange={e => {
              setActionFilter(e.target.value)
              setPage(0)
            }}
            className="px-3 py-2 border border-gray-300 rounded-lg text-sm"
          >
            <option value="">All Actions</option>
            <option value="job_submitted">Job Submitted</option>
            <option value="company_extracted">Company Extracted</option>
            <option value="connection_search">Connection Search</option>
            <option value="connection_found">Connection Found</option>
            <option value="connection_request_sent">Connection Request</option>
            <option value="message_sent">Message Sent</option>
            <option value="linkedin_search">LinkedIn Search</option>
            <option value="error">Errors</option>
          </select>
          <button
            onClick={() => refetch()}
            disabled={isFetching}
            className="p-2 border border-gray-300 rounded-lg hover:bg-gray-50"
          >
            <RefreshCw className={`w-4 h-4 ${isFetching ? 'animate-spin' : ''}`} />
          </button>
        </div>
      </div>

      {/* Logs Table */}
      <div className="bg-white rounded-xl shadow-sm border border-gray-100">
        {isLoading ? (
          <div className="p-8 text-center">
            <Loader2 className="w-8 h-8 animate-spin mx-auto text-gray-400" />
          </div>
        ) : logs.length === 0 ? (
          <div className="p-8 text-center text-gray-500">No activity logs found.</div>
        ) : (
          <>
            <table className="w-full">
              <thead className="bg-gray-50 border-b border-gray-100">
                <tr>
                  <th className="text-left px-4 py-3 text-sm font-medium text-gray-500">Action</th>
                  <th className="text-left px-4 py-3 text-sm font-medium text-gray-500">Description</th>
                  <th className="text-left px-4 py-3 text-sm font-medium text-gray-500">Job</th>
                  <th className="text-left px-4 py-3 text-sm font-medium text-gray-500">Time</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100">
                {logs.map((log: any) => {
                  const Icon = actionIcons[log.action_type] || AlertCircle
                  const color = actionColors[log.action_type] || 'bg-gray-100 text-gray-600'

                  return (
                    <tr key={log.id} className="hover:bg-gray-50">
                      <td className="px-4 py-3">
                        <div className="flex items-center gap-2">
                          <div className={`p-2 rounded-lg ${color}`}>
                            <Icon className="w-4 h-4" />
                          </div>
                          <span className="text-sm font-medium capitalize">
                            {log.action_type.replace(/_/g, ' ')}
                          </span>
                        </div>
                      </td>
                      <td className="px-4 py-3">
                        <p className="text-sm">{log.description}</p>
                        {log.details && (
                          <details className="mt-1">
                            <summary className="text-xs text-gray-500 cursor-pointer">
                              View details
                            </summary>
                            <pre className="text-xs bg-gray-50 p-2 rounded mt-1 overflow-auto max-w-md">
                              {JSON.stringify(log.details, null, 2)}
                            </pre>
                          </details>
                        )}
                      </td>
                      <td className="px-4 py-3 text-sm text-gray-500">
                        {log.job_id ? `#${log.job_id}` : '-'}
                      </td>
                      <td className="px-4 py-3 text-sm text-gray-500">
                        {new Date(log.created_at).toLocaleString()}
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>

            {/* Pagination */}
            <div className="flex items-center justify-between px-4 py-3 border-t border-gray-100">
              <p className="text-sm text-gray-500">
                Showing {page * limit + 1}-{Math.min((page + 1) * limit, total)} of {total}
              </p>
              <div className="flex items-center gap-2">
                <button
                  onClick={() => setPage(p => Math.max(0, p - 1))}
                  disabled={page === 0}
                  className="px-3 py-1 border rounded hover:bg-gray-50 disabled:opacity-50"
                >
                  Previous
                </button>
                <button
                  onClick={() => setPage(p => p + 1)}
                  disabled={(page + 1) * limit >= total}
                  className="px-3 py-1 border rounded hover:bg-gray-50 disabled:opacity-50"
                >
                  Next
                </button>
              </div>
            </div>
          </>
        )}
      </div>
    </div>
  )
}

export default Logs
