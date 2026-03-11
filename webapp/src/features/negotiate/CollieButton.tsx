import React, { useState } from 'react'
import { ChatPanel } from './ChatPanel'

export const CollieButton: React.FC = () => {
  const [isOpen, setIsOpen] = useState(false)

  return (
    <>
      <button
        onClick={() => setIsOpen(!isOpen)}
        className="fixed bottom-6 right-6 z-40 w-16 h-16 rounded-full bg-orange text-white shadow-lg hover:bg-orange/90 transition-all animate-pulse flex items-center justify-center text-2xl"
        title="Talk to The Collie"
      >
        🐕
      </button>

      {isOpen && (
        <ChatPanel onClose={() => setIsOpen(false)} />
      )}
    </>
  )
}
