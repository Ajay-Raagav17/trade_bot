import type { Config } from 'tailwindcss'

const config: Config = {
  content: [
    './src/pages/**/*.{js,ts,jsx,tsx,mdx}',
    './src/components/**/*.{js,ts,jsx,tsx,mdx}',
    './src/app/**/*.{js,ts,jsx,tsx,mdx}',
  ],
  theme: {
    extend: {
      colors: {
        'brand-primary': '#6366F1',     // Indigo-500
        'brand-secondary': '#10B981',   // Emerald-500
        'brand-accent': '#F59E0B',      // Amber-500
        'brand-light': '#F3F4F6',      // Gray-100 (for dark text)
        'brand-dark': '#1F2937',       // Gray-800 (bg for light text areas)
        'brand-darker': '#111827',     // Gray-900 (main bg)
        'brand-base-content': '#D1D5DB',// Gray-300 (default text on dark bg)
        'brand-muted-content': '#9CA3AF',// Gray-400 (muted text)
      },
      backgroundImage: {
        'gradient-radial': 'radial-gradient(var(--tw-gradient-stops))',
        'gradient-conic':
          'conic-gradient(from 180deg at 50% 50%, var(--tw-gradient-stops))',
      },
    },
  },
  plugins: [],
}
export default config
