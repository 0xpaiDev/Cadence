import React from 'react'
import { Badge } from '../../shared/ui/Badge'
import { formatTime } from '../../shared/utils'
import type { CalendarEvent, CalendarTomorrowEvent } from '../../types'

interface ScheduleTimelineProps {
  schedule: CalendarEvent[]
  tomorrowPreview?: CalendarTomorrowEvent[]
}

export const ScheduleTimeline: React.FC<ScheduleTimelineProps> = ({
  schedule,
  tomorrowPreview = [],
}) => {
  // Show all events in morning review (no past-event filtering)
  const todayEvents = schedule

  const allEvents = [
    ...todayEvents.map((e) => ({ ...e, isToday: true, location: e.location })),
    ...tomorrowPreview.map((e) => ({ ...e, time_start: e.start, isToday: false, location: undefined })),
  ]

  if (!allEvents.length) {
    return (
      <div className="text-center py-8 text-gray-400 mb-8">
        No upcoming events.
      </div>
    )
  }

  return (
    <div className="mb-8">
      <h2 className="text-lg font-serif font-bold mb-4 text-gray-100">Schedule</h2>
      <div className="space-y-3 relative pl-6">
        <div className="absolute left-0 top-0 bottom-0 w-0.5 bg-gradient-to-b from-collie-blue to-collie-blue/20" />

        {allEvents.map((event, idx) => (
          <div key={idx} className="relative">
            <div className="absolute -left-2.5 top-2 w-4 h-4 rounded-full bg-collie-blue/50 border-2 border-collie-blue" />
            <div className="bg-slate-dark/50 border border-topo/20 rounded-lg p-4">
              <div className="flex items-start gap-3 mb-2">
                {!event.isToday && <Badge variant="warning">Tomorrow</Badge>}
              </div>
              <h3 className="font-medium text-gray-100">{event.title}</h3>
              <div className="flex items-center gap-2 mt-2">
                {event.time_start && !event.all_day ? (
                  <span className="text-sm text-collie-blue font-medium">
                    {formatTime(event.time_start)}
                    {'time_end' in event && event.time_end ? ` → ${formatTime(event.time_end)}` : ''}
                  </span>
                ) : event.all_day ? (
                  <Badge variant="default">All day</Badge>
                ) : null}
              </div>
              {event.location && (
                <p className="text-sm text-gray-400 mt-2">📍 {event.location}</p>
              )}
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}
