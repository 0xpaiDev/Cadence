import React from 'react'
import { Card } from '../../shared/ui/Card'
import type { Training } from '../../types'

interface TrainingCardProps {
  training: Training
}

export const TrainingCard: React.FC<TrainingCardProps> = ({ training }) => {
  return (
    <div className="mb-8">
      <h2 className="text-lg font-serif font-bold mb-4 text-gray-100">Training Focus</h2>
      <Card>
        <div className="p-6">
          <div className="flex items-center gap-4 mb-4">
            <div className="w-16 h-16 rounded-full border-4 border-collie-blue flex items-center justify-center">
              <div className="w-12 h-12 rounded-full border-2 border-collie-blue" />
            </div>
            <div>
              <p className="text-xs text-gray-400 uppercase tracking-wide">Readiness Level</p>
              <p className="text-sm text-gray-300">Focus Training</p>
            </div>
          </div>
          <p className="text-sm text-gray-300 leading-relaxed">
            {training.summary}
          </p>
          {training.plan_reference && (
            <p className="text-xs text-gray-500 mt-3 pt-3 border-t border-topo/20">
              Reference: {training.plan_reference}
            </p>
          )}
        </div>
      </Card>
    </div>
  )
}
