import React from 'react'
import { Badge } from '../../shared/ui/Badge'
import { formatDate } from '../../shared/utils'
import type { Freshness } from '../../types'

interface HeaderProps {
  date: string
  freshness?: Freshness
  userName?: string
}

export const Header: React.FC<HeaderProps> = ({
  date,
  freshness,
  userName = 'Petras',
}) => {
  return (
    <div className="bg-gradient-to-b from-slate-dark to-obsidian border-b border-topo/30 p-6 pt-8">
      <div className="max-w-3xl mx-auto">
        <h1 className="text-2xl font-serif font-bold mb-2">
          Good Morning, <span className="text-orange">{userName}</span>.
        </h1>
        <p className="text-gray-400 mb-4">The trails are calling.</p> // TODO something usefull here

        <div className="flex items-center justify-between">
          <p className="text-sm text-gray-400">{formatDate(date)}</p>
          {freshness && (
            <div className="flex gap-2">
              <Badge
                variant={freshness.calendar ? 'success' : 'error'}
                title={freshness.calendar ? 'Calendar synced' : 'Calendar stale'}
              >
                📅 Cal {freshness.calendar ? '✓' : '✗'}
              </Badge>
              <Badge
                variant={freshness.news ? 'success' : 'error'}
                title={freshness.news ? 'News fresh' : 'News stale'}
              >
                📰 News {freshness.news ? '✓' : '✗'}
              </Badge>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
