import { defineConfig, loadEnv } from 'vite';
import react from '@vitejs/plugin-react';
import path from 'node:path';

export default defineConfig(({ command, mode }) => {
  const env = loadEnv(mode, process.cwd(), '');
  // Backend is conventionally 100 ports below the frontend dev port; set
  // BACKEND_PORT or DEV_PORT to pin both ends.
  const backendPort =
    process.env.BACKEND_PORT || env.BACKEND_PORT || env.DEV_PORT || '8000';
  const backend = `http://localhost:${backendPort}`;

  return {
    plugins: [react()],
    // Production assets are served by Django's staticfiles app; the dev
    // server keeps the default "/" base.
    base: command === 'build' ? '/static/crudkit_frontend/' : '/',
    resolve: {
      alias: {
        '@': path.resolve(__dirname, '.'),
      },
    },
    server: {
      port: 8100,
      proxy: {
        '/api': backend,
        '/saml2': backend,
        '/static': backend,
        '/media': backend,
        '/ws': { target: backend.replace('http://', 'ws://'), ws: true },
      },
    },
    build: {
      // Build straight into the django-crudkit package so the SPA ships in
      // the wheel. index.html is moved to the app's templates dir by
      // scripts/postbuild.mjs.
      outDir: path.resolve(
        __dirname,
        '../backend/src/crudkit_frontend/static/crudkit_frontend'
      ),
      emptyOutDir: true,
      sourcemap: true,
    },
    test: {
      globals: true,
      environment: 'jsdom',
      setupFiles: ['./src/setupTests.ts'],
    },
  };
});
