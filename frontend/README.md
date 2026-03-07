# IRLI Frontend

Next.js + Tailwind frontend for the Israel Research Lab Index.

## Setup

```bash
npm install
cp .env.local.example .env.local
# Edit .env.local if backend runs elsewhere (default: http://localhost:8000)
```

## Run

```bash
npm run dev
```

Open [http://localhost:3000](http://localhost:3000). Ensure the backend is running (`cd ../backend && uvicorn app.main:app --reload`).

## Features

- **Search**: Semantic search over lab profiles (debounced, syncs with `?q=` URL param)
- **Lab cards**: Grid of labs with PI name, institution, keywords, technologies, hiring badge
- **Lab detail**: Full profile with research summary, keywords, technologies, lab URL
