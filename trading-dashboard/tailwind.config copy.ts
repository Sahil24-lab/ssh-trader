/* 3️⃣ Tailwind configuration (tailwind.config.ts) */
import type { Config } from 'tailwindcss';
import defaultTheme from 'tailwindcss/defaultTheme';

export default {
  darkMode: 'class',
  content: [
    './app/**/*.{js,ts,jsx,tsx}',
    './components/**/*.{js,ts,jsx,tsx}',
  ],
  theme: {
    extend: {
      fontFamily: {
        headline: ['Space Grotesk', ...defaultTheme.fontFamily.sans],
        body: ['IBM Plex Sans', ...defaultTheme.fontFamily.sans],
        mono: ['IBM Plex Mono', ...defaultTheme.fontFamily.mono],
      },
      colors: {
        graphite: '#1e1e2a',
        slate: '#2d2d3a',
        teal: '#0fa3b1',
        amber: '#ffb400',
      },
      backgroundImage: {
        'grid-bg': "url('data:image/svg+xml,%3Csvg width=\"40\" height=\"40\" viewBox=\"0 0 40 40\" xmlns=\"http://www.w3.org/2000/svg\"%3E%3Cpath d=\"M40 0H0v40\" fill=\"none\" stroke=%22%23333%22 stroke-width=\"0.5\"/%3E%3C/svg%3E')",
      },
    },
  },
  plugins: [],
} satisfies Config;
