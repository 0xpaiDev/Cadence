import React from 'react'
import { Header } from '../features/header/Header'
import { DayStatsBar } from '../features/header/DayStats'
import { ScheduleTimeline } from '../features/schedule/ScheduleTimeline'
import { TaskList } from '../features/tasks/TaskList'
import { AddTaskForm } from '../features/tasks/AddTaskForm'
import { CollieButton } from '../features/negotiate/CollieButton'
import { Button } from '../shared/ui/Button'
import type { ApiResponseActive } from '../types'

interface ActiveDayProps {
  data: ApiResponseActive
}

export const ActiveDay: React.FC<ActiveDayProps> = ({ data }) => {
  const { plan, schedule, tasks, stats } = data

  return (
    <div className="min-h-screen bg-obsidian">
      <Header date={plan.date} />

      <main className="max-w-3xl mx-auto px-6 py-8">
        <div className="mb-8 flex justify-between items-center">
          <h2 className="text-lg font-serif font-bold text-gray-100">Today's Progress</h2>
          <Button
            variant="secondary"
            size="sm"
            onClick={() => location.reload()}
          >
            Refresh
          </Button>
        </div>

        <div className="mb-8">
          <DayStatsBar stats={stats} />
        </div>

        <ScheduleTimeline schedule={schedule} />
        <TaskList tasks={tasks.tasks} isActiveDay={true} />
        <AddTaskForm />
      </main>

      <CollieButton />
    </div>
  )
}
