import type { Config } from 'tailwindcss';
import defaultTheme from 'tailwindcss/defaultTheme';

const config: Config = {
  darkMode: 'class',
  content: [
    './app/**/*.{js,ts,jsx,tsx,mdx}',
    './components/**/*.{js,ts,jsx,tsx,mdx}',
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
      },
      backgroundImage: {
        'grid-bg': "url('data:image/svg+xml,%3Csvg width=\"40\" height=\"40\" viewBox=\"0 0 40 40\" xmlns=\"http://www.w3.org/2000/svg\"%3E%3Cpath d=\"M40 0H0v40\" fill=\"none\" stroke=%22%23333%22 stroke-width=\"0.5\"/%3E%3C/svg%3E')",
      },
    },
  },
  plugins: [],
};

export default config;
