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
    // Production assets are served by Django's staticfiles app under the
    // project's own STATIC_URL. The build-time base is only a placeholder:
    // postbuild.mjs rewrites it to {% static %} tags in the shell, and
    // renderBuiltUrl below replaces it with a runtime expression in the JS.
    // The dev server keeps the default "/" base.
    base: command === 'build' ? '/static/crudkit_frontend/' : '/',
    experimental: {
      renderBuiltUrl(filename, { hostType }) {
        if (hostType === 'js') {
          // Asset and chunk URLs referenced from JS must resolve against the
          // consuming project's STATIC_URL at runtime; the global is set by
          // an inline script in the Django-rendered shell.
          return {
            runtime: `(window.__CRUDKIT_STATIC_URL__ || "/static/") + ${JSON.stringify(
              `crudkit_frontend/${filename}`
            )}`,
          };
        }
        if (hostType === 'css') {
          // No url() assets in CSS today; relative keeps any future ones
          // free of a hardcoded prefix.
          return { relative: true };
        }
        // html: fall back to base; postbuild.mjs rewrites to {% static %}.
        return undefined;
      },
    },
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
      // Build straight into the crudkit package so the SPA ships in
      // the wheel. index.html is moved to the app's templates dir by
      // scripts/postbuild.mjs.
      outDir: path.resolve(
        __dirname,
        '../backend/src/crudkit_frontend/static/crudkit_frontend'
      ),
      emptyOutDir: true,
      // The ~6.6 MB .js.map would ship in the wheel; set CRUDKIT_SOURCEMAP=1
      // when you need to debug the production bundle.
      sourcemap: !!process.env.CRUDKIT_SOURCEMAP,
    },
    test: {
      globals: true,
      environment: 'jsdom',
      setupFiles: ['./src/setupTests.ts'],
    },
  };
});
