import React from 'react'
import { Card } from '../../shared/ui/Card'
import { Badge } from '../../shared/ui/Badge'
import type { NewsItem } from '../../types'

interface NewsCardsProps {
  items: NewsItem[]
}

export const NewsCards: React.FC<NewsCardsProps> = ({ items }) => {
  if (!items.length) {
    return (
      <div className="text-center py-8 text-gray-400">
        No news briefing available.
      </div>
    )
  }

  return (
    <div className="mb-8">
      <h2 className="text-lg font-serif font-bold mb-4 text-gray-100">News Briefing</h2>
      <div className="flex gap-4 overflow-x-auto pb-2 -mx-6 px-6">
        {items.map((item) => (
          <a
            key={item.id}
            href={item.url}
            target="_blank"
            rel="noopener noreferrer"
            className="flex-shrink-0 w-72"
          >
            <Card className="h-full hover:border-orange/50 transition-colors cursor-pointer">
              <div className="p-4 h-full flex flex-col">
                <div className="mb-3">
                  <Badge variant="info">{item.topic}</Badge>
                </div>
                <h3 className="font-serif font-bold text-base text-gray-100 mb-2 line-clamp-2">
                  {item.headline}
                </h3>
                <p className="text-sm text-gray-400 line-clamp-2 flex-grow">
                  {item.summary}
                </p>
                <div className="mt-3 pt-3 border-t border-topo/20">
                  <p className="text-xs text-gray-500">{item.url.split('/')[2]}</p>
                </div>
              </div>
            </Card>
          </a>
        ))}
      </div>
    </div>
  )
}
