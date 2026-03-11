import type { Config } from 'tailwindcss'

const config: Config = {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        obsidian: '#030712',
        'slate-dark': '#111827',
        topo: '#334155',
        orange: '#FF5733',
        'collie-blue': '#2196F3',
        canopy: '#4CAF50',
        'diamond-red': '#D32F2F',
      },
      fontFamily: {
        serif: ['Space Mono', 'monospace'],
        sans: ['Inter', 'sans-serif'],
      },
    },
  },
  plugins: [],
}

export default config
