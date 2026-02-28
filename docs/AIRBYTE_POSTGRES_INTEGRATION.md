# Airbyte + PostgreSQL integration (sponsor stack)

This project uses **PostgreSQL** as the data lake and **Airbyte** to ingest release data into it.

## Where they fit

```
Releasetrain API  →  Airbyte (sync)  →  PostgreSQL  →  Node data layer  →  Python backend  →  Frontend
```

- **PostgreSQL**: Stores all release records. The Node service (data layer) reads from Postgres to answer “latest version” and “version on date” queries. Set `DATABASE_URL` to your Postgres instance (e.g. Render Postgres).
- **Airbyte**: Syncs data **into** that same Postgres. You configure a **source** (e.g. file or HTTP) and a **destination** (Postgres). Once the connection runs, release data lands in Postgres and the app can use it.

## Option A: Airbyte Cloud / OSS with File source

1. **Export release data to a file** (one-time or on a schedule):
   ```bash
   npm run export-releasetrain
   ```
   Or: `node scripts/export-releasetrain-for-airbyte.js`  
   This writes `data/releasetrain_export.json` from `https://releasetrain.io/api/component?q=os`. You can run this in a cron job and point Airbyte’s File source at the resulting file (or at a URL that serves it).

2. **In Airbyte** (Cloud or self-hosted):
   - **Source**: Add a **File** source. Point it at the URL that serves `releasetrain_export.json` (e.g. from your repo or a small server), or at a local path if Airbyte can read it.
   - **Destination**: Add **Postgres**. Use the same host, database, user, and password as your `DATABASE_URL` (e.g. from Render). Use a dedicated schema if you want (e.g. `airbyte`) or the default `public`.
   - **Connection**: Create a connection from the File source to the Postgres destination. Run a sync.

3. **Map to our schema (if needed)**  
   Our Node app expects a `releases` table with columns like `version_search_tags_key`, `version_product_name`, `data` (JSONB), etc. If Airbyte creates a different table from the file, you can either:
   - Use a **normalization** step or custom transformation in Airbyte to match our schema, or
   - Keep using **Option B** (direct ingest via Node) for the hackathon and use Airbyte to populate a staging table, then a one-off script to copy into `releases`.

## Option B: Direct ingest (no Airbyte) + Airbyte for “sponsor story”

- **PostgreSQL**: Still required. Node service uses it via `DATABASE_URL`.
- **Ingest**: Run the provided script that fetches Releasetrain and calls the Node `POST /ingest` API so data lands in Postgres. No Airbyte needed for the app to work.
- **Airbyte**: To show Airbyte in the pipeline, add an Airbyte connection that syncs **into** the same Postgres (e.g. from a File source that reads `data/releasetrain_export.json`). You can run it once or on a schedule. The important part for the hackathon is: “We use Airbyte to sync release data into Postgres.”

## Quick Postgres check

- Create a Postgres DB (e.g. Render), set `DATABASE_URL` in `.env`.
- Start the Node service: `npm run dev`. It will create the `releases` table on first run.
- Ingest once: with the Node service running, run `npm run ingest-releasetrain` (or `NODE_INGEST=1 node scripts/export-releasetrain-for-airbyte.js`). This fetches Releasetrain and POSTs to `POST /ingest` so Postgres is filled and the app can answer questions.

## Summary

| Sponsor    | Role in this project |
|-----------|------------------------|
| **PostgreSQL** | Data lake: stores release records; `DATABASE_URL`; used by Node service. |
| **Airbyte**    | Ingestion: syncs release data (e.g. from file or API) into Postgres; optional for minimal run, required for full sponsor integration. |
