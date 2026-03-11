import React from 'react'
import { Card } from '../shared/ui/Card'
import { Button } from '../shared/ui/Button'

export const Completed: React.FC = () => {
  return (
    <div className="min-h-screen bg-obsidian flex items-center justify-center px-6">
      <Card className="max-w-md w-full">
        <div className="p-8 text-center">
          <h1 className="text-4xl font-serif font-bold text-canopy mb-4">
            🎉
          </h1>
          <h2 className="text-2xl font-serif font-bold text-gray-100 mb-4">
            Day Complete
          </h2>
          <p className="text-gray-400 mb-6">
            You crushed it today. Great work!
          </p>
          <Button
            variant="primary"
            onClick={() => location.reload()}
          >
            Check Tomorrow
          </Button>
        </div>
      </Card>
    </div>
  )
}
