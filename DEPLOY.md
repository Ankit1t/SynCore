# Deploying Syncore (free tier)

Two pieces: **backend** (FastAPI) and **frontend** (Next.js). Recommended free
hosts: backend → **Render**, frontend → **Vercel**. Repo:
`https://github.com/Ankit1t/SynCore`.

```
Browser ──> Vercel (Next.js UI)  ──(server-side rewrite /api/*)──>  Render (FastAPI)  ──>  Gemini/Groq
```

Because the UI proxies `/api/*` to the backend server-side (Next rewrites),
there are no CORS headaches and no secrets in the browser.

---

## 0) Push the latest code
```powershell
git add -A
git commit -m "Deploy: LLM providers + deploy config"
git push
```
`.env` is gitignored — your API key is NOT pushed. Set keys in the host dashboards.

## 1) Backend on Render (free)
1. Go to https://render.com → sign in with GitHub.
2. **New +** → **Blueprint** → pick the `SynCore` repo. Render reads `render.yaml`.
3. When prompted, set the secret **`LLM_API_KEY`** = your Gemini key
   (or switch `LLM_PROVIDER`/`LLM_MODEL` to Groq — see below).
4. Create → wait for build. You get a URL like `https://syncore-api.onrender.com`.
5. Verify: open `https://syncore-api.onrender.com/health` → `{"status":"ok"}`.

To use **Groq** instead of Gemini (free + fast): in the Render env vars set
`LLM_PROVIDER=groq`, `LLM_MODEL=` (empty), `LLM_API_KEY=<groq key>`.

## 2) Frontend on Vercel (free)
1. Go to https://vercel.com → sign in with GitHub → **Add New… → Project** →
   import `SynCore`.
2. **Root Directory** → set to `web`.
3. **Environment Variables** → add
   `NEXT_PUBLIC_API_BASE = https://syncore-api.onrender.com` (your Render URL).
4. Deploy. You get a URL like `https://syncore.vercel.app`.

## 3) Test
Open the Vercel URL and type: *"2 tubs of ice cream and a bluetooth speaker under
₹3,000"*. The agent should build a basket.

---

## Honest caveats (free tier)
- **Render free sleeps** after ~15 min idle → the first request is a ~50s cold
  start. Fine for demos; upgrade for always-on.
- **SQLite resets** on Render (ephemeral disk). For persistent orders/delegations,
  add a free Postgres (Render or Neon), set `DATABASE_URL=postgresql+psycopg://…`,
  and change the Render build to `pip install -e ".[postgres]"`.
- **LLM free tiers are rate-limited.** On a 429 the app falls back to the
  deterministic parser (no crash), which is grocery-only.
- Never commit `.env`. Rotate any key you pasted in chat.

## Alternatives
- **All-in-one VPS / local:** `docker compose up --build` (api :8000 + web :3000),
  or `docker compose --profile full up` to add Postgres + Redis.
- **Railway / Fly.io** work the same way as Render (build `pip install -e .`,
  start `uvicorn syncore.api.app:app --host 0.0.0.0 --port $PORT`).
