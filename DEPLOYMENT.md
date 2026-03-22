# Deployment Guide

Deploy the backend first, then the frontend. The frontend needs the backend URL to fetch data.

## 1. Deploy Backend (Render, Railway, etc.)

1. Deploy the `backend/` folder to a service like Render or Railway.
2. Configure environment variables in your host's dashboard:
   - `DATABASE_URL` — your live Postgres (e.g. Supabase) connection string
   - `ALLOWED_ORIGINS` — your frontend URL(s), comma-separated, e.g. `https://your-app.vercel.app`
   - `DEBUG_MODE` — must be `false` in production
   - `OPENAI_API_KEY` or `GEMINI_API_KEY`, `OA_API_KEY`, etc. as needed

3. Note your backend URL (e.g. `https://irli-api.onrender.com`).

## 2. Deploy Frontend (Vercel)

1. Deploy the `frontend/` folder to Vercel.
2. In Vercel **Environment Variables**, add:
   - `NEXT_PUBLIC_API_URL` = your backend URL (e.g. `https://irli-api.onrender.com`)

   Without this, the app defaults to `http://localhost:8000` and API calls will fail in production.

3. `package.json` already has the correct scripts:
   - `build`: `next build`
   - `start`: `next start`

## 3. CORS

The backend uses `ALLOWED_ORIGINS` to allow requests from your frontend. Include your Vercel URL (and custom domain if used):

```
ALLOWED_ORIGINS=https://your-app.vercel.app,https://www.your-domain.com
```

Default when unset: `http://localhost:3000` (for local dev).

## Summary

| Where | Variable | Value |
|-------|----------|-------|
| Backend (Render/Railway) | `ALLOWED_ORIGINS` | Your Vercel frontend URL(s) |
| Backend | `DATABASE_URL` | Live Postgres connection string |
| Backend | `DEBUG_MODE` | `false` |
| Frontend (Vercel) | `NEXT_PUBLIC_API_URL` | Your backend URL |
