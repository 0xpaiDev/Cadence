import React, { useState, useRef, useEffect } from 'react'
import { Button } from '../../shared/ui/Button'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { api } from '../../api'

interface ChatPanelProps {
  onClose: () => void
}

interface ChatMessage {
  role: 'user' | 'agent'
  text: string
}

export const ChatPanel: React.FC<ChatPanelProps> = ({ onClose }) => {
  const queryClient = useQueryClient()
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [input, setInput] = useState('')
  const scrollRef = useRef<HTMLDivElement>(null)

  const negotiateMutation = useMutation({
    mutationFn: (text: string) => api.negotiate(text),
    onSuccess: (data) => {
      setMessages((prev) => [...prev, { role: 'agent', text: data.message }])
      queryClient.invalidateQueries({ queryKey: ['today'] })
    },
  })

  const handleSend = (e: React.FormEvent) => {
    e.preventDefault()
    if (input.trim() && !negotiateMutation.isPending) {
      setMessages((prev) => [...prev, { role: 'user', text: input }])
      negotiateMutation.mutate(input)
      setInput('')
    }
  }

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight
    }
  }, [messages])

  return (
    <div className="fixed inset-0 bg-black/50 z-50 flex flex-col">
      <div className="ml-auto h-full max-w-md bg-slate-dark flex flex-col shadow-xl rounded-l-xl">
        {/* Header */}
        <div className="border-b border-topo/30 p-4 flex items-center justify-between">
          <h3 className="font-serif font-bold text-orange">The Collie</h3>
          <button
            onClick={onClose}
            className="text-gray-400 hover:text-gray-100 transition"
          >
            ✕
          </button>
        </div>

        {/* Messages */}
        <div
          ref={scrollRef}
          className="flex-grow overflow-y-auto p-4 space-y-4 mb-4"
        >
          {messages.length === 0 && (
            <p className="text-gray-400 text-sm">
              Draft your next move or command the Collie...
            </p>
          )}
          {messages.map((msg, idx) => (
            <div
              key={idx}
              className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}
            >
              <div
                className={`max-w-xs rounded-lg p-3 text-sm ${
                  msg.role === 'user'
                    ? 'bg-orange text-white'
                    : 'bg-topo/30 text-gray-100'
                }`}
              >
                {msg.text}
              </div>
            </div>
          ))}
          {negotiateMutation.isPending && (
            <div className="flex justify-start">
              <div className="bg-topo/30 text-gray-100 rounded-lg p-3 text-sm">
                Thinking...
              </div>
            </div>
          )}
        </div>

        {/* Input */}
        <form onSubmit={handleSend} className="border-t border-topo/30 p-4 flex gap-2">
          <input
            type="text"
            placeholder="Your message..."
            value={input}
            onChange={(e) => setInput(e.target.value)}
            disabled={negotiateMutation.isPending}
            className="flex-grow bg-obsidian border border-topo/30 rounded px-3 py-2 text-sm text-gray-100 placeholder-gray-500 focus:outline-none focus:border-orange/50"
          />
          <Button
            type="submit"
            variant="primary"
            size="sm"
            isLoading={negotiateMutation.isPending}
            disabled={!input.trim()}
          >
            Send
          </Button>
        </form>
      </div>
    </div>
  )
}
