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
        <select
          value={priority}
          onChange={(e) => setPriority(e.target.value as TaskPriority)}
          className="bg-obsidian border border-topo/30 rounded px-3 py-2 text-gray-100 focus:outline-none focus:border-orange/50"
        >
          <option value="low">Low</option>
          <option value="normal">Normal</option>
          <option value="high">High</option>
        </select>
      </div>
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
