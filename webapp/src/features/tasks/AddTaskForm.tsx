import React, { useState } from 'react'
import { Button } from '../../shared/ui/Button'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { api } from '../../api'
import type { TaskPriority } from '../../types'

export const AddTaskForm: React.FC = () => {
  const queryClient = useQueryClient()
  const [text, setText] = useState('')
  const [priority, setPriority] = useState<TaskPriority>('normal')

  const addTaskMutation = useMutation({
    mutationFn: (vars: { text: string; priority: TaskPriority }) =>
      api.addTask(vars.text, vars.priority),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['today'] })
      setText('')
      setPriority('normal')
    },
  })

  const isError = addTaskMutation.isError
  const errorMessage = addTaskMutation.error instanceof Error
    ? addTaskMutation.error.message
    : 'Failed to add task'

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    if (text.trim()) {
      addTaskMutation.mutate({ text, priority })
    }
  }

  return (
    <form onSubmit={handleSubmit} className="mb-8 bg-slate-dark/50 border border-topo/20 rounded-lg p-4">
      <div className="flex gap-3 mb-3">
        <input
          type="text"
          placeholder="Add a new task..."
          value={text}
          onChange={(e) => setText(e.target.value)}
          className="flex-grow bg-obsidian border border-topo/30 rounded px-3 py-2 text-gray-100 placeholder-gray-500 focus:outline-none focus:border-orange/50"
        />

        {/* Priority selector with MTB icons */}
        <div className="flex gap-2">
          {/* Low priority - Green circle */}
          <button
            type="button"
            onClick={() => setPriority('low')}
            className={`px-3 py-2 rounded text-sm font-medium transition-all ${
              priority === 'low'
                ? 'bg-canopy/20 ring-1 ring-canopy text-canopy'
                : 'bg-obsidian border border-topo/30 text-canopy hover:border-topo/50'
            }`}
            title="Low priority"
          >
            <span className="mr-1">●</span>Low
          </button>

          {/* Normal priority - Blue square */}
          <button
            type="button"
            onClick={() => setPriority('normal')}
            className={`px-3 py-2 rounded text-sm font-medium transition-all ${
              priority === 'normal'
                ? 'bg-collie-blue/20 ring-1 ring-collie-blue text-collie-blue'
                : 'bg-obsidian border border-topo/30 text-collie-blue hover:border-topo/50'
            }`}
            title="Normal priority"
          >
            <span className="mr-1">■</span>Norm
          </button>

          {/* High priority - Red diamond */}
          <button
            type="button"
            onClick={() => setPriority('high')}
            className={`px-3 py-2 rounded text-sm font-medium transition-all ${
              priority === 'high'
                ? 'bg-diamond-red/20 ring-1 ring-diamond-red text-diamond-red'
                : 'bg-obsidian border border-topo/30 text-diamond-red hover:border-topo/50'
            }`}
            title="High priority"
          >
            <span className="mr-1">◆</span>High
          </button>
        </div>
      </div>

      {isError && (
        <div className="mb-3 p-2 bg-diamond-red/10 border border-diamond-red/30 rounded text-sm text-diamond-red">
          {errorMessage.includes('409') || errorMessage.includes('Conflict')
            ? 'Approve the plan first to add ad-hoc tasks'
            : errorMessage}
        </div>
      )}

      <Button
        type="submit"
        variant="primary"
        size="sm"
        isLoading={addTaskMutation.isPending}
      >
        Add Task
      </Button>
    </form>
  )
}
