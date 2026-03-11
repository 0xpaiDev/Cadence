import React from 'react'
import { Header } from '../features/header/Header'
import { NewsCards } from '../features/news/NewsCards'
import { ScheduleTimeline } from '../features/schedule/ScheduleTimeline'
import { TaskList } from '../features/tasks/TaskList'
import { AddTaskForm } from '../features/tasks/AddTaskForm'
import { TrainingCard } from '../features/training/TrainingCard'
import { CollieButton } from '../features/negotiate/CollieButton'
import { ApproveBanner } from '../features/approve/ApproveBanner'
import type { ApiResponseDraft } from '../types'

interface MorningReviewProps {
  data: ApiResponseDraft
}

export const MorningReview: React.FC<MorningReviewProps> = ({ data }) => {
  const { draft, freshness } = data

  return (
    <div className="min-h-screen bg-obsidian pb-32">
      <Header date={draft.date} freshness={freshness} />

      <main className="max-w-3xl mx-auto px-6 py-8">
        <NewsCards items={draft.news} />
        <ScheduleTimeline
          schedule={draft.schedule}
          tomorrowPreview={draft.tomorrow_preview}
        />
        <TaskList tasks={draft.tasks} isActiveDay={false} />
        <AddTaskForm />
        <TrainingCard training={draft.training} />

        {draft.agent_suggestions.length > 0 && (
          <div className="mb-8">
            <h2 className="text-lg font-serif font-bold mb-4 text-gray-100">AI Suggestions</h2>
            <ul className="space-y-2 text-gray-300 text-sm">
              {draft.agent_suggestions.map((suggestion, idx) => (
                <li key={idx} className="flex gap-2">
                  <span className="text-orange">→</span>
                  <span>{suggestion}</span>
                </li>
              ))}
            </ul>
          </div>
        )}
      </main>

      <CollieButton />
      <ApproveBanner />
    </div>
  )
}
