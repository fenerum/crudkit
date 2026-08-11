// Post-build step: Vite emits index.html next to the hashed assets in the
// staticfiles output dir, but Django renders it as a template — rewrite the
// hardcoded build-time asset URLs to {% static %} tags, move it into the
// crudkit_frontend templates dir, and assert the Django template
// placeholders survived the build.
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const root = path.dirname(path.dirname(fileURLToPath(import.meta.url)));
const appDir = path.resolve(root, '../backend/src/crudkit_frontend');
const source = path.join(appDir, 'static', 'crudkit_frontend', 'index.html');
const targetDir = path.join(appDir, 'templates', 'crudkit_frontend');
const target = path.join(targetDir, 'index.html');

let html = fs.readFileSync(source, 'utf8');
for (const placeholder of [
  '{{ crudkit_config_json }}',
  '{{ csrf_token }}',
  'window.__CRUDKIT_STATIC_URL__ = {{ crudkit_static_url_json }};',
]) {
  if (!html.includes(placeholder)) {
    throw new Error(`Built index.html lost the Django placeholder ${placeholder}`);
  }
}

// Rewrite the build-time base (see vite.config.ts) to {% static %} tags so
// the shell works under any STATIC_URL.
html = html.replace(
  /(["'])\/static\/crudkit_frontend\/([^"']+)\1/g,
  (_match, quote, assetPath) => `${quote}{% static "crudkit_frontend/${assetPath}" %}${quote}`
);
// {% load %} renders to nothing, so the leading position is harmless.
html = '{% load static %}\n' + html;

if (!html.includes('{% static "crudkit_frontend/')) {
  throw new Error('Rewrite produced no {% static %} tags — did the Vite base change?');
}
if (html.includes('/static/')) {
  throw new Error('Built index.html still contains a literal /static/ URL');
}

// The bundle must not hardcode the prefix either: JS asset URLs are built at
// runtime from window.__CRUDKIT_STATIC_URL__ (vite.config.ts renderBuiltUrl).
const scanDirs = [path.join(appDir, 'static', 'crudkit_frontend')];
while (scanDirs.length) {
  const dir = scanDirs.pop();
  for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
    const entryPath = path.join(dir, entry.name);
    if (entry.isDirectory()) {
      scanDirs.push(entryPath);
    } else if (
      /\.(js|css)$/.test(entry.name) &&
      fs.readFileSync(entryPath, 'utf8').includes('/static/crudkit_frontend')
    ) {
      throw new Error(`${entryPath} contains a hardcoded /static/crudkit_frontend URL`);
    }
  }
}

fs.mkdirSync(targetDir, { recursive: true });
fs.writeFileSync(target, html);
fs.unlinkSync(source);
console.log(`Rewrote asset URLs to {% static %} and moved index.html to ${target}`);
