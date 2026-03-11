import React from 'react'
import { Badge } from '../../shared/ui/Badge'
import type { DayStats } from '../../types'

interface DayStatsProps {
  stats: DayStats
}

export const DayStatsBar: React.FC<DayStatsProps> = ({ stats }) => {
  return (
    <div className="flex gap-3 justify-center flex-wrap">
      <Badge variant="success">✓ {stats.completed} Completed</Badge>
      <Badge variant="info">→ {stats.remaining} Remaining</Badge>
      <Badge variant="warning">↯ {stats.deferred} Deferred</Badge>
      <Badge variant="error">✕ {stats.dropped} Dropped</Badge>
    </div>
  )
}
