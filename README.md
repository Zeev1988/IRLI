# IRLI — Israel Research Lab Index

A scalable platform that aggregates graduate research labs across Israeli universities using an LLM-based scraping pipeline resilient to UI changes.

---

## Architecture

```
POST /api/v1/extract { url }
        │
        ▼
   crawler.py          ← Crawl4AI renders JS, strips boilerplate → Markdown
        │
        ▼
  extractor.py         ← instructor + GPT-4o-mini / Gemini 1.5 Flash → LabProfile JSON
        │
        ▼
   FastAPI response    ← validated LabProfile schema
```

---

## Project Structure

```
academia/
├── backend/
│   ├── app/
│   │   ├── main.py               # FastAPI app + CORS + health check
│   │   ├── models/
│   │   │   └── lab.py            # LabProfile Pydantic schema
│   │   ├── services/
│   │   │   ├── crawler.py        # Crawl4AI HTML → Markdown
│   │   │   └── extractor.py      # LLM extraction agent
│   │   └── api/
│   │       └── routes.py         # POST /api/v1/extract
│   ├── pyproject.toml
│   └── .env.example
└── README.md
```

---

## Quick Start

### 1. Install dependencies

```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
# Install Playwright browsers required by Crawl4AI
crawl4ai-setup
```

### 2. Configure environment

```bash
cp .env.example .env
# Edit .env and add your API key
```

### 3. Run the server

```bash
uvicorn app.main:app --reload
```

The API is now available at `http://localhost:8000`.  
Interactive docs: `http://localhost:8000/docs`

---

## API

### `POST /api/v1/extract`

Extract structured lab data from a faculty or lab page.

**Request body**

```json
{ "url": "https://cs.huji.ac.il/~lab-page/" }
```

**Response (200)**

```json
{
  "success": true,
  "data": {
    "pi_name": "Prof. Jane Doe",
    "institution": "Hebrew University of Jerusalem",
    "faculty": "Computer Science",
    "research_summary": [
      "Develops graph neural networks for biological pathway analysis",
      "Applies self-supervised learning to single-cell RNA sequencing",
      "Builds open datasets for Israeli biomedical NLP benchmarks"
    ],
    "keywords": ["Graph Neural Networks", "scRNA-seq", "NLP", "Bioinformatics", "Self-supervised Learning"],
    "hiring_status": true,
    "lab_url": "https://cs.huji.ac.il/~lab-page/"
  },
  "error": null
}
```

### `GET /health`

Returns `{"status": "ok"}`.

---

## LLM Provider

| Provider | Model | Env var needed |
|----------|-------|----------------|
| `openai` (default) | `gpt-4o-mini` | `OPENAI_API_KEY` |
| `gemini` | `gemini-1.5-flash` | `GEMINI_API_KEY` |

Switch provider by setting `LLM_PROVIDER=gemini` in `.env`.

---

## Deployment

See [DEPLOYMENT.md](DEPLOYMENT.md) for deploying the frontend (Vercel) and backend (Render/Railway).

---

## Roadmap

- [ ] PostgreSQL + pgvector (Supabase) for semantic search
- [ ] Bulk crawl mode: accept a department index URL, auto-discover all lab links
- [ ] Next.js frontend with Tailwind CSS
- [ ] Scheduled re-crawl to keep data fresh
