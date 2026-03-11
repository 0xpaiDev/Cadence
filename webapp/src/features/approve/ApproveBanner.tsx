import React from 'react'
import { Button } from '../../shared/ui/Button'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { api } from '../../api'

export const ApproveBanner: React.FC = () => {
  const queryClient = useQueryClient()

  const approveMutation = useMutation({
    mutationFn: () => api.approve(),
    onSuccess: () => {
      // Refetch and wait for the new data (status: ACTIVE with plan and schedule)
      // Returning the promise ensures the mutation loading state continues until refetch completes
      return queryClient.refetchQueries({ queryKey: ['today'] })
    },
  })

  return (
    <div className="fixed bottom-0 left-0 right-0 bg-gradient-to-t from-obsidian via-obsidian to-transparent pt-8 pb-6 px-6 border-t border-topo/30">
      <div className="max-w-3xl mx-auto">
        <Button
          variant="success"
          size="lg"
          onClick={() => approveMutation.mutate()}
          isLoading={approveMutation.isPending}
          className="!bg-orange"
        >
          SEND IT
        </Button>
      </div>
    </div>
  )
}
