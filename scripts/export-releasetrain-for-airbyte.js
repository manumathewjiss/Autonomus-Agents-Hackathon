/**
 * Fetches release data from Releasetrain and:
 * 1. Writes data/releasetrain_export.json (for Airbyte File source → Postgres).
 * 2. If NODE_INGEST=1, also POSTs to the local Node service /ingest to fill Postgres directly.
 *
 * Run from repo root: node scripts/export-releasetrain-for-airbyte.js
 * With ingest: npm run ingest-releasetrain (Node must be running on port 3000).
 */
import 'dotenv/config';
import { writeFileSync, mkdirSync } from 'fs';
import { fileURLToPath } from 'url';
import { dirname, join } from 'path';

const __dirname = dirname(fileURLToPath(import.meta.url));
const REPO_ROOT = join(__dirname, '..');
const DATA_DIR = join(REPO_ROOT, 'data');
const OUT_FILE = join(DATA_DIR, 'releasetrain_export.json');

// Component API (q=os) often returns []; search API returns actual release data.
const RELEASETRAIN_OS_URL = 'https://releasetrain.io/api/component?q=os';
const RELEASETRAIN_SEARCH_URL = 'https://releasetrain.io/api/v/search?q=linux&channel=patch&limit=25&page=1';
const INGEST_URL = process.env.INGEST_URL || 'http://localhost:3000/ingest';

async function fetchUrl(url) {
  const res = await fetch(url);
  if (!res.ok) throw new Error(`Releasetrain API ${res.status}: ${res.statusText}`);
  const data = await res.json();
  return Array.isArray(data) ? data : (data?.data ?? []);
}

/** Fetch from component?q=os and search (linux); merge so data lake has Linux facts. */
async function fetchReleasetrain() {
  const [fromComponent, fromSearch] = await Promise.all([
    fetchUrl(RELEASETRAIN_OS_URL),
    fetchUrl(RELEASETRAIN_SEARCH_URL),
  ]);
  const byId = new Map();
  for (const r of fromComponent) byId.set(r._id || r.versionId, r);
  for (const r of fromSearch) byId.set(r._id || r.versionId, r);
  return Array.from(byId.values());
}

async function main() {
  console.log('Fetching from Releasetrain...');
  const records = await fetchReleasetrain();
  console.log(`Got ${records.length} record(s).`);

  mkdirSync(DATA_DIR, { recursive: true });
  writeFileSync(OUT_FILE, JSON.stringify(records, null, 0), 'utf8');
  console.log(`Wrote ${OUT_FILE}`);

  if (process.env.NODE_INGEST === '1') {
    console.log('Posting to Node /ingest...');
    const res = await fetch(INGEST_URL, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ records }),
    });
    if (!res.ok) {
      console.warn('Ingest failed:', res.status, await res.text());
    } else {
      const body = await res.json();
      console.log('Ingest ok, stored:', body.stored ?? 0);
    }
  } else {
    console.log('Tip: set NODE_INGEST=1 to also push to Node POST /ingest (Node must be running).');
  }
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
