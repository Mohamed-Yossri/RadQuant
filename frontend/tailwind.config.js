/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    './app/**/*.{js,ts,jsx,tsx,mdx}',
    './components/**/*.{js,ts,jsx,tsx,mdx}',
    './lib/**/*.{js,ts,jsx,tsx,mdx}',
  ],
  theme: {
    extend: {
      colors: {
        surface: {
          DEFAULT: '#0A0F1C', // Very deep navy
          1: '#111827',       // Slate 900
          2: '#1F2937',       // Slate 800
          3: '#374151',       // Slate 700
          4: '#4B5563',       // Slate 600
        },
        accent: {
          teal: '#06B6D4',    // Cyan 500 (clinical scrub color)
          sky: '#3B82F6',     // Blue 500 (medical uniform)
          purple: '#8B5CF6',  // Violet 500
        },
        critical: '#EF4444',  // Red 500
        urgent: '#F59E0B',    // Amber 500
        important: '#EAB308', // Yellow 500
        chronic: '#10B981',   // Emerald 500
        border: '#1F2937',    // Slate 800
      },
      fontFamily: {
        sans: ['var(--font-inter)', 'Inter', 'system-ui', 'sans-serif'],
        mono: ['var(--font-mono)', 'JetBrains Mono', 'monospace'],
      },
      animation: {
        'pulse-slow': 'pulse 3s cubic-bezier(0.4, 0, 0.6, 1) infinite',
        'fade-in': 'fadeIn 0.4s ease-out',
        'slide-up': 'slideUp 0.4s ease-out',
      },
      keyframes: {
        fadeIn: { from: { opacity: 0 }, to: { opacity: 1 } },
        slideUp: { from: { opacity: 0, transform: 'translateY(12px)' }, to: { opacity: 1, transform: 'translateY(0)' } },
      },
    },
  },
  plugins: [],
};
