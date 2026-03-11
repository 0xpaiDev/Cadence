import { useQuery } from '@tanstack/react-query'
import { api } from './api'
import { NoDraft } from './screens/NoDraft'
import { MorningReview } from './screens/MorningReview'
import { ActiveDay } from './screens/ActiveDay'
import { Completed } from './screens/Completed'
import type { ApiResponseToday } from './types'

function App() {
  const { data, isLoading, error } = useQuery<ApiResponseToday>({
    queryKey: ['today'],
    queryFn: () => api.getToday(),
    refetchInterval: 30000, // Refetch every 30 seconds
  })

  if (isLoading) {
    return (
      <div className="min-h-screen bg-obsidian flex items-center justify-center">
        <div className="text-center">
          <div className="text-4xl mb-4">🐕</div>
          <p className="text-gray-400">Loading your day...</p>
        </div>
      </div>
    )
  }

  if (error) {
    return (
      <div className="min-h-screen bg-obsidian flex items-center justify-center px-6">
        <div className="text-center max-w-md">
          <h1 className="text-2xl font-serif font-bold text-diamond-red mb-4">
            Connection Error
          </h1>
          <p className="text-gray-400 mb-6">
            Can't reach the API server. Make sure it's running on port 8420.
          </p>
          <button
            onClick={() => location.reload()}
            className="bg-orange text-white px-6 py-2 rounded-lg hover:bg-orange/90 transition"
          >
            Retry
          </button>
        </div>
      </div>
    )
  }

  if (!data) {
    return (
      <div className="min-h-screen bg-obsidian flex items-center justify-center">
        <p className="text-gray-400">No data available</p>
      </div>
    )
  }

  switch (data.status) {
    case 'no_draft':
      return <NoDraft />
    case 'draft':
      return <MorningReview data={data} />
    case 'active':
      return <ActiveDay data={data} />
    case 'completed':
      return <Completed />
    default:
      return <div className="min-h-screen bg-obsidian" />
  }
}

export default App
