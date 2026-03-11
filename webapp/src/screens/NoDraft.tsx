import React from 'react'
import { Card } from '../shared/ui/Card'
import { Button } from '../shared/ui/Button'

export const NoDraft: React.FC = () => {
  return (
    <div className="min-h-screen bg-obsidian flex items-center justify-center px-6">
      <Card className="max-w-md w-full">
        <div className="p-8 text-center">
          <h1 className="text-2xl font-serif font-bold text-orange mb-4">
            Waiting for Today's Plan
          </h1>
          <p className="text-gray-400 mb-6">
            The pipeline generates your daily plan every morning at 06:00.
          </p>
          <p className="text-sm text-gray-500 mb-6">
            Come back in a bit, or refresh the page to check.
          </p>
          <Button
            variant="primary"
            onClick={() => location.reload()}
          >
            Refresh
          </Button>
        </div>
      </Card>
    </div>
  )
}
