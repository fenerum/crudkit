// Post-build step: Vite emits index.html next to the hashed assets in the
// staticfiles output dir, but Django renders it as a template — move it into
// the crudkit_frontend templates dir and assert the Django template
// placeholders survived the build.
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const root = path.dirname(path.dirname(fileURLToPath(import.meta.url)));
const appDir = path.resolve(root, '../backend/src/crudkit_frontend');
const source = path.join(appDir, 'static', 'crudkit_frontend', 'index.html');
const targetDir = path.join(appDir, 'templates', 'crudkit_frontend');
const target = path.join(targetDir, 'index.html');

const html = fs.readFileSync(source, 'utf8');
for (const placeholder of ['{{ crudkit_config_json }}', '{{ csrf_token }}']) {
  if (!html.includes(placeholder)) {
    throw new Error(`Built index.html lost the Django placeholder ${placeholder}`);
  }
}

fs.mkdirSync(targetDir, { recursive: true });
fs.writeFileSync(target, html);
fs.unlinkSync(source);
console.log(`Moved index.html to ${target}`);
