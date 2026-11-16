// copy-web.mjs -- the pages of the mini market (api/src/main/resources/web) into www/, for the app
// (npm run sync: then into the project of Android). The same files as the server gives, nothing else.
import { cpSync, mkdirSync, readdirSync, rmSync } from 'node:fs';
import { fileURLToPath } from 'node:url';

const from = fileURLToPath(new URL('../api/src/main/resources/web/', import.meta.url));
const to = fileURLToPath(new URL('./www/', import.meta.url));
rmSync(to, { recursive: true, force: true });
mkdirSync(to, { recursive: true });
for (const f of readdirSync(from)) cpSync(from + f, to + f);
console.log('== www: ' + readdirSync(to).join(', '));
