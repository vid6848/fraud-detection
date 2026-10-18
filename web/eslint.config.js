import js from '@eslint/js'
import jsxA11y from 'eslint-plugin-jsx-a11y'
import reactHooks from 'eslint-plugin-react-hooks'
import reactRefresh from 'eslint-plugin-react-refresh'
import { defineConfig, globalIgnores } from 'eslint/config'
import globals from 'globals'
import tseslint from 'typescript-eslint'

export default defineConfig([
  globalIgnores(['dist', 'coverage']),
  {
    files: ['**/*.{ts,tsx}'],
    extends: [
      js.configs.recommended,
      tseslint.configs.recommended,
      reactHooks.configs.flat.recommended,
      reactRefresh.configs.vite,
      jsxA11y.flatConfigs.recommended,
    ],
    languageOptions: { ecmaVersion: 2022, globals: globals.browser },
  },
  {
    files: ['tests/**', '*.config.{js,ts}'],
    languageOptions: { globals: globals.node },
  },
  {
    files: ['**/*.test.{ts,tsx}', 'src/test/**', 'tests/**'],
    rules: { 'react-refresh/only-export-components': 'off' },
  },
])
