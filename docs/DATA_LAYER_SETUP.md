# Getting Releasetrain Data and Fixing "NO_RECORD_FOUND"

The app shows **"NO_RECORD_FOUND"** when the **data layer** (Node + Postgres) has no release data for the vendor you asked about. The main answer always comes from the data layer.

Follow these steps so the app can return real answers.

---

## 1. Use the correct `.env` in the project root

- **DATABASE_URL** must be your real Postgres URL (e.g. from Render).  
  Example: `postgresql://user:password@dpg-xxx.oregon-postgres.render.com/dbname?sslmode=require`
- **GEMINI_API_KEY** must be set for the Router (get it from [Google AI Studio](https://aistudio.google.com/apikey)).  
  If you use a Google key in `OPENAI_API_KEY`, set the same value in `GEMINI_API_KEY`.

---

## 2. Node must load `.env` and use that Postgres

- The Node server now loads `.env` from the project root via `dotenv` when you run `npm run dev`.
- Start the Node server **from the project root** so it finds `.env`:
  ```bash
  cd /path/to/Hackathon
  npm run dev
  ```
- You should see **"Database initialized"** in the Node logs.  
  If you see **"Database init failed: database X does not exist"**, fix `DATABASE_URL` in `.env` (wrong host or database name).

---

## 3. Ingest Releasetrain data into Postgres (required once)

With the **Node server running** on port 3000 and **DATABASE_URL** correct:

```bash
cd /path/to/Hackathon
npm run ingest-releasetrain
```

You should see something like:

- `Fetching from Releasetrain...`
- `Got N record(s).`
- `Posting to Node /ingest...`
- `Ingest ok, stored: N`

If you see **"Ingest failed"** or **ECONNREFUSED**, the Node server is not running or not on port 3000.

---

## 4. Restart and test

1. Restart the **Node** server (so it uses the same `DATABASE_URL` and any new `.env`).
2. Restart the **Python** backend if you changed `GEMINI_API_KEY`.
3. Open **http://localhost:5173** and ask e.g. **"What is the latest version for Linux?"**

You should get an answer with **Core evidence (Releasetrain)** if the Releasetrain component API returned data for that vendor.

---

## Quick checklist

| Step | What to do |
|------|------------|
| 1 | `.env` has correct `DATABASE_URL` (Render/Neon Postgres URL). |
| 2 | `.env` has `GEMINI_API_KEY` (Google AI Studio key). |
| 3 | Run `npm install` (so `dotenv` is installed). |
| 4 | Start Node from repo root: `npm run dev` → see "Database initialized". |
| 5 | Run ingest: `npm run ingest-releasetrain` → see "Ingest ok, stored: N". |
| 6 | Ask: "What is the latest version for Linux?" (or another vendor from the ingest). |

If you still see NO_RECORD_FOUND after this, the Releasetrain API (`/api/component?q=os`) may not return data for that vendor; try another (e.g. "Ubuntu", "Windows") that appears in the ingest output.
