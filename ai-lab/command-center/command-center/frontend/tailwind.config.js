/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,jsx}'],
  theme: {
    extend: {
      fontFamily: {
        mono: ['JetBrains Mono', 'Fira Code', 'monospace'],
      },
      colors: {
        orch: '#4338ca',
        worker: '#0f6e56',
        'c-read': '#185fa5',
        'c-write': '#b45309',
        'c-exec': '#993c1d',
        'c-rag': '#0f6e56',
      },
    },
  },
  plugins: [],
}
