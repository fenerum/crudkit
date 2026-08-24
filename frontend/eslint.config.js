import js from '@eslint/js';
import globals from 'globals';
import react from 'eslint-plugin-react';
import reactHooks from 'eslint-plugin-react-hooks';
import tseslint from 'typescript-eslint';

export default tseslint.config(
  // Build output lands outside frontend/ (backend static dir); dist/ kept as a safety net.
  { ignores: ['dist/**'] },

  js.configs.recommended,

  // Non-type-aware TS recommended; also disables core rules TS makes redundant
  // (no-undef, core no-unused-vars) on these files.
  {
    files: ['**/*.{ts,tsx}'],
    extends: [tseslint.configs.recommended],
    rules: {
      // strict is off in tsconfig and `any` is pervasive (~115 sites); keep
      // visible as a warning rather than rewriting them in a lint PR.
      '@typescript-eslint/no-explicit-any': 'warn',
      '@typescript-eslint/no-unused-vars': ['error', { argsIgnorePattern: '^_' }],
    },
  },

  // These flat configs register their own plugins.
  react.configs.flat.recommended,
  react.configs.flat['jsx-runtime'],
  reactHooks.configs['recommended-latest'],

  {
    // The files list also opts .jsx/.ts/.tsx into linting — flat config only
    // picks up .js/.mjs/.cjs by default.
    files: ['**/*.{js,mjs,jsx,ts,tsx}'],
    settings: { react: { version: 'detect' } },
    languageOptions: { globals: globals.browser },
    rules: {
      'sort-imports': 'warn',
      // Mixed TS + untyped JSX codebase; prop-types would be pure noise.
      'react/prop-types': 'off',
    },
  },

  // Underscore-prefixed args mark intentionally unused parameters. JS files
  // only: on TS files the core rule misfires on type-signature params, which
  // is why tseslint recommended turns it off there.
  {
    files: ['**/*.{js,jsx,mjs}'],
    rules: {
      'no-unused-vars': ['error', { argsIgnorePattern: '^_' }],
    },
  },

  // vitest runs with globals: true (vite.config.ts); several test files use
  // describe/expect without importing them.
  {
    files: ['**/*.test.{js,jsx,ts,tsx}', '__tests__/**'],
    languageOptions: { globals: { ...globals.browser, ...globals.vitest } },
  },

  {
    files: ['scripts/**', '*.config.{js,ts,mjs}'],
    languageOptions: { globals: globals.node },
  }
);
