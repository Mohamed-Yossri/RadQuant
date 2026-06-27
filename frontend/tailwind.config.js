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
        // Deep clinical "reading room" navy — radiologists read on dark.
        surface: {
          DEFAULT: '#070B14', // app background
          1: '#0C1220',       // panels
          2: '#121A2B',       // cards
          3: '#1B2538',       // raised / hover
          4: '#2A3650',       // strong divider
        },
        // RadQuant brand duo — clinical teal + sky (the wordmark gradient).
        accent: {
          teal: '#2DD4BF',    // scrubs teal
          sky: '#38BDF8',     // monitor blue
          purple: '#8B5CF6',
        },
        critical: '#F4536B',  // alarm red (softened from pure red)
        urgent: '#F59E0B',    // amber
        important: '#EAB308', // yellow
        chronic: '#34D399',   // vital green ("healthy" / routine)
        border: '#1B2740',    // hairline
      },
      fontFamily: {
        sans: ['var(--font-inter)', 'Inter', 'system-ui', 'sans-serif'],
        mono: ['var(--font-mono)', 'JetBrains Mono', 'monospace'],
      },
      boxShadow: {
        card: '0 1px 0 0 rgba(255,255,255,0.03) inset, 0 8px 24px -12px rgba(0,0,0,0.6)',
        'card-hover': '0 1px 0 0 rgba(255,255,255,0.05) inset, 0 16px 40px -16px rgba(0,0,0,0.75)',
        glow: '0 0 0 1px rgba(45,212,191,0.25), 0 10px 30px -8px rgba(45,212,191,0.35)',
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
