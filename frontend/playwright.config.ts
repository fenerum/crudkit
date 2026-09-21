import { defineConfig, devices } from '@playwright/test';
import os from 'node:os';
import path from 'node:path';

// Runs against the demo project serving the built SPA (`npm run build` first).
// CI boots the server itself from the installed wheel and sets E2E_BASE_URL;
// locally the demo is started on a throwaway SQLite DB.
const port = process.env.E2E_PORT || '8765';
const baseURL = process.env.E2E_BASE_URL || `http://127.0.0.1:${port}`;
const dbPath = path.join(os.tmpdir(), `crudkit-e2e-${port}.sqlite3`);

export default defineConfig({
  testDir: 'e2e',
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 2 : 0,
  reporter: process.env.CI ? [['github'], ['html', { open: 'never' }]] : 'list',
  use: {
    baseURL,
    trace: 'on-first-retry',
  },
  projects: [
    { name: 'setup', testMatch: /auth\.setup\.ts/ },
    {
      name: 'chromium',
      use: { ...devices['Desktop Chrome'], storageState: 'e2e/.auth/admin.json' },
      dependencies: ['setup'],
    },
  ],
  webServer: process.env.E2E_BASE_URL
    ? undefined
    : {
        command:
          `rm -f ${dbPath} && uv run manage.py migrate --noinput && uv run manage.py seed ` +
          `&& uv run manage.py runserver 127.0.0.1:${port} --noreload`,
        cwd: '../examples/demo',
        env: { DEMO_DB_PATH: dbPath },
        url: `${baseURL}/login`,
        reuseExistingServer: true,
        timeout: 120_000,
      },
});
