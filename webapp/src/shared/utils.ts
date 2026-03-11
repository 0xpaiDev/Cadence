export function formatDate(isoString: string): string {
  const date = new Date(isoString)
  return date.toLocaleDateString('en-US', {
    weekday: 'long',
    month: 'long',
    day: 'numeric',
  })
}

export function formatTime(timeString: string): string {
  let date: Date
  // Handle HH:MM format (schedule items)
  if (/^\d{1,2}:\d{2}$/.test(timeString)) {
    const [hours, minutes] = timeString.split(':').map(Number)
    date = new Date()
    date.setHours(hours, minutes, 0, 0)
  } else {
    // Handle ISO 8601 format
    date = new Date(timeString)
  }
  return date.toLocaleTimeString('en-US', {
    hour: 'numeric',
    minute: '2-digit',
    hour12: true,
  })
}

export function isPastEvent(isoString: string): boolean {
  return new Date(isoString) < new Date()
}
