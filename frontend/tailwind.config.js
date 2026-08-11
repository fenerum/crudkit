/** @type {import('tailwindcss').Config} */
export default {
  content: [
    './index.html',
    './src/**/*.{js,jsx,ts,tsx}',
    './components/**/*.{js,jsx,ts,tsx}',
    './layouts/**/*.{js,jsx,ts,tsx}',
    './context/**/*.{js,jsx,ts,tsx}',
  ],
  theme: {
    extend: {
      colors: {
        bg: {
          0: 'var(--bg-0)',
          1: 'var(--bg-1)',
          2: 'var(--bg-2)',
          3: 'var(--bg-3)',
          4: 'var(--bg-4)',
          5: 'var(--bg-5)',
        },
        fg: {
          1: 'var(--fg-1)',
          2: 'var(--fg-2)',
          3: 'var(--fg-3)',
          4: 'var(--fg-4)',
        },
        border: {
          1: 'var(--border-1)',
          2: 'var(--border-2)',
          3: 'var(--border-3)',
        },
        primary: {
          50:  'var(--primary-50)',
          100: 'var(--primary-100)',
          200: 'var(--primary-200)',
          300: 'var(--primary-300)',
          400: 'var(--primary-400)',
          500: 'var(--primary-500)',
          600: 'var(--primary-600)',
          700: 'var(--primary-700)',
        },
        success: 'var(--success)',
        warn: 'var(--warn)',
        danger: 'var(--danger)',
        info: 'var(--info)',
        stage: {
          slate:  'var(--stage-slate)',
          blue:   'var(--stage-blue)',
          violet: 'var(--stage-violet)',
          amber:  'var(--stage-amber)',
          green:  'var(--stage-green)',
          rose:   'var(--stage-rose)',
        },
      },
      fontFamily: {
        sans: ['Inter', 'ui-sans-serif', 'system-ui', '-apple-system', 'Segoe UI', 'sans-serif'],
        mono: ['JetBrains Mono', 'ui-monospace', 'SF Mono', 'Menlo', 'monospace'],
      },
      fontSize: {
        '2xs': '10px',
        xs:    '11px',
        sm:    '12px',
        md:    '13px',
        base:  '13px',
        lg:    '14px',
        xl:    '16px',
        '2xl': '20px',
        '3xl': '24px',
        '4xl': '32px',
        '5xl': '44px',
        '6xl': '60px',
      },
      borderRadius: {
        sm:   'var(--r-sm)',
        md:   'var(--r-md)',
        lg:   'var(--r-lg)',
        xl:   'var(--r-xl)',
        full: 'var(--r-full)',
      },
      spacing: {
        sidebar: 'var(--sidebar-w)',
        topbar: 'var(--topbar-h)',
        inspector: 'var(--inspector-w)',
        row: 'var(--row-h)',
      },
      boxShadow: {
        menu:  'var(--shadow-menu)',
        modal: 'var(--shadow-modal)',
        focus: 'var(--shadow-focus)',
      },
      transitionTimingFunction: {
        'out-ck': 'cubic-bezier(0.2, 0, 0, 1)',
      },
      transitionDuration: {
        fast: '120ms',
        med:  '180ms',
        slow: '260ms',
      },
    },
  },
  plugins: [
    require('@tailwindcss/forms'),
  ],
  safelist: [
    {
      pattern: /grid-cols-\d{1,2}/,
      variants: ['md'],
    },
  ],
};
