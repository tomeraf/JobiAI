import { useQuery } from '@tanstack/react-query'
import {
  Briefcase,
  MessageSquare,
  UserPlus,
} from 'lucide-react'
import { logsApi } from '../api/client'

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

function Stats() {
  const { data: stats } = useQuery({
    queryKey: ['stats'],
    queryFn: logsApi.stats,
  })

  return (
    <div className="p-8">
      <h1 className="text-2xl font-bold mb-6">Stats</h1>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
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
      </div>
    </div>
  )
}

export default Stats
