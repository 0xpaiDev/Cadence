import React, { useState } from 'react'
import { Card } from '../../shared/ui/Card'
import { Button } from '../../shared/ui/Button'
import { cn } from '../../shared/ui/cn'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { api } from '../../api'
import type { Task, TaskPriority } from '../../types'

interface TaskListProps {
  tasks: Task[]
  isActiveDay?: boolean
}

const DIFFICULTY_ICONS: Record<TaskPriority, { icon: string; color: string }> = {
  high: { icon: '◆', color: 'text-diamond-red' },
  normal: { icon: '■', color: 'text-collie-blue' },
  low: { icon: '●', color: 'text-canopy' },
}

export const TaskList: React.FC<TaskListProps> = ({ tasks, isActiveDay = false }) => {
  const queryClient = useQueryClient()
  const [dropReason, setDropReason] = useState<string>('')
  const [droppingTaskId, setDroppingTaskId] = useState<string | null>(null)

  const updateTaskMutation = useMutation({
    mutationFn: (vars: { id: string; action: string; details?: Record<string, unknown> }) =>
      api.updateTask(vars.id, vars.action, vars.details),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['today'] })
      setDropReason('')
      setDroppingTaskId(null)
    },
  })

  const handleComplete = (id: string) => {
    updateTaskMutation.mutate({ id, action: 'complete' })
  }

  const handleDrop = (id: string, reason: string) => {
    updateTaskMutation.mutate({ id, action: 'drop', details: { reason } })
  }

  const handleDefer = (id: string) => {
    updateTaskMutation.mutate({ id, action: 'defer', details: { defer_to: 'tomorrow' } })
  }

  const pending = tasks.filter((t) => t.status === 'pending')
  const completed = tasks.filter((t) => t.status === 'completed')
  const dropped = tasks.filter((t) => t.status === 'dropped')
  const deferred = tasks.filter((t) => t.status === 'deferred')

  const TaskItem: React.FC<{ task: Task; showActions?: boolean }> = ({ task, showActions = true }) => {
    const difficulty = DIFFICULTY_ICONS[task.priority]
    const isDropping = droppingTaskId === task.id

    return (
      <Card className="mb-3 overflow-visible">
        <div className="p-4">
          <div className="flex items-start gap-3">
            <span className={cn('text-lg flex-shrink-0 font-bold', difficulty.color)}>
              {difficulty.icon}
            </span>
            <div className="flex-grow min-w-0">
              <p
                className={cn('text-base', {
                  'line-through text-gray-500': task.status === 'completed' || task.status === 'dropped',
                  'italic text-gray-400': task.status === 'deferred',
                })}
              >
                {task.text}
              </p>
              {task.drop_reason && (
                <p className="text-xs text-gray-500 mt-1">Dropped: {task.drop_reason}</p>
              )}
              {task.deferred_to && (
                <p className="text-xs text-gray-500 mt-1">Deferred to {task.deferred_to}</p>
              )}
              {task.notes && (
                <p className="text-xs text-gray-400 mt-1">Notes: {task.notes}</p>
              )}
            </div>

            {showActions && isActiveDay && task.status === 'pending' && (
              <div className="flex gap-1 flex-shrink-0">
                <Button
                  size="sm"
                  variant="success"
                  onClick={() => handleComplete(task.id)}
                  title="Mark complete"
                >
                  ✓
                </Button>
                <Button
                  size="sm"
                  variant="danger"
                  onClick={() => setDroppingTaskId(task.id)}
                  title="Drop task"
                >
                  ✕
                </Button>
                <Button
                  size="sm"
                  variant="secondary"
                  onClick={() => handleDefer(task.id)}
                  title="Defer to tomorrow"
                >
                  →
                </Button>
              </div>
            )}
          </div>

          {isDropping && (
            <div className="mt-3 pt-3 border-t border-topo/20">
              <input
                type="text"
                placeholder="Reason for dropping..."
                value={dropReason}
                onChange={(e) => setDropReason(e.target.value)}
                className="w-full bg-obsidian border border-topo/30 rounded px-3 py-2 text-sm text-gray-100 placeholder-gray-500 mb-2"
              />
              <div className="flex gap-2">
                <Button
                  size="sm"
                  variant="danger"
                  onClick={() => handleDrop(task.id, dropReason || 'No reason provided')}
                  isLoading={updateTaskMutation.isPending}
                >
                  Confirm Drop
                </Button>
                <Button
                  size="sm"
                  variant="secondary"
                  onClick={() => {
                    setDroppingTaskId(null)
                    setDropReason('')
                  }}
                >
                  Cancel
                </Button>
              </div>
            </div>
          )}
        </div>
      </Card>
    )
  }

  return (
    <div className="mb-8">
      <h2 className="text-lg font-serif font-bold mb-4 text-gray-100">Tasks</h2>

      {pending.length > 0 && (
        <div className="mb-6">
          <h3 className="text-sm font-medium text-gray-300 mb-2">Pending</h3>
          {pending.map((task) => (
            <TaskItem key={task.id} task={task} showActions={isActiveDay} />
          ))}
        </div>
      )}

      {isActiveDay && (
        <>
          {completed.length > 0 && (
            <div className="mb-4">
              <h3 className="text-sm font-medium text-gray-400 mb-2">Completed</h3>
              {completed.map((task) => (
                <TaskItem key={task.id} task={task} showActions={false} />
              ))}
            </div>
          )}

          {deferred.length > 0 && (
            <div className="mb-4">
              <h3 className="text-sm font-medium text-gray-400 mb-2">Deferred</h3>
              {deferred.map((task) => (
                <TaskItem key={task.id} task={task} showActions={false} />
              ))}
            </div>
          )}

          {dropped.length > 0 && (
            <div>
              <h3 className="text-sm font-medium text-gray-400 mb-2">Dropped</h3>
              {dropped.map((task) => (
                <TaskItem key={task.id} task={task} showActions={false} />
              ))}
            </div>
          )}
        </>
      )}
    </div>
  )
}
